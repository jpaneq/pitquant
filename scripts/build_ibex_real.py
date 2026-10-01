"""Build the REAL IBEX 35 membership from archived official BME documents and write the
coverage report (docs/IBEX_COVERAGE_REPORT.md). No network: everything is read back from
raw_source_archive by SHA-256.

    PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db python scripts/build_ibex_real.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import select  # noqa: E402

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.core.errors import UnknownSecurityError  # noqa: E402
from pitquant.data.archive import ArchiveStore  # noqa: E402
from pitquant.db.models import IndexEvent, IndexMembership, RawSourceArchive  # noqa: E402
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402
from pitquant.jobs.index_ingest import ingest_event_source  # noqa: E402
from pitquant.security_master.service import SecurityMaster  # noqa: E402
from pitquant.universe.index_membership import IndexUniverse  # noqa: E402
from pitquant.universe.sources.bme import (  # noqa: E402
    COMPOIBEX_2026_09,
    COMPOIBEX_2026_09_SHA256,
    extract_rows_from_pdf,
)
from pitquant.universe.sources.bme_reconstruction import (  # noqa: E402
    CurrentComposition,
    events_from_official_documents,
)

OBS_ID = "observation:bme-ibex35-constituents:2026-10-01"
COVERAGE_START = date(1995, 1, 2)  # first session in the XMAD calendar
CHECK_DATES = [
    (date(2018, 6, 29), "day before GAS -> NTGY (row 108, 2018-07-02)"),
    (date(2018, 7, 2), "GAS -> NTGY effective"),
    (date(2022, 6, 10), "before REE -> RED (row 122, 2022-06-13)"),
    (date(2022, 6, 13), "REE -> RED effective"),
    (date(2019, 6, 21), "before ordinary review row 112 (2019-06-24: MAS in, TRE out)"),
    (date(2019, 6, 24), "ordinary review row 112 effective"),
    (date(1998, 12, 31), "before re-entry of ANA (row 22, 1999-01-04; ANA left 1997-07-01)"),
    (date(1999, 1, 4), "ANA re-enters (new identity, IDENTITY_UNRESOLVED)"),
    (date(2017, 6, 6), "before extraordinary exclusion of POP (row 104, 2017-06-07)"),
    (date(2017, 6, 7), "POP excluded (Banco Popular resolution)"),
    (date(2006, 7, 28), "33-member window (rows 55-58)"),
    (date(2012, 3, 1), "36-member window (DIA added 2012-01-02)"),
]


def main() -> int:
    s = get_settings()
    store = ArchiveStore(ROOT / s.archive.root)
    factory = make_session_factory(make_engine(s.database.url))
    with factory() as ses:
        obs_row = ses.scalars(
            select(RawSourceArchive).where(RawSourceArchive.source_identifier == OBS_ID)
        ).one()
        obs = json.loads(store.get(obs_row.sha256))
        current = CurrentComposition(
            date.fromisoformat(obs["observed_at"][:10]),
            tuple((t, i) for t, i in obs["constituents"]),
            obs_row.sha256,
        )
        rows = extract_rows_from_pdf(store.get(COMPOIBEX_2026_09_SHA256), COMPOIBEX_2026_09)
        size = s.universe("IBEX35").expected_size
        src, rec = events_from_official_documents(
            rows, current, COVERAGE_START, COMPOIBEX_2026_09_SHA256, size
        )
        rep = ingest_event_source(
            ses, src, exchange="XMAD", currency="EUR", country="ES", expected_size=size
        )
        sm = SecurityMaster(ses)
        for ticker, isin in current.constituents:  # identity known FROM the observation only
            sid = sm.resolve(ticker, "XMAD", current.observed_on)
            try:
                sm.resolve_identifier("ISIN", isin, current.observed_on)
            except UnknownSecurityError:  # not yet recorded
                sm.add_identifier(sid, "ISIN", isin, current.observed_on)
        ses.commit()

        u = IndexUniverse(ses)
        lines = [
            "# IBEX 35 — informe de cobertura del universo real",
            "",
            "Generado con `scripts/build_ibex_real.py`. Fuentes:",
            f"- Composición histórica IBEX 35: `{COMPOIBEX_2026_09_SHA256}`.",
            f"- Composición vigente observada el {current.observed_on}: **transcripción** de la "
            "página oficial de cotizaciones y de las fichas (renderizadas por JavaScript; sus "
            f"bytes no contienen los valores y no pueden archivarse) — `{obs_row.sha256}`. "
            "Por eso el build es PROVISIONAL_RESEARCH_SOURCE.",
            "",
            "GAS→NTGY (fila 108) y REE→RED (fila 122) están entre las 7 filas sin marcador de "
            "leyenda: se cargan como rotación UNRESOLVED_EVENT_TYPE con identidades nuevas. "
            "**No están demostradas como cambios de ticker**; lo demostraría un ISIN fechado del "
            "código antiguo y del nuevo.",
            "",
            f"Build `{rep.build_id}`: estado **{rep.status}**, {rep.n_events} eventos, "
            f"{rep.n_intervals} intervalos.",
            f"Elegible para validación final: **{rep.eligible_for_final_model_validation}**.",
            "Intervalos con identidad sin resolver: "
            f"**{rep.n_identity_unresolved}/{rep.n_intervals}**.",
            "",
            f"Fecha fiable más temprana: {COVERAGE_START} (inicio del calendario XMAD). La "
            "composición en esa fecha se obtiene recorriendo hacia atrás el histórico completo "
            "desde la composición vigente; cada paso está validado.",
            "",
            "## Comprobaciones por fecha",
            "",
        ]
        for d, label in CHECK_DATES:
            mem = u.universe("IBEX35", d)
            tick = sorted(sm.ticker_as_of(m.security_id, d) or "?" for m in mem)
            lines.append(f"- **{d}** ({label}): {len(mem)} miembros — {', '.join(tick)}")
        lines += ["", "## Eventos con tipo no demostrado (UNRESOLVED_EVENT_TYPE)", ""]
        lines += [f"- {e}" for e in rec.unresolved_events] or ["- ninguno"]
        lines += ["", "## Anomalías del documento", ""]
        lines += [f"- {a}" for a in rec.order_anomalies] or ["- ninguna"]
        lines += [
            "",
            "## Identidades no resueltas",
            "",
            "Todas las membresías históricas siguen `IDENTITY_UNRESOLVED`: el histórico usa "
            "códigos (tickers) y ningún documento fechado aporta el ISIN de cada miembro en cada "
            "fecha. Los ISIN de la composición vigente se registran sólo desde "
            f"{current.observed_on}. `backtest_universe()` falla cerrado.",
            "",
            "| Ticker | Desde | Hasta | Entrada | Salida |",
            "|---|---|---|---|---|",
        ]
        for iv in ses.scalars(
            select(IndexMembership)
            .where(IndexMembership.build_id == rep.build_id)
            .order_by(IndexMembership.effective_from, IndexMembership.ticker_at_inclusion)
        ):
            ev = ses.get_one(IndexEvent, iv.source_event_id)
            lines.append(
                f"| {iv.ticker_at_inclusion} | {iv.effective_from} | {iv.effective_to or '—'} "
                f"| {ev.reason} | {iv.exclusion_reason or '—'} |"
            )
        (ROOT / "docs" / "IBEX_COVERAGE_REPORT.md").write_text("\n".join(lines) + "\n")
        print("\n".join(lines[:30]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
