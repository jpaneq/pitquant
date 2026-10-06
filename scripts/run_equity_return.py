#!/usr/bin/env python3
# ruff: noqa: E501
"""Freeze continuous target and definitions before any actual return model fit."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.metadata
import json
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from pitquant.research import equity_baseline as E
from pitquant.research import equity_return as R
from pitquant.research import equity_v1 as V
from pitquant.research import first_ml_contract as C

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PREFIX = R.EXPERIMENT
MANIFEST = DOCS / (PREFIX + "_MANIFEST.json")


def sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def ledger() -> dict[str, str]:
    paths = [
        *DOCS.glob("FIRST_EQUITY_ML_12M_V0*"),
        *DOCS.glob("FIRST_EQUITY_ML_12M_V1*"),
        *DOCS.glob("first_equity_ml_12m_v0_plots/*"),
    ]
    return {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(paths)
        if p.is_file()
    }


def load() -> tuple[dict[str, Any], dict[str, Any]]:
    data = json.loads(
        gzip.decompress((DOCS / "FIRST_EQUITY_ML_12M_V0_DATASET.json.gz").read_bytes())
    )
    old = json.loads((DOCS / "FIRST_EQUITY_ML_12M_V0_MANIFEST.json").read_text())
    if E.digest(data) != V.DATA_HASH or E.digest(old["contracts"]["fold"]) != V.FOLD_HASH:
        raise ValueError("dataset/folds altered ABORT")
    if data["holdout_outcome_rows_accessed"] != 0 or data["oot_outcome_rows_accessed"] != 0:
        raise ValueError("sealed outcomes prohibited")
    return data, old


def freeze() -> None:
    if (
        MANIFEST.exists()
        or subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    ):
        raise ValueError("commit clean code before first freeze; never overwrite manifest")
    data, old = load()
    distributions: dict[str, Any] = {}
    plans = {}
    target_rows: dict[str, Any] = {}
    for f in data["folds"]:
        fid = "F" + str(f["index"])
        distributions[fid] = {}
        target_rows[fid] = {}
        for role in ("TRAIN", "TEST"):
            for row in f[role]:
                E.assert_row(row, role, f["fit_at"])
            distributions[fid][role] = R.distribution(f[role])
            target_rows[fid][role] = [
                [
                    r["target_id"],
                    r["security_id"],
                    r["decision_at"],
                    r["excess_return"],
                    r["benchmark_id"],
                    r["target_end"],
                    r["label_available_at"],
                ]
                for r in f[role]
            ]
        plans[fid] = [
            {k: v for k, v in inner.items() if k not in ("train", "validation")}
            | {"train_n": len(inner["train"]), "validation_n": len(inner["validation"])}
            for inner in V.inner_folds(f)
        ]
    target_contract = {
        "name": "future_excess_total_return_12m",
        "frozen_dataset_field": "excess_return",
        "source_field": "ResearchTarget.excess_total_return",
        "horizon_months": 12,
        "definition": "existing security total return minus existing benchmark total return, unchanged",
        "existing_contract": old["contracts"]["target"],
        "benchmark_contract_version": old["benchmark_contract_version"],
        "benchmark_source_hash": old["benchmark_source_hash"],
        "fx_total_return_entry_maturity": "unchanged targets_v2/benchmark contract and frozen target provenance",
        "rows_hash": E.digest(target_rows),
        "currency_bases": ["USD"],
        "return_types": ["TOTAL_RETURN"],
        "benchmark": "SPY ETF_PROXY",
        "target_transform": "NONE",
    }
    manifest = {
        "experiment_id": PREFIX,
        "created_at": datetime.now(UTC).isoformat(),
        "code_sha": sha(),
        "initial_sha": "6953df783eb183c4c2eb572a745261cb786242c7",
        "dev_adaptive_iteration": 2,
        "status": R.STATUS,
        "interpretation_status": "ADAPTIVE_DEV_EXPLORATORY",
        "data_snapshot_hash": V.DATA_HASH,
        "fold_hash": V.FOLD_HASH,
        "target_contract": target_contract,
        "target_hash": E.digest(target_contract),
        "feature_contract": old["contracts"]["feature"],
        "feature_contract_hash": old["feature_contract_hash"],
        "coverage_contract": old["contracts"]["coverage"],
        "coverage_contract_hash": old["coverage_contract_hash"],
        "common_cohorts": old["contracts"]["fold"],
        "preprocessing": E.PREPROCESSING,
        "preprocessing_hash": old["preprocessing_hash"],
        "grid": R.GRID,
        "grid_hash": E.digest(R.GRID),
        "model_definitions": {
            "R0": "outer TRAIN mean continuous target",
            "R2": {"kind": "ElasticNet/RidgeEquivalent", "features": C.M2.features},
            "R3": {"kind": "ElasticNet/RidgeEquivalent", "features": C.M3.features},
            "R4": {"kind": "ElasticNet/RidgeEquivalent", "features": C.M4.features},
        },
        "model_specs": R.SPEC,
        "model_spec_hash": E.digest(R.SPEC),
        "inner_design": V.DESIGN
        | {"selection": R.SPEC["primary_selection_metric"], "calibration": "NOT_APPLICABLE"},
        "inner_plan": plans,
        "inner_plan_hash": E.digest(plans),
        "seeds": {"model": E.SEED, "bootstrap": E.SEED},
        "bootstrap_pairs": R.PAIRS,
        "bootstrap_repetitions": 1000,
        "classification_rules": R.RULES,
        "prior_experiments_ledger": ledger(),
        "direction_reference": {
            "model_id": "M4R",
            "role": "CURRENT_BEST_DIRECTION_RESEARCH_BASELINE",
            "status": "NOT_CHAMPION_NOT_PRODUCTION_NOT_VALIDATED",
            "prediction_hash": json.loads(
                (DOCS / "FIRST_EQUITY_ML_12M_V1_REPORT.json").read_text()
            )["oof_hash"],
        },
        "dev_budget": "No indefinite adaptive DEV reuse. After this experiment consider at most one further predeclared structural experiment; never auto-start V3.",
        "bug_policy": "STOP and invalidate on data/PIT/preprocessing/fold bug; no quiet patch under same experiment ID",
        "holdout_outcome_rows_accessed": 0,
        "oot_outcome_rows_accessed": 0,
        "target_distribution_hash": E.digest(distributions),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": {
                name: importlib.metadata.version(name)
                for name in ("numpy", "scipy", "scikit-learn", "threadpoolctl")
            },
        },
    }
    manifest["manifest_hash"] = E.digest(manifest)
    E.immutable_json(DOCS / (PREFIX + "_TARGET_DISTRIBUTIONS.json"), distributions)
    E.immutable_json(MANIFEST, manifest)
    print("FROZEN", manifest["manifest_hash"], "target", manifest["target_hash"])


def classify(report: dict[str, Any]) -> str:
    for m in ("R2", "R3", "R4"):
        positive = all(
            v[m]["mean_monthly_cross_sectional_ic"]["mean"] is not None
            and v[m]["mean_monthly_cross_sectional_ic"]["mean"] > 0
            and v[m]["monthly_spread"]["mean"] is not None
            and v[m]["monthly_spread"]["mean"] > 0
            and v[m]["monthly_spread"]["n_available"] == 12
            and v[m]["mean_monthly_cross_sectional_ic"]["n_available"] == 12
            for v in report["per_fold"].values()
        )
        improvement = all(
            v[m]["mae"] < v["R0"]["mae"] and v[m]["rmse"] < v["R0"]["rmse"]
            for v in report["per_fold"].values()
        )
        intervals = report["bootstrap"]["paired_deltas"][m + "-R0"]
        if positive and improvement and all(intervals[k]["high"] < 0 for k in ("mae", "rmse")):
            return "ROBUST_RETURN_SIGNAL"
    for m in ("R2", "R3", "R4"):
        if all(
            v[m]["mean_monthly_cross_sectional_ic"]["mean"] is not None
            and v[m]["mean_monthly_cross_sectional_ic"]["mean"] > 0
            and v[m]["monthly_spread"]["mean"] is not None
            and v[m]["monthly_spread"]["mean"] > 0
            and v[m]["monthly_spread"]["n_available"] == 12
            and v[m]["mean_monthly_cross_sectional_ic"]["n_available"] == 12
            for v in report["per_fold"].values()
        ):
            return "PROMISING_RETURN_RANKING"
    for m in ("R2", "R3", "R4"):
        v = report["POOLED_DEV_OOF"][m]
        if (
            v["mean_monthly_cross_sectional_ic"]["mean"] is not None
            and v["mean_monthly_cross_sectional_ic"]["mean"] > 0
            and v["monthly_spread"]["mean"] is not None
            and v["monthly_spread"]["mean"] > 0
        ):
            return "RETURN_SIGNAL_UNSTABLE"
    return (
        "WEAK_RETURN_SIGNAL"
        if any(
            (report["POOLED_DEV_OOF"][m]["mean_monthly_cross_sectional_ic"]["mean"] or 0) > 0
            or (report["POOLED_DEV_OOF"][m]["monthly_spread"]["mean"] or 0) > 0
            for m in ("R2", "R3", "R4")
        )
        else "NO_RETURN_SIGNAL"
    )


def run() -> None:
    manifest = json.loads(MANIFEST.read_text())
    if (
        sha() != manifest["code_sha"]
        or E.digest({k: v for k, v in manifest.items() if k != "manifest_hash"})
        != manifest["manifest_hash"]
        or ledger() != manifest["prior_experiments_ledger"]
    ):
        raise ValueError("frozen code/manifest/prior artifacts altered ABORT")
    data, _ = load()
    distributions = json.loads((DOCS / (PREFIX + "_TARGET_DISTRIBUTIONS.json")).read_text())
    if E.digest(distributions) != manifest["target_distribution_hash"]:
        raise ValueError("prefit distribution changed")
    predictions: dict[str, list[dict[str, Any]]] = {m: [] for m in ("R0", "R2", "R3", "R4")}
    artifacts: dict[str, Any] = {}
    for fold in data["folds"]:
        fid = "F" + str(fold["index"])
        inners = V.inner_folds(fold)
        for row in fold["TEST"]:
            E.assert_row(row, "TEST", fold["fit_at"])
        chosen_predictions: dict[str, np.ndarray] = {
            "R0": np.full(len(fold["TEST"]), R.train_mean(fold["TRAIN"]))
        }
        artifacts[fid + "-R0"] = {
            "train_mean": R.train_mean(fold["TRAIN"]),
            "train_keys_hash": E.digest([V.key(r) for r in fold["TRAIN"]]),
            "target_values_hash": E.digest(R.target(fold["TRAIN"]).tolist()),
        }
        row_indices = {V.key(r): i for i, r in enumerate(fold["TRAIN"])}
        for model, names in (("R2", C.M2.features), ("R3", C.M3.features), ("R4", C.M4.features)):
            scores, candidates = [], {}
            for alpha, ratio in R.GRID:
                oof: list[dict[str, Any]] = []
                fitted, inner_scores = [], []
                for inner in inners:
                    p, parameters = R.fit_model(
                        inner["train"], inner["validation"], names, alpha, ratio
                    )
                    error = p - R.target(inner["validation"])
                    inner_scores.append(
                        {
                            "fit_at": inner["fit_at"],
                            "n": len(p),
                            "mae": float(np.mean(np.abs(error))),
                            "rmse": float(np.sqrt(np.mean(error**2))),
                        }
                    )
                    fitted.append(
                        parameters
                        | {
                            "fit_at": inner["fit_at"],
                            "validation_keys_hash": inner["validation_keys_hash"],
                        }
                    )
                    oof.extend(
                        {
                            "row_index": row_indices[V.key(row)],
                            "prediction": float(prob),
                            "inner_fit_at": inner["fit_at"],
                            "base_train_keys_hash": inner["train_keys_hash"],
                        }
                        for row, prob in zip(inner["validation"], p, strict=True)
                    )
                residual = np.array(
                    [
                        row["prediction"] - fold["TRAIN"][row["row_index"]]["excess_return"]
                        for row in oof
                    ]
                )
                score = {
                    "alpha": alpha,
                    "l1_ratio": ratio,
                    "mae": float(np.mean(np.abs(residual))),
                    "rmse": float(np.sqrt(np.mean(residual**2))),
                    "mean_nonzero_count": float(np.mean([r["nonzero_count"] for r in fitted])),
                }
                scores.append(score)
                candidates[f"{alpha}/{ratio}"] = {
                    "score": score,
                    "inner_models": fitted,
                    "inner_scores": inner_scores,
                    "oof": oof,
                }
            alpha, ratio = R.choose(scores)
            p, base = R.fit_model(fold["TRAIN"], fold["TEST"], names, alpha, ratio)
            chosen_predictions[model] = p
            artifacts[fid + "-" + model] = {
                "selected_alpha": alpha,
                "selected_l1_ratio": ratio,
                "scores": scores,
                "candidates": candidates,
                "base": base,
            }
            print(
                fid,
                model,
                "alpha",
                alpha,
                "ratio",
                ratio,
                "active",
                base["nonzero_count"],
                flush=True,
            )
        for model, p in chosen_predictions.items():
            for row, predicted in zip(fold["TEST"], p, strict=True):
                predictions[model].append(
                    {
                        "experiment_id": PREFIX,
                        "model_id": model,
                        "fold_id": fold["index"],
                        "decision_at": row["decision_at"],
                        "issuer_id": row["issuer_id"],
                        "security_id": row["security_id"],
                        "predicted_excess_return": float(predicted),
                        "realized_excess_return": row["excess_return"],
                        "raw_score": float(predicted),
                        "future_excess_return_12m": row["excess_return"],
                        "actual_target": row["actual_target"],
                        "benchmark_id": row["benchmark_id"],
                        "target_id": row["target_id"],
                        "target_end": row["target_end"],
                        "label_available_at": row["label_available_at"],
                        "cohort_id": fold["test_cohort_hash"],
                        "snapshot_id": row["snapshot_id"],
                        "data_hash": V.DATA_HASH,
                        "fold_hash": V.FOLD_HASH,
                        "target_hash": manifest["target_hash"],
                        "code_sha": manifest["code_sha"],
                        "created_at": manifest["created_at"],
                        "status": R.STATUS,
                    }
                )
    expected = {V.key(row) for f in data["folds"] for row in f["TEST"]}
    if any(
        len(rows) != len(expected) or {V.key(row) for row in rows} != expected
        for rows in predictions.values()
    ):
        raise ValueError("common cohort changed STOP")
    for rows in predictions.values():
        R.assign_ranks(rows)
    direction = [
        r
        for r in json.loads((DOCS / "FIRST_EQUITY_ML_12M_V1_OOF.json").read_text())
        if r["model_id"] == "M4R"
    ]
    if {V.key(r) for r in direction} != expected:
        raise ValueError("direction comparison cohort changed STOP")
    by_key = {V.key(r): r for r in direction}
    if any(
        row["realized_excess_return"] != by_key[V.key(row)]["future_excess_return_12m"]
        for row in predictions["R4"]
    ):
        raise ValueError("continuous/direction targets differ STOP")
    report = {
        "experiment_id": PREFIX,
        "manifest_hash": manifest["manifest_hash"],
        "status": R.STATUS,
        "dev_adaptive_iteration": 2,
        "target_hash": manifest["target_hash"],
        "per_fold": {
            "F" + str(i): {
                m: R.metrics([r for r in rows if r["fold_id"] == i])
                for m, rows in predictions.items()
            }
            for i in (1, 2, 3)
        },
        "POOLED_DEV_OOF": {m: R.metrics(rows) for m, rows in predictions.items()},
        "direction_ranking_reference": {
            "role": "CURRENT_BEST_DIRECTION_RESEARCH_BASELINE",
            "model_id": "M4R",
            "per_fold": {
                "F" + str(i): R.ranking([r for r in direction if r["fold_id"] == i])
                for i in (1, 2, 3)
            },
            "pooled": R.ranking(direction),
            "comparison_scope": "ranking only; no comparison MAE with LogLoss/probabilities",
        },
        "bootstrap": R.bootstrap(predictions),
        "holdout_outcome_rows_accessed": 0,
        "oot_outcome_rows_accessed": 0,
        "promoted": False,
        "target_transform": "NONE",
    }
    report["classification"] = classify(report)
    report["prediction_hash"] = E.immutable_json(
        DOCS / (PREFIX + "_OOF.json"), [r for rows in predictions.values() for r in rows]
    )
    report["model_parameters_hash"] = R.immutable_gzip(
        DOCS / (PREFIX + "_MODELS.json.gz"), artifacts
    )
    E.immutable_json(DOCS / (PREFIX + "_REPORT.json"), report)
    if ledger() != manifest["prior_experiments_ledger"]:
        raise ValueError("prior experiments modified STOP")
    print(report["classification"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["freeze", "run"])
    args = parser.parse_args()
    freeze() if args.action == "freeze" else run()
