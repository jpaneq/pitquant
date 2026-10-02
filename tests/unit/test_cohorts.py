"""Cohort readiness (identity QA over rebalance dates). FIXTURE index; no returns computed."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy.orm import Session

from pitquant.cohorts import cohort_readiness
from pitquant.config.settings import Settings
from pitquant.core.hashing import content_hash
from pitquant.db.models import RawSourceArchive, SecurityIdentitySnapshot
from pitquant.jobs.index_ingest import ingest_event_source
from pitquant.security_master.identity import IdentityResolutionEngine
from pitquant.security_master.identity_store import load_snapshot_index, run_identity_resolution
from pitquant.universe.events import EventSource, SourceConfidence
from pitquant.universe.sources.bme import BMEHistoryRow, RowStyle, classify_rows

pytestmark = pytest.mark.pit
ISIN = {"AAA": "ES0000000011", "BBB": "ES0000000029"}


def _setup(session: Session, with_bbb: bool) -> str:
    rows = [BMEHistoryRow(date(2011, 1, 3), ("AAA", "BBB"), (), RowStyle.UNKNOWN, "r1")]
    res = classify_rows(rows, (), "FIX_IDX")
    src = EventSource("FIXTURE_BME", SourceConfidence.SYNTHETIC, res.events, f"fixture-{with_bbb}")
    bid = ingest_event_source(
        session, src, exchange="XMAD", currency="EUR", country="ES", expected_size=(2, 2)
    ).build_id
    arch = RawSourceArchive(
        provider="F",
        source_identifier="f",
        retrieved_at=datetime.now(UTC),
        sha256="0" * 64,
        mime_type="application/zip",
        size_bytes=0,
        storage_uri="-",
    )
    session.add(arch)
    session.flush()
    for y in range(2010, 2014):
        for m in (6, 12):
            d = date(y, m, 30 if m == 6 else 31)
            for c in ("AAA", "BBB") if with_bbb else ("AAA",):
                session.add(
                    SecurityIdentitySnapshot(
                        source="CNMV_ANCV",
                        reference_date=d,
                        scope="ACTIVE_IN_ANCV",
                        isin=ISIN[c],
                        issuer_legal_name=f"FIXTURE {c}",
                        instrument_name=f"{c}/AC 1,00",
                        instrument_class="RV",
                        member_name="f",
                        source_hash="0" * 64,
                        archive_id=arch.archive_id,
                        parser_version="fixture",
                    )
                )
    session.flush()
    eng = IdentityResolutionEngine(load_snapshot_index(session), horizon=date(2013, 12, 31))
    run_identity_resolution(
        session,
        index_code="FIX_IDX",
        build_id=bid,
        engine=eng,
        canonical_start=date(2011, 1, 1),
        inputs_hash=content_hash(["c", with_bbb]),
    )
    return bid


def test_identity_cohort_is_not_a_full_cohort_without_prices(
    session: Session, settings: Settings
) -> None:
    bid = _setup(session, with_bbb=True)
    rows, s = cohort_readiness(
        session, settings, "FIX_IDX", start=date(2011, 1, 1), end=date(2012, 12, 31), build_id=bid
    )
    assert all(r.identity_eligible for r in rows) and s.identity_eligible_dates == len(rows)
    assert s.first_identity_cohort == date(2011, 1, 3)
    assert s.first_complete_identity_year == 2011 and len(s.first_12_identity_cohorts) == 12
    # no prices / fundamentals / corporate-action trace: never a canonical cohort
    assert s.eligible_dates == 0 and s.first_canonical_cohort is None
    assert any("PRICES" in x for x in rows[0].blocking_reasons)
    assert any("CORPORATE_ACTIONS" in x for x in rows[0].blocking_reasons)


def test_one_unproven_member_blocks_every_date_and_is_named(
    session: Session, settings: Settings
) -> None:
    bid = _setup(session, with_bbb=False)  # BBB never listed by ANCV
    rows, s = cohort_readiness(
        session, settings, "FIX_IDX", start=date(2011, 1, 1), end=date(2011, 6, 30), build_id=bid
    )
    assert not any(r.identity_eligible for r in rows)
    assert s.first_identity_cohort is None and s.blockers.get("BBB") == len(rows)
    assert any(x.startswith("IDENTITY:BBB") for x in rows[0].blocking_reasons)


def test_dates_in_the_sealed_holdout_are_never_research_cohorts(
    session: Session, settings: Settings
) -> None:
    bid = _setup(session, with_bbb=True)
    ho = settings.validation.final_holdout
    rows, s = cohort_readiness(
        session,
        settings,
        "FIX_IDX",
        start=ho.start,
        end=date(2022, 12, 31),
        build_id=bid,
        check_layers=False,
    )
    assert rows and all(r.in_holdout and not r.eligible for r in rows)
    assert s.research_identity_dates == 0
    assert any("HOLDOUT_SEALED" in x for x in rows[0].blocking_reasons)
