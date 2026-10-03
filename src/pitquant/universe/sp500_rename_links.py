# ruff: noqa: E501
"""Archived S&P releases -> rename statements -> identity links (ADR-0035). No network.

``scan_rename_statements`` reads every archived S&P release (press.spglobal.com tier 1, PRNewswire/Wayback tier 2) and extracts the closed
sentence forms of ``sources.sp500_renames``. ``apply_rename_links`` turns a statement into a membership-preserving ``security_succession``
only when ALL hold: the old and the new name each resolve to exactly ONE anchor security (old in an anchor before the release, new in an anchor
after it, never both), the statement says the constituent REMAINS in the S&P 500, and the SEC 13(f) lists verify the identifier change (same
CUSIP before/after, or the old CUSIP DELETED and the new one ADDED in the same quarter). A statement alone, or a 13(f) change alone, never links.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.config.settings import Settings
from pitquant.data.archive import ArchiveStore
from pitquant.db.models import (
    RawSourceArchive,
    Sec13FListEntry,
    SP500Anchor,
    SP500AnchorMember,
)
from pitquant.universe.identity_bridge import (
    add_cusip_evidence,
    candidates_for,
    link_same_security,
    quarter_of,
)
from pitquant.universe.sources.sp500_renames import RenameStatement, parse_rename_statements
from pitquant.universe.sources.spy_sec_anchors import norm_name


@dataclass(frozen=True)
class ReleaseDoc:
    announced_on: date
    url: str
    sha256: str
    archive_id: str
    text: str


def _plain(raw: bytes) -> str:
    s = raw.decode("utf-8", errors="replace")
    s = re.sub(r"<(script|style)\b.*?</\1>", " ", s, flags=re.S | re.I)
    import html

    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def iter_releases(session: Session, settings: Settings) -> list[ReleaseDoc]:
    """Every archived S&P release with its PUBLICATION date (URL date for tier 1, the PRNewswire stamp for tier 2), de-duplicated by
    (url, sha256). The date is never taken from the text of a sidebar headline."""
    store = ArchiveStore(Path(settings.archive.root))
    out: list[ReleaseDoc] = []
    seen: set[tuple[str, str]] = set()
    for r in session.scalars(
        select(RawSourceArchive).where(RawSourceArchive.provider.like("SP_PRESS:%"))
    ):
        key = (r.source_identifier, r.sha256)
        if key in seen:
            continue
        seen.add(key)
        try:
            raw = store.get(r.sha256)
        except Exception:
            continue
        if r.provider == "SP_PRESS:press.spglobal.com":
            m = re.search(r"spglobal\.com/(\d{4}-\d\d-\d\d)-", r.source_identifier)
            if not m:
                continue
            d = date.fromisoformat(m.group(1))
        else:
            m = re.search(r"(20\d\d-\d\d-\d\d)T\d\d:\d\d:\d\d", raw.decode("utf-8", "replace"))
            if not m:
                continue
            d = date.fromisoformat(m.group(1))
        out.append(ReleaseDoc(d, r.source_identifier, r.sha256, r.archive_id, _plain(raw)))
    return sorted(out, key=lambda x: (x.announced_on, x.url))


_CACHE: dict[tuple[object, ...], list[tuple[ReleaseDoc, RenameStatement]]] = {}


def scan_rename_statements(
    session: Session, settings: Settings
) -> list[tuple[ReleaseDoc, RenameStatement]]:
    n = session.scalar(
        select(RawSourceArchive.archive_id)
        .where(RawSourceArchive.provider.like("SP_PRESS:%"))
        .order_by(RawSourceArchive.archive_id.desc())
        .limit(1)
    )
    key = (str(session.get_bind().engine.url), n, settings.archive.root)
    if key not in _CACHE:
        _CACHE[key] = [
            (d, st)
            for d in iter_releases(session, settings)
            for st in parse_rename_statements(d.text, d.announced_on)
        ]
    return _CACHE[key]


def name_eq(a: str, b: str) -> bool:
    """Equality of the normalised company keys, or one is a whole-word PREFIX of the other («Bemis» / «Bemis Company Inc»)."""
    ka, kb = norm_name(a), norm_name(b)
    return bool(ka and kb and (ka == kb or ka.startswith(kb + " ") or kb.startswith(ka + " ")))


@dataclass
class RenameLinkResult:
    old_name: str
    new_name: str
    release_url: str
    announced_on: date
    status: str  # APPLIED | ALREADY_LINKED | SKIPPED
    reason: str
    old_security_id: str | None = None
    new_security_id: str | None = None
    event_type: str | None = None


def _members_by_key(session: Session, limit: date) -> dict[str, dict[str, list[date]]]:
    out: dict[str, dict[str, list[date]]] = {}
    for sid, nm, d in session.execute(
        select(SP500AnchorMember.security_id, SP500AnchorMember.issuer_name, SP500Anchor.as_of_date)
        .join(SP500Anchor, SP500Anchor.anchor_id == SP500AnchorMember.anchor_id)
        .where(SP500AnchorMember.security_id.is_not(None), SP500Anchor.as_of_date <= limit)
    ):
        if sid:
            out.setdefault(norm_name(nm), {}).setdefault(sid, []).append(d)
    return out


def _entry_for(session: Session, name: str, quarters: list[str]) -> list[Sec13FListEntry]:
    for q in quarters:
        c = candidates_for(session, name, q)
        if len(c) == 1:
            return c
    return []


def apply_rename_links(
    session: Session,
    settings: Settings,
    statements: list[tuple[ReleaseDoc, RenameStatement]] | None = None,
) -> list[RenameLinkResult]:
    """Idempotent: a pair already linked is reported ``ALREADY_LINKED`` and nothing is inserted. Anchors and statements after the last
    pre-holdout day are never read (the sealed holdout)."""
    from pitquant.universe.sp500_anchor_graph import pre_holdout_limit

    limit = pre_holdout_limit(settings)
    members = _members_by_key(session, limit)
    results: list[RenameLinkResult] = []
    quarters = sorted({q for (q,) in session.execute(select(Sec13FListEntry.quarter).distinct())})
    for doc, st in (
        statements if statements is not None else scan_rename_statements(session, settings)
    ):
        if (
            st.kind not in ("TO_BE_RENAMED", "CHANGE_ITS_NAME")
            or not st.remains_in_index
            or doc.announced_on > limit
        ):
            continue
        res = RenameLinkResult(st.old_name, st.new_name, doc.url, doc.announced_on, "SKIPPED", "")
        olds = {
            sid
            for k, v in members.items()
            if name_eq(k, st.old_name)
            for sid, ds in v.items()
            if min(ds) <= doc.announced_on
        }
        news = {
            sid
            for k, v in members.items()
            if name_eq(k, st.new_name)
            for sid, ds in v.items()
            if max(ds) >= doc.announced_on
        }
        if len(olds) != 1 or len(news) != 1 or olds == news:
            res.reason = f"old/new name does not resolve to exactly one anchor security each (old {len(olds)}, new {len(news)})"
            results.append(res)
            continue
        old_sid, new_sid = next(iter(olds)), next(iter(news))
        res.old_security_id, res.new_security_id = old_sid, new_sid
        aq = quarter_of(doc.announced_on)
        before = [q for q in reversed(quarters) if q <= aq]
        after = [q for q in quarters if q >= aq]
        e_old, e_new = (
            _entry_for(session, st.old_name, before),
            _entry_for(session, st.new_name, after),
        )
        if not e_old or not e_new:
            res.reason = "the SEC 13(f) lists do not show exactly one common-stock entry for the old name before and the new name after"
            results.append(res)
            continue
        old, new = e_old[0], e_new[0]
        if old.cusip == new.cusip:
            event_type = "NAME_CHANGE_SAME_SECURITY"
        else:
            both = {
                q
                for q in quarters
                if (
                    a := session.scalars(
                        select(Sec13FListEntry).where(
                            Sec13FListEntry.quarter == q, Sec13FListEntry.cusip == old.cusip
                        )
                    ).first()
                )
                and (
                    b := session.scalars(
                        select(Sec13FListEntry).where(
                            Sec13FListEntry.quarter == q, Sec13FListEntry.cusip == new.cusip
                        )
                    ).first()
                )
                and a.status_added_deleted == "DELETED"
                and b.status_added_deleted == "ADDED"
            }
            if not both:
                res.reason = f"13(f): {old.cusip} DELETED and {new.cusip} ADDED do not coincide in any quarter"
                results.append(res)
                continue
            event_type = (
                "NAME_TICKER_IDENTIFIER_CHANGE_SAME_SECURITY"
                if st.new_ticker
                else "IDENTIFIER_CHANGE_SAME_SECURITY"
            )
        note = f"S&P release {doc.announced_on}: «{st.excerpt}»"[:400]
        add_cusip_evidence(
            session, old_sid, old, f"S&P statement {doc.announced_on}: renamed -> {st.new_name}"
        )
        add_cusip_evidence(
            session, new_sid, new, f"S&P statement {doc.announced_on}: renamed from {st.old_name}"
        )
        from pitquant.db.models import SecuritySuccession

        if session.scalars(
            select(SecuritySuccession).where(
                SecuritySuccession.security_predecessor_id.in_((old_sid, new_sid)),
                SecuritySuccession.security_successor_id.in_((old_sid, new_sid)),
            )
        ).first():
            res.status, res.reason, res.event_type = (
                "ALREADY_LINKED",
                "a succession between these securities already exists",
                event_type,
            )
            results.append(res)
            continue
        link_same_security(
            session,
            old_sid,
            new_sid,
            "SP_PRESS_STATEMENT+SEC_13F_LIST",
            doc.sha256,
            event_type=event_type,
            effective=None,
            note=note,
        )
        res.status, res.reason, res.event_type = (
            "APPLIED",
            "S&P statement (remains in the S&P 500) + 13(f) identifier change verified",
            event_type,
        )
        results.append(res)
    session.flush()
    return results
