"""Data Coverage Engine and Stock Analyzer eligibility (ADR-0021). FIXTURE securities."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy.orm import Session

from pitquant.analyzer.eligibility import SupportStatus, support_decision
from pitquant.coverage import CoverageStatus, security_coverage
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.db.models import FundamentalFact, Issuer, Price, SectorClassification
from pitquant.security_master.service import SecurityMaster

pytestmark = pytest.mark.pit
START, END = date(2024, 1, 2), date(2024, 12, 31)


def _security(session: Session, *, isin: bool, prices: bool) -> str:
    sm = SecurityMaster(session)
    sec = sm.register(name="FIXTURE SA", exchange="XMAD", currency="EUR", country="ES")
    iss = Issuer(name="FIXTURE SA", country="ES")
    session.add(iss)
    session.flush()
    sec.issuer_id = iss.issuer_id
    if isin:
        sm.add_identifier(sec.security_id, "ISIN", "ES0000000045", date(2010, 1, 1))
    cal = get_calendar("XMAD")
    if prices:
        for d in cal.sessions(START, END):
            session.add(
                Price(
                    security_id=sec.security_id,
                    session_date=d,
                    source_id=1,
                    close=10.0,
                    currency="EUR",
                    bar_close_at=cal.session_close(d),
                )
            )
    for m in (3, 9):  # two issuer-level filings a year
        session.add(
            FundamentalFact(
                issuer_id=iss.issuer_id,
                taxonomy="FIXTURE",
                concept="X",
                period_end=date(2024, m - 1, 28),
                value=1.0,
                unit="EUR",
                available_at=datetime(2024, m, 1, 8, tzinfo=UTC),
                source_document=f"fixture-{m}",
            )
        )
    session.add(
        SectorClassification(
            security_id=sec.security_id,
            scheme="FIXTURE",
            sector="X",
            valid_from=date(2000, 1, 1),
            available_at=datetime(2000, 1, 1, tzinfo=UTC),
        )
    )
    session.flush()
    return sec.security_id


def _source(session: Session) -> None:
    from pitquant.db.models import DataSource

    if session.get(DataSource, 1) is None:
        session.add(DataSource(source_id=1, name="FIXTURE_PRICES", provider_type="market_data"))
        session.flush()


def test_identity_gap_dominates(session: Session) -> None:
    _source(session)
    sid = _security(session, isin=False, prices=True)
    cov = security_coverage(session, sid, START, END)
    assert cov.status is CoverageStatus.UNRESOLVED_IDENTITY
    assert support_decision(cov).status is SupportStatus.NOT_SUPPORTED


def test_complete_dimensions_and_missing_ca_source(session: Session) -> None:
    _source(session)
    sid = _security(session, isin=True, prices=True)
    cov = security_coverage(session, sid, START, END)
    st = {d.name: d.status for d in cov.dimensions}
    assert st["identity"] is CoverageStatus.COMPLETE
    assert st["prices"] is CoverageStatus.COMPLETE
    assert st["fundamentals"] is CoverageStatus.COMPLETE  # issuer-level facts count
    assert st["corporate_actions"] is CoverageStatus.INSUFFICIENT  # no accepted source yet
    assert support_decision(cov).status is SupportStatus.NOT_SUPPORTED
    # an accepted source WITHOUT an ingestion trace is not coverage
    no_trace = security_coverage(session, sid, START, END, accepted_ca_sources=["EODHD:div"])
    ca = {d.name: d for d in no_trace.dimensions}["corporate_actions"]
    assert ca.status is CoverageStatus.INSUFFICIENT and "NOT_ATTEMPTED" in ca.detail
    assert support_decision(no_trace).status is SupportStatus.NOT_SUPPORTED
    _trace(session, sid, "COMPLETED", START, END, 0)
    ok = security_coverage(session, sid, START, END, accepted_ca_sources=["EODHD:div"])
    ca = {d.name: d for d in ok.dimensions}["corporate_actions"]
    assert ca.status is CoverageStatus.COMPLETE and "provider-reported events: 0" in ca.detail
    assert support_decision(ok).status is SupportStatus.SUPPORTED_SECURITY


def _trace(session: Session, sid: str, status: str, a: date, b: date, n: int) -> None:
    from pitquant.db.models import CorporateActionIngestion

    session.add(
        CorporateActionIngestion(
            security_id=sid,
            provider="EODHD:div",
            period_start=a,
            period_end=b,
            status=status,
            events_found=n,
        )
    )
    session.flush()


def test_corporate_action_states_are_distinguished(session: Session) -> None:
    from pitquant.coverage import CaCoverageState, corporate_action_state

    _source(session)
    sid = _security(session, isin=True, prices=True)
    acc = ["EODHD:div"]

    def state() -> CaCoverageState:
        return corporate_action_state(session, sid, START, END, acc)[0]

    assert corporate_action_state(session, sid, START, END, [])[0] is (
        CaCoverageState.PROVIDER_UNAVAILABLE
    )
    assert state() is CaCoverageState.NOT_ATTEMPTED
    _trace(session, sid, "FAILED", START, END, 0)
    assert state() is CaCoverageState.ATTEMPTED_FAILED  # an attempt proves nothing
    _trace(session, sid, "COMPLETED", START, date(2024, 6, 30), 2)
    assert state() is CaCoverageState.PARTIAL_PERIOD
    _trace(session, sid, "COMPLETED", date(2024, 7, 1), END, 0)
    assert state() is CaCoverageState.VERIFIED_COVERAGE


def test_support_does_not_depend_on_index_membership(session: Session) -> None:
    """SUPPORTED_SECURITY != INDEX_MEMBERSHIP: a security that never was in any index is
    supported when its data is; the decision has no index input at all."""
    _source(session)
    sid = _security(session, isin=True, prices=True)
    from pitquant.db.models import IndexMembership

    assert session.query(IndexMembership).filter_by(security_id=sid).count() == 0
    from pitquant.db.models import CorporateActionIngestion

    session.add(
        CorporateActionIngestion(
            security_id=sid,
            provider="X",
            period_start=START,
            period_end=END,
            status="COMPLETED",
            events_found=0,
        )
    )
    session.flush()
    cov = security_coverage(session, sid, START, END, accepted_ca_sources=["X"])
    assert support_decision(cov).status is SupportStatus.SUPPORTED_SECURITY


def test_price_gaps_are_partial_or_insufficient(session: Session) -> None:
    _source(session)
    sid = _security(session, isin=True, prices=False)
    cov = security_coverage(session, sid, START, END)
    assert {d.name: d.status for d in cov.dimensions}["prices"] is CoverageStatus.INSUFFICIENT
