"""CNMV ANCV identity snapshots and the IdentityResolutionEngine (ADR-0020).

Zips under tests/fixtures/ancv are REAL EXCERPTS of the public CNMV ANCV semiannual
distributions: the original LEAME and member names are kept; the equity lists are filtered
to a handful of ISINs and the large PDF listing is replaced by a placeholder. The NIF query
page is the real CNMV page for Enagás (CIF A-28294726), retrieved 2026-10-01.
Engine cases built from ``SnapshotLine(...)`` literals are FIXTURES (invented dates/ISINs
are marked ``FIXTURE`` in the issuer name).
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from pitquant.core.errors import DataQualityError
from pitquant.data.archive import ArchiveStore
from pitquant.data.providers.cnmv.ancv import (
    CNMVSecurityIdentityProvider,
    parse_distribution,
    parse_fixed_width_txt,
    parse_ilvrv,
    parse_nif_query,
    reference_date_of,
)
from pitquant.db.models import RawSourceArchive, SecurityIdentitySnapshot
from pitquant.security_master.identity import (
    BACKTESTABLE,
    CodePeriod,
    IdentityResolutionEngine,
    IdentityResolutionStatus,
    MembershipSpan,
    OfficialIdentifier,
    RowOutcome,
    SnapshotIndex,
    SnapshotLine,
    coverage_metrics,
    resolve_code_row,
)

pytestmark = pytest.mark.pit
FIX = Path(__file__).resolve().parents[1] / "fixtures" / "ancv"
M = IdentityResolutionStatus.MULTI_SOURCE_CONFIRMED
P = IdentityResolutionStatus.PROVISIONAL


def _dist(name: str):  # type: ignore[no-untyped-def]
    return parse_distribution((FIX / f"excerpt_{name}.zip").read_bytes())


# ───────────────────────────── parsers (real excerpts) ─────────────────────────────


def test_reference_date_comes_from_content_not_zip_name() -> None:
    # «ANCVSEMESTRAL25.zip» is the DECEMBER 2025 distribution (members LV2512 / root _2_2025)
    d = _dist("ANCVSEMESTRAL25")
    assert d.reference_date == date(2025, 12, 31)
    assert d.equity_format == "LVRV_XML"
    assert all(ln.cfi for ln in d.equity_lines)  # CFI present since 06/2022


def test_december_2022_delimited_layout_and_mixed_member_stamps() -> None:
    # 12/2022: no LVRV XML but a «??»-delimited ILVRV; members stamped LV1222.pdf (mmaa) and
    # LV2212.txt (aamm) — both read as 2022-12-31, never as a 2012 date.
    d = _dist("ANCVSEMESTRAL1222")
    assert d.reference_date == date(2022, 12, 31)
    assert d.equity_format == "ILVRV_DELIMITED"
    eng = next(x for x in d.equity_lines if x.isin == "ES0130960018")
    assert (eng.short_code, eng.share_kind, eng.cfi) == ("ENG", "AC", "ESVUFB")


def test_leame_scope_changes_over_time() -> None:
    old, new = _dist("ANCVSemestral062010"), _dist("ANCVSEMESTRAL25")
    assert old.leame.txt_scope == "ADMITTED_TO_TRADING"
    assert new.leame.txt_scope == "ACTIVE_IN_ANCV"
    assert old.scope_of("ES0130960018") == "ADMITTED_TO_TRADING"
    assert new.scope_of("ES0130960018") == "ACTIVE_IN_ANCV"  # weaker meaning, recorded


def test_issue_date_from_fixed_width_txt() -> None:
    d = _dist("ANCVSEMESTRAL25")
    assert d.txt_issue_dates["ES0105046017"] == date(2025, 6, 12)  # AENA after its split


def test_reference_date_disagreement_fails_closed() -> None:
    members = {
        "X/LVRV1806.XML": b"<?xml version='1.0'?><CODIGOS_ISIN_2_2018></CODIGOS_ISIN_2_2018>",
        "X/LV1806.txt": b"",
    }
    with pytest.raises(DataQualityError, match="disagree"):
        reference_date_of(members)


def test_unknown_layouts_fail_closed() -> None:
    with pytest.raises(DataQualityError, match="8 fields"):
        parse_ilvrv("ENAGAS??ES0130960018??ENG/AC??x".encode("cp1252"))
    with pytest.raises(DataQualityError, match="record length"):
        parse_fixed_width_txt(b"ES0130960018 too short\r\n")


def test_distribution_without_leame_is_refused() -> None:
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as z:
        z.writestr("X/LVRV1806.XML", "<CODIGOS_ISIN_1_2018/>")
    with pytest.raises(DataQualityError, match="LEAME"):
        parse_distribution(bio.getvalue())


def test_nif_query_links_cif_to_isin() -> None:
    r = parse_nif_query((FIX / "nif_query_A-28294726.html").read_bytes())
    assert r.issuer_name == "ENAGAS, S.A."
    (ln,) = r.ordinary_shares()
    assert (ln.isin, ln.issue_date, ln.cfi) == ("ES0130960018", date(1972, 7, 13), "ESVUFB")


def test_ingestion_archives_and_is_idempotent(session: Session, tmp_path: Path) -> None:
    prov = CNMVSecurityIdentityProvider(ArchiveStore(tmp_path))
    url = "https://www.cnmv.es/DocPortal/Publicaciones/ANCV/ANCVSEMESTRAL25.zip"
    data = (FIX / "excerpt_ANCVSEMESTRAL25.zip").read_bytes()
    r1 = prov.ingest_distribution(session, url, data)
    r2 = prov.ingest_distribution(session, url, data)
    assert r1.inserted == r1.lines > 0 and r2.inserted == 0
    arch = session.query(RawSourceArchive).one()
    notes = json.loads(arch.notes or "{}")
    assert notes["reference_date"] == "2025-12-31" and notes["filename"] == "ANCVSEMESTRAL25.zip"
    assert notes["leame_txt_scope"] == "ACTIVE_IN_ANCV"
    assert all(len(h) == 64 for h in notes["member_sha256"].values())
    row = session.query(SecurityIdentitySnapshot).filter_by(isin="ES0130960018").one()
    assert row.reference_date == date(2025, 12, 31) and row.archive_id == arch.archive_id
    assert row.source_hash == notes["member_sha256"][notes["equity_member"]]


# ───────────────────────────── row classification (the 7 BME rows) ─────────────────────


def _real_index() -> SnapshotIndex:
    lines = []
    for n in ("ANCVSEMESTRAL062018", "ANCVSEMESTRAL122018"):
        d = _dist(n)
        lines += [
            SnapshotLine(d.reference_date, x.isin, x.issuer_legal_name, x.instrument_name, x.cfi)
            for x in d.equity_lines
        ]
    return SnapshotIndex(lines)


def test_gas_to_ntgy_is_a_ticker_change_proven_by_isin() -> None:
    r = resolve_code_row(_real_index(), "p3:y197", "GAS", "NTGY", date(2018, 7, 2))
    assert r.outcome is RowOutcome.TICKER_CHANGE
    assert r.isin_before == r.isin_after == "ES0116870314"
    assert any("NATURGY" in e for e in r.evidence)  # legal-name change recorded


def test_row_without_snapshots_on_both_sides_stays_unresolved() -> None:
    r = resolve_code_row(_real_index(), "p2:y291", "CAR", "COL", date(2007, 5, 10))
    assert r.outcome is RowOutcome.UNRESOLVED


def _l(d: str, isin: str, label: str, issuer: str = "FIXTURE CO", **kw: object) -> SnapshotLine:
    return SnapshotLine(date.fromisoformat(d), isin, issuer, label, **kw)  # type: ignore[arg-type]


def test_different_isins_with_old_still_active_is_turnover() -> None:
    ix = SnapshotIndex(
        [
            _l("2020-06-30", "ES0000000001", "AAA/AC 1,00", "FIXTURE A"),
            _l("2020-12-31", "ES0000000001", "AAA/AC 1,00", "FIXTURE A"),
            _l("2020-12-31", "ES0000000002", "BBB/AC 1,00", "FIXTURE B"),
        ]
    )
    r = resolve_code_row(ix, "r", "AAA", "BBB", date(2020, 9, 1))
    assert r.outcome is RowOutcome.INDEX_TURNOVER


# ───────────────────────────── engine ─────────────────────────────


def _span(code: str, f: str, t: str | None) -> MembershipSpan:
    ff, tt = date.fromisoformat(f), date.fromisoformat(t) if t else None
    return MembershipSpan("k", ff, tt, (CodePeriod(code, ff, tt),))


def test_label_reused_by_another_issuer_never_leaks() -> None:
    """Regression: in 2023 the ANCV label GAM belongs to General de Alquiler de Maquinaria,
    not to Gamesa (member 2013-12-23..2017-07-24). Only snapshots inside the interval
    anchor, so the 2023 line can never be chosen."""
    ix = SnapshotIndex(
        [
            _l("2013-12-31", "ES0143416115", "GAM/AC 0,17", "GAMESA CORPORACION TECNOLOGICA"),
            _l("2016-12-31", "ES0143416115", "GAM/AC 0,17", "GAMESA CORPORACION TECNOLOGICA"),
            _l("2017-12-31", "ES0143416115", "SGRE/AC 0,17", "SIEMENS GAMESA RENEWABLE"),
            _l("2023-06-30", "ES0141571192", "GAM/AC 1.00", "GENERAL DE ALQUILER DE MAQUINARIA"),
        ]
    )
    segs = IdentityResolutionEngine(ix, horizon=date(2026, 10, 1)).resolve(
        _span("GAM", "2013-12-23", "2017-07-24")
    )
    assert {s.isin for s in segs if s.status in BACKTESTABLE} == {"ES0143416115"}
    assert all("ES0141571192" not in s.candidates for s in segs)


def test_ticker_alone_is_never_sufficient() -> None:
    ix = SnapshotIndex(
        [
            _l("2015-06-30", "ES0000000011", "XYZ/AC 1,00", "FIXTURE ONE"),
            _l("2015-06-30", "ES0000000029", "XYZ/AC 1,00", "FIXTURE TWO"),
        ]
    )
    segs = IdentityResolutionEngine(ix, horizon=date(2026, 1, 1)).resolve(
        _span("XYZ", "2015-01-02", "2015-12-01")
    )
    assert all(s.status not in BACKTESTABLE and s.isin is None for s in segs)
    assert set(segs[0].candidates) == {"ES0000000011", "ES0000000029"}


def test_new_shares_line_is_not_an_ordinary_share() -> None:
    ln = _l("2015-06-30", "ES0000000011", "XYZ/ACNV 1,00")
    assert not ln.is_ordinary_share


def test_isin_change_with_ancv_issue_date_keeps_one_security() -> None:
    ix = SnapshotIndex(
        [
            _l("2014-06-30", "ES0148396015", "ITX/AC 0,15", "FIXTURE INDITEX"),
            _l(
                "2014-12-31",
                "ES0148396007",
                "ITX/AC 0,03",
                "FIXTURE INDITEX",
                issue_date=date(2014, 7, 15),
            ),
            _l("2015-06-30", "ES0148396007", "ITX/AC 0,03", "FIXTURE INDITEX"),
        ]
    )
    segs = IdentityResolutionEngine(ix, horizon=date(2015, 12, 1)).resolve(
        _span("ITX", "2014-01-02", "2015-09-01")
    )
    proven = [(s.isin, s.start, s.end) for s in segs if s.status is M]
    assert ("ES0148396015", date(2014, 6, 30), date(2014, 7, 15)) in proven
    assert proven[-1][0] == "ES0148396007" and proven[-1][1] == date(2014, 7, 15)


def test_isin_change_without_dated_evidence_leaves_a_provisional_window() -> None:
    ix = SnapshotIndex(
        [
            _l("2016-06-30", "ES0173093115", "REE/AC 2,00", "FIXTURE RED ELECTRICA"),
            _l("2016-12-31", "ES0173093024", "REE/AC 0,50", "FIXTURE RED ELECTRICA"),
        ]
    )
    segs = IdentityResolutionEngine(ix, horizon=date(2017, 6, 1)).resolve(
        _span("REE", "2016-01-04", "2017-03-01")
    )
    win = [s for s in segs if s.status is P and s.start == date(2016, 7, 1)]
    assert win and win[0].end == date(2016, 12, 31) and win[0].isin is None
    assert set(win[0].candidates) == {"ES0173093115", "ES0173093024"}


def test_interval_without_inside_snapshot_is_provisional() -> None:
    ix = SnapshotIndex(
        [
            _l("2012-06-30", "ES0000000037", "ABC/AC 1,00"),
            _l("2012-12-31", "ES0000000037", "ABC/AC 1,00"),
        ]
    )
    (seg,) = IdentityResolutionEngine(ix, horizon=date(2013, 6, 1)).resolve(
        _span("ABC", "2012-07-02", "2012-11-01")
    )
    assert seg.status is P and seg.candidates == ("ES0000000037",)


def test_open_interval_tail_needs_bme_corroboration() -> None:
    ix = SnapshotIndex([_l("2026-06-30", "ES0130960018", "ENG/AC 1.50", "ENAGAS, S.A.")])
    span = _span("ENG", "2026-01-02", None)
    alone = IdentityResolutionEngine(ix, horizon=date(2026, 10, 1)).resolve(span)
    assert alone[-1].status is P
    off = OfficialIdentifier("ENG", "ES0130960018", date(2026, 10, 1), "BME", "h", exact=False)
    both = IdentityResolutionEngine(ix, [off], horizon=date(2026, 10, 1)).resolve(span)
    assert both[-1].status is M and both[-1].end is None


def test_coverage_metrics_count_whole_intervals() -> None:
    from pitquant.security_master.identity import Segment

    spans = {"a": _span("A", "2012-01-02", None), "b": _span("B", "2012-01-02", None)}
    res = {
        "a": [Segment(date(2012, 1, 2), None, M, "ES0000000045")],
        "b": [
            Segment(date(2012, 1, 2), date(2013, 1, 1), M, "ES0000000052"),
            Segment(date(2013, 1, 1), None, P, None),
        ],
    }
    m = coverage_metrics(res, spans, date(2011, 1, 1))
    assert (m["intervals_total"], m["resolved_multi_source"], m["provisional"]) == (2, 1, 1)
    assert m["coverage_percentage"] == 50.0
