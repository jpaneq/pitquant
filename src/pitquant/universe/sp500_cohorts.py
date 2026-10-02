# ruff: noqa: E501
"""US cohort readiness (S&P 500): one row per month-start session (ADR-0026).

``membership_ready`` = the member set at that open is PROVEN by the D-02 reconstruction (anchor +
confirmed events, no unconfirmed event after it). The other layers need every member resolved to a
``security_id`` in the Security Master; unresolved tickers block the cohort and are listed. Holdout
dates are never research cohorts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pitquant.config.settings import get_settings
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.db.models import (
    IndexCurrentAnchor,
    Price,
    SP500MembershipEvent,
    TickerHistory,
)
from pitquant.universe.sources.sp500_anchor import norm_ticker
from pitquant.universe.sources.sp500_evidence import (
    CANONICAL_STATUSES,
    ReplayEvent,
    undo_events,
)
from pitquant.universe.sp500_reconstruct import D02Report, compute_d02


@dataclass
class UsCohortRow:
    date: date
    n_members: int | None
    membership_ready: bool
    identity_ready: bool
    fundamentals_ready: bool
    prices_ready: bool
    corporate_actions_ready: bool
    benchmark_ready: bool
    total_return_ready: bool
    in_holdout: bool
    eligible: bool
    blocking_securities: list[str] = field(default_factory=list)
    blocking_reasons: list[str] = field(default_factory=list)


@dataclass
class UsCohortSummary:
    d02: D02Report
    rows: list[UsCohortRow]
    complete_pre_holdout: int
    longest_complete_run: int
    securities_per_cohort: dict[str, int]
    layer_ready_counts: dict[str, int]


def _members_at(
    session: Session, anchor: IndexCurrentAnchor, d02: D02Report, d: date
) -> set[str] | None:
    if (
        d02.reconstructible_from is not None
        and d <= d02.reconstructible_from
        and d02.reconstructible_from is not None
    ):
        pass
    run_id = session.scalars(
        select(SP500MembershipEvent.run_id).order_by(SP500MembershipEvent.created_at.desc())
    ).first()
    evs = session.scalars(
        select(SP500MembershipEvent).where(
            SP500MembershipEvent.run_id == run_id,
            SP500MembershipEvent.status.in_([x.value for x in CANONICAL_STATUSES]),
        )
    ).all()
    cal = get_calendar("XNYS")
    rep = [
        ReplayEvent(
            cal.session_on_or_after(e.effective_at.date()),
            e.added_ticker and norm_ticker(e.added_ticker),
            e.removed_ticker and norm_ticker(e.removed_ticker),
        )
        for e in evs
        if e.effective_at
    ]
    later = [
        e for e in rep if e.effective_session > d and e.effective_session <= (anchor.as_of or d)
    ]
    try:
        return undo_events({norm_ticker(m["ticker"]) for m in anchor.members}, later)
    except Exception:
        return None


def us_cohort_readiness(session: Session, *, start: date = date(2011, 1, 3)) -> UsCohortSummary:
    d02 = compute_d02(session)
    anchor = session.scalars(
        select(IndexCurrentAnchor)
        .where(IndexCurrentAnchor.index_code == "SP500")
        .order_by(IndexCurrentAnchor.ingested_at.desc())
    ).first()
    ho = get_settings().validation.final_holdout
    cal = get_calendar("XNYS")
    end = d02.anchor_as_of or date(2026, 10, 1)
    rows: list[UsCohortRow] = []
    proven = set(d02.cohorts) | {
        d
        for d in cal.first_sessions_of_months(start, end)
        if ho.start <= d <= ho.end
        and d02.reconstructible_from is not None
        and d > d02.reconstructible_from
    }
    have_ticker = {t.upper() for t in session.scalars(select(TickerHistory.ticker))}
    spy_prices = session.scalar(select(func.count()).select_from(Price)) or 0
    for d in cal.first_sessions_of_months(start, end):
        in_ho = ho.start <= d <= ho.end
        mem_ready = d in proven and anchor is not None
        members = _members_at(session, anchor, d02, d) if mem_ready and anchor is not None else None
        n = len(members) if members is not None else None
        unresolved = sorted(t for t in (members or set()) if t not in have_ticker)
        ident = bool(members) and not unresolved
        reasons = []
        if not mem_ready:
            reasons.append(
                "MEMBERSHIP: not proven (an unconfirmed S&P event lies between this date and the anchor)"
                if anchor
                else "MEMBERSHIP: no anchor"
            )
        if in_ho:
            reasons.append("HOLDOUT_SEALED")
        if mem_ready and not ident:
            reasons.append(
                f"IDENTITY: {len(unresolved)} of {n} members not resolved in the Security Master"
            )
        reasons.append(
            "PRICES/CORPORATE_ACTIONS/BENCHMARK: no accepted US market-data source ingested (D-05)"
        ) if spy_prices == 0 or not ident else None
        rows.append(
            UsCohortRow(
                d,
                n,
                mem_ready,
                ident,
                False,
                False,
                False,
                False,
                False,
                in_ho,
                False,
                unresolved[:25],
                [r for r in reasons if r],
            )
        )
    complete = [r for r in rows if r.eligible and not r.in_holdout]
    by = {
        "n_members_min": min((r.n_members for r in rows if r.n_members), default=0),
        "n_members_max": max((r.n_members for r in rows if r.n_members), default=0),
    }
    layer = {
        k: sum(getattr(r, k) for r in rows)
        for k in (
            "membership_ready",
            "identity_ready",
            "fundamentals_ready",
            "prices_ready",
            "corporate_actions_ready",
            "benchmark_ready",
            "total_return_ready",
            "eligible",
        )
    }
    return UsCohortSummary(d02, rows, len(complete), 0, by, layer)
