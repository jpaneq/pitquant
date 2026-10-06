#!/usr/bin/env python3
"""Audit only frozen DEV artifacts; never construct or fit an estimator."""

# ruff: noqa: E501
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from threadpoolctl import threadpool_limits

from pitquant.research import equity_baseline as E
from pitquant.research import equity_return as R
from pitquant.research import equity_v1 as V
from pitquant.research import first_ml_contract as C
from pitquant.research import return_failure_audit as A
from pitquant.research.metrics import spearman

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PREFIX = "FIRST_EQUITY_RETURN_12M_V0_FAILURE_AUDIT"


def load(name: str) -> Any:
    path = DOCS / name
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if name.endswith(".gz") else raw)


def verify(ledger: dict[str, str]) -> None:
    for name, sha in ledger.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != sha:
            raise ValueError("immutable source changed STOP: " + name)


def ks_distance(x: A.Array, y: A.Array) -> float:
    values = np.sort(np.concatenate((x, y)))
    return float(
        np.max(
            np.abs(
                np.searchsorted(np.sort(x), values, side="right") / len(x)
                - np.searchsorted(np.sort(y), values, side="right") / len(y)
            )
        )
    )


def run() -> dict[str, Any]:
    design = load(PREFIX + "_DESIGN.json")
    verify(design["frozen_files"])
    data = load("FIRST_EQUITY_ML_12M_V0_DATASET.json.gz")
    if E.digest(data) != V.DATA_HASH:
        raise ValueError("dataset hash mismatch")
    A.safe_rows(data)
    models = load("FIRST_EQUITY_RETURN_12M_V0_MODELS.json.gz")
    ret = load("FIRST_EQUITY_RETURN_12M_V0_OOF.json")
    direction = load("FIRST_EQUITY_ML_12M_V1_OOF.json")
    dmodels = load("FIRST_EQUITY_ML_12M_V1_MODELS.json")
    old_report = load("FIRST_EQUITY_RETURN_12M_V0_REPORT.json")
    report = {
        "design_hash": E.digest(design),
        "initial_head": design["initial_head"],
        "dev_adaptive_iteration": 2,
        "new_fits": 0,
        "holdout_outcomes_accessed": 0,
        "oot_outcomes_accessed": 0,
        "frozen_ledger_verified": True,
        "candidate_count": 0,
        "inner_model_count": 0,
        "folds": {},
        "raw_feature_stability": {},
        "family_descriptive": {},
        "limitations": [
            "DEV adaptively inspected; overlapping H12 labels prevent IID significance claims.",
            "TRAIN replay is in-sample, never OOF; no unselected candidate outer TEST predictions generated.",
            "Archived USD/TOTAL_RETURN/SPY and target/binary/hash contracts checked. Original corporate-action and vendor price legs are not present in this frozen dataset: absence of upstream vendor/CA bugs cannot be certified. No internal mismatch detected.",
            "Within-sector uses existing coarse sector_group, not a fitted neutralized model.",
            "Pareto/ranking candidates are diagnostics, not a retrospectively selected challenger.",
            "Raw family means describe feature IC distributions, not composite prediction scores.",
        ],
    }
    for fold in data["folds"]:
        fid = "F" + str(fold["index"])
        surface = A.candidate_surface(fold, models)
        report["candidate_count"] += sum(len(s["candidates"]) for s in surface.values())
        report["inner_model_count"] += sum(
            len(c["inners"]) for s in surface.values() for c in s["candidates"]
        )
        rows = fold["TEST"]
        scores = {}
        for model in ("R0", "R2", "R3", "R4"):
            records = {
                V.key(r): r for r in ret if r["fold_id"] == fold["index"] and r["model_id"] == model
            }
            if set(records) != {V.key(r) for r in rows}:
                raise ValueError("outer OOF coverage mismatch")
            if any(records[V.key(r)]["realized_excess_return"] != r["excess_return"] for r in rows):
                raise ValueError("outer targets mismatch STOP")
            scores[model] = np.asarray([records[V.key(r)]["predicted_excess_return"] for r in rows])
        drecords = {
            V.key(r): r
            for r in direction
            if r["fold_id"] == fold["index"] and r["model_id"] == "M4R"
        }
        if set(drecords) != {V.key(r) for r in rows}:
            raise ValueError("direction common cohort mismatch")
        scores["M4R"] = np.asarray([drecords[V.key(r)]["raw_score"] for r in rows])
        raw = A.raw_features(rows)
        months = {}
        for month in sorted({r["decision_at"][:7] for r in rows}):
            months[month] = A.distribution(
                [r["excess_return"] for r in rows if r["decision_at"][:7] == month]
            )
        extremes = {}
        for role in ("TRAIN", "TEST"):
            ordered = sorted(
                fold[role], key=lambda r: (r["excess_return"], r["security_id"], r["decision_at"])
            )
            n = int(np.ceil(0.01 * len(ordered)))
            extremes[role] = {
                tail: [
                    {
                        k: r[k]
                        for k in (
                            "security_id",
                            "issuer_id",
                            "decision_at",
                            "excess_return",
                            "target_id",
                            "target_end",
                            "benchmark_id",
                        )
                    }
                    | {
                        "ticker": r["source_meta"].get("ticker"),
                        "sector_group": r["source_meta"].get("sector_group"),
                    }
                    for r in selected
                ]
                for tail, selected in (("bottom1", ordered[:n]), ("top1", ordered[-n:]))
            }
        regimes = {}
        for regime in sorted({r["regime"] or "UNKNOWN" for r in rows}):
            idx = [i for i, r in enumerate(rows) if (r["regime"] or "UNKNOWN") == regime]
            sub = [rows[i] for i in idx]
            regimes[regime] = {
                "target": A.distribution(R.target(sub)),
                "model_ic": {m: A.monthly_ic(sub, p[idx]) for m, p in scores.items()},
                "feature_ic": A.raw_features(sub),
            }
        x, _ = A.replay(dmodels[fid + "-M4R"]["base"], rows)
        coefs = np.asarray(dmodels[fid + "-M4R"]["base"]["coefficients"])
        names = dmodels[fid + "-M4R"]["base"]["transformed_features"]
        contributions = {}
        for family, features in (
            ("PRICE", C.PRICE_FAMILY),
            ("FUNDAMENTALS", C.FUNDAMENTAL_FAMILY),
            ("RISK", C.RISK_FAMILY),
        ):
            idx = [i for i, name in enumerate(names) if name.removesuffix("__missing") in features]
            contributions[family] = {
                "coefficient_l1": float(np.abs(coefs[idx]).sum()),
                "mean_abs_fixed_logit_contribution": float(np.abs(x[:, idx] @ coefs[idx]).mean()),
                "interpretation": "fixed existing model decomposition, not counterfactual predictions or performance attribution",
            }
        overlap = []
        if fold["index"] == 1:
            bucket_rows = {
                m: [
                    {
                        "decision_at": r["decision_at"],
                        "security_id": r["security_id"],
                        "raw_score": float(p[i]),
                        "future_excess_return_12m": r["excess_return"],
                        "actual_target": r["actual_target"],
                    }
                    for i, r in enumerate(rows)
                ]
                for m, p in scores.items()
                if m in ("R4", "M4R")
            }
            # Frozen buckets use average ranks; independently duplicate only membership formula.
            from scipy.stats import rankdata

            for month in months:
                ids = [i for i, r in enumerate(rows) if r["decision_at"][:7] == month]
                buckets = {
                    m: np.minimum(
                        4,
                        np.floor(
                            5 * (rankdata(scores[m][ids], method="average") - 0.5) / len(ids)
                        ).astype(int),
                    )
                    for m in bucket_rows
                }
                detail = {"month": month}
                for name, q in (("bottom20", 0), ("top20", 4)):
                    a = {i for i, b in zip(ids, buckets["R4"], strict=True) if b == q}
                    b = {i for i, z in zip(ids, buckets["M4R"], strict=True) if z == q}
                    detail[name] = {
                        "r4_n": len(a),
                        "m4r_n": len(b),
                        "intersection_n": len(a & b),
                        "overlap_fraction_r4": len(a & b) / len(a) if a else None,
                        "jaccard": len(a & b) / len(a | b) if a | b else None,
                    }
                overlap.append(detail)
        inners = V.inner_folds(fold)
        inner_validation = [r for inner in inners for r in inner["validation"]]
        reference = min(r["decision_at"] for r in rows)
        report["folds"][fid] = {
            "surface": surface,
            "target_train": A.distribution(R.target(fold["TRAIN"])),
            "target_test": A.distribution(R.target(rows)),
            "test_monthly_dispersion": months,
            "inner_validation_monthly_dispersion": {
                month: A.distribution(
                    [r["excess_return"] for r in inner_validation if r["decision_at"][:7] == month]
                )
                for month in sorted({r["decision_at"][:7] for r in inner_validation})
            },
            "extremes": extremes,
            "raw_features": raw,
            "raw_train_features": A.raw_features(fold["TRAIN"]),
            "regimes": regimes,
            "sectors": A.sector_diagnostics(rows, scores),
            "train_age": A.age(fold["TRAIN"], reference),
            "inner_train_age": [A.age(i["train"], i["fit_at"]) for i in inners],
            "direction_return": {
                "score_pearson": A.correlation(scores["M4R"], scores["R4"]),
                "score_spearman": spearman(scores["M4R"], scores["R4"]),
                "overlap_months": overlap,
                "constant_return": bool(np.ptp(scores["R4"]) == 0),
                "fixed_direction_family_contributions": contributions,
            },
            "outer_metrics": {
                m: A.metrics(R.target(rows), p) for m, p in scores.items() if m != "M4R"
            },
            "outer_monthly_ic": {m: A.monthly_ic(rows, p) for m, p in scores.items()},
        }
    for feature in C.M4.features:
        means = [
            report["folds"][f]["raw_features"][feature]["summary"]["mean"]
            for f in ("F1", "F2", "F3")
        ]
        valid = [v for v in means if v is not None]
        report["raw_feature_stability"][feature] = {
            "ic_f1_f2_f3": means,
            "mean": float(np.mean(valid)) if valid else None,
            "std": float(np.std(valid)) if valid else None,
            "all_same_nonzero_sign": (len(valid) == 3 and all(v > 0 for v in valid))
            or (len(valid) == 3 and all(v < 0 for v in valid)),
        }
    for family, features in (
        ("PRICE", C.PRICE_FAMILY),
        ("FUNDAMENTALS", C.FUNDAMENTAL_FAMILY),
        ("RISK", C.RISK_FAMILY),
    ):
        report["family_descriptive"][family] = {
            "fold_feature_mean_ic_distribution": {
                f: A.distribution(
                    [
                        report["folds"][f]["raw_features"][name]["summary"]["mean"]
                        for name in features
                        if report["folds"][f]["raw_features"][name]["summary"]["mean"] is not None
                    ]
                )
                for f in ("F1", "F2", "F3")
            },
            "same_sign_features": [
                name
                for name in features
                if report["raw_feature_stability"][name]["all_same_nonzero_sign"]
            ],
        }
    y1 = R.target(data["folds"][0]["TEST"])
    report["target_drift"] = {
        f"F1_vs_F{i}": {
            "ks_distance": ks_distance(y1, R.target(data["folds"][i - 1]["TEST"])),
            "standardized_mean_difference": float(
                (R.target(data["folds"][i - 1]["TEST"]).mean() - y1.mean())
                / np.sqrt((np.var(y1) + np.var(R.target(data["folds"][i - 1]["TEST"]))) / 2)
            ),
        }
        for i in (2, 3)
    }
    report["direction_reference"] = old_report["direction_ranking_reference"]
    consistent_candidates = {
        f: {m: s["ranking_positive_majority"] for m, s in report["folds"][f]["surface"].items()}
        for f in ("F2", "F3")
    }
    raw_consistent = [
        name
        for name in C.M4.features
        if all(
            report["folds"][f]["raw_features"][name]["summary"]["mean"] is not None
            and report["folds"][f]["raw_features"][name]["summary"]["mean"] > 0
            and report["folds"][f]["raw_features"][name]["summary"]["positive_fraction"] > 0.5
            for f in ("F2", "F3")
        )
    ]
    objective = all(any(c for c in consistent_candidates[f].values()) for f in ("F2", "F3"))
    tails = all(
        report["folds"][f]["surface"]["R4"]["selected_inner_loss"]["top_tail_squared_share"]["0.01"]
        > 0.5
        for f in ("F2", "F3")
    )
    breakdown = not raw_consistent and not any(
        c for f in consistent_candidates.values() for c in f.values()
    )
    report["decision_evidence"] = {
        "consistent_candidates": consistent_candidates,
        "raw_features_positive_majority_both_folds": raw_consistent,
        "objective_mismatch_criterion": objective,
        "outlier_dominance_criterion": tails,
        "total_breakdown_criterion": breakdown,
        "regime_dependence": "insufficient independent months/replication for definitive causal attribution",
    }
    # A screening condition is insufficient when recycled early inner months mask drift.
    changed_signs = [
        name
        for name, item in report["raw_feature_stability"].items()
        if all(v is not None for v in item["ic_f1_f2_f3"])
        and min(item["ic_f1_f2_f3"]) < 0 < max(item["ic_f1_f2_f3"])
    ]
    temporal_mixed = objective and bool(changed_signs)
    report["decision_evidence"]["raw_features_sign_changes"] = changed_signs
    report["decision_evidence"]["reused_inner_period_warning"] = (
        "F2 and F3 inner OOF share 2017-2018 months; positive available-month IC is not independent replication. "
        "Best nonzero R2 has defined IC in only the same six 2017 months in both folds. "
        "Best nonzero R3/R4 IC turns negative in the three latest inner periods."
    )
    report["classification"] = (
        "CASE E — MIXED"
        if temporal_mixed or (objective and tails)
        else "CASE A — MAGNITUDE_OBJECTIVE_MISMATCH"
        if objective
        else "CASE C — OUTLIER_LOSS_DOMINANCE"
        if tails
        else "CASE B — TEMPORAL_SIGNAL_BREAKDOWN"
        if breakdown
        else "CASE E — MIXED"
    )
    report["recommendation"] = (
        "NO_FURTHER_MODEL_EXPERIMENT_JUSTIFIED"
        if temporal_mixed or not objective
        else (
            "CROSS_SECTIONAL_RANK_OBJECTIVE — candidate for human-approved final iteration 3; no automatic fit"
        )
    )
    report["recommendation_reason"] = (
        "Objective trade-off exists, but archived inner periods overlap and recent R3/R4 ranking deteriorates. "
        "Raw PRICE/RISK signs change, F3 Direction fails, and F3 regime lacks BEAR counterfactual. "
        "No evidence isolates one loss/objective intervention likely to repair forward stability. "
        "Do not consume last structural iteration merely by changing algorithm."
    )
    if report["candidate_count"] != 315 or report["inner_model_count"] != 945:
        raise ValueError("full surface not covered")
    verify(design["frozen_files"])
    return report


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Auditoría del fallo del modelo Return 12M",
        "",
        report["classification"],
        "",
        "Recomendación: " + report["recommendation"],
        "",
        "Auditoría sin ajustes nuevos: 315 candidatos, 945 ajustes internos archivados. Iteración DEV permanece en 2. Holdout y OOT: cero. Fuentes originales verificadas por SHA-256 antes y después.",
        "",
        "## Selección y ranking interno",
        "",
        "| Fold/modelo | Margen MAE | Mejor cero MAE | Mejor no cero MAE | IC mensual mejor no cero | Pareto (MAE/IC agrupado) |",
        "|---|---:|---:|---:|---:|---|",
    ]

    def fmt(value: Any) -> str:
        return "NA" if value is None else f"{value:.6g}"

    for fold, details in report["folds"].items():
        for model, s in details["surface"].items():
            zero, nonzero = s["best_zero"], s["best_nonzero"]
            lines.append(
                f"| {fold}/{model} | {fmt(s['selection_margin']['absolute'])} | {fmt(zero['validation']['mae'] if zero else None)} | {fmt(nonzero['validation']['mae'] if nonzero else None)} | {fmt(nonzero['monthly_ic']['summary']['mean'] if nonzero else None)} | {', '.join(s['pareto']['non_dominated'])} |"
            )
    lines += [
        "",
        "El margen ordena MAE sin redondeo; el selector original conserva tolerancia 1e-12, alpha mayor, menor complejidad y menor l1_ratio. Un margen cero puede deberse a varios candidatos constantes idénticos. No se cambia el ganador. Complejidad no cero significa media de ajustes internos; no implica que el ajuste exterior no seleccionado exista.",
        "",
        "## Colapso de coeficientes",
        "",
        "| Fold/modelo | Máximo gradiente | Umbral L1 | Condición cero |",
        "|---|---:|---:|---|",
    ]
    for f, d in report["folds"].items():
        for m, s in d["surface"].items():
            k = s["selected_outer_zeroing"]
            lines.append(
                f"| {f}/{m} | {fmt(k['max_gradient'])} | {fmt(k['l1_threshold'])} | {k['zero_optimum_condition']} |"
            )
    lines += [
        "",
        "Con intercepto sin penalizar, el óptimo cero requiere max |X centradaᵀ y centrado / n| ≤ alpha × l1_ratio. Se reconstruye X con los parámetros archivados; no se estiman estadísticas nuevas. Las columnas numéricas tienen escala archivada; los indicadores de faltantes permanecen sin estandarizar.",
        "",
        "## Colas y drift",
        "",
        "| Fold | TRAIN/TEST media | TEST desviación | Top 10% / 5% / 1% error cuadrático interno R4 seleccionado |",
        "|---|---|---:|---|",
    ]
    for f, d in report["folds"].items():
        t = d["surface"]["R4"]["selected_inner_loss"]["top_tail_squared_share"]
        lines.append(
            f"| {f} | {fmt(d['target_train']['mean'])} / {fmt(d['target_test']['mean'])} | {fmt(d['target_test']['std'])} | {' / '.join(fmt(100 * t[p]) + '%' for p in ('0.1', '0.05', '0.01'))} |"
        )
    lines += [
        "",
        "Drift descriptivo: `"
        + json.dumps(report["target_drift"], ensure_ascii=False)
        + "`. No se publican p-values IID: los retornos de 12 meses se solapan.",
        "",
        "## Evidencia y límites",
        "",
        "`" + json.dumps(report["decision_evidence"], ensure_ascii=False) + "`",
        "",
    ]
    lines += [
        "",
        report["recommendation_reason"],
        "",
        "## Señal temporal, familias y sectores",
        "",
        "| Familia | Media de IC individuales F1 / F2 / F3 | Features con signo estable |",
        "|---|---|---|",
    ]
    for family, item in report["family_descriptive"].items():
        lines.append(
            f"| {family} | {' / '.join(fmt(item['fold_feature_mean_ic_distribution'][f]['mean']) for f in ('F1', 'F2', 'F3'))} | {len(item['same_sign_features'])} |"
        )
    lines += [
        "",
        "Estas medias no indican que una familia con IC negativo carezca de señal: el signo económico difiere entre features. No se reorientan ni seleccionan features.",
        "",
        "| Fold | Dispersión mensual media std / IQR / P90−P10 | Edad TRAIN días | IC R4 global / dentro sector |",
        "|---|---|---:|---|",
    ]
    for f, d in report["folds"].items():
        dispersion = d["test_monthly_dispersion"]
        sector = d["sectors"]["models"]["R4"]
        lines.append(
            f"| {f} | {' / '.join(fmt(sum(v[k] for v in dispersion.values()) / len(dispersion)) for k in ('std', 'iqr', 'p90_p10'))} | {fmt(d['train_age']['days']['mean'])} | {fmt(sector['global_monthly_ic']['summary']['mean'])} / {fmt(sector['within_sector_summary']['mean'])} |"
        )
    lines += [
        "",
        "F1 R4 reduce su IC al comparar dentro de sector, compatible con componente sectorial. F2/F3 permanecen NA por predicción constante. Menor dispersión F3 no demuestra ausencia intrínseca de señal.",
        "",
        "F3 contiene únicamente BULL; no permite contrastar BULL/BEAR dentro de ese fold. F1 y F2 sí contienen ambos, pero sector, tiempo y régimen están confundidos. No se justifica atribuir el fallo exclusivamente al régimen.",
        "",
        "## Direction y Return",
        "",
    ]
    direction = report["folds"]["F1"]["direction_return"]
    lines.append(
        f"Sobre las mismas 476 filas F1: Pearson {fmt(direction['score_pearson'])}, Spearman {fmt(direction['score_spearman'])}. Coincidencia media del quintil superior {fmt(sum(m['top20']['overlap_fraction_r4'] for m in direction['overlap_months']) / 12)}, inferior {fmt(sum(m['bottom20']['overlap_fraction_r4'] for m in direction['overlap_months']) / 12)}. F2/F3 Return constante: comparación de ranking indefinida."
    )
    lines += [
        "",
        "M4R AUC congelado: F1 0.613252, F2 0.600629, F3 0.491293. Su componente fundamental tiene mayor contribución logit absoluta F1; esto no prueba atribución causal ni equivale a rendimiento de un modelo por familia.",
        "",
        "## Squared-loss, MAE y colas",
        "",
        "La función ElasticNet minimiza MSE/(2) + alpha*l1_ratio*norma L1 + alpha*(1-l1_ratio)*norma L2²/2. La selección compara MAE fuera de muestra. El JSON permite comparar el candidato con RMSE mínimo y el seleccionado por MAE, sin cambiarlo. Errores TRAIN son in-sample y no justifican selección.",
        "",
        "Los bins por rango absoluto retienen todos los targets, incluidas colas; los límites usan floor y top 1/5/10% ceil. Las colas influyen materialmente pero no satisfacen el umbral predeclarado de dominancia >50% del error cuadrático en el top1% de F2 y F3. No se justifica Huber solo por observar extremos.",
        "",
    ]
    lines += [
        "",
        "## IC raw por feature (medias mensuales)",
        "",
        "| Feature | F1 | F2 | F3 | Mismo signo |",
        "|---|---:|---:|---:|---|",
    ]
    for name, item in report["raw_feature_stability"].items():
        lines.append(
            f"| {name} | {' | '.join(fmt(v) for v in item['ic_f1_f2_f3'])} | {item['all_same_nonzero_sign']} |"
        )
    lines += [
        "",
        "## Relación entre errores e IC de candidatos",
        "",
        "| Fold/modelo | MAE vs IC agrupado | MAE vs IC mensual | RMSE vs IC mensual | Pareto mensual |",
        "|---|---:|---:|---:|---|",
    ]
    for f, d in report["folds"].items():
        for m, s in d["surface"].items():
            monthly = s["candidate_monthly_correlations"]
            lines.append(
                f"| {f}/{m} | {fmt(s['candidate_correlations']['mae_vs_pooled_ic'])} | {fmt(monthly['mae_vs_mean_monthly_ic'])} | {fmt(monthly['rmse_vs_mean_monthly_ic'])} | {', '.join(s['pareto_monthly']['non_dominated'])} |"
            )
    lines += [
        "",
        "Atención: candidatos constantes dentro de cada periodo interno pueden tener IC agrupado por cambiar el intercepto entre periodos. Por eso el Pareto agrupado solicitado y el Pareto mensual se publican por separado. Los meses con IC indefinido no se convierten en cero; la cobertura debe acompañar cada media.",
        "",
    ]
    lines += ["- " + s for s in report["limitations"]]
    lines += [
        "",
        "## Tablas completas y reproducibilidad",
        "",
        "El JSON contiene los 315 candidatos y las 945 tablas internas con MAE, MSE, RMSE, Pearson, Spearman, normas, complejidad, métricas TRAIN in-sample y validación, descomposición de colas, Pareto, márgenes, KKT, IC raw mensual y TRAIN por antigüedad, familias, regímenes, sectores, extremos y coincidencia de quintiles Direction/Return.",
        "",
        "No se construyen predicciones TEST de candidatos no seleccionados. El IC dentro de sector es mensual, con N ≥ 5 y cobertura explícita. Las medias de familias describen los IC individuales; no son scores nuevos. La edad TRAIN se mide en días respecto a la primera decisión TEST; edad interna respecto a inner fit_at.",
        "",
        "Las tablas raw TRAIN permiten comprobar variación por año/mes sin volver a entrenar ni ponderar. El análisis por régimen conserva BULL/BEAR/UNKNOWN del snapshot y no demuestra causalidad frente a tiempo/sector.",
        "",
        "Ejecutar `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/audit_equity_return.py`. Escritura exclusiva: si existe un resultado diferente se rechaza. Un siguiente ajuste requerirá aprobación humana y será la última iteración estructural 3 sobre estos folds; el holdout permanece sellado.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    with threadpool_limits(limits=1):
        report = run()
    E.immutable_json(DOCS / (PREFIX + ".json"), report)
    path = DOCS / (PREFIX + ".md")
    text = markdown(report).encode()
    if path.exists():
        if path.read_bytes() != text:
            raise ValueError("audit Markdown immutable")
    else:
        with path.open("xb") as handle:
            handle.write(text)
    print(
        json.dumps(
            {
                "classification": report["classification"],
                "candidates": report["candidate_count"],
                "inner_models": report["inner_model_count"],
                "recommendation": report["recommendation"],
            }
        )
    )


if __name__ == "__main__":
    main()
