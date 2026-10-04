# ruff: noqa: E501
"""SEC fundamentals for the routine universe (SYNTHETIC identities, canned SEC responses: no network)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from pitquant.analyzer.service import AnalyzerService, clear_cache
from pitquant.config.settings import Settings
from pitquant.data.archive import ArchiveStore
from pitquant.db.models import Issuer, Security
from pitquant.jobs import sec_universe as su
from pitquant.security_master.service import SecurityMaster
from tests.unit.test_feature_engine_v0 import SESSIONS, add_fact, closes_path, load_bars


def test_sic_codes_map_to_a_division_and_to_special_profiles() -> None:
    assert (
        su.division("3571") == "Manufacturing"
        and su.division("7389") == "Services"
        and su.division(None) is None
        and su.division("abc") is None
    )
    assert (
        su.profile_type("2834") == "STANDARD_CORPORATE"
        and su.profile_type("6022") == "BANK"
        and su.profile_type("6311") == "INSURER"
        and su.profile_type("6798") == "REIT"
        and su.profile_type(None) == "STANDARD_CORPORATE"
    )


def test_the_sec_ticker_map_comes_from_the_official_file_and_is_archived(
    session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = json.dumps(
        {
            "0": {"cik_str": 200406, "ticker": "JNJ", "title": "JOHNSON & JOHNSON"},
            "1": {"cik_str": 80424, "ticker": "pg", "title": "PROCTER & GAMBLE"},
        }
    ).encode()
    seen = []
    monkeypatch.setattr(su, "_get", lambda url, ua: (seen.append((url, ua)), body)[1])
    m = su.ticker_map(session, ArchiveStore(tmp_path), "Test User test@example.com")
    assert m == {"JNJ": "0000200406", "PG": "0000080424"} and seen == [
        (su.TICKERS_URL, "Test User test@example.com")
    ]  # CIKs zero-padded to 10, tickers upper-cased


def test_without_a_contact_user_agent_nothing_is_requested(
    session: Session, settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PITQUANT_SEC_USER_AGENT", raising=False)
    called = []
    monkeypatch.setattr(su, "_get", lambda *a: called.append(a))
    with pytest.raises(RuntimeError, match="SOURCE_NOT_CONFIGURED"):
        su.ingest_fundamentals(session, settings, object(), ArchiveStore(tmp_path), ["JNJ"])  # type: ignore[arg-type]
    assert called == []


def test_a_priced_security_is_linked_to_the_sec_issuer_without_mixing_identities(
    session: Session,
) -> None:
    sm = SecurityMaster(session)
    anchor = sm.register(name="CIK 0000000001 (SEC EDGAR)", exchange="XNYS", currency="USD")
    issuer = Issuer(name="SYN ISSUER", country="US")
    session.add(issuer)
    session.flush()
    anchor.issuer_id = issuer.issuer_id
    priced = sm.register(name="SYN (price tracking)", exchange="XNYS", currency="USD")
    other = sm.register(name="OTHER", exchange="XNYS", currency="USD")
    other_issuer = Issuer(name="OTHER ISSUER", country="US")
    session.add(other_issuer)
    session.flush()
    other.issuer_id = other_issuer.issuer_id
    assert (
        su.link_price_security(session, priced.security_id, anchor.security_id) == "LINKED"
        and session.get_one(Security, priced.security_id).issuer_id == issuer.issuer_id
    )
    assert (
        su.link_price_security(session, priced.security_id, anchor.security_id) == "ALREADY_LINKED"
    )
    assert (
        su.link_price_security(session, other.security_id, anchor.security_id)
        == "CONFLICT_DIFFERENT_ISSUER"
        and other.issuer_id == other_issuer.issuer_id
    )  # never overwritten
    assert (
        su.link_price_security(session, anchor.security_id, anchor.security_id) == "SAME_SECURITY"
        and su.link_price_security(session, None, anchor.security_id) == "NO_PRICE_SECURITY"
    )


def test_an_issuer_with_almost_no_history_degrades_instead_of_crashing(
    session: Session, settings: Settings
) -> None:
    """Regression: a registrant with only cover-page facts (e.g. a holding company that just re-registered) made the Analyzer raise ``Invalid isoformat string: 'None'``."""
    clear_cache()
    sm = SecurityMaster(session)
    sec = sm.register(name="SYN NEW REGISTRANT", exchange="XNYS", currency="USD")
    sm.add_ticker(sec.security_id, "SYNR", "XNYS", date(2010, 1, 4))
    load_bars(session, sec.security_id, "R", closes_path(SESSIONS, 100.0, 0.0006))
    add_fact(
        session,
        sec.security_id,
        "EntityCommonStockSharesOutstanding",
        None,
        date(2016, 2, 10),
        100.0,
        datetime(2016, 2, 20, tzinfo=UTC),
        unit="shares",
    )
    session.commit()
    f = AnalyzerService(session, settings).fundamentals(
        sec.security_id, datetime(2016, 12, 31, 23, tzinfo=UTC)
    )
    assert f["latest_period"] is None and f["status"] in ("OK", "NO_DATA", "INSUFFICIENT")
