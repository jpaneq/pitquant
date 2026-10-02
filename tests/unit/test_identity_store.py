"""Identity resolution persisted over a real membership build (ADR-0020). FIXTURE index
(codes AAA..DDD, invented ISINs with valid check digits) — not historical data."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.core.hashing import content_hash
from pitquant.db.models import IdentifierHistory, RawSourceArchive, SecurityIdentitySnapshot
from pitquant.jobs.index_ingest import ingest_event_source
from pitquant.security_master.identity import IdentityResolutionEngine
from pitquant.security_master.identity_store import load_snapshot_index, run_identity_resolution
from pitquant.universe.events import EventSource, SourceConfidence
from pitquant.universe.index_membership import (
    ArchivalPeriodError,
    IdentityUnresolvedError,
    IndexUniverse,
)
from pitquant.universe.sources.bme import BMEHistoryRow, RowStyle, classify_rows

pytestmark = pytest.mark.pit
ISIN = {"AAA": "ES0000000011", "BBB": "ES0000000029", "CCC": "ES0000000037", "DDD": "ES0000000045"}


def _build(session: Session) -> str:
    rows = [
        BMEHistoryRow(date(2010, 1, 4), ("AAA", "BBB", "CCC"), (), RowStyle.UNKNOWN, "r1"),
        BMEHistoryRow(date(2013, 12, 23), ("DDD",), ("AAA",), RowStyle.ORDINARY, "r2"),
        BMEHistoryRow(date(2015, 6, 22), ("AAA",), ("DDD",), RowStyle.ORDINARY, "r3"),  # re-entry
    ]
    res = classify_rows(rows, (), "FIX_IDX")
    src = EventSource("FIXTURE_BME", SourceConfidence.SYNTHETIC, res.events, "fixture-identity-1")
    rep = ingest_event_source(
        session, src, exchange="XMAD", currency="EUR", country="ES", expected_size=(3, 3)
    )
    return rep.build_id


def _snapshots(session: Session, codes_by_date: dict[date, list[str]]) -> None:
    arch = RawSourceArchive(
        provider="FIXTURE_ANCV",
        source_identifier="fixture",
        retrieved_at=datetime.now(UTC),
        sha256="0" * 64,
        mime_type="application/zip",
        size_bytes=0,
        storage_uri="-",
    )
    session.add(arch)
    session.flush()
    for d, codes in codes_by_date.items():
        for c in codes:
            session.add(
                SecurityIdentitySnapshot(
                    source="CNMV_ANCV",
                    reference_date=d,
                    scope="ACTIVE_IN_ANCV",
                    isin=ISIN[c],
                    issuer_legal_name=f"FIXTURE {c} SA",
                    instrument_name=f"{c}/AC 1,00",
                    instrument_class="RV",
                    member_name="fixture",
                    source_hash="0" * 64,
                    archive_id=arch.archive_id,
                    parser_version="fixture",
                )
            )
    session.flush()


def test_reentry_maps_back_to_one_security_and_backtest_uses_it(session: Session) -> None:
    bid = _build(session)
    halfyears = [date(y, m, 30 if m == 6 else 31) for y in range(2009, 2017) for m in (6, 12)]
    _snapshots(session, {d: ["AAA", "BBB", "CCC", "DDD"] for d in halfyears})
    eng = IdentityResolutionEngine(load_snapshot_index(session), horizon=date(2016, 12, 31))
    res = run_identity_resolution(
        session,
        index_code="FIX_IDX",
        build_id=bid,
        engine=eng,
        canonical_start=date(2011, 1, 1),
        inputs_hash=content_hash(["fixture"]),
    )
    owners = set(
        session.scalars(
            select(IdentifierHistory.security_id).where(IdentifierHistory.value == ISIN["AAA"])
        )
    )
    assert len(owners) == 1  # the re-entry is NOT a second security for the same ISIN
    u = IndexUniverse(session)
    before = {m.isin for m in u.backtest_universe("FIX_IDX", date(2012, 3, 1), bid)}
    after = u.backtest_universe("FIX_IDX", date(2016, 3, 1), bid)
    assert before == {ISIN["AAA"], ISIN["BBB"], ISIN["CCC"]}
    aaa_after = next(m for m in after if m.isin == ISIN["AAA"])
    assert aaa_after.security_id == owners.pop()
    assert res.metrics["intervals_total"] == 5
    with pytest.raises(ArchivalPeriodError):
        u.backtest_universe("FIX_IDX", date(2010, 3, 1), bid, canonical_start=date(2011, 1, 1))
    again = run_identity_resolution(  # same inputs: the run is reused, not duplicated
        session,
        index_code="FIX_IDX",
        build_id=bid,
        engine=eng,
        canonical_start=date(2011, 1, 1),
        inputs_hash=content_hash(["fixture"]),
    )
    assert again.run.run_id == res.run.run_id


def test_one_unproven_member_blocks_the_date(session: Session) -> None:
    bid = _build(session)
    halfyears = [date(y, m, 30 if m == 6 else 31) for y in range(2009, 2017) for m in (6, 12)]
    _snapshots(session, {d: ["AAA", "BBB", "DDD"] for d in halfyears})  # CCC never in ANCV
    eng = IdentityResolutionEngine(load_snapshot_index(session), horizon=date(2016, 12, 31))
    run_identity_resolution(
        session,
        index_code="FIX_IDX",
        build_id=bid,
        engine=eng,
        canonical_start=date(2011, 1, 1),
        inputs_hash=content_hash(["fixture-2"]),
    )
    with pytest.raises(IdentityUnresolvedError, match="without a proven identity"):
        IndexUniverse(session).backtest_universe("FIX_IDX", date(2012, 3, 1), bid)


def test_reusing_a_run_whose_stored_output_differs_fails_loudly(session: Session) -> None:
    """Same version + same inputs but different engine output (logic changed without bumping
    ENGINE_VERSION) must not silently report numbers the stored segments do not support."""
    bid = _build(session)
    halfyears = [date(y, m, 30 if m == 6 else 31) for y in range(2009, 2017) for m in (6, 12)]
    _snapshots(session, {d: ["AAA", "BBB", "CCC", "DDD"] for d in halfyears})
    ix = load_snapshot_index(session)
    kw = {
        "index_code": "FIX_IDX",
        "build_id": bid,
        "canonical_start": date(2011, 1, 1),
        "inputs_hash": content_hash(["same-inputs"]),
    }
    run_identity_resolution(
        session, engine=IdentityResolutionEngine(ix, horizon=date(2016, 12, 31)), **kw
    )
    with pytest.raises(ValueError, match="bump ENGINE_VERSION"):
        run_identity_resolution(
            session, engine=IdentityResolutionEngine(ix, horizon=date(2014, 6, 30)), **kw
        )
