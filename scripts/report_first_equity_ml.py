#!/usr/bin/env python3
# ruff: noqa: E501
"""Outcome diagnostics only: never modifies models, preprocessing or predictions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import precision_recall_curve, roc_curve

from pitquant.research import equity_baseline as E

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PREFIX = "FIRST_EQUITY_ML_12M_V0"


def main() -> None:
    report = json.loads((DOCS / f"{PREFIX}_REPORT.json").read_text())
    artifacts = json.loads((DOCS / f"{PREFIX}_MODELS.json").read_text())
    predictions = json.loads((DOCS / f"{PREFIX}_OOF.json").read_text())
    summary: dict[str, Any] = {
        "fold_stability": {},
        "coefficients": {},
        "regimes": {},
        "evidence_classification": "NO_MEANINGFUL_SIGNAL",
    }
    for name in ("M0", "M1", "M2", "M3", "M4"):
        summary["fold_stability"][name] = {}
        for metric in ("auc", "ap", "brier", "log_loss", "rank_ic"):
            values = [
                f["models"][name][metric]
                for f in report["per_fold"]
                if f["models"][name][metric] is not None
            ]
            summary["fold_stability"][name][metric] = (
                {
                    "mean": float(np.mean(values)),
                    "min": float(np.min(values)),
                    "max": float(np.max(values)),
                    "std": float(np.std(values)),
                }
                if values
                else None
            )
        rs = [r for r in predictions if r["model_id"] == name]
        summary["regimes"][name] = {
            regime: E.metrics([r for r in rs if r["regime"] == regime], name != "M1")
            for regime in sorted({r["regime"] for r in rs if r["regime"] is not None})
        }
    for name in ("M2", "M3", "M4"):
        by_fold = [artifacts[f"F{i}-{name}"] for i in (1, 2, 3)]
        summary["coefficients"][name] = []
        for j, feature in enumerate(by_fold[0]["transformed_features"]):
            values = [f["coefficients"][j] for f in by_fold]
            signs = np.sign(values)
            summary["coefficients"][name].append(
                {
                    "feature": feature,
                    "coef_F1": values[0],
                    "coef_F2": values[1],
                    "coef_F3": values[2],
                    "mean_coef": float(np.mean(values)),
                    "std": float(np.std(values)),
                    "sign_consistency": float(
                        max(sum(signs == -1), sum(signs == 0), sum(signs == 1)) / 3
                    ),
                }
            )
    labels = []
    for name in ("M2", "M3", "M4"):
        delta = report["bootstrap"]["paired_deltas"][name + "-M0"]
        folds = [f["models"][name] for f in report["per_fold"]]
        baselines = [f["models"]["M0"] for f in report["per_fold"]]
        auc_wins = sum(f["auc"] > b["auc"] for f, b in zip(folds, baselines, strict=True))
        brier_wins = sum(f["brier"] < b["brier"] for f, b in zip(folds, baselines, strict=True))
        if (
            auc_wins == 3
            and brier_wins == 3
            and delta["auc"]["low"] > 0
            and delta["brier"]["high"] < 0
        ):
            labels.append("STRONG_PROMISING_SIGNAL")
        elif auc_wins >= 2 and delta["auc"]["low"] > 0:
            labels.append("PROMISING_BUT_UNSTABLE")
        elif auc_wins >= 2 and report["POOLED_DEV_OOF"][name]["auc"] > 0.5:
            labels.append("WEAK_SIGNAL")
        else:
            labels.append("NO_MEANINGFUL_SIGNAL")
    order = [
        "STRONG_PROMISING_SIGNAL",
        "PROMISING_BUT_UNSTABLE",
        "WEAK_SIGNAL",
        "NO_MEANINGFUL_SIGNAL",
    ]
    summary["evidence_classification"] = min(labels, key=order.index)
    E.immutable_json(DOCS / f"{PREFIX}_DIAGNOSTICS.json", summary)
    text = [
        f"# {PREFIX}\n",
        "RESEARCH_DEV_ONLY · RETROSPECTIVE_UNVALIDATED. PRIMARY_COMMON_COHORT.\n",
        "## Manifiesto\n",
        f"Código: `{report['manifest']['code_sha']}`. Manifiesto: `{report['manifest']['manifest_hash']}`.\n",
        "## A — Muestras y I — Tasas base\n",
        "|Fold|TRAIN|TEST|Issuers TRAIN/TEST|Base TRAIN|Base TEST|Δ|",
        "|---|---:|---:|---|---:|---:|---:|",
    ]
    for f in report["per_fold"]:
        text.append(
            f"|F{f['fold']}|{f['train_n']}|{f['test_n']}|{f['train_issuers']}/{f['test_issuers']}|{f['train_base_rate']:.4f}|{f['test_base_rate']:.4f}|{f['test_base_rate'] - f['train_base_rate']:+.4f}|"
        )
    for scope, models in [(f"B — F{f['fold']}", f["models"]) for f in report["per_fold"]] + [
        ("C — POOLED_DEV_OOF", report["POOLED_DEV_OOF"])
    ]:
        text.extend(
            [
                f"\n## {scope}\n",
                "|Modelo|AUC|AP|Brier|LogLoss|Accuracy|Balanced|Precision|Recall|F1|IC|",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for name, values in models.items():
            text.append(
                "|"
                + name
                + "|"
                + "|".join(
                    f"{values[k]:.5f}" if values[k] is not None else "N/A"
                    for k in (
                        "auc",
                        "ap",
                        "brier",
                        "log_loss",
                        "accuracy",
                        "balanced_accuracy",
                        "precision",
                        "recall",
                        "f1",
                        "rank_ic",
                    )
                )
                + "|"
            )
    text.extend(
        [
            "\n## D y J — Diferencias pareadas e incertidumbre\n",
            "1.000 remuestreos de meses completos, mismos meses para cada modelo. IC95 exploratorios; Δ Brier negativo favorece el primer modelo.\n",
            "|Comparación|Δ AUC IC95|Δ Brier IC95|Δ spread IC95|",
            "|---|---|---|---|",
        ]
    )
    for name, values in report["bootstrap"]["paired_deltas"].items():
        text.append(
            "|"
            + name
            + "|"
            + "|".join(
                f"[{values[k]['low']:.5f}, {values[k]['high']:.5f}]" if values[k]["n"] else "N/A"
                for k in ("auc", "brier", "spread")
            )
            + "|"
        )
    text.extend(
        [
            "\n## E — Calibración\n",
            "|Modelo|Intercepto|Pendiente|ECE|Estado|",
            "|---|---:|---:|---:|---|",
        ]
    )
    for name, values in report["POOLED_DEV_OOF"].items():
        c = values["calibration"]
        text.append(
            f"|{name}|{c['intercept']}|{c['slope']}|{c['ece']}|{c['status']}|"
            if c
            else f"|{name}|N/A|N/A|N/A|{E.NA}|"
        )
    text.extend(
        [
            "\n## F y G — Buckets y top20–bottom20\n",
            "Buckets mensuales por rango medio; los empates no se separan. M0 constante no tiene spread identificable. Mínimo tres observaciones por bucket esperado; tablas sin umbral inventado de monotonía.\n",
        ]
    )
    for name, values in report["POOLED_DEV_OOF"].items():
        for kind in ("quintiles", "deciles"):
            text.extend(
                [
                    f"\n### {name}: {kind}\n",
                    "|Bucket|N|Exceso medio|Exceso mediano|Outperform|",
                    "|---|---:|---:|---:|---:|",
                ]
            )
            for b in values[kind]["table"]:
                text.append(
                    f"|{b['bucket']}|{b['n']}|{b['mean_excess_return']}|{b['median_excess_return']}|{b['outperform_rate']}|"
                )
        text.append(
            f"\nSpread quintiles, media de meses: {values['quintiles']['mean_month_spread']}; diferencia outperform: {values['quintiles']['mean_month_outperform_spread']}.\n"
        )
    text.extend(
        [
            "\n## H — Coeficientes y estabilidad\n",
            "Coeficientes no causales. Parámetros de preprocesado, correlaciones TRAIN y coeficientes completos por fold: MODELS.json; estabilidad y regímenes: DIAGNOSTICS.json.\n",
        ]
    )
    for name, table in summary["coefficients"].items():
        text.extend(
            [
                f"\n### {name}\n",
                "|Feature|F1|F2|F3|Media|Consistencia signo|",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for r in table:
            text.append(
                f"|{r['feature']}|{r['coef_F1']:.5f}|{r['coef_F2']:.5f}|{r['coef_F3']:.5f}|{r['mean_coef']:.5f}|{r['sign_consistency']:.3f}|"
            )
    text.extend(
        [
            "\n## Estabilidad mensual y por fold\n",
            "36 meses TEST, sin solapamiento de decisiones; estadísticas mensuales por modelo y curva de calibración por fold conservadas en REPORT.json. Los horizontes de retorno de meses contiguos sí se solapan.\n",
            "\n## Límites\n",
            "Universo configurado con sesgo de supervivencia; proxies ETF, fuente retrospectiva Yahoo; panel dependiente. Bootstrap de un mes conserva dependencia transversal pero no toda dependencia serial de retornos a 12 meses. Comparaciones múltiples exploratorias. No cartera, costes, calibración aplicada ni selección de features.\n",
            "Holdout/OOT: cero outcomes accedidos. Sin promoción ni señales live.\n",
            f"\nClasificación predeclarada: **{summary['evidence_classification']}**.\n",
        ]
    )
    path = DOCS / f"{PREFIX}_REPORT.md"
    raw = "\n".join(text)
    if path.exists() and path.read_text() != raw:
        raise ValueError("immutable report conflict")
    if not path.exists():
        with path.open("x") as f:
            f.write(raw)
    plotdir = DOCS / "first_equity_ml_12m_v0_plots"
    plotdir.mkdir(exist_ok=True)
    for kind in ("roc", "pr", "calibration", "distributions", "buckets", "coefficients"):
        fig, ax = plt.subplots(figsize=(9, 6))
        for name in ("M0", "M1", "M2", "M3", "M4"):
            rs = [r for r in predictions if r["model_id"] == name]
            y = np.array([r["actual_target"] for r in rs])
            p = np.array([r["raw_score"] for r in rs])
            if kind == "roc":
                x, yplot, _ = roc_curve(y, p)
                ax.plot(x, yplot, label=name)
            elif kind == "pr":
                precision, recall, _ = precision_recall_curve(y, p)
                ax.plot(recall, precision, label=name)
            elif kind == "calibration" and name != "M1":
                c = report["POOLED_DEV_OOF"][name]["calibration"]["curve"]
                ax.plot(
                    [b["mean_prediction"] for b in c],
                    [b["observed"] for b in c],
                    marker="o",
                    label=name,
                )
            elif kind == "distributions" and name != "M1":
                ax.hist(p, bins=20, histtype="step", label=name)
            elif kind == "buckets" and name != "M0":
                b = report["POOLED_DEV_OOF"][name]["quintiles"]["table"]
                ax.plot(
                    [r["bucket"] for r in b],
                    [r["mean_excess_return"] for r in b],
                    marker="o",
                    label=name,
                )
            elif kind == "coefficients" and name in ("M2", "M3", "M4"):
                table = summary["coefficients"][name]
                ax.scatter(
                    [r["coef_F1"] for r in table],
                    [r["coef_F3"] for r in table],
                    alpha=0.5,
                    label=name,
                )
        ax.set_title(f"POOLED_DEV_OOF — {kind} — RETROSPECTIVE_UNVALIDATED")
        ax.legend()
        ax.grid(alpha=0.2)
        fig.tight_layout()
        path = plotdir / f"{kind}.png"
        if not path.exists():
            fig.savefig(path, dpi=150)
        plt.close(fig)
    print(summary["evidence_classification"])


if __name__ == "__main__":
    main()
