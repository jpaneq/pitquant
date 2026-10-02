# ruff: noqa: E501
"""Exact blockers of a research window of S&P 500 cohorts (ADR-0031). READ-ONLY diagnosis.

``window_readiness(start, end)`` answers, for monthly cohorts in [start, end]:
* how many are reconstructible today (single current anchor: membership at the open of D needs EVERY
  event effective after D confirmed, so events AFTER the window also block, "chain" blockers);
* how many would be reconstructible with a verified anchor at the end of the window (INTRINSIC
  readiness: only the events inside the window matter); a hypothetical, never a status;
* one precise card per blocking event: what is missing, from which side, and whether the problem is
  the parser, the identity or an absent source. Nothing is searched outside the existing raw archive.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.config.settings import Settings, get_settings
from pitquant.data.archive import ArchiveStore
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.db.models import (
    RawSourceArchive,
    SP500Announcement,
    SP500MembershipEvent,
    TickerHistory,
)
from pitquant.universe.sources.sp500_evidence import PARSER_VERSION
from pitquant.universe.sp500_reconstruct import MIN_COHORTS, PREFERRED_COHORTS, compute_d02

_TICKER_IN_DOC = re.compile(
    r"\((?:[A-Za-z][A-Za-z /]{1,18})\s*:\s*([A-Z][A-Za-z0-9.\-]{0,9})\s*(?:[;)])"
)
_RENAME = re.compile(
    r"(?:change (?:its )?name|changing its name|changes its name|name and (?:ticker|symbol)|to be renamed|ticker (?:symbol )?change)"
    r"[^.]{0,200}?\((?:[A-Za-z][A-Za-z /]{1,18})\s*:\s*([A-Z][A-Za-z0-9.\-]{0,9})\s*\)"
)
_ANY_TICK = re.compile(r"\((?:[A-Za-z][A-Za-z /]{1,18})\s*:\s*([A-Z][A-Za-z0-9.\-]{0,9})\s*[;)]")


@dataclass
class GapCard:
    event_id: str
    status: str
    position: str  # IN_WINDOW | AFTER_WINDOW_CHAIN | BEFORE_WINDOW
    effective_date: str | None
    announcement_date: str | None
    added_ticker: str | None
    removed_ticker: str | None
    added_name: str
    removed_name: str
    discovery_source: str | None
    official_source_found: bool
    official_sources: list[str]
    parser_status: str
    identity_status: str
    missing_evidence: str
    reason: str


@dataclass
class WindowReport:
    start: date
    end: date
    monthly_cohorts: int
    reconstructible_cohorts: int  # with the current single anchor (chain through today)
    longest_consecutive_run: int
    intrinsic_reconstructible_cohorts: int  # HYPOTHETICAL: if the membership at `end` were anchored
    intrinsic_longest_run: int
    first_failure: str | None
    blocking_events: list[GapCard] = field(default_factory=list)  # inside the window
    chain_blocking_events: int = 0  # after the window, blocking only because of the single anchor
    chain_blocking_by_year: dict[str, int] = field(default_factory=dict)
    blocking_identity: list[str] = field(default_factory=list)
    status: str = ""
    holdout_overlap: bool = False
    immaterial_conflicts_in_window: int = 0
    rename_candidates: list[dict[str, str]] = field(
        default_factory=list
    )  # ticker change != membership change
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["start"], d["end"] = str(self.start), str(self.end)
        return d


class ArchiveIndex:
    """ticker -> S&P releases in the raw archive that mention «(EXCH: TICKER)». Built offline."""

    def __init__(self, session: Session, settings: Settings) -> None:
        store = ArchiveStore(Path(settings.archive.root))
        self.by_ticker: dict[str, list[tuple[date, str]]] = {}
        self.renames: list[tuple[date, str, str, str]] = []  # (release date, old, new, url)
        seen: set[tuple[str, str]] = set()
        rows = session.scalars(
            select(RawSourceArchive).where(RawSourceArchive.provider.like("SP_PRESS:%"))
        ).all()
        for r in rows:
            k = (r.source_identifier, r.sha256)
            if k in seen:
                continue
            seen.add(k)
            try:
                raw = store.get(r.sha256).decode("utf-8", "replace")
            except Exception:
                continue
            m = re.search(r"spglobal\.com/(20\d\d-\d\d-\d\d)-", r.source_identifier) or re.search(
                r"(20\d\d-\d\d-\d\dT)", raw
            )
            if not m:
                continue
            d = date.fromisoformat(m.group(1)[:10])
            text = re.sub(r"<[^>]+>", " ", raw)
            flat = re.sub(r"\s+", " ", text)
            flat = re.sub(r"\(\s+", "(", flat)
            flat = re.sub(r"\s+\)", ")", flat)
            for rm in _RENAME.finditer(flat):
                new = rm.group(1).upper()
                before = [
                    x.upper()
                    for x in _ANY_TICK.findall(flat[max(0, rm.start() - 450) : rm.start()])
                ]
                olds = [x for x in before if x != new]
                if olds:
                    self.renames.append((d, olds[-1], new, r.source_identifier))
            for t in set(_TICKER_IN_DOC.findall(text)):
                self.by_ticker.setdefault(t.upper(), []).append((d, r.source_identifier))

    def near(self, ticker: str, around: date | None, days: int = 200) -> list[str]:
        if around is None:
            return []
        return sorted(
            {u for d, u in self.by_ticker.get(ticker.upper(), []) if abs((d - around).days) <= days}
        )


def _norm(t: str | None) -> str | None:
    return t.upper().replace("/", ".") if t else None


def _cards(
    session: Session,
    settings: Settings,
    events: list[SP500MembershipEvent],
    break_ids: set[str],
    win: tuple[date, date],
    ho_notes: list[str],
) -> list[GapCard]:
    idx = ArchiveIndex(session, settings)
    anns = session.scalars(
        select(SP500Announcement).where(SP500Announcement.parser_version == PARSER_VERSION)
    ).all()
    names: dict[str, str] = {}
    announced_pairs: set[tuple[str, str]] = set()
    for a in anns:
        names.setdefault(a.added_ticker.upper(), a.added_name)
        if a.removed_ticker:
            names.setdefault(a.removed_ticker.upper(), a.removed_name)
        announced_pairs.add(("A", a.added_ticker.upper()))
        if a.removed_ticker:
            announced_pairs.add(("R", a.removed_ticker.upper()))
    tick_ids: dict[str, list[tuple[date, date | None]]] = {}
    for th in session.scalars(select(TickerHistory)):
        tick_ids.setdefault(th.ticker.upper(), []).append((th.valid_from, th.valid_to))
    cards: list[GapCard] = []
    for e in events:
        if e.event_id not in break_ids:
            continue
        official = e.effective_at.date() if e.effective_at else None
        cand = [d for d in (official, e.stated_change_date, e.discovery_date) if d is not None]
        eff = official or e.stated_change_date or e.discovery_date
        late = max(cand) if cand else None
        pos = (
            "BEFORE_WINDOW"
            if late is not None and late < win[0]
            else "AFTER_WINDOW_CHAIN"
            if late is not None and late > win[1]
            else "IN_WINDOW"
        )
        at, rt = _norm(e.added_ticker), _norm(e.removed_ticker)
        found: list[str] = []
        for t in (at, rt):
            if t:
                found += idx.near(t, e.discovery_date or eff)
        found = sorted(set(found))
        parsed_here = e.announcement_row_id is not None
        if e.status == "CONFLICT":
            ps, why = (
                "PARSED_DATE_CONFLICT",
                (
                    f"official effective {official} vs CSV {e.discovery_date}: the difference spans a monthly cohort open"
                ),
            )
            miss = "which date is the real effective session (a later release, an S&P statement or the ETF-holdings change); official date is never edited to match the CSV"
        elif e.status in ("UNRESOLVED", "DATE_TBA"):
            ps, why = "PARSED_NO_DATE", e.reason
            miss = "a release or follow-up that states the concrete effective date/timing of this change"
        elif parsed_here:
            ps, why, miss = "PARSED", e.reason, "official date confirmation"
        else:
            sides = [x for x, k in (("A", at), ("R", rt)) if k and (x, k) in announced_pairs]
            if sides:
                ps = "PARSED_BUT_NOT_MATCHED"
                why = "an announcement for this ticker exists but does not match this CSV row"
                miss = "check whether the announcement is another event of the same ticker (re-entry) or a date outside the matching window"
            elif found:
                ps = "PARSER_MISS"
                why = "an archived S&P release mentions this ticker but no clause was parsed"
                miss = "parser extension for the release layout (offline, no new download)"
            else:
                ps = "NO_DOCUMENT"
                why = e.reason
                miss = "the S&P DJI release announcing this change is NOT in the archive: external source needed"
        ident = []
        ren = [
            f"{o}->{n}"
            for d_, o, n, _u in idx.renames
            if (at in (o, n) or rt in (o, n)) and abs((d_ - (eff or d_)).days) <= 200
        ]
        for t in (at, rt):
            if t:
                ident.append(f"{t}:{'RESOLVED' if t in tick_ids else 'NO_SECURITY'}")
        cards.append(
            GapCard(
                e.event_id,
                e.status,
                pos,
                str(eff) if eff else None,
                str(e.announcement_at.date()) if e.announcement_at else None,
                at,
                rt,
                names.get(at or "", ""),
                names.get(rt or "", ""),
                "chinobing/historical_sp500_constituents" if e.discovery_row_id else None,
                bool(found) or parsed_here,
                found[:3],
                ps,
                (" ".join(ident) or "n/a")
                + (f" TICKER_CHANGE_CANDIDATE({','.join(sorted(set(ren)))})" if ren else ""),
                miss,
                why,
            )
        )
    cards.sort(key=lambda c: (c.effective_date or "", c.event_id))
    return cards


def window_readiness(
    session: Session, start: date, end: date, *, settings: Settings | None = None
) -> WindowReport:
    cfg = settings or get_settings()
    ho = cfg.validation.final_holdout
    cal = get_calendar("XNYS")
    d02 = compute_d02(session)
    cohorts = cal.first_sessions_of_months(start, end)
    rep = WindowReport(
        start,
        end,
        len(cohorts),
        0,
        0,
        0,
        0,
        None,
        holdout_overlap=any(ho.start <= d <= ho.end for d in cohorts) or not (end < ho.start),
    )
    if rep.holdout_overlap:
        rep.notes.append(
            "the window touches the sealed holdout: those cohorts are never research cohorts"
        )
    events = (
        list(
            session.scalars(
                select(SP500MembershipEvent).where(SP500MembershipEvent.run_id == d02.run_id)
            )
        )
        if d02.run_id
        else []
    )
    break_dates = {eid: d for d, eid in d02.break_event_ids}
    rep.immaterial_conflicts_in_window = sum(
        1 for d, _ in d02.immaterial_conflicts if start <= d <= end
    )
    if d02.anchor_status != "MULTI_SOURCE_CONFIRMED":
        rep.status = "BLOCKED_NO_ANCHOR"
        return rep
    # current chain: cohort d is proven iff no break in [d, anchor]; intrinsic: no break in [d, end]
    cur = [d for d in cohorts if all(bd < d for bd in break_dates.values())]
    intr = [d for d in cohorts if all(bd < d or bd > end for bd in break_dates.values())]

    def longest(ds: list[date]) -> int:
        best = run = 0
        prev: date | None = None
        for d in ds:
            run = (
                run + 1
                if prev is not None and (d.year * 12 + d.month) - (prev.year * 12 + prev.month) == 1
                else 1
            )
            best, prev = max(best, run), d
        return best

    rep.reconstructible_cohorts, rep.longest_consecutive_run = len(cur), longest(cur)
    rep.intrinsic_reconstructible_cohorts, rep.intrinsic_longest_run = len(intr), longest(intr)
    cards = _cards(session, cfg, events, set(break_dates), (start, end), rep.notes)
    rep.blocking_events = [c for c in cards if c.position == "IN_WINDOW"]
    rep.rename_candidates = [
        {"release_date": str(d_), "old": o, "new": n, "source": u}
        for d_, o, n, u in sorted(ArchiveIndex(session, cfg).renames)
        if start - timedelta(days=60) <= d_ <= end
    ]
    chain = [c for c in cards if c.position == "AFTER_WINDOW_CHAIN"]
    rep.chain_blocking_events = len(chain)
    for c in chain:
        y = (c.effective_date or "????")[:4]
        rep.chain_blocking_by_year[y] = rep.chain_blocking_by_year.get(y, 0) + 1
    missing = [c for c in cohorts if c not in set(cur)]
    if missing:
        first = missing[0]
        blockers = [c for c in cards if c.effective_date and c.effective_date >= str(first)]
        rep.first_failure = (
            f"cohort {first}: {len(blockers)} unconfirmed events dated on/after it; "
            f"nearest {blockers[0].effective_date} +{blockers[0].added_ticker} -{blockers[0].removed_ticker} ({blockers[0].status})"
            if blockers
            else f"cohort {first}"
        )
    uniq = sorted(
        {
            tk
            for c in rep.blocking_events
            for tk in (c.added_ticker, c.removed_ticker)
            if tk and f"{tk}:RESOLVED" not in c.identity_status.split()
        }
    )
    rep.blocking_identity = uniq
    need = MIN_COHORTS
    if rep.longest_consecutive_run >= need:
        rep.status = "READY"
    elif rep.intrinsic_longest_run >= need and rep.blocking_events:
        rep.status = "BLOCKED_BY_EVENTS_IN_WINDOW_AND_CHAIN"
    elif rep.intrinsic_longest_run >= need:
        rep.status = "BLOCKED_BY_CHAIN_AFTER_WINDOW (needs an anchor inside/after the window)"
    else:
        rep.status = "BLOCKED_BY_EVENTS_IN_WINDOW"
    rep.notes.append(
        f"gate: {MIN_COHORTS} consecutive monthly cohorts (preferred {PREFERRED_COHORTS}); "
        "intrinsic_* is a hypothetical (anchor at window end), never used as readiness"
    )
    return rep
