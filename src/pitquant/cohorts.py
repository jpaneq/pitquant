"""Cohort readiness: can the universe at date D be reconstructed WITHOUT exceptions?

A cohort is the index membership at one rebalance date (first session of a month). It is
``identity_eligible`` when EVERY member has a backtestable identity segment (EXACT or
MULTI_SOURCE_CONFIRMED) at D — the fail-closed rule of ``backtest_universe``, never relaxed. It
is ``eligible`` (full) only if, in addition, every member has PRICES, FUNDAMENTALS and
verified CORPORATE-ACTION coverage at D. Dates inside the sealed holdout are never research
cohorts (``in_holdout``): identity QA only.

Nothing here computes returns, scores or any predictive statistic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from pitquant.config.settings import Settings
from pitquant.core.timeutils import utc_now
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.db.models import FundamentalFact, Price, Security
from pitquant.security_master.identity import BACKTESTABLE, IdentityResolutionStatus
from pitquant.security_master.identity_store import latest_run, segment_at
from pitquant.universe.index_membership import IndexUniverse

MIN_COVERAGE = 0.95  # share of members a layer must cover for the cohort to be eligible


@dataclass
class CohortRow:
    date: date
    universe_size: int
    resolved_identities: int
    price_coverage: float
    fundamental_coverage: float
    corporate_action_coverage: float
    identity_eligible: bool
    eligible: bool
    in_holdout: bool
    blocking_reasons: list[str] = field(default_factory=list)


@dataclass
class CohortSummary:
    index_code: str
    build_id: str
    total_dates: int
    identity_eligible_dates: int
    eligible_dates: int
    first_identity_cohort: date | None
    first_canonical_cohort: date | None  # FIRST_CANONICAL_COHORT (full eligibility)
    first_12_identity_cohorts: list[date]
    first_complete_identity_year: int | None
    first_complete_year: int | None  # full eligibility
    research_identity_dates: int  # identity-eligible and NOT in the sealed holdout
    blockers: dict[str, int] = field(default_factory=dict)  # security code -> blocked dates


def _consecutive_run(dates: list[date], n: int) -> list[date]:
    """First run of ``n`` consecutive month-start rebalance dates inside ``dates``."""
    ok = sorted(dates)
    allm = sorted({(d.year, d.month) for d in ok})
    idx = {ym: i for i, ym in enumerate(allm)}
    for i, d in enumerate(ok):
        run = [d]
        y, m = d.year, d.month
        for _ in range(n - 1):
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
            nxt = next((x for x in ok if (x.year, x.month) == (y, m)), None)
            if nxt is None:
                break
            run.append(nxt)
        if len(run) == n:
            return run
        _ = idx, i
    return []


def _complete_year(dates: list[date]) -> int | None:
    by_year: dict[int, set[int]] = {}
    for d in dates:
        by_year.setdefault(d.year, set()).add(d.month)
    for y in sorted(by_year):
        if by_year[y] == set(range(1, 13)):
            return y
    return None


def _price_ok(session: Session, security_id: str, d: date, lookback: int = 252) -> bool:
    sec = session.get(Security, security_id)
    if sec is None:
        return False
    cal = get_calendar(sec.exchange)
    sessions = [s for s in cal.sessions(date(d.year - 2, 1, 1), d)][-lookback:]
    if not sessions:
        return False
    n = session.scalar(
        select(func.count(func.distinct(Price.session_date))).where(
            Price.security_id == security_id,
            Price.session_date >= sessions[0],
            Price.session_date <= d,
        )
    )
    return (n or 0) >= MIN_COVERAGE * len(sessions)


def _facts_ok(session: Session, security_id: str, d: date) -> bool:
    sec = session.get(Security, security_id)
    subject = [FundamentalFact.security_id == security_id]
    if sec is not None and sec.issuer_id:
        subject.append(FundamentalFact.issuer_id == sec.issuer_id)
    n = session.scalar(
        select(func.count())
        .select_from(FundamentalFact)
        .where(or_(*subject), func.date(FundamentalFact.available_at) <= d.isoformat())
    )
    return bool(n)


def _ca_ok(session: Session, security_id: str, start: date, d: date) -> bool:
    """VERIFIED corporate-action coverage (ingestion trace) — see ``pitquant.coverage``."""
    from pitquant.coverage import corporate_action_verified

    return corporate_action_verified(session, security_id, start, d)


def cohort_readiness(
    session: Session,
    settings: Settings,
    index_code: str = "IBEX35",
    *,
    start: date | None = None,
    end: date | None = None,
    build_id: str | None = None,
    check_layers: bool = True,
    calendar: str = "XMAD",
) -> tuple[list[CohortRow], CohortSummary]:
    u = IndexUniverse(session)
    build = (
        u.active_build(index_code)
        if build_id is None
        else session.get_one(
            __import__("pitquant.db.models", fromlist=["MembershipBuild"]).MembershipBuild, build_id
        )
    )
    run = latest_run(session, build.build_id)
    start = start or settings.canonical_period.start
    end = end or utc_now().date()
    try:
        cal_code = settings.universe(index_code).calendar
    except KeyError:  # an index outside the configured universes (tests, research indices)
        cal_code = calendar
    cal = get_calendar(cal_code)
    ho = settings.validation.final_holdout
    rows: list[CohortRow] = []
    blockers: dict[str, int] = {}
    from pitquant.security_master.service import SecurityMaster

    sm = SecurityMaster(session)
    for d in cal.first_sessions_of_months(start, end):
        members = u.universe(index_code, d, build.build_id)
        reasons: list[str] = []
        resolved = 0
        proven: list[str] = []
        for m in members:
            seg = (
                segment_at(session, run.run_id, m.membership_id, d)
                if run is not None and m.membership_id is not None
                else None
            )
            ok = m.identity_status == "RESOLVED" or (
                seg is not None
                and seg.security_id is not None
                and IdentityResolutionStatus(seg.status) in BACKTESTABLE
            )
            code = sm.ticker_as_of(m.security_id, d) or "?"
            if ok:
                resolved += 1
                proven.append(
                    m.security_id
                    if m.identity_status == "RESOLVED" or seg is None or seg.security_id is None
                    else seg.security_id
                )
            else:
                reasons.append(f"IDENTITY:{code}({seg.status if seg else 'no segment'})")
                blockers[code] = blockers.get(code, 0) + 1
        n = len(members)
        id_ok = n > 0 and resolved == n
        pc = fc = cc = 0.0
        if check_layers and n:
            pc = sum(_price_ok(session, s, d) for s in proven) / n
            fc = sum(_facts_ok(session, s, d) for s in proven) / n
            cc = sum(_ca_ok(session, s, start, d) for s in proven) / n
        if pc < MIN_COVERAGE:
            reasons.append(f"PRICES: {pc:.0%} of members covered")
        if fc < MIN_COVERAGE:
            reasons.append(f"FUNDAMENTALS: {fc:.0%} of members covered")
        if cc < MIN_COVERAGE:
            reasons.append(f"CORPORATE_ACTIONS: {cc:.0%} of members verified")
        in_ho = ho.start <= d <= ho.end
        if in_ho:
            reasons.append("HOLDOUT_SEALED: identity QA only")
        rows.append(
            CohortRow(
                d,
                n,
                resolved,
                pc,
                fc,
                cc,
                id_ok,
                id_ok
                and pc >= MIN_COVERAGE
                and fc >= MIN_COVERAGE
                and cc >= MIN_COVERAGE
                and not in_ho,
                in_ho,
                reasons,
            )
        )
    idd = [r.date for r in rows if r.identity_eligible]
    full = [r.date for r in rows if r.eligible]
    research_id = [r.date for r in rows if r.identity_eligible and not r.in_holdout]
    summary = CohortSummary(
        index_code,
        build.build_id,
        len(rows),
        len(idd),
        len(full),
        min(idd) if idd else None,
        min(full) if full else None,
        _consecutive_run(research_id, 12),
        _complete_year(research_id),
        _complete_year(full),
        len(research_id),
        dict(sorted(blockers.items(), key=lambda kv: -kv[1])),
    )
    return rows, summary
