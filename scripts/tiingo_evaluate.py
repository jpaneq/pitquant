# ruff: noqa: E501
"""Evaluate Tiingo Free as D-05 candidate (ADR-0024) and generate docs/TIINGO_SP500_COVERAGE.md.

    PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db python scripts/tiingo_evaluate.py

Without ``PITQUANT_TIINGO_API_KEY`` nothing is requested from the token-gated API
(BLOCKED_BY_CREDENTIAL). The vendor's PUBLIC ``supported_tickers.zip`` (no token, no quota) is
archived and used for coverage discovery. With a key: AAPL and MSFT from 2011-01-01, archived raw.
The historical S&P 500 universe does not exist in the database (D-02): the coverage table is then
BLOCKED, never filled with an invented universe.
"""

from __future__ import annotations

import io
import sys
import urllib.request
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import select  # noqa: E402

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.core.timeutils import utc_now  # noqa: E402
from pitquant.data.archive import ArchiveStore, archive_document  # noqa: E402
from pitquant.data.point_in_time.context import PITContext  # noqa: E402
from pitquant.db.models import MembershipBuild, Security  # noqa: E402
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402
from pitquant.market.ca_compare import (  # noqa: E402
    Agreement,
    compare_with_official,
    record_disagreements,
)
from pitquant.market.credentials import SourceStatus  # noqa: E402
from pitquant.market.providers.eodhd import EODHDMarketDataProvider  # noqa: E402
from pitquant.market.providers.tiingo import TiingoBudget, TiingoEODMarketDataProvider  # noqa: E402
from pitquant.market.tiingo_eval import (  # noqa: E402
    UniverseRow,
    coverage_rows,
    evaluate_d05,
    ingest_symbol,
    load_supported,
)

SUPPORTED_URL = "https://apimedia.tiingo.com/docs/tiingo/daily/supported_tickers.zip"
BUDGET_FILE = ROOT / "data" / "tiingo_budget.json"


class _Demo:
    def get(self) -> str:
        return "demo"

    def status(self) -> SourceStatus:
        return SourceStatus.CONFIGURED


def main() -> int:
    s = get_settings()
    store = ArchiveStore(ROOT / s.archive.root)
    now = utc_now()
    out: list[str] = ["# Tiingo Free como candidato D-05 (cobertura S&P 500)", "",
        "> Generado por `scripts/tiingo_evaluate.py` (ADR-0024). Evaluación, **no** fuente canónica.", ""]  # fmt: skip
    with make_session_factory(make_engine(s.database.url))() as ses:
        sec = {
            n: ses.scalars(
                select(Security.security_id).where(Security.name == f"CIK {c} (SEC EDGAR)")
            ).one()
            for n, c in (("AAPL", "0000320193"), ("MSFT", "0000789019"))
        }
        # ── 1. public supported-tickers list (no token, no quota) ──────────────────────
        req = urllib.request.Request(SUPPORTED_URL, headers={"User-Agent": "PITQuant research"})
        zbytes = urllib.request.urlopen(req, timeout=120).read()
        zrow = archive_document(ses, store, provider="TIINGO:supported_tickers", source_identifier=SUPPORTED_URL,
            data=zbytes, mime_type="application/zip", parser_version="tiingo-supported-1",
            notes="public vendor file; no token")  # fmt: skip
        csv_bytes = zipfile.ZipFile(io.BytesIO(zbytes)).read("supported_tickers.csv")
        supported = load_supported(csv_bytes)
        asof = now.date()

        # ── 2. historical S&P universe ─────────────────────────────────────────────────
        sp = ses.scalars(select(MembershipBuild).where(MembershipBuild.index_code == "SP500")).all()
        universe_rows: list[UniverseRow] = []
        blocked = not sp
        sample = [
            UniverseRow(sec["AAPL"], "AAPL", date(2011, 1, 3), None),
            UniverseRow(sec["MSFT"], "MSFT", date(2011, 1, 3), None),
        ]
        cov = coverage_rows(sample, supported, asof)
        out += ["## Resumen", "", "```",
                f"total_unique_securities   = {'n/a (BLOCKED: no historical S&P 500 universe)' if blocked else len(universe_rows)}",
                "resolved                 = n/a" if blocked else "resolved                 = ...",
                "price_history_available  = n/a",
                "missing                  = n/a", "delisted_resolved        = n/a", "delisted_missing         = n/a",
                "ticker_recycled_cases    = n/a", "coverage_percentage      = n/a", "```", ""]  # fmt: skip
        if blocked:
            out += [
                "**BLOCKED**: la base no contiene ninguna membresía histórica del S&P 500 (D-02: el fichero S&P DJI",
                "lo aporta el propietario; el candidato Sharadar SP500 está `BLOCKED_BY_CREDENTIAL`). No se ha",
                "inventado un universo: sin él no se puede medir la cobertura de *former/delisted constituents*, que es",
                "el test crítico. La herramienta (`coverage_rows`) está lista y testeada con estados",
                "`ACTIVE_COVERED / DELISTED_COVERED / PARTIAL_PERIOD / TICKER_RECYCLED_SUSPECT / MISSING`.",
                "",
            ]
        out += ["## Filas disponibles (las dos únicas securities US reales; tickers actuales, no históricos)", "",
                "| security_id | historical_ticker | period | tiingo_ticker | start_date | end_date | is_active | status | reason |", "|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
        for r in cov:
            out.append(
                f"| {r.security_id[:8]} | {r.historical_ticker} | {r.period} | {r.tiingo_ticker} | {r.start_date} | {r.end_date} | {r.is_active} | {r.status} | {r.reason} |"
            )
        # vendor-wide statistics (NOT S&P coverage)
        us = [
            (t, r)
            for t, rows in supported.items()
            for r in rows
            if r["exchange"] in {"NYSE", "NASDAQ", "NYSE MKT", "NYSE ARCA", "AMEX", "BATS"}
            and r["asset"] == "Stock"
        ]
        delisted = [
            x
            for x in us
            if x[1]["end"]
            and x[1]["end"] < date(asof.year, asof.month, 1).replace(day=1)
            and (asof - x[1]["end"]).days > 10
        ]
        dup = [t for t, rows in supported.items() if len(rows) > 1]
        by_end = Counter(r["end"].year for _, r in delisted if r["end"] and r["end"].year >= 2011)
        out += ["", "## Estadística del fichero público de Tiingo (todo el vendor, NO cobertura del S&P 500)", "",
                f"- Fichero archivado: sha256 `{zrow.sha256}` ({len(csv_bytes)} bytes descomprimido).",
                f"- Tickers distintos: {len(supported)}; filas acciones en bolsas US: {len(us)}; con `endDate` anterior a hoy (delistadas/inactivas): {len(delisted)}.",
                f"- Tickers con más de una fila (reciclados/ambiguos): {len(dup)}.",
                f"- Delistadas por año de `endDate` (2011+): {dict(sorted(by_end.items()))}.", "",
                "Estas cifras no prueban cobertura de antiguos miembros del S&P 500; sólo muestran que Tiingo lista",
                "símbolos inactivos. Cada ticker de un miembro histórico habría que cruzarlo contra su periodo.", ""]  # fmt: skip

        # ── 3. vendor vs official corporate actions (EODHD demo existing + Tiingo if key) ──
        official = {
            k: [
                a
                for a in PITContext(ses, now).market_actions(v)
                if a.provenance.tier.value == "OFFICIAL"
            ]
            for k, v in sec.items()
        }
        eod = EODHDMarketDataProvider(credential=_Demo())  # type: ignore[arg-type]
        out += [
            "## Eventos del proveedor vs evidencia oficial",
            "",
            "| fuente | security | evento oficial | estado | diferencias | info |",
            "|---|---|---|---|---|---|",
        ]
        for sym, (a, b) in (
            ("AAPL", ("2020-06-01", "2020-12-31")),
            ("MSFT", ("2004-10-01", "2004-12-31")),
        ):
            raw = {
                ep: eod.download(ep, f"{sym}.US", **{"from": a, "to": b})[0]
                for ep in ("eod", "splits", "div")
            }
            vend = eod.normalize(sym, f"{sym}.US", raw["eod"], raw["splits"], raw["div"]).actions
            win = [
                o
                for o in official[sym]
                if a <= str(o.anchor_date) <= b and o.provenance.provider != "APPLE_IR+EODHD_EXDATE"
            ]
            comps = compare_with_official(win, vend)
            existing = {
                (i.details.get("official_anchor"), i.check_name)
                for i in ses.execute(
                    select(
                        __import__(
                            "pitquant.db.models", fromlist=["DataQualityIssue"]
                        ).DataQualityIssue
                    ).where(
                        __import__(
                            "pitquant.db.models", fromlist=["DataQualityIssue"]
                        ).DataQualityIssue.security_id
                        == sec[sym]
                    )
                ).scalars()
            }
            new = [
                c
                for c in comps
                if c.status is not Agreement.MATCH
                and (str(c.official.anchor_date), c.status.value) not in existing
            ]
            record_disagreements(ses, sec[sym], new)
            for c in comps:
                out.append(
                    f"| EODHD demo | {sym} | {c.official.kind.value} {c.official.anchor_date} | {c.status} | {'; '.join(c.differences) or '—'} | {'; '.join(c.info) or '—'} |"
                )
        out += [
            "",
            "El evento oficial manda siempre. La diferencia de Microsoft 2004 queda registrada como `VENDOR_DISAGREEMENT`",
            "(`data_quality_issues`) **sin explicación**: no hay eventos separados que permitan demostrar que 3.08 = 3.00 + 0.08.",
            "",
        ]

        # ── 4. Tiingo real run (only with a key) ───────────────────────────────────────
        prov = TiingoEODMarketDataProvider(budget=TiingoBudget.load(BUDGET_FILE))
        series, comparisons_t = [], []
        out += ["## Tiingo real (AAPL, MSFT desde 2011-01-01)", ""]
        if prov.status() is SourceStatus.SOURCE_NOT_CONFIGURED:
            out += [
                "**BLOCKED_BY_CREDENTIAL**: `PITQUANT_TIINGO_API_KEY` no está definida; no se ha hecho ninguna llamada",
                "con token (cupo gratuito intacto). Adaptador, parser, presupuesto de cupo y comparadores testeados con",
                "payloads sintéticos en el formato documentado.",
                "",
            ]
        else:
            out += [
                "| ticker | primera | última | barras | duplicados | fuera de orden | no-sesión | sesiones ausentes | imposibles | días adj≠raw | factor última barra | sha256 |",
                "|---|---|---|---|---|---|---|---|---|---|---|---|",
            ]
            for sym in ("AAPL", "MSFT"):
                r = ingest_symbol(
                    ses,
                    store,
                    prov,
                    ticker=sym,
                    security_id=sec[sym],
                    start=date(2011, 1, 1),
                    official=official[sym],
                )
                v, ad = r.series, r.adjustment
                series.append(v)
                comparisons_t += r.comparisons
                out.append(
                    f"| {sym} | {v.first_date} | {v.last_date} | {v.n_bars} | {len(v.duplicates)} | {v.out_of_order} | {len(v.non_session)} | {v.n_missing} | {len(v.impossible)} | {ad.n_adjusted_days} | {ad.last_bar_factor} | `{r.sha256[:16]}…` |"
                )
                record_disagreements(
                    ses, sec[sym], [c for c in r.comparisons if c.status is not Agreement.MATCH]
                )
            prov.budget.save(BUDGET_FILE)
            out += ["", f"Cupo usado: {prov.budget.used(now)}", ""]
        ev = evaluate_d05(series=series, comparisons=comparisons_t, identity_reproducible=True,
                          coverage=None if blocked else cov, provenance_complete=True if series else None)  # fmt: skip
        out += [
            "## Criterios D-05",
            "",
            f"**TIINGO_D05_CANDIDATE = {str(ev.candidate).lower()}** (nunca implica CANONICAL)",
            "",
            "| criterio | resultado | detalle |",
            "|---|---|---|",
        ]
        for k, (c, d) in ev.criteria.items():
            out.append(f"| {k} | {c} | {d} |")
        ses.commit()
    Path(ROOT / "docs" / "TIINGO_SP500_COVERAGE.md").write_text(
        "\n".join(out) + "\n", encoding="utf-8"
    )
    print("wrote docs/TIINGO_SP500_COVERAGE.md; candidate =", ev.candidate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
