"""D-01: SEC EDGAR point-in-time fundamentals. All data are FIXTURES (fictional CIK)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pitquant.config.settings import Settings
from pitquant.core.errors import ImmutableRecordError, ProviderContractError
from pitquant.data.archive import ArchiveStore
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.data.point_in_time.availability import filing_available_at
from pitquant.data.point_in_time.engine import facts_as_of, latest_for_period
from pitquant.data.providers.sec_edgar.client import SECClient
from pitquant.data.providers.sec_edgar.parsers import parse_acceptance_datetime
from pitquant.data.providers.sec_edgar.provider import (
    SECEdgarFundamentalProvider,
    SecIngestReport,
    ingest_sec_company,
)
from pitquant.db.models import (
    DataQualityIssue,
    FundamentalFact,
    RawSourceArchive,
    SecFiling,
)
from pitquant.security_master.service import SecurityMaster
from tests.conftest import ny, utc
from tests.fixtures.sec_edgar import CIK, A, B, C, D, FakeSEC, P, X

pytestmark = pytest.mark.pit
UA = "PITQuant tests fixture@example.invalid"


def _provider(tmp_path: Path, settings: Settings, fake: FakeSEC) -> SECEdgarFundamentalProvider:
    client = SECClient(fake, UA, max_requests_per_second=1000, sleep=lambda _s: None)
    return SECEdgarFundamentalProvider(client, ArchiveStore(tmp_path), settings.fundamentals.sec)


def _security(session: Session) -> str:
    sm = SecurityMaster(session)
    sec = sm.register(name="FIXTURE CORP", exchange="XNYS", currency="USD")
    sm.add_ticker(sec.security_id, "FIXC", "XNYS", date(2005, 1, 3))
    sm.add_identifier(sec.security_id, "CIK", CIK.zfill(10), date(2005, 1, 3))
    return sec.security_id


def _ingest(
    session: Session,
    tmp_path: Path,
    settings: Settings,
    visible: set[str] | None = None,
    sid: str | None = None,
) -> tuple[str, SecIngestReport]:
    sid = sid or _security(session)
    fake = FakeSEC(visible=visible) if visible is not None else FakeSEC()
    rep = ingest_sec_company(session, _provider(tmp_path, settings, fake), CIK, sid)
    return sid, rep


def _rev(session: Session, sid: str, as_of, start: date, end: date):  # type: ignore[no-untyped-def]
    facts = facts_as_of(session, sid, as_of, ["Revenues"])
    hits = [f for k, f in facts.items() if k.period_start == start and k.period_end == end]
    return hits[0] if hits else None


FY23 = (date(2023, 1, 1), date(2023, 12, 31))
Q1_24 = (date(2024, 1, 1), date(2024, 3, 31))


def test_later_restatement_does_not_rewrite_history(
    session: Session, tmp_path: Path, settings: Settings
) -> None:
    sid, _ = _ingest(session, tmp_path, settings, visible={A, B, C})
    snap_2024 = _rev(session, sid, ny(2024, 6, 28, 16), *FY23)
    assert snap_2024 is not None and snap_2024.value == 100.0 and snap_2024.accession_number == A
    # A year later the FY2024 10-K presents FY2023 restated to 95 ...
    _ingest(session, tmp_path, settings, sid=sid)
    again_2024 = _rev(session, sid, ny(2024, 6, 28, 16), *FY23)
    assert again_2024 is not None
    assert (again_2024.fact_id, again_2024.value) == (snap_2024.fact_id, 100.0)  # history intact
    now_2025 = _rev(session, sid, ny(2025, 3, 3, 16), *FY23)
    assert now_2025 is not None and now_2025.value == 95.0 and now_2025.accession_number == D
    # ... and the original version is retained, never updated.
    versions = session.scalars(
        select(FundamentalFact).where(
            FundamentalFact.concept == "Revenues",
            FundamentalFact.period_end == FY23[1],
            FundamentalFact.period_start == FY23[0],
        )
    ).all()
    assert sorted(v.value for v in versions) == [95.0, 100.0]
    versions[0].value = 1.0
    with pytest.raises(ImmutableRecordError):
        session.flush()


def test_companyfacts_later_fact_not_visible_early(
    session: Session, tmp_path: Path, settings: Settings
) -> None:
    sid, _ = _ingest(session, tmp_path, settings)
    # companyfacts (downloaded in 2026) already contains Q1-2024; it must stay invisible
    # until filing B's acceptance (10:15 ET) + 15 min lag.
    assert _rev(session, sid, ny(2024, 4, 30, 16), *Q1_24) is None
    assert _rev(session, sid, ny(2024, 5, 1, 10, 29), *Q1_24) is None
    hit = _rev(session, sid, ny(2024, 5, 1, 10, 30), *Q1_24)
    assert hit is not None and hit.value == 30.0


def test_fact_bound_to_accession(session: Session, tmp_path: Path, settings: Settings) -> None:
    sid, rep = _ingest(session, tmp_path, settings)
    facts = session.scalars(select(FundamentalFact).where(FundamentalFact.security_id == sid)).all()
    assert facts
    for f in facts:
        filing = session.get_one(SecFiling, f.accession_number)
        assert (f.cik, f.form, f.filed_date, f.accepted_at, f.is_amendment) == (
            filing.cik,
            filing.form,
            filing.filed_date,
            filing.accepted_at,
            filing.is_amendment,
        )
        assert f.taxonomy == "us-gaap" and f.unit == "USD" and f.source_document
        assert f.available_at == filing.available_at >= filing.accepted_at
        hdr = session.get_one(RawSourceArchive, filing.header_archive_id)
        assert hdr.published_at == filing.accepted_at and hdr.source_identifier.endswith(
            ".hdr.sgml"
        )
    assert X not in {f.accession_number for f in facts}  # orphan accession rejected
    issues = {i.check_name for i in session.scalars(select(DataQualityIssue))}
    assert "fact_without_filing" in issues
    assert rep.facts_rejected >= 1


def test_amended_filing_visibility(session: Session, tmp_path: Path, settings: Settings) -> None:
    sid, _ = _ingest(session, tmp_path, settings)
    before = _rev(session, sid, ny(2024, 6, 7, 16), *Q1_24)
    after = _rev(session, sid, ny(2024, 6, 10, 16), *Q1_24)
    assert before is not None and (before.value, before.form) == (30.0, "10-Q")
    assert after is not None and (after.value, after.form, after.is_amendment) == (
        28.0,
        "10-Q/A",
        True,
    )
    assert _rev(session, sid, ny(2024, 6, 10, 11, 59), *Q1_24).value == 30.0  # type: ignore[union-attr]


def test_acceptance_datetime_controls_availability(
    session: Session, tmp_path: Path, settings: Settings
) -> None:
    sid, _ = _ingest(session, tmp_path, settings)
    a = session.get_one(SecFiling, A)
    assert a.filed_date == date(2024, 2, 20)
    assert a.accepted_at == ny(2024, 2, 20, 16, 15, 2)
    # Accepted after the close: NOT usable at that day's close, usable from next open.
    assert a.available_at == ny(2024, 2, 21, 9, 30)
    assert _rev(session, sid, ny(2024, 2, 20, 16, 0), *FY23) is None
    assert _rev(session, sid, ny(2024, 2, 20, 23, 59), *FY23) is None
    assert _rev(session, sid, ny(2024, 2, 21, 9, 30), *FY23) is not None
    # Pre-market acceptance (D, 07:00 ET) is usable the same morning.
    assert session.get_one(SecFiling, D).available_at == ny(2025, 2, 18, 7, 15)
    # Intraday filing whose lag crosses the close also rolls to the next open.
    cal = get_calendar("XNYS")
    assert filing_available_at(cal, ny(2024, 5, 1, 15, 50), "conservative_session", 15) == ny(
        2024, 5, 2, 9, 30
    )
    assert filing_available_at(cal, ny(2024, 5, 1, 15, 50), "accepted_plus_lag", 15) == ny(
        2024, 5, 1, 16, 5
    )
    # Saturday acceptance -> Monday open
    assert filing_available_at(cal, ny(2024, 5, 4, 12), "conservative_session", 15) == ny(
        2024, 5, 6, 9, 30
    )


def test_same_period_multiple_filings(session: Session, tmp_path: Path, settings: Settings) -> None:
    sid, _ = _ingest(session, tmp_path, settings)
    q1 = session.scalars(
        select(FundamentalFact).where(
            FundamentalFact.concept == "Revenues",
            FundamentalFact.period_start == Q1_24[0],
            FundamentalFact.period_end == Q1_24[1],
        )
    ).all()
    assert {(f.accession_number, f.value) for f in q1} == {(B, 30.0), (C, 28.0)}
    fy = session.scalars(
        select(FundamentalFact).where(
            FundamentalFact.concept == "Revenues",
            FundamentalFact.period_start == FY23[0],
            FundamentalFact.period_end == FY23[1],
        )
    ).all()
    assert {(f.accession_number, f.value) for f in fy} == {(A, 100.0), (D, 95.0)}
    # One version visible per as_of, always from the latest filing available then.
    assert (
        latest_for_period(
            facts_as_of(session, sid, ny(2024, 12, 31, 16), ["Revenues"]), "Revenues", FY23[1]
        ).accession_number
        == A
    )  # type: ignore[union-attr]


def test_xbrl_instance_validates_companyfacts(
    session: Session, tmp_path: Path, settings: Settings
) -> None:
    _sid, _rep = _ingest(session, tmp_path, settings)
    ni = session.scalars(
        select(FundamentalFact).where(FundamentalFact.concept == "NetIncomeLoss")
    ).all()
    assert ni == []  # companyfacts said 5, the filing's own XBRL says 6 -> rejected
    assert (
        session.scalars(
            select(DataQualityIssue).where(
                DataQualityIssue.check_name == "companyfacts_xbrl_mismatch"
            )
        ).first()
        is not None
    )
    assert (
        session.scalars(
            select(DataQualityIssue).where(DataQualityIssue.check_name == "acceptance_mismatch")
        ).first()
        is not None
    )  # D cross-check


def test_coverage_starts_in_xbrl_era(session: Session, tmp_path: Path, settings: Settings) -> None:
    sid, rep = _ingest(session, tmp_path, settings)
    assert session.get(SecFiling, P) is None
    assert rep.facts_out_of_coverage >= 1
    assert facts_as_of(session, sid, ny(2011, 1, 3, 16)) == {}


def test_sec_ingestion_is_idempotent(session: Session, tmp_path: Path, settings: Settings) -> None:
    sid, first = _ingest(session, tmp_path, settings)
    _, second = _ingest(session, tmp_path, settings, sid=sid)
    assert first.facts_inserted > 0 and second.facts_inserted == 0
    assert second.filings_inserted == 0
    n = session.scalar(select(func.count()).select_from(FundamentalFact))
    assert n == first.facts_inserted


def test_header_acceptance_is_eastern_time_with_dst() -> None:
    summer = b"<ACCEPTANCE-DATETIME>20240701161500"
    winter = b"<ACCEPTANCE-DATETIME>20240115161500"
    assert parse_acceptance_datetime(summer) == utc(2024, 7, 1, 20, 15)
    assert parse_acceptance_datetime(winter) == utc(2024, 1, 15, 21, 15)


def test_client_requires_contact_and_retries(tmp_path: Path) -> None:
    with pytest.raises(ProviderContractError):
        SECClient(FakeSEC(), "anonymous-bot")
    fake = FakeSEC()
    url = f"https://data.sec.gov/submissions/CIK{int(CIK):010d}.json"
    fake.fail_once.add(url)
    sleeps: list[float] = []
    client = SECClient(fake, UA, max_requests_per_second=1000, sleep=sleeps.append)
    assert client.get(url).status == 200
    assert client.requests_made == 2 and any(s >= 1.0 for s in sleeps)
    assert all(h["User-Agent"] == UA for _, h in fake.calls)
