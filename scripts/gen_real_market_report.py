# ruff: noqa: E501, E402
"""Generate docs/REAL_MARKET_DATA_US.md from the database (never by hand): series validation,
archive hashes, official corporate actions, vendor-vs-official discrepancies and the real
total-return validation cases (engine vs independent closed form). ADR-0023."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import select

from pitquant.config.settings import get_settings
from pitquant.core.timeutils import utc_now
from pitquant.data.point_in_time.context import PITContext
from pitquant.db.models import (
    CorporateActionEvent,
    DataSource,
    Issuer,
    Price,
    RawSourceArchive,
    Security,
)
from pitquant.db.session import make_engine, make_session_factory
from pitquant.market.normalized import MarketBar, Provenance, SourceTier
from pitquant.market.validation import validate_series


def main() -> int:
    s = get_settings()
    out: list[str] = [
        "# Datos de mercado reales: AAPL, MSFT y ENG (iteración 4, ADR-0023)",
        "",
        "> Generado por `scripts/gen_real_market_report.py` desde la base local. **No es histórico",
        "> canónico**: son ventanas cortas de QA/prototipo. `FEATURE_RESEARCH_READY = false`.",
        "",
    ]
    with make_session_factory(make_engine(s.database.url))() as ses:
        ids = {
            "AAPL": ses.scalars(
                select(Security.security_id).where(Security.name == "CIK 0000320193 (SEC EDGAR)")
            ).one(),
            "MSFT": ses.scalars(
                select(Security.security_id).where(Security.name == "CIK 0000789019 (SEC EDGAR)")
            ).one(),
            "ENG": ses.scalars(
                select(Security.security_id)
                .join(Issuer, Issuer.issuer_id == Security.issuer_id)
                .where(Issuer.name == "ENAGAS, S.A.")
            ).one(),
        }
        out += ["## 1. Alpha Vantage `TIME_SERIES_DAILY`", ""]
        av = ses.scalars(
            select(RawSourceArchive).where(
                RawSourceArchive.provider == "ALPHAVANTAGE:TIME_SERIES_DAILY"
            )
        ).all()
        if not av:
            out += [
                "**BLOCKED_BY_CREDENTIAL**: `PITQUANT_ALPHAVANTAGE_API_KEY` no está definida en este entorno; no se",
                "ha hecho ninguna llamada real y no se ha inventado ningún dato. Adaptador, parser y validación",
                "están testeados con payloads sintéticos y con fetch inyectado (`tests/unit/test_market_validation.py`);",
                "la prueba real (`tests/real_api/`) se ejecuta sólo con clave. Con clave gratuita,",
                "`outputsize=compact` = últimas 100 observaciones: sirve para probar la cadena, **no** para el",
                "backfill 2011+.",
                "",
            ]
        else:
            for r in av:
                out.append(
                    f"- {r.source_identifier} sha256 `{r.sha256}` retrieved {r.retrieved_at}"
                )
            out.append("")
        out += ["## 2. Series de precios almacenadas (RAW, validación contra calendario)", ""]
        out += [
            "| security | fuente | primer día | último día | barras | duplicados | fuera de orden | no-sesión | sesiones ausentes | valores imposibles |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for name, sid in ids.items():
            srcs = ses.execute(
                select(DataSource.name, DataSource.source_id)
                .join(Price, Price.source_id == DataSource.source_id)
                .where(Price.security_id == sid)
                .distinct()
            ).all()
            for sname, source_id in srcs:
                rows = ses.scalars(
                    select(Price)
                    .where(Price.security_id == sid, Price.source_id == source_id)
                    .order_by(Price.session_date)
                ).all()
                prov = Provenance(sname, SourceTier.VENDOR, "db", "0" * 64, "report")
                bars = [
                    MarketBar(
                        name,
                        r.session_date,
                        r.open,
                        r.high,
                        r.low,
                        r.close,
                        r.volume,
                        r.currency,
                        r.bar_close_at,
                        prov,
                    )
                    for r in rows
                ]
                exch = ses.get_one(Security, sid).exchange
                v = validate_series(bars, exch)
                out.append(
                    f"| {name} | {sname} | {v.first_date} | {v.last_date} | {v.n_bars} | {len(v.duplicates)} | {v.out_of_order} | {len(v.non_session)} | {v.n_missing if name != 'ENG' else 'n/a (4 sesiones sueltas)'} | {len(v.impossible)} |"
                )
        out += [
            "",
            "Las series de EODHD (token público `demo`, sólo AAPL.US/MSFT.US) son ventanas dirigidas alrededor de los",
            "eventos reales (QA, fuente única, no aceptada). ENG: cuatro sesiones sueltas del boletín oficial de BME",
            "(sin `open`: el boletín no lo publica; nunca se imputa). «Sesiones ausentes» se mide dentro de cada",
            "ventana, no es una laguna del histórico.",
            "",
        ]
        out += [
            "## 3. Archivo raw (URL sin claves, SHA-256)",
            "",
            "| proveedor | identificador | sha256 | retrieved_at |",
            "|---|---|---|---|",
        ]
        for r in ses.scalars(
            select(RawSourceArchive)
            .where(
                RawSourceArchive.provider.in_(
                    [
                        "APPLE_IR:dividend-history",
                        "ENAGAS_IR:dividends",
                        "MICROSOFT_IR:dividends",
                        "BME_BOLETIN_DIARIO",
                        "EODHD:eod",
                        "EODHD:splits",
                        "EODHD:div",
                    ]
                )
            )
            .order_by(RawSourceArchive.provider, RawSourceArchive.retrieved_at)
        ):
            if r.provider == "BME_BOLETIN_DIARIO" and not any(
                d in r.source_identifier for d in ("20231219", "20231220", "20240701", "20240702")
            ):
                continue
            out.append(
                f"| {r.provider} | {r.source_identifier[:110]} | `{r.sha256[:16]}…` | {str(r.retrieved_at)[:19]} |"
            )
        out += [
            "",
            "La página de Apple responde 403 a clientes automáticos: se archiva la copia de Internet Archive",
            "(forma `id_`, sello 20260422063456) de la URL oficial. La página de Enagás cambia de bytes entre",
            "capturas: cada captura es una fila nueva y el motor deduplica por `(provider, evento)` quedándose con",
            "la versión más reciente.",
            "",
        ]
        out += [
            "## 4. Corporate actions oficiales normalizadas",
            "",
            "| security | tipo | anuncio | ex | record | pago | efectiva | ratio | importe | fuente |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        inv = {v: k for k, v in ids.items()}
        seen: set[tuple[object, ...]] = set()
        for e in ses.scalars(
            select(CorporateActionEvent).order_by(
                CorporateActionEvent.security_id,
                CorporateActionEvent.ex_date,
                CorporateActionEvent.effective_date,
            )
        ):
            key = (e.security_id, e.provider, e.provider_event_id, e.event_type)
            if key in seen:
                continue
            seen.add(key)
            if (
                e.security_id in inv and (e.ex_date or e.effective_date) >= date(2016, 1, 1)
            ) or e.event_type == "SPECIAL_DIVIDEND":
                out.append(
                    f"| {inv.get(e.security_id)} | {e.event_type} | {e.announcement_date or '—'} | {e.ex_date or '—'} | {e.record_date or '—'} | {e.payment_date or '—'} | {e.effective_date or '—'} | {e.ratio or '—'} | {e.cash_amount if e.cash_amount is not None else '—'} {e.currency or ''} | {e.provider} `{e.source_hash[:10]}` |"
                )
        out += [
            "",
            "`—` = la fuente no publica ese campo; **no se infiere**. Apple IR no publica ex-date: sus dividendos",
            "(59 desde 1995) quedan como `data_quality_issues.ca_unresolved_ex_date` y cualquier ventana de retorno que los",
            "pueda contener se **rechaza** (`InsufficientValuationError`). El split de Apple se ancla en su «primera fecha",
            "negociada ajustada» (`effective_date`). Enagás: la web publica ex-date sólo desde 2016-06-30; las 27 filas",
            "anteriores (2003–2015, incluidas las de 2011–2015) no traen ex-date y quedan sin resolver.",
            "",
        ]
        out += [
            "## 5. Validación de Total Return con datos reales",
            "",
            "Motor = `PITContext.total_return` (precios RAW + acciones conocidas en `as_of`). Cálculo independiente =",
            "forma cerrada del test (no usa adjusted close del proveedor).",
            "",
            "| caso | start | end | P0 | P1 | acción | raw price return | TR motor | TR independiente | Δ |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        ctx = PITContext(ses, utc_now())

        def px(sid: str, d: date) -> float:
            return float(
                ses.scalars(
                    select(Price.close).where(Price.security_id == sid, Price.session_date == d)
                ).first()
            )

        cases = [
            (
                "AAPL 4:1 split",
                "AAPL",
                date(2020, 8, 28),
                date(2020, 8, 31),
                "split x4",
                lambda p0, p1: p1 / (p0 / 4) - 1,
            ),
            (
                "AAPL 4:1 split (ventana 08-25→09-04)",
                "AAPL",
                date(2020, 8, 25),
                date(2020, 9, 4),
                "split x4",
                lambda p0, p1: p1 / (p0 / 4) - 1,
            ),
            (
                "AAPL dividendo + split (ventana 08-03→08-31)",
                "AAPL",
                date(2020, 8, 3),
                date(2020, 8, 31),
                "0.82 USD (ex 08-07, EODHD) + split x4",
                lambda p0, p1: (
                    4
                    * p1
                    * (px(ids["AAPL"], date(2020, 8, 7)) + 0.82)
                    / (p0 * px(ids["AAPL"], date(2020, 8, 7)))
                    - 1
                ),
            ),
            (
                "MSFT dividendo especial",
                "MSFT",
                date(2004, 11, 12),
                date(2004, 11, 15),
                "3.00 USD",
                lambda p0, p1: (p1 - p0 + 3.0) / p0,
            ),
            (
                "ENG dividendo a cuenta FY2023",
                "ENG",
                date(2023, 12, 19),
                date(2023, 12, 20),
                "0.696 EUR",
                lambda p0, p1: (p1 - p0 + 0.696) / p0,
            ),
            (
                "ENG dividendo complementario FY2023",
                "ENG",
                date(2024, 7, 1),
                date(2024, 7, 2),
                "1.044 EUR",
                lambda p0, p1: (p1 - p0 + 1.044) / p0,
            ),
        ]
        for label, name, a, b, act, f in cases:
            sid = ids[name]
            p0, p1 = px(sid, a), px(sid, b)
            tr = ctx.total_return(sid, a, b).total_return
            ind = f(p0, p1)
            out.append(
                f"| {label} | {a} | {b} | {p0} | {p1} | {act} | {p1 / p0 - 1:+.4%} | {tr:+.6%} | {ind:+.6%} | {abs(tr - ind):.1e} |"
            )
        out += [
            "",
            "El retorno de precio del split de Apple sería −74 %: el motor lo neutraliza con el ratio oficial.",
            "Invariancia ante split (100 € × 1 → 50 € × 2) y fórmula de dividendo simple en `tests/unit/test_real_market_ca.py`.",
            "",
        ]
        out += [
            "## 6. Discrepancias entre fuentes (QA, nunca autocorregidas)",
            "",
            "- **MSFT dividendo especial 2004-11-15**: Microsoft IR = 3.00 USD (anuncio 2004-07-20); EODHD = 3.08",
            "  (`unadjustedValue` = `value`, `period=Quarterly`, declaración 2004-07-21). Diferencia de 0.08 USD y de un día;",
            "  posible suma del dividendo regular de 0.08 pagado el mismo día (NO probado). Se usa el oficial; el vendor es QA.",
            "- **Apple ex-date**: Apple IR no lo publica; EODHD da 2020-08-07 (dividendo 0.82) y 2020-11-06 (0.205), con",
            "  declaración/record/pago/importe idénticos a Apple IR. Se usa SÓLO esa coincidencia completa (tier VENDOR,",
            "  `details.field_sources`); el resto de dividendos de Apple sigue sin ex-date.",
            "- **EODHD volumen**: publicado ajustado por splits; el adaptador lo des-ajusta y lo marca `imputed`.",
            "- **Apple IR vs EODHD** (split 2020-08-31): coinciden en fecha y ratio 4:1.",
            "- **Alpha Vantage vs EODHD**: no medible (sin clave de Alpha Vantage). El comparador",
            "  `compare_bars` está implementado y testeado (exactas/pequeñas/grandes/ausentes en A/B).",
            "- **ENG en EODHD demo**: 403 (el token `demo` sólo sirve algunos tickers US) → `SOURCE_COVERAGE_INSUFFICIENT`;",
            "  las cuatro sesiones ENG vienen del boletín oficial de BME.",
            "",
        ]
    Path(ROOT / "docs" / "REAL_MARKET_DATA_US.md").write_text(
        "\n".join(out) + "\n", encoding="utf-8"
    )
    print("wrote docs/REAL_MARKET_DATA_US.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
