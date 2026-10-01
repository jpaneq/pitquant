"""Regenerate docs/REAL_DATA_SEC_DEMO.md and docs/REAL_DATA_CNMV_DEMO.md from the local real
database (fact ids change whenever the local DB is rebuilt)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import select  # noqa: E402

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.db.models import CnmvFiling, IdentifierHistory  # noqa: E402
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402


def explain(*args: str) -> str:
    out = subprocess.run(["pitquant", "explain", *args], capture_output=True, text=True, check=True)
    return out.stdout.rstrip()


def block(title: str, *args: str) -> list[str]:
    return ["", f"## {title}", "```", explain(*args), "```"]


def main() -> int:
    s = get_settings()
    with make_session_factory(make_engine(s.database.url))() as ses:
        msft = ses.scalars(
            select(IdentifierHistory.security_id).where(IdentifierHistory.value == "0000789019")
        ).one()
        aapl = ses.scalars(
            select(IdentifierHistory.security_id).where(IdentifierHistory.value == "0000320193")
        ).one()
        enagas = ses.scalars(select(CnmvFiling.security_id)).first()
    sec = [
        "# Demostración PIT con datos REALES de SEC EDGAR",
        "",
        "Generado con `scripts/gen_real_demos.py` (`pitquant explain`) sobre la base local real "
        "(MSFT y AAPL: 127 filings, 51.538 versiones de hechos; headers e instancias XBRL "
        "archivados con SHA-256). La semántica temporal sigue el ADR-0019.",
        "",
        "`ticker then: unknown` es deliberado: los emisores se registran por su CIK y nunca se "
        "proyecta hacia atrás el ticker actual.",
        "",
        "### 1. Reexpresión real: beneficio neto de MSFT FY2016 (16.798 M$ → 20.539 M$)",
    ]
    for t in (
        "2016-07-28T16:00:00-04:00",
        "2018-08-03T11:15:00-04:00",
        "2018-08-03T11:20:00-04:00",
    ):
        sec += block(
            f"as_of {t}", msft, "NetIncomeLoss", "2016-06-30", t, "--period-start", "2015-07-01"
        )
    sec += [
        "",
        "### 2. Enmienda real: MSFT 10-Q/A 0001193125-12-026864",
        "",
        "El 10-Q original (0001193125-12-017029, aceptado el 2012-01-19) **no tenía XBRL** (sólo "
        "HTML): el 10-Q/A del 2012-01-27 aportó el anexo XBRL. El original queda registrado con "
        "su header y marcado como no resuelto (`filing_not_cited_by_companyfacts` + "
        "`xbrl_instance_missing`).",
    ]
    for t in ("2012-01-26T16:00:00-05:00", "2012-01-27T15:30:00-05:00"):
        sec += block(
            f"as_of {t}", msft, "SalesRevenueNet", "2011-12-31", t, "--period-start", "2011-10-01"
        )
    sec += [
        "",
        "### 3. «¿Por qué NO se conocía?»: valor de companyfacts rechazado (AAPL)",
        "",
        "companyfacts da 0.0 como valor nominal; la instancia XBRL del propio 10-Q dice 1e-05.",
    ]
    sec += block(
        "as_of 2014-12-31T16:00:00-05:00",
        aapl,
        "CommonStockParOrStatedValuePerShare",
        "2014-03-29",
        "2014-12-31T16:00:00-05:00",
    )
    (ROOT / "docs" / "REAL_DATA_SEC_DEMO.md").write_text("\n".join(sec) + "\n")

    concept = "I2235[SegmentosIngresos=IngresosOrdinariosClientesExternos]"
    cnmv = [
        "# Demostración PIT con datos REALES de la CNMV (Enagás, CIF A-28294726)",
        "",
        "Generado con `scripts/gen_real_demos.py`. Fuentes: 5 informes semestrales oficiales "
        "(2017S1–2019S1); cada ficha y cada XBRL IPP están archivados con SHA-256. Taxonomía "
        "en la clave (`ipp_ge@2016-06-01`): sólo se comparan versiones dentro de la misma "
        "taxonomía.",
        "",
        f"Concepto `{concept}` a 30-06-2017. El informe 2017S1 (publicado el 18-07-2017 y "
        "modificado el 27-07-2017) se usa desde la apertura del 28-07 (DATE_ONLY, *fail "
        "closed*). El informe 2018S1 da otro valor en su columna comparativa: es una versión "
        "posterior y no reescribe la anterior. La CNMV no indica hora: nunca se inventa.",
    ]
    for t in (
        "2017-07-27T17:30:00+02:00",
        "2018-07-17T17:30:00+02:00",
        "2018-07-18T09:00:00+02:00",
    ):
        cnmv += block(f"as_of {t}", enagas or "", concept, "2017-06-30", t)
    (ROOT / "docs" / "REAL_DATA_CNMV_DEMO.md").write_text("\n".join(cnmv) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
