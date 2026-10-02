# ruff: noqa: E501
"""S&P 500 membership evidence run (D-02 candidate, ADR-0025). Idempotent.

    PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db python scripts/ingest_sp500_evidence.py [--refresh]

1. DISCOVERY: community CSV (rows since 2011-01-01) — never membership.
2. TIER 1: S&P Global's press archive (press.spglobal.com) index-change releases.
3. TIER 2: PRNewswire copies of S&P releases (Wayback ``id_`` captures, found with the CDX index).
4. Parse «X will replace Y in the S&P 500», derive effective_at with the NYSE calendar, match
   against discovery, persist one RUN of events. Official data is never edited to fit discovery.
5. Current anchor: S&P DJI page; if it cannot be archived (HTTP 403 / login) → CURRENT_ANCHOR_BLOCKED.
Every raw document is archived (URL, retrieved_at, SHA-256) BEFORE parsing.
"""

from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import select  # noqa: E402

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.data.archive import ArchiveStore, archive_document  # noqa: E402
from pitquant.db.models import (  # noqa: E402
    RawSourceArchive,
    SP500Announcement,
    SP500DiscoveryRow,
    SP500MembershipEvent,
    TickerHistory,
)
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402
from pitquant.universe.sources.sp500_evidence import (  # noqa: E402
    PARSER_VERSION,
    Announcement,
    SourceTier,
    effective_at,
    match_discovery,
    parse_discovery_csv,
    parse_release,
)

UA = {"User-Agent": "Mozilla/5.0 (compatible; PITQuant research)"}
DISCOVERY_URL = "https://raw.githubusercontent.com/chinobing/historical_sp500_constituents/main/sp500_changes_since_1996.csv"
SPDJI_URL = "https://www.spglobal.com/spdji/en/indices/equity/sp-500/"
PRESS = "https://press.spglobal.com/index.php?"
KEYWORDS = ("S&P 500", "Changes to U.S. Indices", "Set to Join", "Replace")
CDX_PREFIXES = (
    "standard--poors-announces-change",
    "sp-dow-jones-indices-announces",
    "standard--poors-to",
    "sp-dow-jones-indices-announce",
)
PR_SLUG = re.compile(
    r"announces-changes?-(to|in)-(the-)?(sp-)?(us-)?(index|indices)|set-to-join|replace|implementation-of"
)
PR_SKIP = re.compile(r"methodolog|weight|global-100|select-sector|policies")
NY = ZoneInfo("America/New_York")


def http(url: str, tries: int = 4) -> bytes | None:
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r:
                body: bytes = r.read()
            time.sleep(1.0)
            return body
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                return None
            time.sleep(4 * (i + 1))
        except Exception:
            time.sleep(4 * (i + 1))
    return None


def text_of(b: bytes) -> str:
    s = b.decode("utf-8", errors="replace")
    s = re.sub(r"<(script|style)\b.*?</\1>", " ", s, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def is_sp_release(text: str) -> bool:
    """Tier-2 gate: an S&P-issued release republished by PRNewswire (never a third party)."""
    head = text[:1500]
    return (
        "PRNewswire" in text
        and bool(
            re.search(
                r"Standard & Poor's Announces|S&P Dow Jones Indices|S&P will make|S&P Indices",
                head + text[-1500:],
            )
        )
        and "About S&P" in text
    )


def crawl_press() -> dict[str, tuple[date, str]]:
    """The WHOLE paginated archive of press.spglobal.com (2012-01 onwards, ~3,700 releases), then a
    title filter for index-change releases. Releases without S&P 500 clauses simply parse to nothing."""
    found: dict[str, tuple[date, str]] = {}
    o = 0
    while o < 8000:
        b = http(PRESS + urllib.parse.urlencode({"s": 2429, "l": 100, "keywords": "", "o": o}))
        rows = re.findall(
            r'<a[^>]+href="(https://press\.spglobal\.com/(\d{4}-\d\d-\d\d)-[^"]+)"[^>]*>(.*?)</a>',
            b.decode("utf-8", "replace") if b else "",
            flags=re.S,
        )
        if not rows:
            break
        for u, d, t in rows:
            found[u] = (date.fromisoformat(d), re.sub(r"\s+", " ", re.sub("<[^>]+>", "", t)))
        o += 100
    ok = re.compile(
        r"Announces Changes? to U\.S\.|Join|Replac|Added to|Switch|Remov|Dropp|Changes? to (the )?S&P|S&P 500",
        re.I,
    )
    drop = re.compile(
        r"Case-Shiller|Dividend|Buyback|Rating|Launch|Sustainab|Credit|Earnings|Platts|Market Intelligence|Mobility|Methodolog|Consultation|Review Results|Healthcare Economic|SPIVA|Quarter|Sales|Growth",
        re.I,
    )
    return {u: v for u, v in found.items() if ok.search(v[1]) and not drop.search(v[1])}


def crawl_prnewswire() -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for pfx in CDX_PREFIXES:
        q = urllib.parse.urlencode(
            {
                "url": "prnewswire.com/news-releases/" + pfx,
                "matchType": "prefix",
                "output": "json",
                "fl": "original,timestamp,statuscode",
                "collapse": "urlkey",
                "limit": 3000,
            }
        )
        b = http("https://web.archive.org/cdx/search/cdx?" + q)
        if not b:
            continue
        for o, ts, sc in json.loads(b)[1:]:
            k = re.sub(r":80", "", o).replace("http://www.", "https://www.")
            if sc == "200" and PR_SLUG.search(k) and not PR_SKIP.search(k):
                out[k] = (ts, k)
    return out


def archived_docs(ses, store):  # type: ignore[no-untyped-def]
    """OFFLINE: every S&P release already in the raw archive (no network). Same tiering and the same
    publication timestamps as the online crawl; one entry per distinct (URL, sha256)."""
    out = []
    seen: set[tuple[str, str]] = set()
    rows = ses.scalars(
        select(RawSourceArchive).where(RawSourceArchive.provider.like("SP_PRESS:%"))
    ).all()
    for r in rows:
        key = (r.source_identifier, r.sha256)
        if key in seen:
            continue
        seen.add(key)
        b = store.get(r.sha256)
        if r.provider == "SP_PRESS:press.spglobal.com":
            m = re.search(r"spglobal\.com/(\d{4}-\d\d-\d\d)-", r.source_identifier)
            if not m:
                continue
            d = date.fromisoformat(m.group(1))
            at = datetime.combine(d, datetime.max.time().replace(microsecond=0), NY).astimezone(UTC)
            out.append(
                (SourceTier.OFFICIAL_SPDJI, r.source_identifier, r.source_identifier, b, d, at)
            )
        else:
            m = re.search(r"(20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d)", b.decode("utf-8", "replace"))
            if not m or not is_sp_release(text_of(b)):
                continue
            at = datetime.fromisoformat(m.group(1)).replace(tzinfo=NY)
            orig = re.search(r"original_url=(\S+)", r.notes or "")
            out.append(
                (
                    SourceTier.OFFICIAL_REPUBLISHED,
                    r.source_identifier,
                    orig.group(1) if orig else r.source_identifier,
                    b,
                    at.date(),
                    at.astimezone(UTC),
                )
            )
    return out


def main(refresh: bool, offline: bool = False) -> int:
    s = get_settings()
    store = ArchiveStore(ROOT / s.archive.root)
    report: dict[str, object] = {}
    with make_session_factory(make_engine(s.database.url))() as ses:

        def archive(provider: str, ident: str, body: bytes, mime: str, notes: str):  # type: ignore[no-untyped-def]
            return archive_document(ses, store, provider=provider, source_identifier=ident, data=body,
                                    mime_type=mime, parser_version=PARSER_VERSION, notes=notes)  # fmt: skip

        def fetch_cached(url: str) -> bytes | None:
            """Previously archived document (same URL) is reused: the archive is the cache."""
            row = ses.scalars(
                select(RawSourceArchive)
                .where(RawSourceArchive.source_identifier == url)
                .order_by(RawSourceArchive.retrieved_at.desc())
            ).first()
            if row is not None and not refresh:
                return store.get(row.sha256)
            return http(url)

        # 1. discovery -----------------------------------------------------------------
        if offline:
            drow0 = ses.scalars(
                select(RawSourceArchive)
                .where(RawSourceArchive.provider == "SP500_DISCOVERY:chinobing")
                .order_by(RawSourceArchive.retrieved_at.desc())
            ).first()
            assert drow0 is not None, "no archived discovery CSV (offline mode)"
            body = store.get(drow0.sha256)
        else:
            body = http(DISCOVERY_URL)
        assert body, "discovery CSV unavailable"
        drow = archive(
            "SP500_DISCOVERY:chinobing",
            DISCOVERY_URL,
            body,
            "text/csv",
            "DISCOVERY_ONLY; MIT licence; never membership",
        )
        rows = parse_discovery_csv(body, date(2011, 1, 1))
        row_ids: dict[tuple[date, tuple[str, ...], tuple[str, ...]], str] = {}
        for r in rows:
            ex = ses.scalars(
                select(SP500DiscoveryRow).where(
                    SP500DiscoveryRow.source_sha256 == drow.sha256,
                    SP500DiscoveryRow.row_date == r.row_date,
                )
            ).all()
            hit = next(
                (
                    e
                    for e in ex
                    if tuple(e.added_tickers) == r.added and tuple(e.removed_tickers) == r.removed
                ),
                None,
            )
            if hit is None:
                hit = SP500DiscoveryRow(
                    source="chinobing/historical_sp500_constituents",
                    source_sha256=drow.sha256,
                    archive_id=drow.archive_id,
                    row_date=r.row_date,
                    added_tickers=list(r.added),
                    removed_tickers=list(r.removed),
                )
                ses.add(hit)
                ses.flush()
            row_ids[(r.row_date, r.added, r.removed)] = hit.row_id
        report["discovery_rows"] = len(rows)

        # 2. current anchor ------------------------------------------------------------
        a = None if offline else http(SPDJI_URL, tries=1)
        report["current_anchor"] = (
            "CURRENT_ANCHOR_BLOCKED (S&P DJI page not retrievable without login/403)"
            if a is None and not offline
            else "offline: anchor step skipped (ADR-0026 anchor unchanged)"
            if a is None
            else "page retrieved (constituent list not parsed)"
        )
        if a is not None:
            archive("SPDJI:sp500_page", SPDJI_URL, a, "text/html", "current anchor page")

        # 3/4. announcements -----------------------------------------------------------
        anns: list[tuple[Announcement, str, datetime]] = []
        docs: list[tuple[SourceTier, str, str, bytes, date, datetime]] = []
        if offline:
            docs = archived_docs(ses, store)
        for u, (d, _t) in sorted({} if offline else crawl_press().items()):
            b = fetch_cached(u)
            if b:
                docs.append(
                    (
                        SourceTier.OFFICIAL_SPDJI,
                        u,
                        u,
                        b,
                        d,
                        datetime.combine(
                            d, datetime.max.time().replace(microsecond=0), NY
                        ).astimezone(UTC),
                    )
                )
        for _k, (ts, orig) in sorted({} if offline else crawl_prnewswire().items()):
            w = f"https://web.archive.org/web/{ts}id_/{orig}"
            b = fetch_cached(w)
            if not b:
                continue
            txt = text_of(b)
            m = re.search(r"(20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d)", b.decode("utf-8", "replace"))
            if not m or not is_sp_release(txt):
                continue
            at = datetime.fromisoformat(m.group(1)).replace(
                tzinfo=NY
            )  # PRNewswire stamps are US/Eastern
            docs.append(
                (SourceTier.OFFICIAL_REPUBLISHED, w, orig, b, at.date(), at.astimezone(UTC))
            )
        n_docs = {SourceTier.OFFICIAL_SPDJI: 0, SourceTier.OFFICIAL_REPUBLISHED: 0}
        parsed_docs = {SourceTier.OFFICIAL_SPDJI: 0, SourceTier.OFFICIAL_REPUBLISHED: 0}
        for tier, url, orig, b, ann_date, ann_at in docs:
            n_docs[tier] += 1
            arow = archive(
                "SP_PRESS:press.spglobal.com"
                if tier is SourceTier.OFFICIAL_SPDJI
                else "SP_PRESS:prnewswire-via-wayback",
                url,
                b,
                "text/html",
                f"tier={tier}; original_url={orig}",
            )
            changes = parse_release(text_of(b), ann_date)
            if changes:
                parsed_docs[tier] += 1
            for c in changes:
                eff = None
                try:
                    eff = effective_at(c.timing, c.stated_change_date)
                except Exception:
                    c.notes.append("effective_at not computable (non-session date)")
                ex = ses.scalars(
                    select(SP500Announcement).where(
                        SP500Announcement.source_sha256 == arow.sha256,
                        SP500Announcement.added_ticker == c.added_ticker,
                        SP500Announcement.removed_ticker == c.removed_ticker,
                        SP500Announcement.parser_version == PARSER_VERSION,
                    )
                ).first()
                if ex is None:
                    ex = SP500Announcement(
                        source_tier=tier.value,
                        source_url=url,
                        archive_id=arow.archive_id,
                        source_sha256=arow.sha256,
                        announcement_at=ann_at,
                        stated_change_date=c.stated_change_date,
                        timing=c.timing.value,
                        effective_at=eff,
                        added_ticker=c.added_ticker,
                        added_name=c.added_name[:120],
                        removed_ticker=c.removed_ticker,
                        removed_name=c.removed_name[:120],
                        reason_class=c.reason_class,
                        excerpt=c.excerpt[:500],
                        notes=c.notes,
                        parser_version=PARSER_VERSION,
                    )
                    ses.add(ex)
                    ses.flush()
                anns.append(
                    (
                        Announcement(tier, url, arow.sha256, ann_date, c),
                        ex.announcement_row_id,
                        ann_at,
                    )
                )
        report["documents"] = {k.value: v for k, v in n_docs.items()}
        report["documents_with_sp500_clauses"] = {k.value: v for k, v in parsed_docs.items()}
        report["announcement_clauses"] = len(anns)
        ses.commit()

        # 5. match + persist one run ---------------------------------------------------
        import uuid

        run_id = str(uuid.uuid4())
        results = match_discovery(rows, [a for a, _, _ in anns])
        ann_ids = {
            (a.sha256, a.change.added_ticker, a.change.removed_ticker): (rid, at)
            for a, rid, at in anns
        }
        tick = {
            t: sid
            for t, sid in ses.execute(select(TickerHistory.ticker, TickerHistory.security_id))
        }
        for r in results:
            ann = r.announcement
            rid, at = (
                ann_ids.get(
                    (ann.sha256, ann.change.added_ticker, ann.change.removed_ticker), (None, None)
                )
                if ann
                else (None, None)
            )
            ses.add(SP500MembershipEvent(
                run_id=run_id, discovery_row_id=row_ids.get((r.row.row_date, r.row.added, r.row.removed)), announcement_row_id=rid,
                added_ticker=r.added, added_security_id=None, removed_ticker=r.removed, removed_security_id=None,
                announcement_at=at, stated_change_date=ann.change.stated_change_date if ann else None,
                timing=ann.change.timing.value if ann else None,
                effective_at=effective_at(ann.change.timing, ann.change.stated_change_date) if ann and r.effective_session else None,
                discovery_date=r.row.row_date, source_tier=ann.tier.value if ann else SourceTier.DISCOVERY_ONLY.value,
                source_url=ann.url if ann else None, raw_source_hash=ann.sha256 if ann else None,
                status=r.status.value, reason=r.reason[:300]))  # fmt: skip
        ses.commit()
        _ = tick
        report["run_id"] = run_id
        report["events"] = len(results)
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--refresh" in sys.argv, "--offline" in sys.argv))
