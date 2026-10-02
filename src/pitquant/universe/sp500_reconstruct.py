# ruff: noqa: E501
"""D-02 reconstruction from the current anchor (ADR-0026) and the D02_RESEARCH_READY gate.

``anchor -> undo confirmed events -> historical snapshots -> replay forward -> anchor`` must be
exact. Membership at the OPEN of session D needs EVERY event effective after D undone; therefore a
single unconfirmed event (DISCOVERY_ONLY / TBA / UNRESOLVED / CONFLICT) makes every date before it
non-canonical, but never a later, fully demonstrated period. Break dates are the LATEST candidate
date of the event (discovery vs official), so uncertainty can only shrink the proven region.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.config.settings import get_settings
from pitquant.core.errors import DataQualityError
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.db.models import IndexCurrentAnchor, SP500MembershipEvent
from pitquant.universe.sources.sp500_anchor import norm_ticker
from pitquant.universe.sources.sp500_evidence import (
    CANONICAL_STATUSES,
    EventStatus,
    ReplayEvent,
    replay_events,
    undo_events,
)

MIN_COHORTS = 60
PREFERRED_COHORTS = 96


@dataclass
class D02Report:
    anchor_status: str
    anchor_as_of: date | None
    n_events: int = 0
    n_confirmed: int = 0
    breaks: list[tuple[date, str]] = field(default_factory=list)  # (date, "status ADD/REM reason")
    reconstructible_from: date | None = None  # first session whose membership is proven
    cohorts: list[date] = field(
        default_factory=list
    )  # month-start sessions, proven, outside the holdout
    longest_run: list[date] = field(default_factory=list)
    first_complete_year: int | None = None
    last_complete_year: int | None = None
    reversible: bool | None = None
    holdout_cohorts_excluded: int = 0
    notes: list[str] = field(default_factory=list)
    # CONFLICT events whose two candidate dates leave every monthly cohort unchanged (ADR-0031)
    immaterial_conflicts: list[tuple[date, str]] = field(default_factory=list)
    break_event_ids: list[tuple[date, str]] = field(default_factory=list)  # (break date, event_id)
    run_id: str | None = None

    @property
    def d02_research_ready(self) -> bool:
        return len(self.longest_run) >= MIN_COHORTS

    @property
    def preferred(self) -> bool:
        return len(self.longest_run) >= PREFERRED_COHORTS


def _runs(months: list[date]) -> list[list[date]]:
    runs: list[list[date]] = []
    for d in months:
        if runs and (d.year * 12 + d.month) - (runs[-1][-1].year * 12 + runs[-1][-1].month) == 1:
            runs[-1].append(d)
        else:
            runs.append([d])
    return runs


def compute_d02(session: Session, *, exchange: str = "XNYS") -> D02Report:
    anchor = session.scalars(
        select(IndexCurrentAnchor)
        .where(IndexCurrentAnchor.index_code == "SP500")
        .order_by(IndexCurrentAnchor.ingested_at.desc())
    ).first()
    if anchor is None or anchor.status != "MULTI_SOURCE_CONFIRMED" or anchor.as_of is None:
        return D02Report(
            anchor.status if anchor else "BLOCKED",
            anchor.as_of if anchor else None,
            notes=["no confirmed current anchor: nothing can be reconstructed"],
        )
    run_id = session.scalars(
        select(SP500MembershipEvent.run_id).order_by(SP500MembershipEvent.created_at.desc())
    ).first()
    events = (
        session.scalars(
            select(SP500MembershipEvent).where(SP500MembershipEvent.run_id == run_id)
        ).all()
        if run_id
        else []
    )
    rep = D02Report(anchor.status, anchor.as_of, n_events=len(events), run_id=run_id)
    A = anchor.as_of
    cal = get_calendar(exchange)
    month_opens = cal.first_sessions_of_months(date(2011, 1, 1), A)
    confirmed: list[ReplayEvent] = []
    break_dates: list[date] = []
    for e in events:
        official = (
            e.effective_at.astimezone(__import__("datetime").timezone.utc).date()
            if e.effective_at
            else None
        )
        cand = [d for d in (e.discovery_date, official, e.stated_change_date) if d is not None]
        immaterial = False
        if (
            EventStatus(e.status) is EventStatus.CONFLICT
            and official is not None
            and e.discovery_date is not None
            and (e.added_ticker or e.removed_ticker)
        ):
            # official release > discovery CSV (ADR-0031): the OFFICIAL date drives the replay; the
            # disagreement only blocks if a monthly cohort open lies between the two dates
            lo = cal.session_on_or_after(min(official, e.discovery_date))
            hi = cal.session_on_or_after(max(official, e.discovery_date))
            immaterial = not any(lo <= m < hi for m in month_opens)
            if immaterial:
                rep.immaterial_conflicts.append(
                    (
                        official,
                        f"+{e.added_ticker or '-'} -{e.removed_ticker or '-'}: official {official} vs CSV {e.discovery_date}",
                    )
                )
        if (EventStatus(e.status) in CANONICAL_STATUSES or immaterial) and official is not None:
            confirmed.append(
                ReplayEvent(
                    cal.session_on_or_after(official),
                    e.added_ticker and norm_ticker(e.added_ticker),
                    e.removed_ticker and norm_ticker(e.removed_ticker),
                )
            )
        else:
            b = max(cand) if cand else A
            if b <= A:
                break_dates.append(b)
                rep.break_event_ids.append((b, e.event_id))
                rep.breaks.append(
                    (
                        b,
                        f"{e.status} +{e.added_ticker or '-'} -{e.removed_ticker or '-'}: {e.reason}",
                    )
                )
    rep.n_confirmed = len(confirmed)
    rep.breaks.sort()
    last_break = max(break_dates) if break_dates else None
    # events AFTER the anchor date are not relevant (the anchor is the present)
    confirmed = [
        c
        for c in confirmed
        if c.effective_session <= A and (last_break is None or c.effective_session > last_break)
    ]  # only the proven region
    members = {norm_ticker(m["ticker"]) for m in anchor.members}
    # consistency of the undo/replay on the confirmed chain (reversibility) — fail closed
    try:
        hist = undo_events(members, confirmed)
        rep.reversible = replay_events(hist, confirmed) == members
    except DataQualityError as e:
        rep.reversible = False
        rep.notes.append(f"undo/replay inconsistency on the confirmed chain: {e}")
    start = cal.session_on_or_after(last_break) if last_break else None
    rep.reconstructible_from = start
    ho = get_settings().validation.final_holdout
    if start is None:
        start = date(2011, 1, 3)
    months = cal.first_sessions_of_months(max(start, date(2011, 1, 1)), A)
    # a cohort at the open of D is proven if no break lies in [D, A] -> D > last_break
    proven = [d for d in months if last_break is None or d > last_break]
    rep.holdout_cohorts_excluded = sum(1 for d in proven if ho.start <= d <= ho.end)
    rep.cohorts = [d for d in proven if not (ho.start <= d <= ho.end)]
    runs = _runs(rep.cohorts)
    rep.longest_run = max(runs, key=len) if runs else []
    years = sorted({d.year for d in rep.longest_run})
    full = [
        y for y in years if {d.month for d in rep.longest_run if d.year == y} == set(range(1, 13))
    ]
    rep.first_complete_year, rep.last_complete_year = (full[0], full[-1]) if full else (None, None)
    if rep.reversible is not True:
        rep.cohorts, rep.longest_run = [], []
        rep.notes.append("reversibility not demonstrated: no cohort is declared canonical")
    return rep
