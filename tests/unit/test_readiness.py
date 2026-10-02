"""data-readiness: statuses are computed from DB state and fixtures never count.

Rows created here with a non-fixture CIK/hash exist only to exercise the status logic in a
throwaway test database; they are not real data.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from pitquant.cli import main
from pitquant.config.settings import Settings
from pitquant.data.archive import ArchiveStore, archive_document
from pitquant.db.models import DataSource, FundamentalFact, RawSourceArchive, SecFiling
from pitquant.readiness import Check, Status, data_readiness
from pitquant.security_master.service import SecurityMaster
from pitquant.universe.index_membership import IndexUniverse
from pitquant.universe.sources.spdji import (
    SPDJIAnnouncementReconstructionProvider,
    SPDJILicensedFileProvider,
)
from tests.conftest import ny
from tests.unit.test_ibex_history import avisos, rows
from tests.unit.test_sec_edgar import _ingest
from tests.unit.test_sp500_history import ANNOUNCEMENTS, LICENSED, SNAPSHOT
from tests.unit.test_sp500_history import _ingest as _ingest_sp

pytestmark = pytest.mark.pit


def _by_name(rep, name):  # type: ignore[no-untyped-def]
    return next(c for c in rep.components if c.name == name)


def test_empty_database_is_blocked(session: Session, settings: Settings) -> None:
    rep = data_readiness(session, settings)
    assert rep.overall is Status.BLOCKED
    assert rep.feature_engine_ready is False  # derived: only a global READY opens it
    assert rep.as_dict()["feature_engine_ready"] is False
    # every DATA component is blocked; only code components (total-return engine) are not
    assert {c.status for c in rep.components if c.critical} == {Status.BLOCKED}
    assert "invariant scans ran over zero real rows (vacuous PASS)" in rep.blockers


def test_fixtures_never_count(session: Session, tmp_path: Path, settings: Settings) -> None:
    from pitquant.jobs.index_ingest import ingest_event_source
    from pitquant.universe.sources.bme import events_from_rows

    _ingest(session, tmp_path, settings)  # SEC fixture issuer, CIK 0000999999
    src = events_from_rows(rows(), avisos(), raw_source_hash="fixture-bme-1")
    ingest_event_source(
        session, src, exchange="XMAD", currency="EUR", country="ES", expected_size=(34, 36)
    )
    rep = data_readiness(session, settings)
    assert _by_name(rep, "SEC fundamentals").status is Status.BLOCKED
    assert _by_name(rep, "IBEX membership").status is Status.BLOCKED
    assert rep.excluded_fixture_rows["fixture_sec_filings"] >= 4
    assert rep.excluded_fixture_rows["fixture_or_synthetic_builds"] == 1
    assert rep.overall is not Status.READY


def test_provisional_sp500_is_never_ready(
    session: Session, tmp_path: Path, settings: Settings
) -> None:
    p = SPDJIAnnouncementReconstructionProvider(
        date(2015, 1, 2), SNAPSHOT, ANNOUNCEMENTS, date(2010, 1, 4), ArchiveStore(tmp_path)
    )
    _ingest_sp(session, p.load(session))
    rep = data_readiness(session, settings)
    sp = _by_name(rep, "S&P membership")
    assert sp.status is Status.PROVISIONAL
    assert "SP500:SPDJI_ANNOUNCEMENT_RECONSTRUCTION" in rep.provisional_sources
    assert rep.identity_coverage_pct is not None and rep.identity_coverage_pct < 100
    assert rep.overall is not Status.READY


def _real_like_sec(session: Session, tmp_path: Path, security_id: str, cik: str) -> SecFiling:
    store = ArchiveStore(tmp_path)
    hdr = archive_document(
        session,
        store,
        provider="SEC_EDGAR",
        source_identifier=f"hdr:{cik}",
        data=f"<ACCEPTANCE-DATETIME>20240220161502 {cik}".encode(),
        mime_type="text/plain",
    )
    src = session.query(DataSource).filter_by(name="SEC_EDGAR").first()
    if src is None:
        src = DataSource(name="SEC_EDGAR", provider_type="fundamentals", is_point_in_time=True)
        session.add(src)
        session.flush()
    acc = f"{cik}-24-000001"
    f = SecFiling(
        accession_number=acc,
        cik=cik,
        security_id=security_id,
        form="10-K",
        is_amendment=False,
        filed_date=date(2024, 2, 20),
        accepted_at=ny(2024, 2, 20, 16, 15, 2),
        available_at=ny(2024, 2, 21, 9, 30),
        availability_policy="conservative_session",
        header_archive_id=hdr.archive_id,
    )
    session.add(f)
    session.flush()
    session.add(
        FundamentalFact(
            security_id=security_id,
            taxonomy="us-gaap",
            concept="Revenues",
            period_start=date(2023, 1, 1),
            period_end=date(2023, 12, 31),
            value=1.0,
            unit="USD",
            available_at=f.available_at,
            accepted_at=f.accepted_at,
            cik=cik,
            accession_number=acc,
            source_id=src.source_id,
        )
    )
    session.flush()
    return f


def test_partial_coverage_and_scans(session: Session, tmp_path: Path, settings: Settings) -> None:
    lic = SPDJILicensedFileProvider(LICENSED, "licensed://test", ArchiveStore(tmp_path))
    _ingest_sp(session, lic.load(session))
    members = IndexUniverse(session).universe_ids("SP500", date(2011, 1, 3))
    _real_like_sec(session, tmp_path, members[0], "0000000001")
    rep = data_readiness(session, settings)
    assert _by_name(rep, "S&P membership").status is Status.READY
    sec = _by_name(rep, "SEC fundamentals")
    assert sec.status is Status.PARTIAL and sec.securities == 1
    assert any("of universe members have facts" in g for g in sec.gaps)
    assert {s.result for s in rep.scans} == {Check.PASS}
    assert rep.overall is Status.PARTIAL
    # Official filings are a definitive source even while coverage is partial.
    assert "SEC_EDGAR" in rep.definitive_sources
    assert "SEC_EDGAR" not in rep.provisional_sources


def test_scans_detect_pit_and_provenance_violations(
    session: Session, tmp_path: Path, settings: Settings
) -> None:
    sid = SecurityMaster(session).register(name="X", exchange="XNYS", currency="USD").security_id
    f = _real_like_sec(session, tmp_path, sid, "0000000002")
    # A fact whose availability does not come from its filing.
    session.add(
        FundamentalFact(
            security_id=sid,
            taxonomy="us-gaap",
            concept="Assets",
            period_end=date(2023, 12, 31),
            value=1.0,
            unit="USD",
            available_at=ny(2024, 2, 20, 16, 30),
            accepted_at=f.accepted_at,
            cik="0000000002",
            accession_number=f.accession_number,
        )
    )
    session.flush()
    Path(session.get_one(RawSourceArchive, f.header_archive_id).storage_uri).write_bytes(b"x")
    rep = data_readiness(session, settings)
    pit, prov = rep.scans
    assert pit.result is Check.FAIL and any("differ from filing" in v for v in pit.violations)
    assert prov.result is Check.FAIL and any("SHA-256 mismatch" in v for v in prov.violations)
    assert "PIT validation: FAIL" in rep.blockers and "Raw provenance: FAIL" in rep.blockers


def test_cli_exit_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:  # type: ignore[no-untyped-def]
    from pitquant.config import settings as settings_mod
    from pitquant.db.session import create_all, make_engine

    url = f"sqlite:///{tmp_path / 'r.db'}"
    create_all(make_engine(url))
    monkeypatch.setenv("PITQUANT_DATABASE_URL", url)
    settings_mod.get_settings.cache_clear()
    try:
        assert main(["data-readiness"]) == 1
        assert "PITQuant data readiness: BLOCKED" in capsys.readouterr().out
        assert main(["data-readiness", "--json"]) == 1
        assert '"overall": "BLOCKED"' in capsys.readouterr().out
    finally:
        settings_mod.get_settings.cache_clear()


def test_v2_maturity_and_source_labels(
    session: Session, tmp_path: Path, settings: Settings
) -> None:
    lic = SPDJILicensedFileProvider(LICENSED, "licensed://test-v2", ArchiveStore(tmp_path))
    _ingest_sp(session, lic.load(session))
    rep = data_readiness(session, settings)
    sp = _by_name(rep, "S&P membership")
    assert sp.source_status == "SOURCE_CANONICAL"
    assert {"CODE_READY", "CONTRACT_TESTED", "REAL_DATA_TESTED"} <= set(sp.maturity)
    assert sp.active is not None and sp.unresolved_identities == 0
    us = _by_name(rep, "US real market data")
    assert "BLOCKED" in us.maturity and "REAL_DATA_TESTED" not in us.maturity
    ad = _by_name(rep, "US market adapter")  # a finished adapter never makes the SOURCE ready
    assert {"CODE_READY", "CONTRACT_TESTED"} <= set(ad.maturity) and not ad.critical
