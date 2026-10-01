"""Calibrated extraction of the REAL BME «Composición histórica – IBEX 35» (Sep-2026).

The PDF is not committed (official third-party document): it is read from the local raw
archive by its SHA-256 and the test is skipped when absent.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from pitquant.data.archive import sha256_hex
from pitquant.universe.sources.bme import (
    COMPOIBEX_2026_09,
    COMPOIBEX_2026_09_SHA256,
    BMELayoutCalibration,
    RowStyle,
    extract_rows_from_pdf,
)

SHA = COMPOIBEX_2026_09_SHA256
PDF = Path("data/archive") / SHA[:2] / SHA[2:4] / SHA
pytestmark = [
    pytest.mark.realdata,
    pytest.mark.skipif(not PDF.exists(), reason="BME PDF not in the local archive"),
]


@pytest.fixture(scope="module")
def rows():  # type: ignore[no-untyped-def]
    data = PDF.read_bytes()
    assert sha256_hex(data) == SHA
    return extract_rows_from_pdf(data, COMPOIBEX_2026_09)


def test_every_review_row_extracted(rows) -> None:  # type: ignore[no-untyped-def]
    assert sorted(r.review_number for r in rows) == list(range(1, 138))
    adds = sum(len(r.additions) + len(r.ticker_changes) for r in rows)
    dels = sum(len(r.deletions) + len(r.ticker_changes) for r in rows)
    assert adds == dels == 138  # constant-size index


def test_styles_follow_the_legend_only(rows) -> None:  # type: ignore[no-untyped-def]
    by = {r.review_number: r for r in rows}
    assert Counter(r.style for r in rows) == {
        RowStyle.ORDINARY: 87,
        RowStyle.EXTRAORDINARY: 43,
        RowStyle.UNKNOWN: 7,
    }
    # Cell-level «Cambio de código», even inside an ordinary review row.
    assert by[42].ticker_changes == (("ACE", "ABE"), ("VAL", "SYV"))
    assert by[25].ticker_changes == (("TAB", "ALT"),)
    assert by[25].additions == ("AMS", "SGC", "TPI")
    # The fill not explained by the legend is never mapped by inference.
    unknown = {r.review_number for r in rows if r.style is RowStyle.UNKNOWN}
    assert unknown == {62, 76, 80, 91, 106, 108, 122}
    assert by[104].style is RowStyle.EXTRAORDINARY and by[104].deletions == ("POP",)


def test_document_anomalies_are_visible(rows) -> None:  # type: ignore[no-untyped-def]
    by = {r.review_number: r for r in rows}
    # Row 108 (GAS -> NTGY) is dated after row 109: the source's order is not chronological.
    assert by[108].effective_date == date(2018, 7, 2) > by[109].effective_date
    # Row 1 already has deletions: the document carries no initial composition.
    assert by[1].deletions


def test_foreign_calibration_refuses(rows) -> None:  # type: ignore[no-untyped-def]
    other = BMELayoutCalibration(
        header_additions="Inclusiones",
        header_deletions="Exclusiones",
        style_by_color=dict(COMPOIBEX_2026_09.style_by_color),
        calibrated_for_sha256="other-version",
    )
    assert {r.style for r in extract_rows_from_pdf(PDF.read_bytes(), other)} == {RowStyle.UNKNOWN}


def test_membership_cannot_be_built_from_this_document_alone(rows) -> None:  # type: ignore[no-untyped-def]
    """No initial composition and 7 rows without a legend marker: the classifier refuses
    instead of guessing (an official initial composition / current constituents list and
    the BME avisos for rows 62, 76, 80, 91, 106, 108, 122 are required)."""
    from pitquant.universe.events import UnresolvedSourceEventError
    from pitquant.universe.sources.bme import classify_rows

    with pytest.raises(UnresolvedSourceEventError) as exc:
        classify_rows(rows)
    msg = str(exc.value)
    assert "deletion of non-member" in msg
    assert "visual marker unknown and no BME aviso" in msg


OBS = Path("data/sources/bme_ibex35_current_constituents_20261001.json")


@pytest.mark.skipif(not OBS.exists(), reason="BME current-composition observation absent")
def test_real_ibex_build_from_official_documents(rows, session, settings) -> None:  # type: ignore[no-untyped-def]
    import json

    from pitquant.jobs.index_ingest import ingest_event_source
    from pitquant.security_master.service import SecurityMaster
    from pitquant.universe.index_membership import IdentityUnresolvedError, IndexUniverse
    from pitquant.universe.sources.bme_reconstruction import (
        CurrentComposition,
        events_from_official_documents,
    )

    obs = json.loads(OBS.read_text())
    cur = CurrentComposition(date(2026, 10, 1), tuple(map(tuple, obs["constituents"])), "obs")
    size = settings.universe("IBEX35").expected_size
    src, rec = events_from_official_documents(rows, cur, date(1995, 1, 2), SHA, size)
    rep = ingest_event_source(
        session, src, exchange="XMAD", currency="EUR", country="ES", expected_size=size
    )
    assert rep.status == "ok" and rep.n_intervals == 138
    assert rep.n_identity_unresolved == 138 and not rep.eligible_for_final_model_validation
    assert len(rec.unresolved_events) == 7
    u, sm = IndexUniverse(session), SecurityMaster(session)

    def tickers(d: date) -> set[str]:
        return {sm.ticker_as_of(m.security_id, d) or "?" for m in u.universe("IBEX35", d)}

    assert "GAS" in tickers(date(2018, 6, 29)) and "NTGY" not in tickers(date(2018, 6, 29))
    assert "NTGY" in tickers(date(2018, 7, 2)) and "GAS" not in tickers(date(2018, 7, 2))
    assert "REE" in tickers(date(2022, 6, 10)) and "RED" in tickers(date(2022, 6, 13))
    assert "POP" in tickers(date(2017, 6, 6)) and "POP" not in tickers(date(2017, 6, 7))
    assert len(tickers(date(2006, 7, 28))) == 33 and len(tickers(date(2012, 3, 1))) == 36
    assert tickers(date(2026, 9, 30)) == {t for t, _ in cur.constituents}
    with pytest.raises(IdentityUnresolvedError):
        u.backtest_universe("IBEX35", date(2018, 7, 2))
