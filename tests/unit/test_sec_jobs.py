"""SEC jobs on FIXTURES: CIK-driven ingestion and query-based stress-case selection."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from pitquant.cli import main
from pitquant.config.settings import Settings
from pitquant.core.errors import ProviderContractError, UnknownSecurityError
from pitquant.jobs.sec_ingest import ingest_ciks, scan_stress_cases
from pitquant.security_master.service import SecurityMaster
from tests.fixtures.sec_edgar import CIK, A, B, C, D, E, FakeSEC
from tests.unit.test_sec_edgar import _provider

pytestmark = pytest.mark.pit


def test_stress_scan_classifies_by_metadata(
    session: Session, tmp_path: Path, settings: Settings
) -> None:
    prov = _provider(tmp_path, settings, FakeSEC())
    scan = scan_stress_cases(CIK, prov.submissions(session, CIK), settings.fundamentals.sec.forms)
    t = scan.by_tag
    assert A in t["10-K"] and B in t["10-Q"] and C in t["amendment"]
    assert A in t["after_close"] and B in t["intraday"] and C in t["intraday"]
    assert E in t["after_close"] and E in t["filing_date_after_acceptance_day"]
    assert set(t["same_period_multiple_filings"]) >= {B, C}
    # D's submissions field says 09:00 (Z-suffixed); as an ET hint that is pre-market.
    assert D in t["pre_market"]
    assert "friday_after_close" in scan.missing


def test_ingest_ciks_requires_known_security_unless_registering(
    session: Session, tmp_path: Path, settings: Settings
) -> None:
    prov = _provider(tmp_path, settings, FakeSEC())
    with pytest.raises(UnknownSecurityError):
        ingest_ciks(session, prov, settings, [CIK])
    (rep,) = ingest_ciks(session, prov, settings, [CIK], register_missing=True)
    assert rep.facts_inserted > 0
    sid = SecurityMaster(session).resolve_identifier(
        "CIK", CIK.zfill(10), settings.fundamentals.sec.coverage_start
    )
    # No ticker invented from today's submissions document.
    assert (
        SecurityMaster(session).ticker_as_of(sid, settings.fundamentals.sec.coverage_start) is None
    )


def test_cli_refuses_sec_without_contact_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    from pitquant.config import settings as settings_mod

    monkeypatch.delenv("PITQUANT_SEC_USER_AGENT", raising=False)
    settings_mod.get_settings.cache_clear()
    try:
        with pytest.raises(ProviderContractError, match="User-Agent"):
            main(["sec-stress-scan", "320193"])
    finally:
        settings_mod.get_settings.cache_clear()
