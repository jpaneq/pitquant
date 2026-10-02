"""Data Coverage Engine — the backend of the future Data Coverage Panel (ADR-0021).

For one ``security_id`` and a period it reports, from what is STORED (nothing inferred):

* price coverage: sessions with a RAW bar / expected sessions of the security's calendar;
* fundamentals coverage: issuer (or security) facts whose ``available_at`` falls in the
  period, and how many distinct filings delivered them;
* corporate-action coverage: whether an accepted corporate-action source covers the period
  (a source with zero events is still coverage; no accepted source is not);
* identity confidence: an ISIN proven for the whole period (``identifier_history``);
* benchmark / sector availability.

Status per dimension and overall: ``COMPLETE`` / ``PARTIAL`` / ``INSUFFICIENT`` /
``UNRESOLVED_IDENTITY`` (identity gaps dominate: data about an unknown security is not
coverage). No BUY/HOLD/SELL here.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.db.models import (
    BenchmarkLevel,
    CorporateActionIngestion,
    FundamentalFact,
    IdentifierHistory,
    Price,
    SectorClassification,
    Security,
)


class CoverageStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"
    UNRESOLVED_IDENTITY = "UNRESOLVED_IDENTITY"


@dataclass(frozen=True)
class CoverageThresholds:
    price_complete: float = 0.98  # share of expected sessions with a raw bar
    price_min: float = 0.80
    min_fundamental_filings_per_year: float = 2.0


@dataclass
class DimensionCoverage:
    name: str
    status: CoverageStatus
    value: float | None
    detail: str


@dataclass
class SecurityCoverage:
    security_id: str
    start: date
    end: date
    dimensions: list[DimensionCoverage] = field(default_factory=list)

    @property
    def status(self) -> CoverageStatus:
        st = {d.name: d.status for d in self.dimensions}
        if st.get("identity") is CoverageStatus.UNRESOLVED_IDENTITY:
            return CoverageStatus.UNRESOLVED_IDENTITY
        if any(s is CoverageStatus.INSUFFICIENT for s in st.values()):
            return CoverageStatus.INSUFFICIENT
        if all(s is CoverageStatus.COMPLETE for s in st.values()):
            return CoverageStatus.COMPLETE
        return CoverageStatus.PARTIAL

    def as_rows(self) -> list[tuple[str, str, str]]:
        return [(d.name, d.status.value, d.detail) for d in self.dimensions]


def _identity(s: Session, sec: Security, start: date, end: date) -> DimensionCoverage:
    rows = s.scalars(
        select(IdentifierHistory).where(
            IdentifierHistory.security_id == sec.security_id, IdentifierHistory.id_type == "ISIN"
        )
    ).all()
    spans = sorted((r.valid_from, r.valid_to or date.max) for r in rows)
    cur = start
    for a, b in spans:
        if a <= cur < b:
            cur = b
    if cur > end:
        isins = sorted({r.value for r in rows})
        return DimensionCoverage("identity", CoverageStatus.COMPLETE, 1.0, f"ISIN proven: {isins}")
    return DimensionCoverage(
        "identity",
        CoverageStatus.UNRESOLVED_IDENTITY,
        None,
        f"no proven ISIN from {cur}" if rows else "no proven ISIN",
    )


def _prices(
    s: Session, sec: Security, start: date, end: date, th: CoverageThresholds
) -> DimensionCoverage:
    cal = get_calendar(sec.exchange)
    lo = max(start, sec.listing_start or start)
    hi = min(end, sec.listing_end or end)
    expected = cal.sessions(lo, hi) if lo <= hi else []
    have = (
        s.scalar(
            select(func.count(func.distinct(Price.session_date))).where(
                Price.security_id == sec.security_id, Price.session_date.between(lo, hi)
            )
        )
        or 0
    )
    if not expected:
        return DimensionCoverage("prices", CoverageStatus.INSUFFICIENT, None, "no sessions")
    r = have / len(expected)
    st = (
        CoverageStatus.COMPLETE
        if r >= th.price_complete
        else CoverageStatus.PARTIAL
        if r >= th.price_min
        else CoverageStatus.INSUFFICIENT
    )
    return DimensionCoverage("prices", st, r, f"{have}/{len(expected)} sessions with a raw bar")


def _fundamentals(
    s: Session, sec: Security, start: date, end: date, th: CoverageThresholds
) -> DimensionCoverage:
    subject = [FundamentalFact.security_id == sec.security_id]
    if sec.issuer_id:
        subject.append(FundamentalFact.issuer_id == sec.issuer_id)
    filings = (
        s.scalar(
            select(
                func.count(
                    func.distinct(
                        func.coalesce(
                            FundamentalFact.accession_number,
                            FundamentalFact.cnmv_filing_id,
                            FundamentalFact.source_document,
                        )
                    )
                )
            ).where(
                or_(*subject),
                FundamentalFact.available_at >= datetime.combine(start, time(), UTC),
                FundamentalFact.available_at
                < datetime.combine(end + timedelta(days=1), time(), UTC),
            )
        )
        or 0
    )
    years = max((end - start).days / 365.25, 0.25)
    rate = filings / years
    st = (
        CoverageStatus.COMPLETE
        if rate >= th.min_fundamental_filings_per_year
        else CoverageStatus.PARTIAL
        if filings
        else CoverageStatus.INSUFFICIENT
    )
    who = "issuer+security" if sec.issuer_id else "security only (issuer not linked)"
    return DimensionCoverage(
        "fundamentals", st, rate, f"{filings} filings ({rate:.1f}/year) via {who}"
    )


class CaCoverageState(StrEnum):
    """Why corporate-action coverage is (not) claimed for one security and period."""

    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"  # no accepted source configured
    NOT_ATTEMPTED = "NOT_ATTEMPTED"  # accepted source exists, never queried for this security
    ATTEMPTED_FAILED = "ATTEMPTED_FAILED"
    PARTIAL_PERIOD = "PARTIAL_PERIOD"  # completed ingestion covers only part of the period
    VERIFIED_COVERAGE = "VERIFIED_COVERAGE"  # completed ingestion covers the whole period


def corporate_action_state(
    session: Session, security_id: str, start: date, end: date, accepted: Sequence[str]
) -> tuple[CaCoverageState, str]:
    if not accepted:
        # No source is accepted (D-05 open): coverage can NEVER be VERIFIED, but the real
        # ingestion attempts of non-accepted (e.g. official issuer) sources are still shown.
        traces = session.scalars(
            select(CorporateActionIngestion).where(
                CorporateActionIngestion.security_id == security_id
            )
        ).all()
        if not traces:
            return (
                CaCoverageState.PROVIDER_UNAVAILABLE,
                "no accepted corporate-action source (D-05)",
            )
        done = [r for r in traces if r.status == "COMPLETED"]
        found = sum(r.events_found for r in done)
        if not done:
            return (
                CaCoverageState.ATTEMPTED_FAILED,
                f"{len(traces)} attempt(s) by non-accepted sources, none completed",
            )
        return (
            CaCoverageState.PARTIAL_PERIOD,
            f"source(s) {sorted({r.provider for r in done})} NOT accepted (D-05): never verified; "
            f"{found} event(s) from {min(r.period_start for r in done)}",
        )
    rows = session.scalars(
        select(CorporateActionIngestion).where(
            CorporateActionIngestion.security_id == security_id,
            CorporateActionIngestion.provider.in_(list(accepted)),
        )
    ).all()
    if not rows:
        return CaCoverageState.NOT_ATTEMPTED, f"no ingestion trace from {list(accepted)}"
    done = sorted(
        (r for r in rows if r.status == "COMPLETED"), key=lambda r: (r.period_start, r.period_end)
    )
    if not done:
        return CaCoverageState.ATTEMPTED_FAILED, f"{len(rows)} attempt(s), none completed"
    cur = start
    for r in done:
        if r.period_start <= cur <= r.period_end:
            cur = r.period_end + timedelta(days=1)
    found = sum(r.events_found for r in done)
    note = f"provider-reported events: {found} (absence of events is the provider's statement)"
    if cur > end:
        return CaCoverageState.VERIFIED_COVERAGE, note
    return (
        CaCoverageState.PARTIAL_PERIOD,
        f"completed ingestion covers up to {cur - timedelta(days=1)}; {note}",
    )


def corporate_action_verified(session: Session, security_id: str, start: date, end: date) -> bool:
    from pitquant.config.settings import get_settings

    accepted = get_settings().data_readiness.accepted_corporate_action_sources
    state, _ = corporate_action_state(session, security_id, start, end, accepted)
    return state is CaCoverageState.VERIFIED_COVERAGE


def _corporate_actions(
    s: Session, sec: Security, start: date, end: date, accepted: Sequence[str]
) -> DimensionCoverage:
    state, detail = corporate_action_state(s, sec.security_id, start, end, accepted)
    status = {
        CaCoverageState.VERIFIED_COVERAGE: CoverageStatus.COMPLETE,
        CaCoverageState.PARTIAL_PERIOD: CoverageStatus.PARTIAL,
    }.get(state, CoverageStatus.INSUFFICIENT)
    return DimensionCoverage("corporate_actions", status, None, f"{state.value}: {detail}")


def _benchmark(s: Session, start: date, end: date, code: str | None) -> DimensionCoverage:
    if code is None:
        return DimensionCoverage("benchmark", CoverageStatus.INSUFFICIENT, None, "no benchmark")
    n = (
        s.scalar(
            select(func.count())
            .select_from(BenchmarkLevel)
            .where(
                BenchmarkLevel.benchmark_code == code,
                BenchmarkLevel.session_date.between(start, end),
            )
        )
        or 0
    )
    st = CoverageStatus.COMPLETE if n else CoverageStatus.INSUFFICIENT
    return DimensionCoverage("benchmark", st, float(n), f"{code}: {n} levels")


def _sector(s: Session, sec: Security, start: date, end: date) -> DimensionCoverage:
    n = (
        s.scalar(
            select(func.count())
            .select_from(SectorClassification)
            .where(
                SectorClassification.security_id == sec.security_id,
                SectorClassification.valid_from <= end,
                or_(SectorClassification.valid_to.is_(None), SectorClassification.valid_to > start),
            )
        )
        or 0
    )
    st = CoverageStatus.COMPLETE if n else CoverageStatus.INSUFFICIENT
    return DimensionCoverage("sector", st, float(n), f"{n} classification rows")


def security_coverage(
    session: Session,
    security_id: str,
    start: date,
    end: date,
    *,
    benchmark_code: str | None = None,
    accepted_ca_sources: Sequence[str] = (),
    thresholds: CoverageThresholds | None = None,
) -> SecurityCoverage:
    th = thresholds or CoverageThresholds()
    sec = session.get_one(Security, security_id)
    out = SecurityCoverage(security_id, start, end)
    out.dimensions = [
        _identity(session, sec, start, end),
        _prices(session, sec, start, end, th),
        _fundamentals(session, sec, start, end, th),
        _corporate_actions(session, sec, start, end, accepted_ca_sources),
        _benchmark(session, start, end, benchmark_code),
        _sector(session, sec, start, end),
    ]
    return out
