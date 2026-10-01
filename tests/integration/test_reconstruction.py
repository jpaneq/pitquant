"""Completion criterion for D-01..D-03: auditable, reproducible reconstruction at T.

FIXTURE DATA ONLY (fictional issuer and index rows).
"""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from pitquant.audit.reconstruction import current_data_version, reconstruct
from pitquant.config.settings import Settings
from pitquant.data.archive import ArchiveStore
from pitquant.data.providers.sec_edgar.provider import ingest_sec_company
from pitquant.jobs.index_ingest import ingest_event_source
from pitquant.security_master.service import SecurityMaster
from pitquant.universe.sources.spdji import SPDJILicensedFileProvider
from tests.conftest import ny
from tests.fixtures.sec_edgar import CIK, A, B, C, FakeSEC
from tests.unit.test_sec_edgar import UA

pytestmark = pytest.mark.pit

HISTORY_V1 = b"""event_id,effective_date,announced_at,action,ticker,new_ticker,identifier,reason
I1,2020-01-02,,INITIAL,FIXC,,CIK:0000999999,
I2,2020-01-02,,INITIAL,AAA,,FIX:0001,
I3,2020-01-02,,INITIAL,BBB,,FIX:0002,
E1,2024-09-23,2024-09-06T21:15:00+00:00,DELETE,BBB,,FIX:0002,acquired
E2,2024-09-23,2024-09-06T21:15:00+00:00,ADD,DDD,,FIX:0004,replaces BBB
"""
# The provider later CORRECTS the effective date of E1/E2 (a new source version).
HISTORY_V2 = HISTORY_V1.replace(b"2024-09-23", b"2024-09-30")

T = ny(2024, 6, 28, 16, 0)


def _sec(tmp_path: Path, settings: Settings, visible: set[str]):  # type: ignore[no-untyped-def]
    from pitquant.data.providers.sec_edgar.client import SECClient
    from pitquant.data.providers.sec_edgar.provider import SECEdgarFundamentalProvider

    return SECEdgarFundamentalProvider(
        SECClient(
            FakeSEC(visible=visible), UA, max_requests_per_second=1000, sleep=lambda _s: None
        ),
        ArchiveStore(tmp_path),
        settings.fundamentals.sec,
    )


def _load_history(session: Session, tmp_path: Path, data: bytes, ident: str) -> None:
    src = SPDJILicensedFileProvider(data, ident, ArchiveStore(tmp_path)).load(session)
    ingest_event_source(
        session, src, exchange="XNYS", currency="USD", country="US", expected_size=(3, 3)
    )


def test_reconstruction_at_T_is_auditable_and_immune_to_later_data(
    session: Session, tmp_path: Path, settings: Settings
) -> None:
    _load_history(session, tmp_path, HISTORY_V1, "licensed://spdji/v1")
    fixc = SecurityMaster(session).resolve("FIXC", "XNYS", date(2024, 1, 2))
    ingest_sec_company(session, _sec(tmp_path, settings, {A, B, C}), CIK, fixc)
    session.flush()
    time.sleep(0.01)
    v1 = current_data_version(session, ["SP500"])

    r1 = reconstruct(session, T, "SP500", "XNYS", v1, ["Revenues"])
    # (1) universe and (2) tickers at T
    assert sorted(m["ticker_at_T"] for m in r1["members"]) == ["AAA", "BBB", "FIXC"]
    # (3)-(5) fundamentals published at T, with filing provenance and availability
    rows = r1["fundamentals"][fixc]
    fy23 = next(
        r
        for r in rows
        if r["period_end"] == date(2023, 12, 31) and r["period_start"] == date(2023, 1, 1)
    )
    assert (fy23["value"], fy23["accession_number"], fy23["form"]) == (100.0, A, "10-K")
    assert fy23["accepted_at"] <= fy23["available_at"] <= T
    assert all(r["available_at"] <= T for r in rows)
    assert all(m["entry_event"]["source_event_id"] for m in r1["members"])
    assert r1["membership_build"]["confidence"] == "CANONICAL"

    # (7) repeating the reconstruction gives exactly the same result
    assert (
        reconstruct(session, T, "SP500", "XNYS", v1, ["Revenues"])["report_hash"]
        == r1["report_hash"]
    )

    # Later world: FY2024 10-K restating FY2023, and a provider correction of the index file.
    time.sleep(0.01)
    ingest_sec_company(
        session, _sec(tmp_path, settings, {A, B, C, "0000999999-25-000010"}), CIK, fixc
    )
    _load_history(session, tmp_path, HISTORY_V2, "licensed://spdji/v2")

    # (6) the pinned reconstruction of T is unchanged
    again = reconstruct(session, T, "SP500", "XNYS", v1, ["Revenues"])
    assert again == r1

    # With today's data the restatement is still invisible at T (published 2025); the
    # corrected build is used, but membership at T is the same because the fix is in Sep-24.
    v2 = current_data_version(session, ["SP500"])
    assert v2.membership_builds["SP500"] != v1.membership_builds["SP500"]
    now = reconstruct(session, T, "SP500", "XNYS", v2, ["Revenues"])

    def ids(r):  # type: ignore[no-untyped-def]
        return [(m["security_id"], m["ticker_at_T"]) for m in r["members"]]

    assert ids(now) == ids(r1)  # same securities/tickers; entry events come from the new build
    assert now["fundamentals"] == r1["fundamentals"]
    assert now["report_hash"] != r1["report_hash"]  # different data_version is recorded


def test_full_audit_chain_security_to_snapshot_to_explain(
    session: Session, tmp_path: Path, settings: Settings
) -> None:
    """security → ticker at T → filing → raw source → fact → available_at → PITContext →
    frozen snapshot → reconstruction → explain, all agreeing on the same version."""
    from pitquant.audit.explain import explain_fact
    from pitquant.data.point_in_time.context import PITContext
    from pitquant.data.point_in_time.engine import latest_for_period
    from pitquant.db.models import RawSourceArchive, SecFiling
    from pitquant.features.snapshot import FeatureValue, SnapshotBuilder
    from tests.fixtures.sec_edgar import D

    _load_history(session, tmp_path, HISTORY_V1, "licensed://spdji/chain")
    fixc = SecurityMaster(session).resolve("FIXC", "XNYS", date(2024, 1, 2))
    ingest_sec_company(session, _sec(tmp_path, settings, {A, B, C}), CIK, fixc)
    session.flush()
    time.sleep(0.01)
    v1 = current_data_version(session, ["SP500"])

    ctx = PITContext(session, T, ingested_before=v1.ingested_before)
    fact = latest_for_period(ctx.facts(fixc, ["Revenues"]), "Revenues", date(2023, 12, 31))
    assert fact is not None and fact.accession_number == A
    builder = SnapshotBuilder(fixc, T, "fv-test", "dv-test", "code-test")
    builder.add(FeatureValue("revenue_fy", fact.value, fact.available_at, fact.fact_id))
    snap = builder.freeze()

    ex = explain_fact(
        session, fixc, "Revenues", date(2023, 12, 31), T, ingested_before=v1.ingested_before
    )
    assert ex.known is not None and ex.known.fact_id == fact.fact_id
    assert snap.availability["revenue_fy"]["source_ref"] == ex.known.fact_id
    assert ex.ticker_at_as_of == "FIXC"
    filing = session.get_one(SecFiling, A)
    assert (
        ex.known.header_sha256 == session.get_one(RawSourceArchive, filing.header_archive_id).sha256
    )

    rec = reconstruct(session, T, "SP500", "XNYS", v1, ["Revenues"])
    row = next(
        r
        for r in rec["fundamentals"][fixc]
        if r["period_end"] == date(2023, 12, 31) and r["period_start"] == date(2023, 1, 1)
    )
    assert (row["fact_id"], row["accession_number"], row["available_at"]) == (
        ex.known.fact_id,
        ex.known.accession_number,
        ex.known.effective_available_at,
    )

    # A later restatement (D) changes neither the snapshot built at T nor the explanation.
    ingest_sec_company(session, _sec(tmp_path, settings, {A, B, C, D}), CIK, fixc)
    rebuilt = SnapshotBuilder(fixc, T, "fv-test", "dv-test", "code-test")
    again = latest_for_period(
        PITContext(session, T, ingested_before=v1.ingested_before).facts(fixc, ["Revenues"]),
        "Revenues",
        date(2023, 12, 31),
    )
    assert again is not None and again.fact_id == fact.fact_id
    rebuilt.add(FeatureValue("revenue_fy", again.value, again.available_at, again.fact_id))
    assert rebuilt.freeze().content_hash == snap.content_hash
