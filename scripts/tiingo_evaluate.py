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
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import select  # noqa: E402

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.core.timeutils import utc_now  # noqa: E402
from pitquant.data.archive import ArchiveStore, archive_document  # noqa: E402
from pitquant.data.point_in_time.context import PITContext  # noqa: E402
from pitquant.db.models import Security  # noqa: E402
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
    CoverageStatus,
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

        # ── 2. candidate universe from the D-02 evidence (DISCOVERY-grade periods) ──────
        from pitquant.db.models import IndexCurrentAnchor, SP500MembershipEvent
        from pitquant.market.tiingo_eval import deterministic_sample

        anchor = ses.scalars(
            select(IndexCurrentAnchor)
            .where(IndexCurrentAnchor.index_code == "SP500")
            .order_by(IndexCurrentAnchor.ingested_at.desc())
        ).first()
        run_id = ses.scalars(
            select(SP500MembershipEvent.run_id).order_by(SP500MembershipEvent.created_at.desc())
        ).first()
        evs = (
            ses.scalars(
                select(SP500MembershipEvent).where(SP500MembershipEvent.run_id == run_id)
            ).all()
            if run_id
            else []
        )
        active_t = sorted({m["ticker"] for m in (anchor.members if anchor else [])})
        former: dict[str, date] = {}
        for e in evs:
            if e.removed_ticker and e.discovery_date and e.removed_ticker not in active_t:
                former[e.removed_ticker] = max(
                    former.get(e.removed_ticker, date(1900, 1, 1)), e.discovery_date
                )
        blocked = not evs
        universe_rows = [UniverseRow(t, t, date(2011, 1, 3), None) for t in active_t] + [
            UniverseRow(t, t, date(2011, 1, 3), d) for t, d in sorted(former.items())
        ]
        cov_all = coverage_rows(universe_rows, supported, asof)
        sample_active = deterministic_sample(active_t, 20, salt="ACTIVE")
        sample_former = deterministic_sample(former, 20, salt="FORMER")
        sample = [
            UniverseRow(sec["AAPL"], "AAPL", date(2011, 1, 3), None),
            UniverseRow(sec["MSFT"], "MSFT", date(2011, 1, 3), None),
        ]
        cov = coverage_rows(sample, supported, asof)
        from collections import Counter

        cnt = Counter(r.status for r in cov_all)
        n_unique = len({r.historical_ticker for r in cov_all})
        resolved = sum(1 for r in cov_all if r.status is not CoverageStatus.MISSING)
        covered = cnt[CoverageStatus.ACTIVE_COVERED] + cnt[CoverageStatus.DELISTED_COVERED]
        former_rows = [r for r in cov_all if r.historical_ticker in former]
        out += ["## Resumen (nivel `supported_tickers.zip`: descubrimiento, NO cobertura de precios)", "", "```",
                f"total_unique_securities   = {n_unique}   (tickers del universo candidato: {len(active_t)} activos del ancla + {len(former)} ex-miembros de los eventos)",
                f"resolved                 = {resolved}",
                f"price_history_available  = {covered}   (rango del ticker cubre el periodo de pertenencia aproximado)",
                f"missing                  = {cnt[CoverageStatus.MISSING]}",
                f"delisted_resolved        = {sum(1 for r in former_rows if r.status is not CoverageStatus.MISSING)}",
                f"delisted_missing         = {sum(1 for r in former_rows if r.status is CoverageStatus.MISSING)}",
                f"ticker_recycled_cases    = {cnt[CoverageStatus.TICKER_RECYCLED_SUSPECT]}",
                f"partial_period           = {cnt[CoverageStatus.PARTIAL_PERIOD]}",
                f"coverage_percentage      = {100 * covered / max(len(cov_all), 1):.1f}%", "```", "",
                "**Calidad del universo:** los periodos de pertenencia son aproximados (2011-01-03 → fecha del CSV de descubrimiento del último evento de salida); los ex-miembros proceden de eventos de descubrimiento y NO son membresía canónica (D02_RESEARCH_READY = false). Los tickers se cruzan con la lista pública de Tiingo; un ticker presente no garantiza datos de precios y un ticker reciclado puede pertenecer a otra empresa.", ""]  # fmt: skip
        if blocked:
            out += ["**BLOCKED**: no hay ninguna ejecución de evidencia S&P en la base.", ""]
        out += ["## Muestra determinista D-05 (semilla SHA-256 de `PITQUANT_D05_SAMPLE_V1`)", "",
                f"- 20 activas: {', '.join(sample_active)}", f"- 20 ex-miembros: {', '.join(sample_former)}",
                "- Fijas: AAPL, MSFT, SPY. Categoría «cambios de ticker/reorganizaciones»: vacía hasta resolver renombres con identidad (los renombres no son eventos de membresía).",
                f"- Símbolos únicos de la muestra: {len(set(sample_active) | set(sample_former) | {'AAPL', 'MSFT', 'SPY'})} de 500/mes del plan gratuito; la descarga NO se hace sin clave.", ""]  # fmt: skip
        out += ["## Filas de la muestra a nivel de lista pública", "", "| security_id | historical_ticker | period | tiingo_ticker | start_date | end_date | is_active | status | reason |", "|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
        for r in [
            x for x in cov_all if x.historical_ticker in set(sample_active) | set(sample_former)
        ] + cov:
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
            from pitquant.db.models import TickerHistory
            from pitquant.security_master.service import SecurityMaster

            spy_row = supported.get("SPY", [{}])[0]
            if "SPY" not in sec:
                existing = ses.scalars(
                    select(TickerHistory.security_id).where(TickerHistory.ticker == "SPY")
                ).first()
                if (
                    existing is None
                ):  # US_BENCHMARK_SPY_TOTAL_RETURN: an investable ETF proxy, NOT the official index
                    existing = (
                        SecurityMaster(ses)
                        .register(
                            name="SPDR S&P 500 ETF Trust (SPY) - benchmark ETF_PROXY",
                            exchange="XNYS",
                            currency="USD",
                            ticker="SPY",
                            listed_from=spy_row.get("start") or date(1993, 1, 29),
                        )
                        .security_id
                    )
                sec["SPY"] = existing
                official["SPY"] = []
            for sym in ("AAPL", "MSFT", "SPY"):
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
        from pitquant.market.tiingo_eval import evaluate_sample

        gt_unexplained = (
            None
            if not series
            else sum(
                1
                for c in comparisons_t
                if c.status is not Agreement.MATCH
                and c.official.provenance.provider != "MICROSOFT_IR:dividends"
            )
        )
        verdict = evaluate_sample(
            [],
            ground_truth_unexplained=gt_unexplained,
            mapping_reproducible=None,
            provenance_complete=True if series else None,
        )
        out += [
            "",
            "## Veredicto de la muestra (umbrales fijos: ≥ 98 % activas, ≥ 95 % ex-miembros, 100 % ground truth sin contradicción)",
            "",
            f"- `TIINGO_D05_CANDIDATE = {str(verdict.candidate and ev.candidate).lower()}`",
        ] + [f"- {r}" for r in verdict.reasons]
        ses.commit()
    Path(ROOT / "docs" / "TIINGO_SP500_COVERAGE.md").write_text(
        "\n".join(out) + "\n", encoding="utf-8"
    )
    print("wrote docs/TIINGO_SP500_COVERAGE.md; candidate =", ev.candidate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
