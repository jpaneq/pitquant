"""SEC jobs on FIXTURES: CIK-driven ingestion and query-based stress-case selection."""

from __future__ import annotations

import math
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from pitquant.cli import main
from pitquant.config.settings import Settings
from pitquant.core.errors import ProviderContractError, UnknownSecurityError
from pitquant.jobs.sec_ingest import ingest_ciks, scan_stress_cases
from pitquant.security_master.service import SecurityMaster
from tests.fixtures.sec_edgar import CIK, A, B, C, D, E, FakeSEC, P
from tests.unit.test_sec_edgar import _provider

pytestmark = pytest.mark.pit


def test_stress_scan_classifies_by_metadata(
    session: Session, tmp_path: Path, settings: Settings
) -> None:
    prov = _provider(tmp_path, settings, FakeSEC())
    cfg = settings.fundamentals.sec
    scan = scan_stress_cases(CIK, prov.submissions(session, CIK), cfg.forms, cfg.coverage_start)
    t = scan.by_tag
    assert A in t["10-K"] and B in t["10-Q"] and C in t["amendment"]
    assert A in t["after_close"] and B in t["intraday"] and C in t["intraday"]
    assert E in t["after_close"] and E in t["filing_date_after_acceptance_day"]
    assert set(t["same_period_multiple_filings"]) >= {B, C}
    # D's submissions field says 09:00Z = 04:00 ET: pre-market as a hint.
    assert D in t["pre_market"]
    assert "friday_after_close" in scan.missing
    # P (2010) is before the XBRL-era coverage start: out of scope, like ingestion.
    assert not any(P in accs for accs in t.values())


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


def test_scan_after_ingestion_uses_header_acceptance(
    session: Session, tmp_path: Path, settings: Settings
) -> None:
    from pitquant.jobs.sec_ingest import scan_ingested

    prov = _provider(tmp_path, settings, FakeSEC())
    ingest_ciks(session, prov, settings, [CIK], register_missing=True)
    t = scan_ingested(session, CIK).by_tag
    assert D in t["pre_market"]  # header 07:00 ET, whatever submissions said
    assert A in t["after_close"] and E in t["filing_date_after_acceptance_day"]


def test_xbrl_duplicates_at_different_precision() -> None:
    from pitquant.data.providers.sec_edgar.parsers import parse_xbrl_instance

    def inst(*facts: tuple[str, str]) -> bytes:
        body = "".join(
            f'<us-gaap:CommercialPaper contextRef="c" unitRef="u" decimals="{d}">{v}'
            "</us-gaap:CommercialPaper>"
            for v, d in facts
        )
        return (
            '<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" '
            'xmlns:us-gaap="http://fasb.org/us-gaap/2023"><xbrli:unit id="u"><xbrli:measure>'
            'iso4217:USD</xbrli:measure></xbrli:unit><xbrli:context id="c"><xbrli:period>'
            "<xbrli:instant>2023-09-30</xbrli:instant></xbrli:period></xbrli:context>"
            + body
            + "</xbrli:xbrl>"
        ).encode()

    key = ("us-gaap", "CommercialPaper", None, date(2023, 9, 30), "USD")
    # Shape of MSFT 10-Q 0000950170-23-054855: same fact at -6 and -8.
    for order in (
        (("25808000000", "-6"), ("25800000000", "-8")),
        (("25800000000", "-8"), ("25808000000", "-6")),
    ):
        assert parse_xbrl_instance(inst(*order))[key] == 25808000000.0
    bad = parse_xbrl_instance(inst(("25808000000", "-6"), ("26000000000", "-8")))
    assert math.isnan(bad[key])
