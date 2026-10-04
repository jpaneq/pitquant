# ruff: noqa: E501
"""Generate docs/RUN3_CONTINUOUS_FEATURES_REPORT.md (+ .json) FROM THE DATABASE (never by hand). Read-only on the dev segment; the sealed holdout is not touched.

Usage: python scripts/gen_run3_report.py [--db sqlite:///data/pitquant.db] [--out docs/RUN3_CONTINUOUS_FEATURES_REPORT.md]
"""

from __future__ import annotations

import argparse
import json
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select

from pitquant.analyzer.market import load_market
from pitquant.db.models import Price, Security
from pitquant.db.session import make_engine, make_session_factory
from pitquant.features.v0.engine import load_facts
from pitquant.research import dataset_v1 as DS
from pitquant.research import effectiveness_v1 as E
from pitquant.research import features_v1 as FT
from pitquant.research import fundamentals_v1 as FU
from pitquant.research import model_contracts as MC

warnings.filterwarnings("ignore")
PRIORITY = (6, 12)
DIAG = (1, 3, 24)


def f(x: Any, n: int = 3) -> str:
    return (
        "—"
        if x is None or (isinstance(x, float) and pd.isna(x))
        else (f"{x:.{n}f}" if isinstance(x, float) else str(x))
    )


def table(rows: list[list[Any]], head: list[str]) -> str:
    return (
        "\n".join(
            [
                "| " + " | ".join(head) + " |",
                "|" + "|".join("---" for _ in head) + "|",
                *("| " + " | ".join(f(c) for c in r) + " |" for r in rows),
            ]
        )
        + "\n"
    )


def coverage_table(session: Any) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    out = []
    for sid in sorted({s for (s,) in session.execute(select(Price.security_id).distinct())}):
        sec = session.get_one(Security, sid)
        tk = DS._ticker(session, sid)
        if sec.is_synthetic or not tk or tk in DS.BENCH_TICKERS:
            continue
        facts = load_facts(session, sid, now)
        sic, _ = DS._profile_sic(session, sec)
        md = load_market(session, sid, now, sec.exchange)
        if md.bars.empty:
            continue
        r = FU.coverage_row(
            session,
            sid,
            tk,
            facts,
            now,
            sic,
            md.bars.index[-1],
            float(md.bars["close"].iloc[-1]),
            md.actions,
            float(md.series.split_adjusted["close"].iloc[-1]),
        )
        out.append({**r, "exchange": sec.exchange})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="sqlite:///data/pitquant.db")
    ap.add_argument("--out", default="docs/RUN3_CONTINUOUS_FEATURES_REPORT.md")
    a = ap.parse_args()
    S = make_session_factory(make_engine(a.db))()
    df = E.load_frame(S)
    cols = E.feature_columns(df)
    price_cols = [c for c in cols if c in FT.ALL_NAMES]
    fund_cols = [c for c in cols if c in FU.FEATURE_NAMES]
    js: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "rows": len(df),
        "securities": int(df.security_id.nunique()),
        "months": int(df.month.nunique()),
    }
    md: list[str] = []
    w = md.append
    w("# RUN 3 — Features continuas PIT, fundamentales y efectividad (informe generado)\n")
    w(
        f"Generado desde la base el {js['generated_at'][:19]}Z · segmento **DEV** (decisiones ≤ 2022-09-30) · {len(df):,} filas · {js['securities']} valores · {js['months']} meses. El holdout oct-2022→sep-2025 no se ha leído: sus decisiones no se generan y los objetivos que lo tocan son `UNAVAILABLE`. Todo es **descriptivo**: no se entrena ni se seleccionan pesos.\n"
    )
    w(
        "> Limitaciones que se aplican a TODO lo que sigue: universo = conjunto de investigación ACTUAL (sesgo de supervivencia, no es membresía de índice), benchmarks son proxies (SPY ETF; ^IBEX índice de precio sin dividendos; URTH ETF USD con desajuste de divisa en no-USD), fundamentales sólo EE. UU. y sectores soportados.\n"
    )
    # 1-2
    d = E.describe(df, cols)
    js["describe"] = d.round(6).to_dict("index")
    w("## 1. Cobertura de features / 2. Missingness\n")
    miss = d.sort_values("missing_pct", ascending=False)
    w(
        f"{len(cols)} features analizadas ({len(price_cols)} técnicas/soporte/riesgo, {len(fund_cols)} fundamentales/valoración). Missing nunca se rellena con 0; las razones por feature están en cada snapshot.\n"
    )
    w(
        table(
            [
                [n, int(r.n), r.missing_pct, r["mean"], r["std"], r.p10, r.p50, r.p90]
                for n, r in miss.iterrows()
            ],
            ["feature", "N", "missing %", "media", "std", "P10", "P50", "P90"],
        )
    )
    # 3-5, 9-12
    res: dict[str, list[dict[str, Any]]] = {}
    for h in (*PRIORITY, *DIAG):
        res[f"excess_{h}"] = [E.feature_report(df, c, h, "excess") for c in cols]
    for h in PRIORITY:
        res[f"ret_{h}"] = [E.feature_report(df, c, h, "ret") for c in cols]
        res[f"mdd_{h}"] = [E.feature_report(df, c, h, "mdd") for c in cols]
    js["effectiveness"] = res
    for sec_no, title, key in (
        (3, "IC raw (retorno total futuro)", "ret"),
        (4, "IC excess return vs benchmark", "excess"),
        (5, "IC vs max drawdown (negativo = más caída si el feature sube)", "mdd"),
    ):
        w(f"## {sec_no}. {title}\n")
        for h in PRIORITY:
            rows = sorted(res[f"{key}_{h}"], key=lambda r: -abs(r["ic"] or 0))[:25]
            w(f"### Horizonte {h}M (top 25 por |IC|; IC y t sobre offsets no solapados)\n")
            w(
                table(
                    [
                        [
                            r["feature"],
                            r["ic"],
                            r["t"],
                            r["avg_names_per_month"],
                            r["missing_pct"],
                            r["label"],
                        ]
                        for r in rows
                    ],
                    ["feature", "IC", "t", "N medio/mes", "missing %", "etiqueta"],
                )
            )
    # 6-8
    w("## 6-8. Deciles, D10−D1 y monotonicidad (excess, DEV)\n")
    qrows = []
    ranked = sorted(res["excess_6"], key=lambda r: -abs(r["ic"] or 0))[:15]
    for r in ranked:
        for h in PRIORITY:
            q = E.quantiles(df, r["feature"], f"excess_{h}", 10)
            q5 = E.quantiles(df, r["feature"], f"excess_{h}", 5)
            qrows.append(
                [
                    r["feature"],
                    f"{h}M",
                    q["top_minus_bottom"],
                    q["monotonicity"],
                    q5["top_minus_bottom"],
                    q5["monotonicity"],
                ]
            )
            js.setdefault("quantiles", {})[f"{r['feature']}_{h}"] = {"deciles": q, "quintiles": q5}
    w(table(qrows, ["feature", "H", "D10−D1", "monot. deciles", "Q5−Q1", "monot. quintiles"]))
    w("## 9. Robustez no solapada\n")
    w(
        "Para el horizonte H sólo se usan los meses congruentes módulo H (H offsets sin solape) y se reporta la media de los t por offset. Un IC con t<2 en este esquema no se considera evidencia.\n"
    )
    w("## 10-12. Estabilidad por periodo, región y régimen (IC medio excess 6M)\n")
    srows = [
        [
            r["feature"],
            *(
                r["strata"].get(k)
                for k in (
                    "H1_2011_2016",
                    "H2_2017_2022",
                    "regime=BULL",
                    "regime=BEAR",
                    "region=US",
                    "region=EU",
                    "region=ES",
                    "region=ASIA",
                    "region=NA",
                )
            ),
        ]
        for r in sorted(res["excess_6"], key=lambda r: -abs(r["ic"] or 0))[:25]
    ]
    w(
        table(
            srows, ["feature", "2011-16", "2017-22", "BULL", "BEAR", "US", "EU", "ES", "ASIA", "NA"]
        )
    )
    # 13
    w("## 13. Redundancia (|Spearman| ≥ 0.85, sólo DEV)\n")
    red = E.redundancy(df, cols)
    js["redundancy"] = red
    w(
        table([[a, b, r] for a, b, r in red[:60]], ["feature A", "feature B", "ρ"])
        if red
        else "Sin pares ≥ 0.85.\n"
    )
    # 14
    w("## 14. Fundamentales continuos: qué componente aporta\n")
    comp = E.component_composites(df)
    crow = []
    for c in comp.columns:
        dd = pd.concat(
            [
                df[["month"]],
                comp[[c]],
                df[[f"excess_{h}" for h in (6, 12, 24)] + ["mdd_6", "mdd_12"]],
            ],
            axis=1,
        )
        crow.append(
            [
                c,
                *(
                    E.offset_summary(E.monthly_ic(dd, c, t), int(t.split("_")[1])).get("ic")
                    for t in ("excess_6", "excess_12", "excess_24", "mdd_6", "mdd_12")
                ),
                *(
                    E.offset_summary(E.monthly_ic(dd, c, t), int(t.split("_")[1])).get("t")
                    for t in ("excess_6", "excess_12", "excess_24")
                ),
            ]
        )
    js["components"] = crow
    w(
        "Compuesto = media de rangos percentiles orientados a priori (`ORIENT`, fijados antes de ver ningún IC). IC frente a excess 6/12/24M y drawdown 6/12M.\n"
    )
    w(
        table(
            crow,
            [
                "componente",
                "IC exc 6M",
                "IC exc 12M",
                "IC exc 24M",
                "IC mdd 6M",
                "IC mdd 12M",
                "t 6M",
                "t 12M",
                "t 24M",
            ],
        )
    )
    # 15
    w("## 15. Cobertura SEC de fundamentales (tabla)\n")
    cov = coverage_table(S)
    js["fundamentals_coverage"] = cov
    cnt = pd.Series([c["status"] for c in cov if c["exchange"] == "XNYS"]).value_counts().to_dict()
    w(
        f"Valores XNYS con precios: {sum(cnt.values())} → {cnt}. No-XNYS: sin fundamentales SEC (`NOT_REGISTERED`, esperado).\n"
    )
    w(
        table(
            [
                [
                    c["ticker"],
                    c["status"],
                    c.get("sic"),
                    c.get("coverage"),
                    c.get("first_filing"),
                    ", ".join(c.get("missing", [])[:6]),
                ]
                for c in cov
                if c["exchange"] == "XNYS"
            ],
            ["ticker", "estado", "SIC", "cobertura", "1º filing", "métricas ausentes"],
        )
    )
    # 16-18
    labels = pd.DataFrame(res["excess_6"] + res["excess_12"])
    w("## 16. Features candidatas (PROMISING, a validar fuera de muestra)\n")
    prom = labels[labels.label == "PROMISING"]
    w(
        table(
            [[r.feature, r.horizon, r.ic, r.t, r.avg_names_per_month] for r in prom.itertuples()],
            ["feature", "H", "IC", "t", "N medio"],
        )
        if len(prom)
        else "Ninguna cumple el criterio completo.\n"
    )
    w("## 17. Features débiles\n")
    wk = labels[labels.label == "WEAK"]
    w(", ".join(sorted(set(wk.feature))) + "\n")
    w("## 18. Features problemáticas (UNSTABLE / DATA_QUALITY_LIMITED)\n")
    pr = labels[labels.label.isin(["UNSTABLE", "DATA_QUALITY_LIMITED"])]
    w(
        table(
            [
                [r.feature, r.horizon, r.label, r.missing_pct, r.avg_names_per_month]
                for r in pr.itertuples()
            ],
            ["feature", "H", "etiqueta", "missing %", "N medio"],
        )
    )
    # RISK_ALERT
    w("## RISK_ALERT: señal de riesgo, no de venta\n")
    ra = E.risk_alert_report(df)
    js["risk_alert"] = ra
    w(
        table(
            [
                [
                    r["alert"],
                    f"{r['target_horizon']}M",
                    r["base_rate_alert"],
                    r["ic_vs_max_drawdown"].get("ic"),
                    r["ic_vs_max_drawdown"].get("t"),
                    *(
                        f"{r[k]['or']:.2f} [{r[k]['lo']:.2f}, {r[k]['hi']:.2f}]"
                        if r[k]["or"]
                        else None
                        for k in ("dd10", "dd15", "dd20")
                    ),
                    r["dd15"]["rate_flag"],
                    r["dd15"]["rate_no_flag"],
                ]
                for r in ra
            ],
            [
                "alerta",
                "H",
                "tasa alerta",
                "IC vs mdd",
                "t",
                "OR dd≥10%",
                "OR dd≥15%",
                "OR dd≥20%",
                "P(dd15|alerta)",
                "P(dd15|sin)",
            ],
        )
    )
    # baselines
    w("## Baselines ingenuos\n")
    bl = {h: E.naive_baselines(df, h) for h in (6, 12)}
    js["baselines"] = bl
    w(
        table(
            [[f"{h}M", *(v for v in b.values())] for h, b in bl.items()],
            ["H", *next(iter(bl.values())).keys()],
        )
    )
    # 19-20
    w("## 19. Gates antes de ML\n")
    gates = MC.gate_status(S)
    js["gates"] = gates
    w(table([[g["gate"], g["status"], g["detail"]] for g in gates], ["gate", "estado", "detalle"]))
    w("## 20. Recomendación para el primer baseline ML\n")
    blocked = [g["gate"] for g in gates if g["status"] != "READY"]
    w(
        (
            "**No entrenar todavía.** Gates bloqueados: " + ", ".join(blocked) + ". "
            if blocked
            else "Gates listos. "
        )
        + "Primer experimento recomendado: comparar `EQUITY_6M_LOGISTIC_V0` y `EQUITY_12M_ELASTIC_NET_V0` (contratos en `research/model_contracts.py`) contra los baselines de arriba con folds expansivos purgados sobre DEV; descartar si no los superan fuera de muestra.\n"
    )
    Path(a.out).write_text("\n".join(md), encoding="utf-8")
    Path(a.out).with_suffix(".json").write_text(
        json.dumps(js, default=str, indent=1), encoding="utf-8"
    )
    print("written", a.out, len(df))


if __name__ == "__main__":
    main()
