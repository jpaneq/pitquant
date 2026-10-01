"""Audit: why a value was known at T, and why others were not. FIXTURE data (CIK 0000999999)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from pitquant.audit.explain import explain_fact
from pitquant.config.settings import Settings
from pitquant.core.timeutils import utc_now
from pitquant.data.providers.sec_edgar.provider import ingest_sec_company
from pitquant.db.models import FundamentalFact, RawSourceArchive, SecFiling
from tests.conftest import ny
from tests.fixtures.sec_edgar import CIK, A, B, D, FakeSEC, X
from tests.unit.test_sec_edgar import _ingest, _provider, _security

pytestmark = pytest.mark.pit

FY23_END = date(2023, 12, 31)


def test_known_value_carries_full_provenance(
    session: Session, tmp_path: Path, settings: Settings
) -> None:
    sid, _ = _ingest(session, tmp_path, settings)
    ex = explain_fact(session, sid, "Revenues", FY23_END, ny(2024, 12, 31, 16))
    k = ex.known
    assert k is not None and k.value == 100.0 and k.accession_number == A
    assert ex.ticker_at_as_of == "FIXC" and ex.security_id == sid
    filing = session.get_one(SecFiling, A)
    assert k.accepted_at == ny(2024, 2, 20, 16, 15, 2)  # header
    assert k.effective_available_at == ny(2024, 2, 21, 9, 30)  # policy, never the same field
    assert k.accepted_at != k.effective_available_at
    assert k.availability_policy == "conservative_session"
    assert k.header_sha256 == session.get_one(RawSourceArchive, filing.header_archive_id).sha256
    assert k.xbrl_sha256 is not None and k.parser_version == "sec-edgar-1"
    assert k.source_document is not None and k.source_document.endswith(".htm")
    assert (k.taxonomy, k.unit, k.period_start) == ("us-gaap", "USD", date(2023, 1, 1))
    # Why NOT the restated 95 (D) — it was published later.
    reasons = {n.reason: n for n in ex.not_known}
    assert reasons["available_after_as_of"].provenance.accession_number == D  # type: ignore[union-attr]
    # Why NOT 101 — companyfacts cited an accession with no verified filing.
    rejected = [n for n in ex.not_known if n.reason.startswith("rejected:fact_without_filing")]
    assert len(rejected) == 1 and rejected[0].issue["accession"] == X  # type: ignore[index]
    text = ex.to_text()
    assert "KNOWN: 100.0 USD" in text and "available_after_as_of" in text


def test_restatement_supersedes_without_rewriting(
    session: Session, tmp_path: Path, settings: Settings
) -> None:
    sid, _ = _ingest(session, tmp_path, settings)
    ex = explain_fact(session, sid, "Revenues", FY23_END, ny(2025, 3, 3, 16))
    assert ex.known is not None and (ex.known.value, ex.known.accession_number) == (95.0, D)
    sup = [n for n in ex.not_known if n.reason.startswith("superseded_by:")]
    assert len(sup) == 1 and sup[0].provenance.accession_number == A  # type: ignore[union-attr]
    # The past is untouched: at the earlier instant the original is still the answer.
    assert (
        explain_fact(session, sid, "Revenues", FY23_END, ny(2024, 12, 31, 16)).known.value == 100.0
    )  # type: ignore[union-attr]


def test_rejected_value_explained_by_quality_issue(
    session: Session, tmp_path: Path, settings: Settings
) -> None:
    sid, _ = _ingest(session, tmp_path, settings)
    ex = explain_fact(session, sid, "NetIncomeLoss", date(2024, 3, 31), ny(2024, 12, 31, 16))
    assert ex.known is None
    (n,) = ex.not_known
    assert n.reason.startswith("rejected:companyfacts_xbrl_mismatch:")
    assert n.issue is not None and n.issue["accession"] == B
    assert (n.issue["companyfacts_value"], n.issue["instance_value"]) == (5.0, 6.0)
    assert "KNOWN: nothing" in ex.to_text()


def test_pinned_data_version_explains_later_ingestion(
    session: Session, tmp_path: Path, settings: Settings
) -> None:
    sid = _security(session)
    ingest_sec_company(session, _provider(tmp_path, settings, FakeSEC(visible={A})), CIK, sid)
    cutoff = utc_now()
    ingest_sec_company(session, _provider(tmp_path, settings, FakeSEC()), CIK, sid)
    ex = explain_fact(
        session, sid, "Revenues", FY23_END, ny(2025, 3, 3, 16), ingested_before=cutoff
    )
    assert ex.known is not None and ex.known.accession_number == A
    assert {n.reason for n in ex.not_known} == {"ingested_after_data_version"}


def test_ambiguous_period_requires_disambiguation(
    session: Session, tmp_path: Path, settings: Settings
) -> None:
    sid, _ = _ingest(session, tmp_path, settings)
    # A second duration ending on the same date (a Q4 fact next to the FY fact).
    session.add(
        FundamentalFact(
            security_id=sid,
            taxonomy="us-gaap",
            concept="Revenues",
            period_start=date(2023, 10, 1),
            period_end=FY23_END,
            value=30.0,
            unit="USD",
            available_at=ny(2024, 2, 21, 9, 30),
        )
    )
    session.flush()
    with pytest.raises(ValueError, match="ambiguous"):
        explain_fact(session, sid, "Revenues", FY23_END, ny(2024, 12, 31, 16))
    ex = explain_fact(
        session, sid, "Revenues", FY23_END, ny(2024, 12, 31, 16), period_start=date(2023, 1, 1)
    )
    assert ex.known is not None and ex.known.value == 100.0
