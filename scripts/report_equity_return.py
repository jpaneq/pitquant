#!/usr/bin/env python3
# ruff: noqa: E501
"""Read-only report rendering; all numeric source artifacts remain immutable."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
from typing import Any

import numpy as np

from pitquant.research import equity_baseline as E
from pitquant.research import equity_return as R

DOCS = Path(__file__).resolve().parents[1] / "docs"
PREFIX = R.EXPERIMENT
DISTRIBUTION_COLUMNS = (
    "n",
    "mean",
    "median",
    "std_ddof0",
    "p01",
    "p05",
    "p25",
    "p75",
    "p95",
    "p99",
    "min",
    "max",
)


def fmt(value: Any) -> str:
    return (
        "NA"
        if value is None
        else f"{value:.6f}"
        if isinstance(value, (float, np.floating))
        else str(value)
    )


def table(headers: tuple[str, ...], rows: list[list[Any]]) -> str:
    return "\n".join(
        [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
            *["| " + " | ".join(fmt(x) for x in row) + " |" for row in rows],
        ]
    )


def write_markdown(path: Path, text: str) -> None:
    if path.exists():
        if path.read_text() != text:
            raise ValueError("immutable rendered document differs")
    else:
        with path.open("x") as f:
            f.write(text)


def distribution_document() -> str:
    data = json.loads((DOCS / (PREFIX + "_TARGET_DISTRIBUTIONS.json")).read_text())
    rows = [
        [fid, role, *[distribution[k] for k in DISTRIBUTION_COLUMNS]]
        for fid, values in data.items()
        for role, distribution in values.items()
    ]
    return "\n".join(
        [
            "# Distribuciones previas al fit",
            "",
            "Retornos en fracción: 0.07 = +7 puntos porcentuales. Dataset y target congelados; no se modifica ningún valor.",
            "",
            table(("Fold", "Role", *DISTRIBUTION_COLUMNS), rows),
            "",
            "Extremos/outliers descriptivos completos en el JSON. Se conservan todas las filas. SD ddof=0; cuantiles lineales.",
            "",
        ]
    )


def coefficient_diagnostics(models: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for model in ("R2", "R3", "R4"):
        bases = [models[f"F{i}-{model}"]["base"] for i in (1, 2, 3)]
        coef = np.array([b["coefficients"] for b in bases])
        result[model] = {
            "selected": [
                {
                    "alpha": b["alpha"],
                    "l1_ratio": b["l1_ratio"],
                    "nonzero_count": b["nonzero_count"],
                    "l1_norm": b["l1_norm"],
                    "l2_norm": b["l2_norm"],
                }
                for b in bases
            ],
            "features": {
                name: {
                    "F1": float(coef[0, j]),
                    "F2": float(coef[1, j]),
                    "F3": float(coef[2, j]),
                    "sign_consistent": bool(np.all(np.sign(coef[:, j]) == np.sign(coef[0, j]))),
                    "nonzero_frequency": float(np.mean(np.abs(coef[:, j]) > 1e-12)),
                    "dispersion_std_ddof0": float(np.std(coef[:, j])),
                }
                for j, name in enumerate(bases[0]["transformed_features"])
            },
            "sign_consistent_raw": int(
                np.sum(
                    np.all(
                        np.sign(coef[:, : len(bases[0]["features"])])
                        == np.sign(coef[0, : len(bases[0]["features"])]),
                        axis=0,
                    )
                )
            ),
            "constant_zero_warning": "Zero in every fold counts as sign-consistent inactivity, not reproducible predictive effect",
            "coefficient_scope": "fold-specific standardized feature coefficients, including unscaled binary missing indicators; no causal interpretation or feature redesign",
        }
    return result


def main() -> None:
    report = json.loads((DOCS / (PREFIX + "_REPORT.json")).read_text())
    models = json.loads(gzip.decompress((DOCS / (PREFIX + "_MODELS.json.gz")).read_bytes()))
    diagnostic = coefficient_diagnostics(models)
    E.immutable_json(DOCS / (PREFIX + "_COEFFICIENTS.json"), diagnostic)
    lines = [
        "# FIRST_EQUITY_RETURN_12M_V0",
        "",
        "**RESEARCH_DEV_ONLY · ADAPTIVE_DEV_EXPLORATORY · dev_adaptive_iteration=2 · RETROSPECTIVE_UNVALIDATED**",
        "",
        "Este experimento se diseñó tras observar Direction V0/V1. No es confirmación independiente. Holdout/OOT: cero resultados accedidos. No champion, producción, señales live ni portfolio.",
        "",
        "## Diseño congelado",
        "",
        "Dataset, cohortes y folds exactamente iguales a Direction V0/V1. Target existente ResearchTarget.excess_total_return (campo congelado excess_return): total return security menos SPY total return, misma moneda USD, horizonte/entrada/madurez intactos. No target nuevo ni winsorización.",
        "",
        "R0: media TRAIN. R2/R3/R4: familias 18/18/44 intactas. Grid alpha={.001,.003,.01,.03,.1,.3,1}, l1_ratio={0,.25,.5,.75,1}. l1_ratio=0 usa Ridge alpha=n*alpha por equivalencia de objetivos. Elastic Net cyclic, max_iter=100000, tol=1e-8.",
        "",
        "Inner CV causal 1/3/5 bloques de seis meses, TRAIN expansivo mínimo 18 meses, H12+embargo1 y madurez efectiva. Preprocessing de V0 en cada inner TRAIN. Selección sólo MAE OOF; RMSE diagnóstico. Empate 1e-12: alpha mayor, menor número medio de coeficientes activos, l1_ratio menor.",
        "",
        "R0 constante: IC/spread mensual NA, no cero. Ranking del pooled puede reflejar cambios entre folds; para selección interesa IC cross-sectional mensual. Spreads son diagnósticos, no estrategia.",
        "",
        "## Distribuciones antes de fit",
        "",
        distribution_document(),
        "",
        "## Resultados por fold antes de pooled",
    ]
    for scope, values in [
        *report["per_fold"].items(),
        ("POOLED_DEV_OOF", report["POOLED_DEV_OOF"]),
    ]:
        lines += [
            "",
            "### " + scope,
            "",
            table(
                (
                    "Modelo",
                    "N",
                    "MAE",
                    "RMSE",
                    "R²",
                    "Pearson",
                    "POOLED_OBSERVATION_IC",
                    "MEAN_MONTHLY_CROSS_SECTIONAL_IC",
                    "spread mensual",
                ),
                [
                    [
                        m,
                        v["n"],
                        v["mae"],
                        v["rmse"],
                        v["r2"],
                        v["pearson"],
                        v["pooled_observation_ic"],
                        v["mean_monthly_cross_sectional_ic"]["mean"],
                        v["monthly_spread"]["mean"],
                    ]
                    for m, v in values.items()
                ],
            ),
            "",
            "IC y spread: resumen mensual",
            "",
            table(
                (
                    "Modelo",
                    "Diagnóstico",
                    "N meses",
                    "mean",
                    "median",
                    "positive_fraction",
                    "min",
                    "max",
                    "SD",
                ),
                [
                    [
                        m,
                        metric,
                        *[
                            v[metric][k]
                            for k in (
                                "n_available",
                                "mean",
                                "median",
                                "positive_fraction",
                                "min",
                                "max",
                                "std_ddof0",
                            )
                        ],
                    ]
                    for m, v in values.items()
                    for metric in ("mean_monthly_cross_sectional_ic", "monthly_spread")
                ],
            ),
        ]
    lines += [
        "",
        "## Quintiles por fold y pooled",
        "",
        "Rankings calculados dentro de cada mes; empates promedio, sin desempate por identidad o resultado. N y medias de tabla ponderan filas; spread principal promedia meses por igual.",
        "",
        table(
            ("Fold", "Modelo", "Q", "N", "exceso medio", "exceso mediano", "outperform rate"),
            [
                [
                    scope,
                    m,
                    *[
                        q[k]
                        for k in (
                            "bucket",
                            "n",
                            "mean_excess_return",
                            "median_excess_return",
                            "outperform_rate",
                        )
                    ],
                ]
                for scope, values in [
                    *report["per_fold"].items(),
                    ("POOLED", report["POOLED_DEV_OOF"]),
                ]
                for m, v in values.items()
                for q in v["quintiles"]["table"]
            ],
        ),
    ]
    lines += [
        "",
        "## R4 frente a M4R: métricas comunes de ranking",
        "",
        "M4R: CURRENT_BEST_DIRECTION_RESEARCH_BASELINE, sin validación ni promoción. Mismas TEST rows y mismo retorno realizado. No se compara MAE con LogLoss.",
        "",
        table(
            ("Fold", "Modelo", "IC observaciones", "IC mensual", "spread mensual"),
            [
                [
                    scope,
                    model,
                    v["pooled_observation_ic"],
                    v["mean_monthly_cross_sectional_ic"]["mean"],
                    v["monthly_spread"]["mean"],
                ]
                for scope in ("F1", "F2", "F3", "POOLED")
                for model, v in [
                    (
                        "R4",
                        report["POOLED_DEV_OOF"]["R4"]
                        if scope == "POOLED"
                        else report["per_fold"][scope]["R4"],
                    ),
                    (
                        "M4R",
                        report["direction_ranking_reference"]["pooled"]
                        if scope == "POOLED"
                        else report["direction_ranking_reference"]["per_fold"][scope],
                    ),
                ]
            ],
        ),
        "",
        "Quintiles M4R de referencia",
        "",
        table(
            ("Fold", "Q", "N", "exceso medio", "exceso mediano", "outperform rate"),
            [
                [
                    scope,
                    *[
                        q[k]
                        for k in (
                            "bucket",
                            "n",
                            "mean_excess_return",
                            "median_excess_return",
                            "outperform_rate",
                        )
                    ],
                ]
                for scope, values in [
                    *report["direction_ranking_reference"]["per_fold"].items(),
                    ("POOLED", report["direction_ranking_reference"]["pooled"]),
                ]
                for q in values["quintiles"]["table"]
            ],
        ),
    ]
    lines += [
        "",
        "## Coeficientes, sparsity y estabilidad",
        "",
        table(
            ("Modelo", "Fold", "alpha", "l1_ratio", "nonzero", "L1", "L2"),
            [
                [
                    model,
                    "F" + str(i + 1),
                    *[v[k] for k in ("alpha", "l1_ratio", "nonzero_count", "l1_norm", "l2_norm")],
                ]
                for model, vals in diagnostic.items()
                for i, v in enumerate(vals["selected"])
            ],
        ),
        "",
        "Vectores completos, signos y frecuencia nozero por feature en COEFFICIENTS.json; parámetros/preprocessing de todos los candidatos en MODELS.json.gz. No interpretar causalmente; cero estable no demuestra señal. No se eliminan features.",
        "",
        "## Bootstrap ADAPTIVE_DEV_EXPLORATORY_INTERVAL",
        "",
        "1000 muestras pareadas de meses completos. Dependencia dentro del mes preservada; no toda la dependencia serial H12. Deltas MAE/RMSE negativos favorecen el primer modelo; IC/spread positivos lo favorecen. R0 no tiene ranking mensual: sus comparaciones IC/spread quedan NA.",
        "",
        table(
            ("Comparación", "Métrica", "N réplicas disponibles", "IC95 inferior", "IC95 superior"),
            [
                [pair, metric, v["n"], v["low"], v["high"]]
                for pair, vals in report["bootstrap"]["paired_deltas"].items()
                for metric, v in vals.items()
            ],
        ),
        "",
        "## F3 y clasificación",
        "",
        report["classification"],
        "",
        "La etiqueta aplica la regla descriptiva congelada antes de fit; consultar conclusiones Q1–Q10. No es gate operativo.",
        "",
        "## Presupuesto DEV",
        "",
        "No continuar indefinidamente reutilizando DEV. Considerar como máximo un siguiente experimento estructural predeclarado; no iniciar V3 automáticamente.",
        "",
    ]
    document = "\n".join(lines)
    write_markdown(DOCS / (PREFIX + "_REPORT.md"), document)
    E.immutable_json(
        DOCS / (PREFIX + "_DOCUMENT_HASH.json"), {"report_markdown_hash": E.digest(document)}
    )
    print(report["classification"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["distributions", "report"])
    args = parser.parse_args()
    if args.action == "distributions":
        write_markdown(DOCS / (PREFIX + "_TARGET_DISTRIBUTIONS.md"), distribution_document())
    else:
        main()
