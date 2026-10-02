# ruff: noqa: E501
"""Generate the D-02 window reports from the database (never by hand), ADR-0031.

    PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db python scripts/gen_us_window_reports.py

Writes docs/SP500_WINDOW_READINESS.md, docs/SP500_GAP_CARDS.md (+ .json), docs/US_MARKET_BACKFILL_PLAN.md and
docs/US_WINDOW_DRY_RUNS.md. Read-only on the database; no network.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.data.calendars.market_calendar import get_calendar  # noqa: E402
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402
from pitquant.market.providers.tiingo import CREDENTIAL  # noqa: E402
from pitquant.research.walkforward import WalkForwardConfig, dry_run, format_dry_run  # noqa: E402
from pitquant.universe.sp500_reconstruct import compute_d02  # noqa: E402
from pitquant.universe.sp500_window import window_readiness  # noqa: E402
from pitquant.universe.us_window_plan import (  # noqa: E402
    backfill_plan,
    dataset_dry_run,
    fundamental_coverage,
)

MIN_W = (date(2017, 10, 1), date(2022, 9, 30))
PREF_W = (date(2014, 10, 1), date(2022, 9, 30))
DOCS = ROOT / "docs"


def esc(x: object) -> str:
    return str(x if x is not None else "—").replace("|", "/").replace("\n", " ")


def main() -> int:
    cfg = get_settings()
    ho = cfg.validation.final_holdout
    with make_session_factory(make_engine(cfg.database.url))() as s:
        d02 = compute_d02(s)
        reps = {k: window_readiness(s, *w) for k, w in (("min", MIN_W), ("pref", PREF_W))}
        plan = backfill_plan(s, *PREF_W)
        plan_min = backfill_plan(s, *MIN_W)
        fund = fundamental_coverage(s, plan)
        rows, builder = dataset_dry_run(s, *PREF_W, plan)
    # ───────────────────────────────────────── window readiness
    L = [
        "# S&P 500 — readiness de ventanas D-02 (generado)\n",
        "> Generado por `scripts/gen_us_window_reports.py` desde la base. No editar a mano.\n",
    ]
    L.append(
        f"Ancla: `{d02.anchor_status}` as_of {d02.anchor_as_of} · run de eventos `{d02.run_id}` · {d02.n_events} eventos, {d02.n_confirmed} confirmados "
        f"(incl. {len(d02.immaterial_conflicts)} CONFLICT inmateriales), {len(d02.breaks)} rompen la cadena · `D02_RESEARCH_READY = {str(d02.d02_research_ready).lower()}` · holdout {ho.start} → {ho.end} sellado.\n"
    )
    L.append("## Hallazgo estructural\n")
    L.append(
        "Con **una sola ancla (hoy, 2026-10-01)** la pertenencia en la apertura de una fecha D exige TODOS los eventos posteriores a D confirmados: "
        "los eventos de 2022-10 → 2026 (periodo de holdout y posterior) bloquean cohortes de 2017-2022 aunque estén fuera de la ventana. "
        "El número «hipotético con ancla al final de la ventana» muestra cuánto se ganaría con una segunda ancla verificada cerca de 2022-09/10 (no es un estado).\n"
    )
    for key, title, w in (
        ("min", "Gate mínimo (60 cohortes)", MIN_W),
        ("pref", "Gate preferido (96 cohortes)", PREF_W),
    ):
        r = reps[key]
        L += [f"## {title}: {w[0]} → {w[1]}\n", "| campo | valor |", "|---|---|"]
        for k, v in (
            ("status", r.status),
            ("monthly_cohorts", r.monthly_cohorts),
            ("reconstructible_cohorts (hoy)", r.reconstructible_cohorts),
            ("longest consecutive run (hoy)", r.longest_consecutive_run),
            (
                "HIPOTÉTICO con ancla al final de la ventana",
                f"{r.intrinsic_reconstructible_cohorts} cohortes, racha {r.intrinsic_longest_run}",
            ),
            ("first_failure", r.first_failure),
            ("blocking events DENTRO de la ventana", len(r.blocking_events)),
            (
                "blocking events DESPUÉS (cadena)",
                f"{r.chain_blocking_events} {r.chain_blocking_by_year}",
            ),
            ("CONFLICT inmateriales resueltos en la ventana", r.immaterial_conflicts_in_window),
            ("blocking_identity (tickers sin security)", len(r.blocking_identity)),
            ("holdout_overlap", r.holdout_overlap),
        ):
            L.append(f"| {k} | {esc(v)} |")
        by: dict[str, int] = {}
        for c in r.blocking_events:
            by[f"{c.status} / {c.parser_status}"] = by.get(f"{c.status} / {c.parser_status}", 0) + 1
        L += [
            "",
            "Bloqueos dentro de la ventana por causa:\n",
            "| estado / parser | n |",
            "|---|---|",
        ]
        L += [f"| {k} | {v} |" for k, v in sorted(by.items(), key=lambda kv: -kv[1])]
        L.append("")
    L += [
        "## Clasificación de causas\n",
        "- `NO_DOCUMENT`: el comunicado de S&P DJI no está en el archivo crudo → fuente externa (ChatGPT).",
        "- `PARSER_MISS`: hay un comunicado archivado que menciona el ticker pero no se extrajo la cláusula (layout no soportado, p. ej. «added … replacing … which will be removed» con fechas distintas por lado). Trabajo offline, sin descargas.",
        "- `PARSED_NO_DATE`: comunicado parseado sin fecha/hora efectiva (TBA o redacción sin fecha concreta).",
        "- `PARSED_DATE_CONFLICT`: fecha oficial ≠ CSV y el intervalo contiene una apertura mensual (material).",
        "- `TICKER_CHANGE_CANDIDATE(...)`: el ticker aparece en una cláusula de cambio de nombre/ticker de un comunicado; un cambio de ticker NO es un cambio de membresía (hoy sólo se marca; persistirlo como evento de identidad exige securities US en el Security Master).\n",
    ]
    L += [
        "## Reprocesado del archivo (parser `sp500-evidence-3`)\n",
        "Sin descargas: 1.396 documentos archivados (1.344 press.spglobal.com + 52 PRNewswire/Wayback) re-parseados. Patrones nuevos: «will move to the S&P 500, replacing/switching places with» (rebalanceos), «will switch places with … respectively in the S&P 500», sustituido sin ticker («X will replace Joy Global in the S&P 500», ticker resuelto en el mismo comunicado), tipografía «S& P» / «( NASD : T )», «effective before the open». "
        "El CSV de discovery sigue siendo sólo QA: un CONFLICT cuya diferencia no cruza ninguna apertura mensual se resuelve con la fecha OFICIAL (nunca se edita para coincidir con el CSV).\n",
    ]
    (DOCS / "SP500_WINDOW_READINESS.md").write_text("\n".join(L), encoding="utf-8")
    # ───────────────────────────────────────── gap cards
    min_dates = {c.event_id for c in reps["min"].blocking_events}
    with make_session_factory(make_engine(cfg.database.url))() as s2:
        all_cards = window_readiness(
            s2, date(2011, 1, 3), date(2026, 9, 30)
        )  # every break in the chain
    every = all_cards.blocking_events
    G = [
        "# S&P 500 — fichas de gaps para investigación externa (generado)\n",
        "> Una ficha por evento que rompe la cadena. Orden cronológico. `ventana` = pertenece a la ventana mínima (M), sólo a la preferida (P) o es posterior a ambas (cadena: 2022-10 → 2026). **No se ha buscado nada fuera del archivo existente.**\n",
        "| # | ventana | effective_date | announcement | + added | − removed | nombres | estado | parser | identidad | fuente oficial archivada | qué falta | motivo |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, c in enumerate(every, 1):
        win = (
            "M"
            if c.event_id in min_dates
            else "P"
            if c.effective_date
            and PREF_W[0].isoformat() <= c.effective_date <= PREF_W[1].isoformat()
            else "cadena"
            if (c.effective_date or "") > PREF_W[1].isoformat()
            else "pre-2014"
        )
        G.append(
            "| "
            + " | ".join(
                esc(x)
                for x in (
                    i,
                    win,
                    c.effective_date,
                    c.announcement_date,
                    c.added_ticker,
                    c.removed_ticker,
                    f"{c.added_name} / {c.removed_name}",
                    c.status,
                    c.parser_status,
                    c.identity_status,
                    "; ".join(u.rsplit("/", 1)[-1][:60] for u in c.official_sources) or "no",
                    c.missing_evidence,
                    c.reason,
                )
            )
            + " |"
        )
    (DOCS / "SP500_GAP_CARDS.md").write_text("\n".join(G) + "\n", encoding="utf-8")
    (DOCS / "sp500_gap_cards.json").write_text(
        json.dumps([c.__dict__ for c in every], indent=1, default=str) + "\n", encoding="utf-8"
    )
    # ───────────────────────────────────────── backfill plan
    sm = plan.summary
    B = [
        "# Plan de backfill de mercado US (generado)\n",
        f"> **{sm['label']}**: la pertenencia de la ventana NO está probada (D-02). Esto estima la DEMANDA de precios (cota superior de símbolos únicos); no es un universo ni una cobertura de proveedor.\n",
        f"Ventana preferida {PREF_W[0]} → {PREF_W[1]} (la mínima {MIN_W[0]} → {MIN_W[1]} necesita {plan_min.summary['unique_securities_required']} símbolos). `PITQUANT_TIINGO_API_KEY`: **{CREDENTIAL.status().value}** (sin llamadas).\n",
        "| métrica | mínima | preferida |",
        "|---|---|---|",
    ]
    for k in (
        "unique_securities_required",
        "active_securities",
        "former_securities",
        "estimated_unique_symbols",
        "already_available",
        "missing_market_data",
        "identifiers_without_security",
    ):
        B.append(f"| {k} | {plan_min.summary[k]} | {sm[k]} |")
    cap = sm["free_plan_capacity"]
    B.append(
        f"| free_plan_capacity | {cap['monthly_unique_symbols']} símbolos/mes · {cap['daily_requests']} req/día · {cap['hourly_requests']} req/h (límites codificados en `TiingoBudget`, no re-verificados) | meses necesarios: {cap['months_needed_for_symbols']} |"
    )
    B += [
        "",
        f"`already_available`: {sm['already_available_note']}.",
        "",
        "Estados por security: precio = REQUIRED; dividendos y splits = `REQUIRED_UNVERIFIED` (la ausencia de eventos no es cobertura verificada); corporate actions complejas = `UNKNOWN`.",
        "",
        "| ticker | security_id | tickers históricos | membership_start | membership_end | price_required_from | price_required_to | identifier_status | precios | dividendos | splits | CA complejas |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in plan.rows:
        B.append(
            "| "
            + " | ".join(
                esc(x)
                for x in (
                    r.ticker,
                    r.security_id,
                    r.ticker,
                    r.membership_start,
                    r.membership_end,
                    r.price_required_from,
                    r.price_required_to,
                    r.identifier_status,
                    r.price_state,
                    r.dividend_coverage,
                    r.split_coverage,
                    r.complex_ca,
                )
            )
            + " |"
        )
    (DOCS / "US_MARKET_BACKFILL_PLAN.md").write_text("\n".join(B) + "\n", encoding="utf-8")
    # ───────────────────────────────────────── dry runs
    D = [
        "# US — dry-runs de fundamentales, dataset y walk-forward (generado)\n",
        f"> {sm['label']}. Ningún modelo entrenado, ninguna etiqueta consumida, holdout {ho.start} → {ho.end} intacto.\n",
        "## Cobertura fundamental (SEC ya ingerido)\n",
    ]
    ok = [f for f in fund if f.fundamental_months_possible > 0]
    D.append(
        f"{len(ok)} de {len(fund)} valores candidatos tienen hechos SEC ({sum(f.fundamental_months_possible for f in ok)} de {sum(f.membership_months for f in fund)} meses-valor posibles). Sin security resuelta no hay vínculo CIK→security: el siguiente cuello de botella tras los precios.\n"
    )
    D += [
        "| ticker | security_id | membership_months | fundamental_months_possible | first_fundamental_snapshot | last_fundamental_snapshot | missing_reason |",
        "|---|---|---|---|---|---|---|",
    ]
    for f in [x for x in fund if x.security_id] + [x for x in fund if not x.security_id][:25]:
        D.append(
            "| "
            + " | ".join(
                esc(x)
                for x in (
                    f.ticker,
                    f.security_id,
                    f.membership_months,
                    f.fundamental_months_possible,
                    f.first_fundamental_snapshot,
                    f.last_fundamental_snapshot,
                    f.missing_reason,
                )
            )
            + " |"
        )
    D.append(
        f"\n(Se listan los resueltos y 25 de {sum(1 for x in fund if not x.security_id)} sin security; el resto idéntico: `NO_SECURITY`.)\n"
    )
    D += [
        "## Dataset dry-run por cohorte (membresía candidata)\n",
        "| cohorte | members | identity_ready | fundamentals_ready | prices_ready | corporate_actions_ready | eligible |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows[::6]:
        D.append(
            f"| {r.date} | {r.members} | {r.identity_ready} | {r.fundamentals_ready} | {r.prices_ready} | {r.corporate_actions_ready} | {r.eligible} |"
        )
    D.append(
        f"\n(Una de cada 6 cohortes; {len(rows)} en total.) Dataset Builder real sobre los valores resueltos: `{json.dumps(builder.get('summary', {}).get('blocking_reasons', {}))}` — las filas no elegibles se conservan.\n"
    )
    cal = get_calendar("XNYS")
    for name, w in (("mínima", MIN_W), ("preferida", PREF_W)):
        ds = cal.first_sessions_of_months(*w)
        D.append(f"## Walk-forward (PLAN) — ventana {name} {w[0]} → {w[1]}\n")
        for h in (6, 12):
            c = WalkForwardConfig(label_horizon_months=h, purge_months=1, embargo_months=1)
            folds = dry_run(ds, c, (ho.start, ho.end))
            D += [
                f"Horizonte {h}M · train_min {c.train_min_months}m · validación {c.validation_months}m · purge {c.purge_months} · embargo {c.embargo_months} · `holdout_overlap = false`\n",
                "```",
                format_dry_run(folds),
                "```\n",
            ]
    (DOCS / "US_WINDOW_DRY_RUNS.md").write_text("\n".join(D), encoding="utf-8")
    print(
        "written: SP500_WINDOW_READINESS, SP500_GAP_CARDS(.json), US_MARKET_BACKFILL_PLAN, US_WINDOW_DRY_RUNS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
