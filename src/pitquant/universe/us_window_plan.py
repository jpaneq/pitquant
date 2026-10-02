# ruff: noqa: E501
"""Demand planning for a US research window (ADR-0031). READ-ONLY, no API calls, no invented coverage.

The S&P 500 membership of the window is NOT proven yet (D-02), so the securities that would need prices are
estimated from a CANDIDATE membership: the current anchor with EVERY event (any status, best known date)
reversed leniently. It is a demand estimate (an upper bound on the unique symbols), never a universe, and every
output is labelled ``CANDIDATE_MEMBERSHIP_NOT_PROVEN``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pitquant.config.settings import get_settings
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.db.models import (
    FundamentalFact,
    IndexCurrentAnchor,
    Price,
    SecurityIdentifierEvidence,
    SecurityProfile,
    SP500MembershipEvent,
    TickerHistory,
)
from pitquant.market.providers.tiingo import TiingoBudget
from pitquant.universe.sources.sp500_anchor import norm_ticker
from pitquant.universe.sp500_reconstruct import compute_d02

LABEL = "CANDIDATE_MEMBERSHIP_NOT_PROVEN"
US_EXCHANGES = ("XNYS", "XNAS", "XASE", "ARCX", "BATS")
FEATURE_LOOKBACK_DAYS = 400  # 252 sessions of history for the 12M features + margin
MAX_HORIZON_MONTHS = 12


def _best_date(e: SP500MembershipEvent) -> date | None:
    return (
        (e.effective_at.date() if e.effective_at else None)
        or e.discovery_date
        or e.stated_change_date
    )


def candidate_membership(session: Session, cohorts: list[date]) -> tuple[dict[date, set[str]], int]:
    """cohort date -> candidate member tickers; second value = events that did not fit (lenient undo)."""
    d02 = compute_d02(session)
    anchor = session.scalars(
        select(IndexCurrentAnchor)
        .where(IndexCurrentAnchor.index_code == "SP500")
        .order_by(IndexCurrentAnchor.ingested_at.desc())
    ).first()
    if anchor is None or anchor.as_of is None or d02.run_id is None:
        return {}, 0
    cal = get_calendar("XNYS")
    evs = [
        (cal.session_on_or_after(d), e)
        for e in session.scalars(
            select(SP500MembershipEvent).where(SP500MembershipEvent.run_id == d02.run_id)
        )
        if (d := _best_date(e)) is not None and d <= anchor.as_of
    ]
    evs.sort(key=lambda x: x[0], reverse=True)
    cur = {norm_ticker(m["ticker"]) for m in anchor.members}
    out: dict[date, set[str]] = {}
    misfits, i = 0, 0
    for d in sorted(cohorts, reverse=True):
        while i < len(evs) and evs[i][0] > d:
            e = evs[i][1]
            i += 1
            if e.added_ticker:
                t = norm_ticker(e.added_ticker)
                if t in cur:
                    cur.discard(t)
                else:
                    misfits += 1
            if e.removed_ticker:
                cur.add(norm_ticker(e.removed_ticker))
        out[d] = set(cur)
    return out, misfits


@dataclass
class PlanRow:
    ticker: str
    security_id: str | None
    membership_start: date
    membership_end: date
    months: int
    price_required_from: date
    price_required_to: date
    identifier_status: str
    active_today: bool
    price_bars_in_db: int
    price_state: str
    dividend_coverage: str = "REQUIRED_UNVERIFIED"
    split_coverage: str = "REQUIRED_UNVERIFIED"
    complex_ca: str = "UNKNOWN"
    note: str = LABEL


@dataclass
class BackfillPlan:
    start: date
    end: date
    cohorts: int
    rows: list[PlanRow] = field(default_factory=list)
    misfit_events: int = 0
    summary: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "start": str(self.start),
            "end": str(self.end),
            "cohorts": self.cohorts,
            "summary": self.summary,
            "rows": [asdict(r) for r in self.rows],
        }


def _sec_for(ticker: str, d: date, ticks: dict[str, list[TickerHistory]]) -> str | None:
    for th in ticks.get(ticker.upper(), []):
        if th.valid_from <= d and (th.valid_to is None or d <= th.valid_to):
            return th.security_id
    return None


def backfill_plan(session: Session, start: date, end: date) -> BackfillPlan:
    cfg = get_settings()
    ho = cfg.validation.final_holdout
    cal = get_calendar("XNYS")
    cohorts = [d for d in cal.first_sessions_of_months(start, end) if not (ho.start <= d <= ho.end)]
    members, misfit = candidate_membership(session, cohorts)
    plan = BackfillPlan(start, end, len(cohorts), misfit_events=misfit)
    ticks: dict[str, list[TickerHistory]] = {}
    for th in session.scalars(
        select(TickerHistory).where(TickerHistory.exchange.in_(US_EXCHANGES))
    ):
        ticks.setdefault(th.ticker.upper(), []).append(th)
    prof: dict[str, str] = {}
    for sp in session.scalars(select(SecurityProfile).order_by(SecurityProfile.ingested_at)):
        if sp.current_ticker:
            prof[sp.current_ticker.upper()] = sp.security_id
    anchor = session.scalars(
        select(IndexCurrentAnchor)
        .where(IndexCurrentAnchor.index_code == "SP500")
        .order_by(IndexCurrentAnchor.ingested_at.desc())
    ).first()
    active = {norm_ticker(m["ticker"]) for m in anchor.members} if anchor else set()
    seen: dict[str, list[date]] = {}
    for d, tk in members.items():
        for t in tk:
            seen.setdefault(t, []).append(d)
    off_cusip = {
        r
        for (r,) in session.execute(
            select(SecurityIdentifierEvidence.security_id).where(
                SecurityIdentifierEvidence.kind == "OFFICIAL",
                SecurityIdentifierEvidence.id_type == "CUSIP",
            )
        )
    }
    for t, ds in sorted(seen.items()):
        ds.sort()
        sid = _sec_for(t, ds[0], ticks)
        via_profile = False
        if sid is None and t in prof and t in active:
            sid, via_profile = prof[t], True  # CIK profile: the CURRENT ticker only
        bars = 0
        if sid:
            bars = (
                session.scalar(
                    select(func.count()).select_from(Price).where(Price.security_id == sid)
                )
                or 0
            )
        ident = (
            "NO_SECURITY (ticker not in Security Master; needs CUSIP/CIK evidence)"
            if sid is None
            else "OFFICIAL_CUSIP"
            if sid in off_cusip
            else "ISSUER_CIK_CURRENT_TICKER_ONLY"
            if via_profile
            else "SECURITY_NO_OFFICIAL_CUSIP"
        )
        req_to = min(ds[-1] + timedelta(days=30 * MAX_HORIZON_MONTHS), ho.start - timedelta(days=1))
        plan.rows.append(
            PlanRow(
                t,
                sid,
                ds[0],
                ds[-1],
                len(ds),
                ds[0] - timedelta(days=FEATURE_LOOKBACK_DAYS),
                req_to,
                ident,
                t in active,
                bars,
                "VENDOR_QA_ONLY (not accepted D-05)" if bars else "MISSING",
            )
        )
    n = len(plan.rows)
    b = TiingoBudget()
    plan.summary = {
        "label": LABEL,
        "unique_securities_required": n,
        "active_securities": sum(r.active_today for r in plan.rows),
        "former_securities": sum(not r.active_today for r in plan.rows),
        "estimated_unique_symbols": n,
        "already_available": sum(r.price_bars_in_db > 0 for r in plan.rows),
        "already_available_note": "non-canonical vendor QA bars only (EODHD public demo); they do not satisfy D-05",
        "missing_market_data": sum(r.price_bars_in_db == 0 for r in plan.rows),
        "free_plan_capacity": {
            "monthly_unique_symbols": b.monthly_symbols,
            "daily_requests": b.daily,
            "hourly_requests": b.hourly,
            "source": "limits encoded in TiingoBudget (ADR-0024); not re-verified here",
            "months_needed_for_symbols": -(-n // b.monthly_symbols),
        },
        "identifiers_without_security": sum(r.security_id is None for r in plan.rows),
        "lenient_undo_misfits": misfit,
    }
    return plan


@dataclass
class FundCoverageRow:
    ticker: str
    security_id: str | None
    membership_months: int
    fundamental_months_possible: int
    first_fundamental_snapshot: str | None
    last_fundamental_snapshot: str | None
    missing_reason: str


def fundamental_coverage(session: Session, plan: BackfillPlan) -> list[FundCoverageRow]:
    out: list[FundCoverageRow] = []
    for r in plan.rows:
        if r.security_id is None:
            out.append(
                FundCoverageRow(
                    r.ticker,
                    None,
                    r.months,
                    0,
                    None,
                    None,
                    "NO_SECURITY: no CIK/issuer link yet, SEC facts not ingested",
                )
            )
            continue
        lo, hi = session.execute(
            select(
                func.min(FundamentalFact.available_at), func.max(FundamentalFact.available_at)
            ).where(FundamentalFact.security_id == r.security_id)
        ).one()
        if lo is None:
            out.append(
                FundCoverageRow(
                    r.ticker,
                    r.security_id,
                    r.months,
                    0,
                    None,
                    None,
                    "NO_FACTS: security resolved but SEC facts not ingested",
                )
            )
            continue
        lo_d, hi_d = lo.date(), hi.date()
        cal = get_calendar("XNYS")
        possible = sum(
            1
            for d in cal.first_sessions_of_months(r.membership_start, r.membership_end)
            if lo_d <= d
        )
        out.append(
            FundCoverageRow(
                r.ticker,
                r.security_id,
                r.months,
                min(possible, r.months),
                str(lo_d),
                str(hi_d),
                "" if possible else "FACTS_START_AFTER_MEMBERSHIP",
            )
        )
    return out


@dataclass
class CohortDryRun:
    date: str
    members: int
    identity_ready: int
    fundamentals_ready: int
    prices_ready: int
    corporate_actions_ready: int
    eligible: int
    proven_membership: bool = False
    label: str = LABEL


def dataset_dry_run(
    session: Session, start: date, end: date, plan: BackfillPlan
) -> tuple[list[CohortDryRun], dict[str, Any]]:
    """Layer readiness per cohort. Prices / corporate actions are READY only when an ACCEPTED (non vendor-QA)
    source exists: today none. The real Dataset Builder is run for the securities that resolve to the Security
    Master (no labels needed to see feature/price reasons), so the reason codes are the builder's own."""
    from pitquant.research.dataset_builder import DatasetSpec, build_dataset, summarize

    cal = get_calendar("XNYS")
    ho = get_settings().validation.final_holdout
    cohorts = [d for d in cal.first_sessions_of_months(start, end) if not (ho.start <= d <= ho.end)]
    members, _ = candidate_membership(session, cohorts)
    sec_of = {r.ticker: r.security_id for r in plan.rows}
    fund = {
        f.ticker: f.fundamental_months_possible > 0 for f in fundamental_coverage(session, plan)
    }
    rows: list[CohortDryRun] = []
    for d in cohorts:
        tk = members.get(d, set())
        ident = sum(1 for t in tk if sec_of.get(t))
        fu = sum(1 for t in tk if fund.get(t))
        rows.append(CohortDryRun(str(d), len(tk), ident, fu, 0, 0, 0))
    resolved = tuple(sorted({s for s in sec_of.values() if s}))
    builder: dict[str, Any] = {
        "securities_run": len(resolved),
        "note": "real Dataset Builder, securities that resolve in the Security Master",
    }
    if resolved and cohorts:
        res = build_dataset(
            session, DatasetSpec("SP500", "CANDIDATE", resolved, cohorts[0], cohorts[-1])
        )
        builder["summary"] = summarize(res.rows)
        builder["dataset_hash"] = res.dataset_hash
    return rows, builder
