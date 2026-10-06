#!/usr/bin/env python3
# ruff: noqa: E501
"""Read immutable V1/V0 artifacts; publish descriptive diagnostics, never fit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from pitquant.research import equity_baseline as E

DOCS = Path(__file__).resolve().parents[1] / "docs"
PREFIX = "FIRST_EQUITY_ML_12M_V1"
ORDER = ("M0", "M2", "M3", "M3R", "M3RC", "M4", "M4R", "M4RC")


def fmt(value: Any) -> str:
    return "NA" if value is None else f"{value:.6f}" if isinstance(value, float) else str(value)


def table(models: dict[str, Any]) -> str:
    lines = [
        "| Modelo | AUC | AP | Brier | LogLoss | slope | intercept | ECE | IC | spread |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for m in ORDER:
        v = models[m]
        values = (
            [v[k] for k in ("auc", "ap", "brier", "log_loss")]
            + [v["calibration"][k] for k in ("slope", "intercept", "ece")]
            + [v["rank_ic"], v["quintiles"]["mean_month_spread"]]
        )
        lines.append(
            "| "
            + m
            + (" V0" if m in ("M0", "M2", "M3", "M4") else "")
            + " | "
            + " | ".join(fmt(x) for x in values)
            + " |"
        )
    return "\n".join(lines)


def diagnostics(
    report: dict[str, Any], models: dict[str, Any], old_models: dict[str, Any]
) -> dict[str, Any]:
    coefficients = {}
    stability = {}
    for m in ("M3", "M4"):
        for name in (m, m + "R"):
            a = [
                old_models[f"F{i}-{m}"] if name == m else models[f"F{i}-{name}"]["base"]
                for i in (1, 2, 3)
            ]
            cs = np.array([r["coefficients"] for r in a])
            n = len(a[0]["features"])
            coefficients[name] = {
                "raw_features": n,
                "all_coefficients": cs.shape[1],
                "sign_consistent_raw": int(
                    np.sum(np.all(np.sign(cs[:, :n]) == np.sign(cs[0, :n]), axis=0))
                ),
                "sign_consistent_all": int(np.sum(np.all(np.sign(cs) == np.sign(cs[0]), axis=0))),
                "mean_std_raw": float(np.mean(np.std(cs[:, :n], axis=0))),
                "median_std_raw": float(np.median(np.std(cs[:, :n], axis=0))),
                "mean_std_all": float(np.mean(np.std(cs, axis=0))),
                "l2_norms_all": np.linalg.norm(cs, axis=1).tolist(),
                "l2_norms_raw": np.linalg.norm(cs[:, :n], axis=1).tolist(),
                "per_feature": {
                    feature: {
                        "coefficients": cs[:, j].tolist(),
                        "std": float(np.std(cs[:, j])),
                        "sign_consistent": bool(np.all(np.sign(cs[:, j]) == np.sign(cs[0, j]))),
                    }
                    for j, feature in enumerate(a[0]["transformed_features"])
                },
            }
    for m in ORDER:
        stability[m] = {
            k: {
                "values": [report["per_fold"][f"F{i}"][m][k] for i in (1, 2, 3)],
                "std": float(np.std([report["per_fold"][f"F{i}"][m][k] for i in (1, 2, 3)])),
            }
            for k in ("auc", "log_loss", "brier", "rank_ic")
        }
    return {
        "coefficients": coefficients,
        "fold_stability": stability,
        "selected_c": {
            m: [models[f"F{i}-{m}"]["selected_c"] for i in (1, 2, 3)] for m in ("M3R", "M4R")
        },
        "platt": {key: value["calibrator"] for key, value in models.items()},
        "coefficient_warning": "Standardized coefficients compare fold-specific scales; constant retained features and missing indicators included. No feature selection.",
    }


def classify(r: dict[str, Any], d: dict[str, Any]) -> str:
    p = r["POOLED_DEV_OOF"]
    for m in ("M3R", "M4R"):
        improvement = (
            p[m + "C"]["log_loss"] < p[m]["log_loss"] and p[m + "C"]["brier"] < p[m]["brier"]
        )
        stable = all(
            r["per_fold"][f"F{i}"][m]["auc"] > 0.5
            and r["per_fold"][f"F{i}"][m]["quintiles"]["mean_month_spread"] > 0
            for i in (1, 2, 3)
        )
        if improvement and stable:
            return "CALIBRATION_IMPROVED_SIGNAL_STABLE"
    for m in ("M3R", "M4R"):
        if p[m + "C"]["log_loss"] < p[m]["log_loss"] and p[m + "C"]["brier"] < p[m]["brier"]:
            return "CALIBRATION_IMPROVED_RANKING_UNSTABLE"
    for m in ("M3", "M4"):
        if (
            d["fold_stability"][m + "R"]["auc"]["std"] < d["fold_stability"][m]["auc"]["std"]
            and r["per_fold"]["F3"][m + "R"]["log_loss"] < r["per_fold"]["F3"][m]["log_loss"]
        ):
            return "REGULARIZATION_IMPROVED_STABILITY"
    return (
        "WEAK_UNSTABLE_SIGNAL"
        if any(p[m]["auc"] > 0.5 for m in ("M3R", "M4R"))
        else "NO_REPRODUCIBLE_SIGNAL"
    )


def main() -> None:
    r = json.loads((DOCS / (PREFIX + "_REPORT.json")).read_text())
    m = json.loads((DOCS / (PREFIX + "_MODELS.json")).read_text())
    old = json.loads((DOCS / "FIRST_EQUITY_ML_12M_V0_MODELS.json").read_text())
    d = diagnostics(r, m, old)
    d["classification"] = classify(r, d)
    E.immutable_json(DOCS / (PREFIX + "_DIAGNOSTICS.json"), d)
    lines = [
        "# FIRST_EQUITY_ML_12M_V1",
        "",
        "**RESEARCH_DEV_ONLY · ADAPTIVE_DEV_ITERATION_1 · RETROSPECTIVE_UNVALIDATED**",
        "",
        "V1 se diseñó después de observar V0 DEV. No es confirmación independiente. Holdout y OOT: cero resultados consultados. Sin promoción.",
        "",
        "## Diseño congelado",
        "",
        "Dataset, target, familias y folds externos idénticos a V0. Inner TRAIN expansivo mínimo 18 meses, validación 6 meses, separación H12+embargo1 y madurez efectiva. 1/3/5 validaciones en F1/F2/F3. C seleccionado por LogLoss OOF; empate menor C; preprocessing V0 sin cambios. Platt positivo MLE sólo OOF interna, nunca in-sample ni TEST externo.",
        "",
        "F1 dispone de 222 observaciones para seleccionar C y ajustar Platt: incertidumbre alta. Ambas etapas comparten OOF interna; posible optimismo interno. Ninguna selección usa TEST externo.",
        "",
        "Calibración preserva AUC/AP/IC y quintiles dentro de cada fold y mes. El pooled reúne mapas distintos y puede cambiar su orden temporal. Spreads en fracción de retorno, media mensual con igual peso; no son una estrategia.",
        "",
        "## Métricas por fold (antes de pooled)",
    ]
    for fid in ("F1", "F2", "F3"):
        lines += ["", "### " + fid, "", table(r["per_fold"][fid])]
    lines += [
        "",
        "## POOLED_DEV_OOF",
        "",
        table(r["POOLED_DEV_OOF"]),
        "",
        "M0: AUC=0.5 dentro de cada fold. Su AUC pooled refleja diferencias de prevalencia entre folds, no ranking cross-sectional.",
        "",
        "## C y calibradores",
        "",
        "```json",
        json.dumps({"selected_c": d["selected_c"], "platt": d["platt"]}, indent=2),
        "```",
        "",
        "## Cambio de prevalencia",
        "",
        "```json",
        json.dumps(r["base_rate_shift"], indent=2),
        "```",
        "",
        "## Estabilidad entre folds y coeficientes",
        "",
        "```json",
        json.dumps(
            {
                "fold_stability": d["fold_stability"],
                "coefficients": {
                    k: {a: b for a, b in v.items() if a != "per_feature"}
                    for k, v in d["coefficients"].items()
                },
            },
            indent=2,
        ),
        "```",
        "",
        d["coefficient_warning"],
        "",
        "## Distribuciones de probabilidad",
        "",
        "| Fold | Modelo | min | p05 | p25 | median | p75 | p95 | max |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for fid in ("F1", "F2", "F3"):
        for model in ORDER:
            lines.append(
                "| "
                + fid
                + " | "
                + model
                + " | "
                + " | ".join(
                    fmt(v) for v in r["per_fold"][fid][model]["probability_distribution"].values()
                )
                + " |"
            )
    lines += [
        "",
        "## Quintiles mensuales",
        "",
        "Se agrupan rankings dentro de cada mes; las tablas resumen sus observaciones. El JSON contiene las tablas y spreads de cada mes y fold.",
        "",
        "| Fold | Modelo | Q | N | exceso medio | outperform rate |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for fid, vals in [*r["per_fold"].items(), ("POOLED", r["POOLED_DEV_OOF"])]:
        for model in ("M3R", "M4R"):
            for q in vals[model]["quintiles"]["table"]:
                lines.append(
                    "| "
                    + " | ".join(
                        fmt(x)
                        for x in (
                            fid,
                            model,
                            q["bucket"],
                            q["n"],
                            q["mean_excess_return"],
                            q["outperform_rate"],
                        )
                    )
                    + " |"
                )
    lines += [
        "",
        "## Bootstrap pareado: ADAPTIVE_DEV_EXPLORATORY",
        "",
        "1000 remuestreos de los mismos meses completos para todas las comparaciones. No conserva dependencia serial de objetivos H12. LL/Brier negativos favorecen el primer modelo; AUC/spread positivos lo favorecen.",
        "",
        "| Comparación | Métrica | IC95 inferior | IC95 superior |",
        "|---|---|---:|---:|",
    ]
    for pair, metrics in r["bootstrap"]["paired_deltas"].items():
        for metric, interval in metrics.items():
            lines.append(
                "| "
                + " | ".join(fmt(x) for x in (pair, metric, interval["low"], interval["high"]))
                + " |"
            )
    lines += [
        "",
        "## Evolución mensual",
        "",
        "El JSON de informe contiene para cada modelo/mes N, AUC, probabilidad media, prevalencia, quintiles y calibración. N mensual pequeño: descriptivo, sin claims fuertes.",
        "",
        "## Clasificación predeclarada",
        "",
        d["classification"],
        "",
        "Se aplica la regla descriptiva congelada en el manifiesto. No equivale a un gate ni a validación externa.",
    ]
    E.immutable_json(
        DOCS / (PREFIX + "_DOCUMENT_HASH.json"),
        {"report_markdown_hash": E.digest("\n".join(lines))},
    )
    path = DOCS / (PREFIX + "_REPORT.md")
    content = "\n".join(lines) + "\n"
    if path.exists() and path.read_text() != content:
        raise ValueError("immutable report differs")
    path.write_text(content)
    print(d["classification"])


if __name__ == "__main__":
    main()
