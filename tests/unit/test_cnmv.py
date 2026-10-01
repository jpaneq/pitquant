"""D-04 CNMV vertical slice. Pages under tests/fixtures/cnmv_real are REAL public CNMV pages
(Enagás, archived 2026-10-01); the IPP XBRL instances below are FIXTURES shaped like the
real ones (IPP taxonomy, relative-period members), with invented values."""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from pitquant.core.errors import DataQualityError
from pitquant.data.archive import ArchiveStore
from pitquant.data.point_in_time.engine import facts_as_of
from pitquant.data.providers.cnmv.parsers import parse_ifi_detail, parse_ifi_list, parse_ipp_xbrl
from pitquant.data.providers.cnmv.provider import CNMVFundamentalProvider, ingest_cnmv_report
from pitquant.db.models import CnmvFiling
from tests.conftest import MAD

pytestmark = pytest.mark.pit
REAL = Path(__file__).resolve().parents[1] / "fixtures" / "cnmv_real"
NS = "http://www.cnmv.es/xbrl/ipp/ge/2016-06-01"


def test_real_detail_page_is_date_only_with_modifications() -> None:
    d = parse_ifi_detail((REAL / "DetalleIFI_2017082262.html").read_bytes())
    assert (d.company, d.cif) == ("ENAGAS, S.A.", "A-28294726")
    assert (d.period_start, d.period_end, d.fiscal_year) == (
        date(2017, 1, 1),
        date(2017, 6, 30),
        2017,
    )
    assert d.publication_date == date(2017, 7, 18) and d.publication_time is None
    assert d.last_modification == date(2017, 7, 27)
    assert {m.on for m in d.modifications} == {date(2017, 7, 19), date(2017, 7, 27)}
    assert d.xbrl_path is not None and "descargaxbrlipp.ashx" in d.xbrl_path


def test_real_report_list() -> None:
    entries = parse_ifi_list((REAL / "ListaIFI_A-28294726.html").read_bytes())
    by = {e.nreg: e for e in entries}
    assert by["2017082262"].published == date(2017, 7, 18)
    assert by["2018085463"].label.startswith("I semestre de 2018")
    assert len(entries) >= 60


def _ipp(facts: list[tuple[str, str, str | None, str, str]]) -> bytes:
    """(code, member, start, end, value) with at most one explicit member each."""
    ctx, body = [], []
    for i, (code, member, start, end, value) in enumerate(facts):
        period = (
            f"<xbrli:startDate>{start}</xbrli:startDate><xbrli:endDate>{end}</xbrli:endDate>"
            if start
            else f"<xbrli:instant>{end}</xbrli:instant>"
        )
        seg = (
            '<xbrli:segment><xbrldi:explicitMember dimension="d:SegmentosIngresosEje">'
            f"d:{member}</xbrldi:explicitMember></xbrli:segment>"
            if member
            else ""
        )
        ctx.append(
            f'<xbrli:context id="c{i}"><xbrli:entity><xbrli:identifier scheme="x">A-0'
            f"</xbrli:identifier>{seg}</xbrli:entity><xbrli:period>{period}</xbrli:period>"
            "</xbrli:context>"
        )
        body.append(f'<ipp:{code} contextRef="c{i}" unitRef="u" decimals="0">{value}</ipp:{code}>')
    return (
        '<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" '
        'xmlns:xbrldi="http://xbrl.org/2006/xbrldi" '
        f'xmlns:ipp="{NS}" xmlns:d="{NS}/dim">'
        '<xbrli:unit id="u"><xbrli:measure>iso4217:EUR</xbrli:measure></xbrli:unit>'
        + "".join(ctx)
        + "".join(body)
        + "</xbrli:xbrl>"
    ).encode()


EXT = "IngresosOrdinariosClientesExternos"
H1_17 = _ipp(
    [
        ("I2235", f"{EXT}PeriodoActualMiembro", None, "2017-06-30", "688"),
        ("I2235", "IngresosOrdinariosSegmentosPeriodoActualMiembro", None, "2017-06-30", "5"),
    ]
)
H1_18 = _ipp(
    [
        ("I2235", f"{EXT}PeriodoActualMiembro", None, "2018-06-30", "676"),
        ("I2235", f"{EXT}PeriodoAnteriorMiembro", None, "2017-06-30", "682"),
    ]
)
CONCEPT = f"I2235[SegmentosIngresos={EXT}]"


def test_relative_period_suffix_is_normalised_but_meaning_kept() -> None:
    a = {(f.concept, f.period_end): f.value for f in parse_ipp_xbrl(H1_17)}
    b = {(f.concept, f.period_end): f.value for f in parse_ipp_xbrl(H1_18)}
    key = (CONCEPT, date(2017, 6, 30))
    assert a[key] == 688 and b[key] == 682  # same fact, two reports -> two versions
    assert ("I2235[SegmentosIngresos=IngresosOrdinariosSegmentos]", date(2017, 6, 30)) in a


def test_conflicting_duplicates_are_rejected() -> None:
    bad = _ipp(
        [
            ("I1205", "AcumuladoActualMiembro", "2017-01-01", "2017-06-30", "10"),
            ("I1205", "", "2017-01-01", "2017-06-30", "11"),
        ]
    )
    with pytest.raises(DataQualityError, match="conflicting duplicate"):
        parse_ipp_xbrl(bad)


class FakeFetcher:
    def __init__(self, pages: dict[str, tuple[bytes, bytes]]) -> None:
        self.pages = pages

    def get(self, url: str) -> tuple[bytes, str]:
        for nreg, (detail, xbrl) in self.pages.items():
            if url.endswith(f"nreg={nreg}"):
                return detail, "text/html"
            if "descargaxbrlipp" in url and url.endswith(f"t={nreg}"):
                return xbrl, "text/xml"
        raise AssertionError(url)


def _detail(nreg: str, pub: str, start: str, end: str, last_mod: str | None) -> bytes:
    """The REAL page layout with substituted dates (the two modification dates collapse to
    ``last_mod``, or the table is removed when None)."""
    page = (REAL / "DetalleIFI_2017082262.html").read_text(encoding="utf-8")
    page = page.replace("18/07/2017", pub).replace("01/01/2017", start)
    page = page.replace("30/06/2017", end)
    if last_mod is None:
        page = re.sub(r'panelModificaciones".*?</table>', 'panelModificaciones">', page, flags=re.S)
    else:
        page = page.replace("27/07/2017", last_mod).replace("19/07/2017", last_mod)
    return re.sub(
        r"descargaxbrlipp\.ashx\?t=[^\"]+", f"descargaxbrlipp.ashx?t={nreg}", page
    ).encode()


def _provider(tmp_path: Path, pages: dict[str, tuple[bytes, bytes]]) -> CNMVFundamentalProvider:
    return CNMVFundamentalProvider(FakeFetcher(pages), ArchiveStore(tmp_path))  # type: ignore[arg-type]


def test_date_only_availability_waits_for_last_modification(
    session: Session, tmp_path: Path
) -> None:
    prov = _provider(
        tmp_path,
        {"A": (_detail("A", "18/07/2017", "01/01/2017", "30/06/2017", "27/07/2017"), H1_17)},
    )
    rep = ingest_cnmv_report(session, prov, "A", register_missing=True)
    assert rep.status == "ok" and rep.facts_inserted == 2
    f = session.query(CnmvFiling).one()
    assert f.availability_precision == "DATE_ONLY" and f.publication_time is None
    assert f.publication_date == date(2017, 7, 18)
    assert f.last_modification_date == date(2017, 7, 27)
    # The downloadable XBRL is the CURRENT version: usable only after the last modification.
    assert f.effective_available_at == datetime(2017, 7, 28, 9, 0, tzinfo=MAD)
    assert facts_as_of(session, f.security_id, datetime(2017, 7, 27, 23, 0, tzinfo=MAD)) == {}
    assert len(facts_as_of(session, f.security_id, datetime(2017, 7, 28, 9, 0, tzinfo=MAD))) == 2
    assert ingest_cnmv_report(session, prov, "A").status == "already_ingested"


def test_later_report_restates_without_rewriting(session: Session, tmp_path: Path) -> None:
    prov = _provider(
        tmp_path,
        {
            "A": (_detail("A", "18/07/2017", "01/01/2017", "30/06/2017", None), H1_17),
            "B": (_detail("B", "17/07/2018", "01/01/2018", "30/06/2018", None), H1_18),
        },
    )
    ingest_cnmv_report(session, prov, "A", register_missing=True)
    ingest_cnmv_report(session, prov, "B")
    sid = session.query(CnmvFiling).first().security_id  # type: ignore[union-attr]

    def v(at: datetime) -> float | None:
        hits = [
            f
            for k, f in facts_as_of(session, sid, at, [CONCEPT]).items()
            if k.period_end == date(2017, 6, 30)
        ]
        return hits[0].value if hits else None

    assert v(datetime(2018, 7, 17, 23, 0, tzinfo=MAD)) == 688  # what was known then
    assert v(datetime(2018, 7, 18, 9, 0, tzinfo=MAD)) == 682  # the later version


def test_rejected_report_can_be_reparsed_without_new_filing_row(
    session: Session, tmp_path: Path
) -> None:
    bad = _ipp(
        [
            ("I1205", "AcumuladoActualMiembro", "2017-01-01", "2017-06-30", "10"),
            ("I1205", "", "2017-01-01", "2017-06-30", "11"),
        ]
    )
    pages = {"A": (_detail("A", "18/07/2017", "01/01/2017", "30/06/2017", None), bad)}
    prov = _provider(tmp_path, pages)
    assert ingest_cnmv_report(session, prov, "A", register_missing=True).status == "rejected"
    assert session.query(CnmvFiling).count() == 1  # the filing (provenance) stays
    assert ingest_cnmv_report(session, prov, "A").status == "rejected"  # same bytes, same verdict
    assert session.query(CnmvFiling).count() == 1
