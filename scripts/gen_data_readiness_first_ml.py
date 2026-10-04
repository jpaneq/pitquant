# ruff: noqa: E501
"""DATA READINESS FOR FIRST ML: generates docs/DATA_READINESS_FIRST_ML.md and docs/BENCHMARK_RETURN_CONTRACT.md (+ .json) FROM THE DATABASE. Read-only; trains nothing; lowers no gate.

PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db python scripts/gen_data_readiness_first_ml.py
"""

from __future__ import annotations

import json
import os
import warnings
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from pitquant.config.settings import get_settings
from pitquant.db.models import DataSource, Price, Security
from pitquant.db.session import make_engine, make_session_factory
from pitquant.market.canonical import FEATURE_VERSION, TARGET_VERSION, audit_series
from pitquant.positions import routine as rt
from pitquant.research import benchmark_contract as BC
from pitquant.research import dataset_v1 as DS
from pitquant.research import first_ml as FM
from pitquant.research import first_ml_contract as C
from pitquant.research.membership_bridge import build_bridge
from pitquant.research_readiness import research_readiness
from pitquant.universe.sp500_anchor_graph import reconstruct

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent


def cell(x: Any) -> str:
    return "—" if x is None else (f"{x:.3f}" if isinstance(x, float) else str(x))


def table(rows: list[list[Any]], head: list[str]) -> str:
    return (
        "\n".join(
            [
                "| " + " | ".join(head) + " |",
                "|" + "|".join("---" for _ in head) + "|",
                *("| " + " | ".join(cell(c) for c in r) + " |" for r in rows),
            ]
        )
        + "\n"
    )


def main() -> None:
    from pitquant.db.models_research import ResearchFeatureSnapshot, ResearchTarget

    cfg = get_settings()
    S = make_session_factory(make_engine(os.environ["PITQUANT_DATABASE_URL"]))()
    rf = research_readiness(S, cfg)
    js: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "experiment": C.EXPERIMENT_ID,
    }
    # ---- D02 ------------------------------------------------------------------------------------------------------------------
    rep = reconstruct(S, date(2011, 1, 1), date(2022, 9, 30), standard="MONTHLY")
    months = []
    for c in rep.cohorts:
        ready = c.status == "MEMBERSHIP_READY"
        months.append({"month": c.date.strftime("%Y-%m"), "date": c.date, "expected_universe": c.n_members, "resolved_members": len(c.members) if (ready and c.members) else None, "unresolved_members": None if ready else len(c.reasons) or None,
                       "identity_resolved": ready, "membership_evidence": (f"segment {c.segment}; forward==backward" if c.sets_equal else (f"segment {c.segment}" if c.segment else None)), "status": "READY" if ready else ("BLOCKED" if c.status == "BLOCKED" else "NO_ANCHOR"),
                       "blocking_reason": None if ready else ("; ".join(c.reasons)[:120] or c.status)})  # fmt: skip
    ready_dates = [m["date"] for m in months if m["status"] == "READY"]
    plan = C.walk_forward_folds(ready_dates)
    d02 = {"total_months": len(months), "ready_months": len(ready_dates), "partial_months": 0, "blocked_months": sum(1 for m in months if m["status"] == "BLOCKED"), "no_anchor_months": sum(1 for m in months if m["status"] == "NO_ANCHOR"),
           "coverage_pct": round(100 * len(ready_dates) / max(len(months), 1), 1), "longest_run": rep.longest_run, "feasible_folds": len(plan.folds), "reason_if_no_folds": plan.reason_if_none}  # fmt: skip
    js["d02"] = d02
    js["flags"] = {k: bool(v) for k, v in rf.flags.items()}
    js["flags_scope"] = (
        "Legacy Research Lab feature-collection flags; experiment readiness is defined by gates, not flags."
    )
    # ---- data ------------------------------------------------------------------------------------------------------------------
    securities = [
        s
        for s in S.scalars(select(Security))
        if S.scalar(
            select(func.count())
            .select_from(Price)
            .where(Price.security_id == s.security_id)
            .limit(1)
        )
        and not s.is_synthetic
    ]
    ticker_of = {s.security_id: DS._ticker(S, s.security_id) for s in securities}
    snaps: list[dict[str, Any]] = []
    for sn in S.scalars(
        select(ResearchFeatureSnapshot).where(
            ResearchFeatureSnapshot.feature_set_version == FEATURE_VERSION
        )
    ):
        keep = set(C.CORE_PRICE_FEATURES) | set(C.CORE_FUNDAMENTAL_FEATURES)
        snaps.append(
            {
                "security_id": sn.security_id,
                "decision_at": sn.decision_at,
                "decision_session": sn.decision_session,
                "exchange": sn.exchange,
                "meta": sn.meta,
                "ticker": sn.meta.get("ticker"),
                "features": {k: v["value"] for k, v in sn.features.items() if k in keep},
            }
        )
    targets12 = {(t.security_id, t.decision_at): {"status": t.status, "reason": t.reason, "outperform": t.outperform, "details": t.details} for t in S.scalars(select(ResearchTarget).where(ResearchTarget.target_set_version == TARGET_VERSION, ResearchTarget.horizon_months == C.HORIZON_MONTHS))}  # fmt: skip
    # ---- context ---------------------------------------------------------------------------------------------------------------
    bridge, unresolved_bridge = build_bridge(S)
    cohorts = {
        c.date: {"status": c.status, "members": frozenset(c.members or ())} for c in rep.cohorts
    }
    identity_ok = set(bridge)
    js["identity_bridge"] = {
        "evidence_class": "DERIVED_EXACT_NAME_UNIQUE",
        "bridged": len(bridge),
        "unresolved": unresolved_bridge,
    }
    cached_qa = {row["security_id"]: row for row in rf.metrics["yahoo_d05"]}
    qa = [
        cached_qa[s.security_id] if s.security_id in cached_qa else audit_series(S, s)
        for s in securities
    ]
    js["d05_quality"] = qa
    present = {r["security_id"] for r in qa if r["status"] == "READY"}
    out: dict[str, Any] = {}
    for label, accepted in (
        ("strict", True),
        ("preview_if_D05_accepted", True),
    ):
        ctx = FM.EligibilityContext(cohorts, bridge, identity_ok, accepted, present)
        for fam in ("PRICE", "FUNDAMENTALS"):
            res = [
                FM.first_ml_eligibility(
                    ctx, s, targets12.get((s["security_id"], s["decision_at"])), family=fam
                )
                for s in snaps
            ]
            out[f"{label}_{fam}"] = {
                **FM.funnel(res),
                "securities_with_eligible_rows": len(
                    {s["security_id"] for s, r in zip(snaps, res, strict=True) if r["eligible"]}
                ),
            }
    targets6 = {
        (t.security_id, t.decision_at): {
            "status": t.status,
            "reason": t.reason,
            "outperform": t.outperform,
            "details": t.details,
        }
        for t in S.scalars(
            select(ResearchTarget).where(
                ResearchTarget.target_set_version == TARGET_VERSION,
                ResearchTarget.horizon_months == 6,
            )
        )
    }
    js["eligibility_6m"] = FM.funnel(
        [
            FM.first_ml_eligibility(
                ctx, snap, targets6.get((snap["security_id"], snap["decision_at"])), family="PRICE"
            )
            for snap in snaps
        ]
    )
    js["funnel"] = out
    fm = FM.fundamentals_months(snaps)
    js["fundamentals"] = {"n_ok": fm["n_ok"], "required": C.REQUIRED_FUNDAMENTAL_SECURITIES, "per_security": {v["ticker"]: {"usable_months": v["usable"], "first": str(v["first"]) if v["first"] else None, "last": str(v["last"]) if v["last"] else None, "snapshots": v["n"]} for v in fm["per_security"].values()}}  # fmt: skip
    # ---- security audit -------------------------------------------------------------------------------------------------------
    uni = rt.load_universe()
    cfg_tickers = sorted(
        {t.upper().split(".")[0] for lst in uni.values() for t in lst} | {"SPY", "URTH", "^IBEX"}
    )
    snap_secs = {s["security_id"] for s in snaps}
    audit = []
    for s in securities:
        tk = ticker_of[s.security_id]
        dates = S.execute(
            select(func.min(Price.session_date), func.max(Price.session_date), func.count())
            .join(DataSource)
            .where(Price.security_id == s.security_id, DataSource.name == "YAHOO_CHART:eod")
        ).one()
        st = defaultdict(int)
        for x in snaps:
            if x["security_id"] == s.security_id:
                st[(x["meta"].get("fundamental_status") or "NONE")] += 1
        reason = None
        if tk in DS.BENCH_TICKERS:
            reason = "BENCHMARK_SERIES (not a research security)"
        elif s.security_id not in snap_secs:
            reason = "PRICES: fewer than 30 bars" if dates[2] < 30 else "OTHER: no snapshots built"
        eligibility = [
            FM.first_ml_eligibility(
                ctx, x, targets12.get((x["security_id"], x["decision_at"])), family="PRICE"
            )
            for x in snaps
            if x["security_id"] == s.security_id
        ]
        eligible_rows = sum(r["eligible"] for r in eligibility)
        exclusion_reasons = dict(Counter(reason for r in eligibility for reason in r["reasons"]))
        if reason is None and not eligible_rows:
            reason = "; ".join(sorted(exclusion_reasons)) or "NO_ELIGIBLE_SNAPSHOTS"
        audit.append({"eligible_12m_rows": eligible_rows, "exclusion_reasons": exclusion_reasons,"security_id": s.security_id, "ticker_at_T": tk, "issuer_id": s.issuer_id, "market": s.exchange, "first_date": str(dates[0]), "last_date": str(dates[1]), "bars": dates[2], "identity_status": ("RESOLVED" if s.security_id in identity_ok else "UNRESOLVED_SECURITY_LINK") if s.exchange == "XNYS" else "NOT_ASSESSED_NON_US", "price_status": "YAHOO_CANONICAL (per-series QA required)", "fundamental_status": max(st, key=lambda k: st[k]) if st else "NONE", "reason_not_usable": reason})  # fmt: skip
    in_cfg = {t for t in cfg_tickers}
    have = {a["ticker_at_T"] for a in audit}
    missing_cfg = sorted(t for t in in_cfg if t not in have)
    research = [
        a
        for a in audit
        if a["ticker_at_T"] not in DS.BENCH_TICKERS and a["security_id"] in snap_secs
    ]
    js["security_audit"] = audit
    js["coverage"] = {"required": C.REQUIRED_SECURITIES, "configured_tickers": len(cfg_tickers) - 3, "with_prices": len([a for a in audit if a["ticker_at_T"] not in DS.BENCH_TICKERS]), "with_snapshots": len(research), "identity_ready": sum(a["security_id"] in identity_ok for a in research), "configured_labels_unmatched": [t for t in missing_cfg if t not in DS.BENCH_TICKERS],
                      "usable_strict": out["strict_PRICE"]["securities_with_eligible_rows"], "usable_preview": out["preview_if_D05_accepted_PRICE"]["securities_with_eligible_rows"]}  # fmt: skip
    # ---- benchmark table ------------------------------------------------------------------------------------------------------
    bt: dict[tuple[Any, ...], Counter[str]] = defaultdict(Counter)
    for (sid, _), t in targets12.items():
        bc = t["details"].get("benchmark_contract") or {}
        sec = next((s for s in securities if s.security_id == sid), None)
        if sec is None:
            continue
        key = (
            sec.exchange,
            DS.REGION.get(sec.exchange),
            bc.get("security_currency"),
            bc.get("benchmark_id"),
            bc.get("benchmark_currency"),
            bc.get("benchmark_return_type"),
            bc.get("return_currency_basis"),
            bc.get("benchmark_quality_status"),
        )
        bt[key]["rows"] += 1
        bt[key]["comparable"] += 1 if bc.get("comparability") == "COMPARABLE" else 0
        bt[key]["immature"] += 1 if t["status"] != "OK" else 0
    brows = [
        [*k, f"{v['comparable']}/{v['rows']}", "—" if v["comparable"] else "no comparable rows"]
        for k, v in sorted(bt.items(), key=lambda kv: str(kv[0]))
    ]
    js["benchmark_table"] = [[*map(str, k), dict(v)] for k, v in bt.items()]
    mism = Counter(
        (t["details"].get("benchmark_contract") or {}).get("comparability")
        for t in targets12.values()
        if t["status"] == "OK"
    )
    cur = Counter(
        (t["details"].get("benchmark_contract") or {}).get("currency_conversion_method")
        for t in targets12.values()
        if t["status"] == "OK"
    )
    js["comparability"] = dict(mism)
    js["currency_methods"] = dict(cur)
    # ---- gates ----------------------------------------------------------------------------------------------------------------
    bad_holdout = sum(1 for s in snaps if C.HOLDOUT[0] <= s["decision_session"] <= C.HOLDOUT[1])
    us_rows = [
        (k, t)
        for k, t in targets12.items()
        if t["status"] == "OK"
        and (t["details"].get("benchmark_contract") or {}).get("security_currency") == "USD"
    ]
    us_ok = sum(
        1
        for _, t in us_rows
        if (t["details"]["benchmark_contract"]).get("comparability") == "COMPARABLE"
    )
    fund_ready = fm["n_ok"] >= C.REQUIRED_FUNDAMENTAL_SECURITIES
    d02_ready = bool(rf.flags["D02_MONTHLY_RESEARCH_READY"]) and len(plan.folds) >= C.MIN_FOLDS
    gates = {
        "D02_MONTHLY_RESEARCH_READY": FM.gate(
            "READY" if d02_ready else "BLOCKED",
            f">= {C.MIN_FOLDS} feasible walk-forward folds on consecutive READY months",
            f"{d02['ready_months']}/{d02['total_months']} months READY, longest run {d02['longest_run']}, folds {d02['feasible_folds']}",
            None if d02_ready else (plan.reason_if_none or "existing D02 gate false"),
        ),
        "US_SECURITY_IDENTITY_READY": FM.gate(
            "READY" if rf.flags["US_SECURITY_IDENTITY_READY"] else "PARTIAL",
            "0 weak identity members, 0 unresolved lines",
            "see D02 graph metrics",
            None
            if rf.flags["US_SECURITY_IDENTITY_READY"]
            else "unresolved identity evidence; see D02 graph metrics",
        ),
        "D05_READY": FM.gate(
            "READY" if rf.flags["US_D05_RESEARCH_READY"] else "BLOCKED",
            "accepted prices + corporate actions + adjustment method + provenance",
            "Yahoo Finance (CANONICAL_PROVIDER_FOR_PITQUANT, VENDOR)",
            None
            if rf.flags["US_D05_RESEARCH_READY"]
            else "per-series quality checks remain blocked; see d05_quality and D05_YAHOO_QA.json",
        ),
        "BENCHMARK_RETURN_BASIS_READY": FM.gate(
            "READY"
            if us_rows
            and us_ok == len(us_rows)
            and any(DS._ticker(S, r["security_id"]) == "SPY" and r["status"] == "READY" for r in qa)
            else "PARTIAL",
            "first ML US scope: comparable return + currency basis, accepted provenance",
            f"US rows comparable {us_ok}/{len(us_rows)}; non-US via USD conversion (PROXY)",
            None
            if us_rows and us_ok == len(us_rows)
            else "US return-basis comparability incomplete; Spain: IBEX Total Return not verified, ^IBEX price-only",
        ),
        "RESEARCH_SECURITY_COVERAGE_READY": FM.gate(
            "READY" if js["coverage"]["usable_strict"] >= C.REQUIRED_SECURITIES else "BLOCKED",
            f">= {C.REQUIRED_SECURITIES} usable securities",
            f"{js['coverage']['usable_strict']} usable (strict); {js['coverage']['usable_preview']} if D05 were accepted; {js['coverage']['with_snapshots']} with snapshots",
            "fewer than 100 securities satisfy all PIT eligibility conditions; see the per-security audit",
        ),
        "US_FUNDAMENTALS_READY": FM.gate(
            "READY" if fund_ready else "BLOCKED",
            f">= {C.REQUIRED_FUNDAMENTAL_SECURITIES} securities with >= {C.REQUIRED_FUNDAMENTAL_MONTHS} usable PIT months",
            f"{fm['n_ok']} securities",
            None if fund_ready else "below the required count",
        ),
        "HOLDOUT_SEALED": FM.gate(
            "READY" if bad_holdout == 0 else "BLOCKED",
            "0 research rows inside 2022-10-01..2025-09-30",
            f"{bad_holdout} snapshots inside the holdout",
            None if bad_holdout == 0 else "holdout rows present",
        ),
    }
    gates["RESEARCH_DATA_READY"] = FM.gate("READY" if all(gates[g]["status"] == "READY" for g in ("D02_MONTHLY_RESEARCH_READY", "US_SECURITY_IDENTITY_READY", "D05_READY", "BENCHMARK_RETURN_BASIS_READY", "RESEARCH_SECURITY_COVERAGE_READY", "US_FUNDAMENTALS_READY")) else "BLOCKED", "all data gates READY", "derived", "at least one data gate is not READY")  # fmt: skip
    ml = FM.first_ml_baseline_ready(gates, FM.REQUIRED_GATES)
    gates["FIRST_ML_BASELINE_READY"] = FM.gate(
        "READY" if ml else "BLOCKED",
        "all required gates READY",
        str(ml).lower(),
        None
        if ml
        else "required gates not READY: "
        + ", ".join(g for g in FM.REQUIRED_GATES if gates[g]["status"] != "READY"),
    )
    js["gates"] = gates
    # ---- write ----------------------------------------------------------------------------------------------------------------
    md: list[str] = []
    w = md.append
    w("# DATA READINESS FOR FIRST ML (generado desde la base)\n")
    w(
        f"Generado {js['generated_at'][:19]}Z · experimento preparado `{C.EXPERIMENT_ID}` (NO ejecutado). Fuente de datos de mercado y FX: **Yahoo Finance** (decisión del propietario; VENDOR, `CANONICAL_PROVIDER_FOR_PITQUANT`). Ningún gate se ha bajado: `required_securities = {C.REQUIRED_SECURITIES}`.\n"
    )
    w("## Matriz de gates\n")
    w(
        table(
            [
                [g, v["required"], v["actual"], v["status"], v["blocking_reason"]]
                for g, v in gates.items()
            ],
            ["Gate", "Required", "Actual", "Status", "Blocking reason"],
        )
    )
    w(f"`FIRST_ML_BASELINE_READY = {str(ml).lower()}` (calcularlo no entrena nada).\n")
    w(
        "La matriz corresponde al primer ML. Los `flags` del JSON describen el Research Lab histórico y su disponibilidad para recopilar features; no autorizan entrenamiento ni sustituyen estos gates.\n"
    )
    w("## D02 mensual\n")
    w(table([[k, v] for k, v in d02.items()], ["métrica", "valor"]))
    w(
        "Walk-forward factible (train_min 36, purge 12, embargo 1, test 12): "
        + (f"{len(plan.folds)} folds" if plan.folds else f"**0 folds** — {plan.reason_if_none}")
        + "\n"
    )
    w(
        table(
            [
                [
                    m["month"],
                    m["expected_universe"],
                    m["resolved_members"],
                    m["unresolved_members"],
                    m["identity_resolved"],
                    m["membership_evidence"],
                    m["status"],
                    m["blocking_reason"],
                ]
                for m in months
            ],
            [
                "month",
                "expected_universe",
                "resolved_members",
                "unresolved_members",
                "identity_resolved",
                "membership_evidence",
                "status",
                "blocking_reason",
            ],
        )
    )
    w("## Cobertura de securities frente al requisito de 100\n")
    w(table([[k, v] for k, v in js["coverage"].items()], ["métrica", "valor"]))
    w(
        table(
            [
                [
                    a["security_id"][:8],
                    a["ticker_at_T"],
                    (a["issuer_id"] or "")[:8],
                    a["market"],
                    a["first_date"],
                    a["last_date"],
                    a["identity_status"],
                    a["price_status"],
                    a["fundamental_status"],
                    a["reason_not_usable"],
                ]
                for a in audit
            ],
            [
                "security_id",
                "ticker_at_T",
                "issuer_id",
                "market",
                "first_date",
                "last_date",
                "identity_status",
                "price_status",
                "fundamental_status",
                "reason_not_usable",
            ],
        )
    )
    w("## Fundamentales: securities con ≥36 meses PIT utilizables\n")
    w(
        f"{fm['n_ok']} de los que tienen snapshots (requeridos {C.REQUIRED_FUNDAMENTAL_SECURITIES}).\n"
    )
    w(
        table(
            [
                [t, v["usable_months"], v["first"], v["last"], v["snapshots"]]
                for t, v in sorted(
                    js["fundamentals"]["per_security"].items(),
                    key=lambda kv: -kv[1]["usable_months"],
                )
            ],
            ["ticker", "meses utilizables", "primero", "último", "snapshots"],
        )
    )
    w("## Embudo de filas (12M)\n")
    for k, v in out.items():
        w(f"### {k}\n")
        w(
            table(
                [
                    ["raw snapshots", v["raw"]],
                    *[[f"− {r}", n] for r, n in v["removed_by"].items() if n],
                    ["= eligible", v["eligible"]],
                    ["securities con filas elegibles", v["securities_with_eligible_rows"]],
                ],
                ["etapa", "filas"],
            )
        )
    w("## Benchmarks por mercado (12M)\n")
    w(
        table(
            brows,
            [
                "market",
                "region",
                "security_ccy",
                "benchmark",
                "bench_ccy",
                "return_type",
                "currency_basis",
                "quality",
                "comparables/filas",
                "bloqueo",
            ],
        )
    )
    w("## Blockers restantes y mínima acción correcta\n")
    w(
        table(
            [
                [name, data["status"], data["actual"], data["blocking_reason"]]
                for name, data in gates.items()
                if data["status"] != "READY"
            ],
            ["gate", "estado", "actual", "bloqueo técnico"],
        )
    )
    w(
        "PPoG→PPG está aprobado y aplicado como alias documental. La extensión SEC requiere el correo de contacto; no se inventan anclas anteriores.\n"
    )
    bc_md = [
        "# Contrato de retorno de benchmark (ADR-0049, generado)\n",
        "Versión `"
        + BC.BENCHMARK_CONTRACT_VERSION
        + "`. `future_excess_total_return = retorno total del valor − retorno del benchmark`, sólo si ambos están en la MISMA base de retorno y de divisa.\n",
        "## Reglas\n",
        "* Valor con retorno total frente a benchmark de precio (`PRICE_RETURN`) ⇒ `PRICE_RETURN_ONLY` / `NOT_COMPARABLE_RETURN_BASIS`: el exceso NO se calcula (NULL) y la fila queda fuera del ML.",
        "* Divisa distinta: el valor se convierte a USD en cada instante con FX PIT (`fx_rates`, Yahoo, VENDOR/CANONICAL, disponible a las 00:00 UTC del día siguiente a la cotización; máx. 7 días de antigüedad). Sin FX ⇒ `FX_MISMATCH` / `FX_DATA_NOT_READY`. Nunca el tipo actual para el histórico.",
        "* ETF ⇒ siempre `ETF_PROXY`, nunca el índice oficial. `READY` se reserva a una serie oficial de retorno total; `PROXY_ACCEPTABLE` (ETF con dividendos y base comparable) es el estado aprobado por metodología para el primer ML. `APPROVED_FOR_ML = {READY, PROXY_ACCEPTABLE}`.",
        "* Benchmarks: XNYS→SPY; XMAD→IBEX 35 Total Return (ES0SI0000047) **MISSING**, `^IBEX` es sólo precio (`PRICE_RETURN_ONLY`), fallback URTH+FX diagnóstico; resto→URTH+FX (URTH empieza en 2012-01).",
        "* Campos guardados por fila (`research_targets.details.benchmark_contract`): benchmark_id, benchmark_security_id, benchmark_name, benchmark_type, benchmark_return_type, benchmark_currency, security_currency, return_currency_basis, currency_conversion_method, fx_source, fx_available_at, fx_rate_date, benchmark_start_price, benchmark_end_price, benchmark_total_return, benchmark_source, benchmark_version, benchmark_provenance, benchmark_quality_status, comparability, skipped_candidates.\n",
        "## Estado por mercado (horizonte 12M, filas con objetivo calculable o no)\n",
        table(
            brows,
            [
                "market",
                "region",
                "security_ccy",
                "benchmark",
                "bench_ccy",
                "return_type",
                "currency_basis",
                "quality",
                "comparables/filas",
                "bloqueo",
            ],
        ),
        "## Resumen\n",
        table(
            [[k, v] for k, v in sorted(js["comparability"].items(), key=lambda kv: str(kv[0]))],
            ["comparabilidad (filas OK)", "n"],
        ),
        table(
            [[k, v] for k, v in sorted(js["currency_methods"].items(), key=lambda kv: str(kv[0]))],
            ["método de conversión (filas OK)", "n"],
        ),
    ]
    Path(ROOT / "docs/BENCHMARK_RETURN_CONTRACT.md").write_text("\n".join(bc_md), encoding="utf-8")
    Path(ROOT / "docs/DATA_READINESS_FIRST_ML.md").write_text("\n".join(md), encoding="utf-8")
    Path(ROOT / "docs/DATA_READINESS_FIRST_ML.json").write_text(
        json.dumps(js, default=str, indent=1), encoding="utf-8"
    )
    print(
        json.dumps({k: v["status"] for k, v in gates.items()}, indent=1),
        json.dumps(js["coverage"], default=str),
        json.dumps({k: (v["raw"], v["eligible"]) for k, v in out.items()}),
    )


if __name__ == "__main__":
    main()
