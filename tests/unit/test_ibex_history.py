"""IBEX 35 from BME event streams (D-03).

FIXTURE DATA: tickers GAS/NTGY and REE/RED are used because the requirement names them,
but every DATE below is illustrative and has NOT been verified against BME documents.
"""

from __future__ import annotations

import io
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.config.settings import Settings
from pitquant.data.archive import ArchiveStore, sha256_hex
from pitquant.db.models import IndexEvent, IndexMembership, TickerHistory
from pitquant.jobs.index_ingest import ingest_event_source
from pitquant.security_master.service import SecurityMaster
from pitquant.universe.events import BuildReport, UnresolvedSourceEventError
from pitquant.universe.index_membership import IdentityUnresolvedError, IndexUniverse
from pitquant.universe.sources.bme import (
    BMEAviso,
    BMEHistoryRow,
    BMELayoutCalibration,
    RowStyle,
    classify_rows,
    events_from_rows,
    extract_rows_from_pdf,
)

pytestmark = pytest.mark.pit

BASE = tuple(["GAS", "REE"] + [f"T{i:02d}" for i in range(1, 34)])  # 35 founding codes
D_INIT = date(1991, 1, 14)
D_ORD = date(2012, 6, 18)
D_EXTRA = date(2016, 3, 21)
D_REE = date(2017, 7, 3)
D_GAS = date(2018, 6, 29)
D_ANN = datetime(2020, 6, 4, 17, 0, tzinfo=UTC)
D_EFF = date(2020, 6, 22)


def rows() -> list[BMEHistoryRow]:
    return [
        BMEHistoryRow(D_INIT, BASE, (), RowStyle.UNKNOWN, "p1:r1"),
        BMEHistoryRow(D_ORD, ("N01",), ("T01",), RowStyle.ORDINARY, "p2:r1"),
        BMEHistoryRow(D_EXTRA, ("N02",), ("T02",), RowStyle.UNKNOWN, "p2:r2"),
        BMEHistoryRow(D_REE, ("RED",), ("REE",), RowStyle.TICKER_CHANGE, "p3:r1"),  # visual marker
        BMEHistoryRow(D_GAS, ("NTGY",), ("GAS",), RowStyle.UNKNOWN, "p3:r2"),  # marker unreadable
        BMEHistoryRow(D_EFF, ("N03",), ("T03",), RowStyle.ORDINARY, "p4:r1"),
    ]


def avisos() -> list[BMEAviso]:
    return [
        BMEAviso(
            "AV-EXTRA",
            datetime(2016, 3, 10, 18, 0, tzinfo=UTC),
            D_EXTRA,
            RowStyle.EXTRAORDINARY,
            additions=("N02",),
            deletions=("T02",),
        ),
        BMEAviso(
            "AV-GAS",
            datetime(2018, 6, 27, 18, 0, tzinfo=UTC),
            D_GAS,
            RowStyle.TICKER_CHANGE,
            ticker_changes=(("GAS", "NTGY"),),
        ),
        BMEAviso("AV-ORD", D_ANN, D_EFF, RowStyle.ORDINARY, additions=("N03",), deletions=("T03",)),
    ]


@pytest.fixture
def ibex(session: Session, settings: Settings) -> BuildReport:
    src = events_from_rows(rows(), avisos(), raw_source_hash="fixture-bme-1")
    return ingest_event_source(
        session,
        src,
        exchange="XMAD",
        currency="EUR",
        country="ES",
        expected_size=settings.universe("IBEX35").expected_size,
    )


def _sid(session: Session, ticker: str, on: date) -> str:
    return SecurityMaster(session).resolve(ticker, "XMAD", on)


def test_ibex_membership_reconstruction_from_events(session: Session, ibex: BuildReport) -> None:
    u = IndexUniverse(session)
    assert ibex.status == "ok"
    for d in (D_INIT, D_ORD, D_EXTRA, D_REE, D_GAS, D_EFF, date(2024, 1, 2)):
        assert len(u.universe_ids("IBEX35", d)) == 35
    t01 = _sid(session, "T01", date(2010, 1, 4))
    assert t01 in u.universe_ids("IBEX35", date(2012, 6, 15))
    assert t01 not in u.universe_ids("IBEX35", D_ORD)  # effective date is exclusive for exits
    assert _sid(session, "N01", D_ORD) in u.universe_ids("IBEX35", D_ORD)
    assert u.universe_ids("IBEX35", date(1990, 12, 31)) == []


def test_ibex_ticker_change_preserves_security_id(session: Session, ibex: BuildReport) -> None:
    before = _sid(session, "REE", date(2017, 6, 30))
    after = _sid(session, "RED", D_REE)
    assert before == after
    hist = session.scalars(
        select(TickerHistory)
        .where(TickerHistory.security_id == before)
        .order_by(TickerHistory.valid_from)
    ).all()
    assert [(h.ticker, h.valid_to) for h in hist] == [("REE", D_REE), ("RED", None)]


def _intervals(session: Session, security_id: str) -> list[IndexMembership]:
    return list(
        session.scalars(
            select(IndexMembership).where(
                IndexMembership.security_id == security_id, IndexMembership.index_code == "IBEX35"
            )
        )
    )


def test_ree_to_red_not_membership_turnover(session: Session, ibex: BuildReport) -> None:
    sid = _sid(session, "RED", date(2020, 1, 2))
    ivs = _intervals(session, sid)
    assert len(ivs) == 1 and ivs[0].effective_from == D_INIT and ivs[0].effective_to is None
    ev = session.scalars(
        select(IndexEvent).where(
            IndexEvent.security_id == sid, IndexEvent.event_type == "TICKER_CHANGE"
        )
    ).one()
    assert (ev.ticker, ev.new_ticker, ev.effective_date) == ("REE", "RED", D_REE)
    assert (
        session.scalars(
            select(IndexEvent).where(
                IndexEvent.ticker.in_(["REE", "RED"]),
                IndexEvent.event_type.in_(["INDEX_ADD", "INDEX_DELETE"]),
            )
        ).all()
        == []
    )


def test_gas_to_ntgy_not_membership_turnover(session: Session, ibex: BuildReport) -> None:
    """Visual marker unreadable -> resolved by the BME aviso, not guessed."""
    old, new = _sid(session, "GAS", date(2018, 6, 28)), _sid(session, "NTGY", D_GAS)
    assert old == new
    assert len(_intervals(session, new)) == 1
    ev = session.scalars(
        select(IndexEvent).where(
            IndexEvent.event_type == "TICKER_CHANGE", IndexEvent.new_ticker == "NTGY"
        )
    ).one()
    assert ev.announced_at is not None  # provenance from the aviso


def test_unknown_marker_without_aviso_is_not_guessed() -> None:
    bad = [*rows()[:2], BMEHistoryRow(D_GAS, ("NTGY",), ("GAS",), RowStyle.UNKNOWN, "p3:r2")]
    with pytest.raises(UnresolvedSourceEventError):
        classify_rows(bad, avisos=[])


def test_marker_contradicting_aviso_fails() -> None:
    bad = [rows()[0], BMEHistoryRow(D_GAS, ("NTGY",), ("GAS",), RowStyle.ORDINARY, "p3:r2")]
    with pytest.raises(UnresolvedSourceEventError):
        classify_rows(bad, avisos())


def test_ibex_extraordinary_review(session: Session, ibex: BuildReport) -> None:
    parent = session.scalars(
        select(IndexEvent).where(IndexEvent.event_type == "EXTRAORDINARY_REVIEW")
    ).one()
    children = session.scalars(
        select(IndexEvent).where(IndexEvent.parent_event_id == parent.event_id)
    ).all()
    assert {(c.event_type, c.ticker) for c in children} == {
        ("INDEX_DELETE", "T02"),
        ("INDEX_ADD", "N02"),
    }
    assert parent.effective_date == D_EXTRA and parent.reason == "AV-EXTRA"
    assert session.scalars(
        select(IndexEvent).where(
            IndexEvent.event_type == "ORDINARY_REVIEW", IndexEvent.effective_date == D_ORD
        )
    ).one()


def test_announcement_date_not_effective_date(session: Session, ibex: BuildReport) -> None:
    u = IndexUniverse(session)
    n03 = _sid(session, "N03", D_EFF)
    t03 = _sid(session, "T03", date(2020, 6, 1))
    # Announced on 4 June, effective 22 June: membership changes ONLY on the effective date.
    assert n03 not in u.universe_ids("IBEX35", date(2020, 6, 19))
    assert t03 in u.universe_ids("IBEX35", date(2020, 6, 19))
    assert n03 in u.universe_ids("IBEX35", D_EFF)
    known = u.announced_changes("IBEX35", datetime(2020, 6, 10, 12, tzinfo=UTC))
    assert {(c.event_type, c.ticker) for c in known} == {
        ("ORDINARY_REVIEW", None),
        ("INDEX_ADD", "N03"),
        ("INDEX_DELETE", "T03"),
    }
    assert u.announced_changes("IBEX35", datetime(2020, 6, 3, 12, tzinfo=UTC)) == []
    ev = session.scalars(select(IndexEvent).where(IndexEvent.ticker == "N03")).one()
    assert ev.announced_at is not None and ev.announced_at.date() != ev.effective_date


def test_size_validation_rejects_wrong_count(session: Session) -> None:
    from pitquant.universe.events import MembershipSequenceError

    short = [BMEHistoryRow(D_INIT, BASE[:30], (), RowStyle.UNKNOWN, "p1:r1")]
    src = events_from_rows(short, [], raw_source_hash="fixture-short")
    with pytest.raises(MembershipSequenceError):
        ingest_event_source(
            session, src, exchange="XMAD", currency="EUR", country="ES", expected_size=(34, 36)
        )


def test_reingestion_is_idempotent(session: Session, settings: Settings, ibex: BuildReport) -> None:
    src = events_from_rows(rows(), avisos(), raw_source_hash="fixture-bme-1")
    again = ingest_event_source(
        session,
        src,
        exchange="XMAD",
        currency="EUR",
        country="ES",
        expected_size=settings.universe("IBEX35").expected_size,
    )
    assert again.build_id == ibex.build_id


# ── PDF extraction mechanics (synthetic PDF generated here, NOT the BME document) ──


def _make_pdf() -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(60, 780, "Fecha")
    c.drawString(160, 780, "Altas")
    c.drawString(300, 780, "Bajas")
    c.drawString(60, 750, "18/06/2012")
    c.drawString(160, 750, "N01")
    c.drawString(300, 750, "T01")
    c.setFillColorRGB(0, 0, 1)  # blue = code change (calibrated below)
    c.drawString(60, 730, "03/07/2017")
    c.drawString(160, 730, "RED")
    c.drawString(300, 730, "REE")
    c.save()
    return buf.getvalue()


def test_pdf_rows_and_calibrated_markers() -> None:
    pdf = _make_pdf()
    cal = BMELayoutCalibration(
        style_by_color={(0.0, 0.0, 1.0): RowStyle.TICKER_CHANGE},
        calibrated_for_sha256=sha256_hex(pdf),
    )
    out = extract_rows_from_pdf(pdf, cal)
    assert [(r.effective_date, r.additions, r.deletions, r.style) for r in out] == [
        (date(2012, 6, 18), ("N01",), ("T01",), RowStyle.ORDINARY),
        (date(2017, 7, 3), ("RED",), ("REE",), RowStyle.TICKER_CHANGE),
    ]


def test_uncalibrated_or_foreign_calibration_yields_unknown(tmp_path: object) -> None:
    pdf = _make_pdf()
    for cal in (
        BMELayoutCalibration(),
        BMELayoutCalibration(
            style_by_color={(0.0, 0.0, 1.0): RowStyle.TICKER_CHANGE},
            calibrated_for_sha256="another-document-version",
        ),
    ):
        assert {r.style for r in extract_rows_from_pdf(pdf, cal)} == {RowStyle.UNKNOWN}


def test_archive_store_verifies_hashes(tmp_path: object) -> None:
    from pathlib import Path

    from pitquant.core.errors import DataQualityError

    store = ArchiveStore(Path(str(tmp_path)))
    sha, path = store.put(b"aviso")
    assert store.get(sha) == b"aviso"
    path.write_bytes(b"tampered")
    with pytest.raises(DataQualityError):
        store.get(sha)


# ── identity vs membership (fail closed) ─────────────────────────────────────


def test_membership_without_isin_is_identity_unresolved(
    session: Session, ibex: BuildReport
) -> None:
    u = IndexUniverse(session)
    members = u.universe("IBEX35", D_ORD)
    assert len(members) == 35
    assert {m.identity_status for m in members} == {"IDENTITY_UNRESOLVED"}
    assert ibex.status == "ok" and not ibex.eligible_for_final_model_validation
    with pytest.raises(IdentityUnresolvedError):
        u.backtest_universe("IBEX35", D_ORD)


def _isins(on: date, codes: tuple[str, ...]) -> dict[tuple[str, date], str]:
    return {(c, on): f"ES0FIX{i:06d}" for i, c in enumerate(codes)}


def test_official_isins_resolve_identity(session: Session, settings: Settings) -> None:
    ids = _isins(D_INIT, BASE) | {("N01", D_ORD): "ES0FIXN00001", ("N03", D_EFF): "ES0FIXN00003"}
    avs = avisos()
    avs[0] = BMEAviso(
        "AV-EXTRA",
        datetime(2016, 3, 10, 18, 0, tzinfo=UTC),
        D_EXTRA,
        RowStyle.EXTRAORDINARY,
        additions=("N02",),
        deletions=("T02",),
        identifiers={"N02": "ES0FIXN00002"},
    )
    src = events_from_rows(rows(), avs, raw_source_hash="fixture-bme-isin", identities=ids)
    rep = ingest_event_source(
        session,
        src,
        exchange="XMAD",
        currency="EUR",
        country="ES",
        expected_size=settings.universe("IBEX35").expected_size,
    )
    assert rep.n_identity_unresolved == 0 and rep.eligible_for_final_model_validation
    u = IndexUniverse(session)
    assert len(u.backtest_universe("IBEX35", D_EFF)) == 35  # ticker changes keep identity


REENTRY = (
    BMEHistoryRow(D_INIT, BASE, (), RowStyle.UNKNOWN, "p1:r1"),
    BMEHistoryRow(D_ORD, ("N01",), ("T05",), RowStyle.ORDINARY, "p2:r1"),
    BMEHistoryRow(D_EFF, ("T05",), ("N01",), RowStyle.ORDINARY, "p4:r1"),
)


def test_reentry_without_isin_is_a_new_unresolved_identity(
    session: Session, settings: Settings
) -> None:
    src = events_from_rows(REENTRY, (), raw_source_hash="fixture-bme-reentry")
    assert any("re-entry without ISIN" in w for w in src.warnings)
    ingest_event_source(
        session,
        src,
        exchange="XMAD",
        currency="EUR",
        country="ES",
        expected_size=settings.universe("IBEX35").expected_size,
    )
    first = _sid(session, "T05", D_INIT)
    again = _sid(session, "T05", D_EFF)
    assert first != again  # same ticker is NOT assumed to be the same security
    u = IndexUniverse(session)
    assert first in u.universe_ids("IBEX35", D_INIT)
    assert first not in u.universe_ids("IBEX35", D_EFF)
    assert again in u.universe_ids("IBEX35", D_EFF)


def test_reentry_with_same_isin_is_the_same_security(session: Session, settings: Settings) -> None:
    ids = _isins(D_INIT, BASE) | {("N01", D_ORD): "ES0FIXN00001"}
    ids[("T05", D_EFF)] = ids[("T05", D_INIT)]
    src = events_from_rows(REENTRY, (), raw_source_hash="fixture-bme-reentry-isin", identities=ids)
    assert not any("re-entry" in w for w in src.warnings)
    rep = ingest_event_source(
        session,
        src,
        exchange="XMAD",
        currency="EUR",
        country="ES",
        expected_size=settings.universe("IBEX35").expected_size,
    )
    assert rep.n_identity_unresolved == 0
    assert _sid(session, "T05", D_INIT) == _sid(session, "T05", D_EFF)


def test_every_event_and_interval_without_isin_is_unresolved(
    session: Session, ibex: BuildReport
) -> None:
    keyed = session.scalars(select(IndexEvent).where(IndexEvent.security_id.is_not(None))).all()
    assert {e.event_type for e in keyed} >= {"INDEX_DELETE", "TICKER_CHANGE", "INDEX_ADD"}
    assert {e.identity_status for e in keyed} == {"IDENTITY_UNRESOLVED"}
    ivs = session.scalars(select(IndexMembership)).all()
    assert {i.identity_status for i in ivs} == {"IDENTITY_UNRESOLVED"}
