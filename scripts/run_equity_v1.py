#!/usr/bin/env python3
# ruff: noqa: E501
"""Freeze V1 before fit; independent runner reads only the frozen V0 DEV archive."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from pitquant.research import equity_baseline as E
from pitquant.research import equity_v1 as V
from pitquant.research import first_ml_contract as C

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PREFIX = "FIRST_EQUITY_ML_12M_V1"
MANIFEST = DOCS / (PREFIX + "_MANIFEST.json")
RULES = {
    "CALIBRATION_IMPROVED_SIGNAL_STABLE": "Either family: calibrated pooled LL and Brier improve base; base AUC > .5 and monthly spread > 0 in every fold",
    "CALIBRATION_IMPROVED_RANKING_UNSTABLE": "Otherwise either family calibrated pooled LL and Brier improve base but base AUC <= .5 or spread <= 0 in at least one fold",
    "REGULARIZATION_IMPROVED_STABILITY": "Otherwise either family has lower across-fold AUC SD and better F3 LL than V0",
    "WEAK_UNSTABLE_SIGNAL": "Otherwise either regularized family pooled AUC > .5",
    "NO_REPRODUCIBLE_SIGNAL": "Otherwise",
    "scope": "Descriptive preregistered classification, no production pass or independent confirmation",
}


def sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def ledger() -> dict[str, str]:
    return {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(
            [*DOCS.glob("FIRST_EQUITY_ML_12M_V0*"), *DOCS.glob("first_equity_ml_12m_v0_plots/*")]
        )
        if p.is_file()
    }


def load_data() -> tuple[dict[str, Any], dict[str, Any]]:
    data = json.loads(
        gzip.decompress((DOCS / "FIRST_EQUITY_ML_12M_V0_DATASET.json.gz").read_bytes())
    )
    old = json.loads((DOCS / "FIRST_EQUITY_ML_12M_V0_MANIFEST.json").read_text())
    if (
        E.digest(data) != V.DATA_HASH
        or old["fold_hash"] != V.FOLD_HASH
        or E.digest(old["contracts"]["fold"]) != V.FOLD_HASH
    ):
        raise ValueError("V0 dataset/fold hash changed ABORT")
    return data, old


def freeze() -> None:
    if MANIFEST.exists():
        raise ValueError("V1 already frozen")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip():
        raise ValueError("commit clean code before freezing")
    data, old = load_data()
    plan = {}
    for fold in data["folds"]:
        plan[str(fold["index"])] = [
            {k: v for k, v in inner.items() if k not in ("train", "validation")}
            | {"train_n": len(inner["train"]), "validation_n": len(inner["validation"])}
            for inner in V.inner_folds(fold)
        ]
    manifest = {
        "experiment_id": V.EXPERIMENT,
        "created_at": datetime.now(UTC).isoformat(),
        "code_sha": sha(),
        "initial_sha": "1ca46e90c6b010fdfbeee657d60c2092aeb76ddc",
        "dev_adaptive_iteration": 1,
        "iteration_label": "ADAPTIVE_DEV_ITERATION_1",
        "status": V.STATUS,
        "data_snapshot_hash": V.DATA_HASH,
        "fold_hash": V.FOLD_HASH,
        "v0_manifest_hash": old["manifest_hash"],
        "v0_ledger": ledger(),
        "contracts": old["contracts"],
        "preprocessing": old["preprocessing"],
        "preprocessing_hash": old["preprocessing_hash"],
        "inner_design": V.DESIGN,
        "inner_plan": plan,
        "inner_plan_hash": E.digest(plan),
        "grid": V.GRID,
        "base_parameters": E.PARAMS,
        "primary_metric": "LOG_LOSS",
        "seeds": old["seeds"],
        "comparisons": V.PAIRS,
        "bootstrap_repetitions": 1000,
        "interpretation_rule": RULES,
        "environment": old["environment"],
        "holdout_outcome_rows_accessed": 0,
        "oot_outcome_rows_accessed": 0,
        "bug_policy": "STOP and invalidate affected experiment; never silently repair after fit",
    }
    manifest["manifest_hash"] = E.digest(manifest)
    E.immutable_json(MANIFEST, manifest)
    print("FROZEN", manifest["manifest_hash"], {k: len(v) for k, v in plan.items()})


def run() -> None:
    manifest = json.loads(MANIFEST.read_text())
    if (
        E.digest({k: v for k, v in manifest.items() if k != "manifest_hash"})
        != manifest["manifest_hash"]
        or sha() != manifest["code_sha"]
        or ledger() != manifest["v0_ledger"]
    ):
        raise ValueError("frozen manifest/code/V0 altered ABORT")
    data, _ = load_data()
    old_rows = json.loads((DOCS / "FIRST_EQUITY_ML_12M_V0_OOF.json").read_text())
    refs = {m: [r for r in old_rows if r["model_id"] == m] for m in ("M0", "M2", "M3", "M4")}
    predictions: dict[str, list[dict[str, Any]]] = {m: [] for m in ("M3R", "M3RC", "M4R", "M4RC")}
    artifacts: dict[str, Any] = {}
    for fold in data["folds"]:
        fid = "F" + str(fold["index"])
        inners = V.inner_folds(fold)
        for r in fold["TEST"]:
            E.assert_row(r, "TEST", fold["fit_at"])
        for model, names in (("M3R", C.M3.features), ("M4R", C.M4.features)):
            candidates: dict[str, Any] = {}
            scores = {}
            for c in V.GRID:
                oof, fitted, training_keys = [], [], {}
                for inner in inners:
                    p, a = V.fit_base(inner["train"], inner["validation"], names, c)
                    fitted.append(
                        a
                        | {
                            "fit_at": inner["fit_at"],
                            "validation_keys_hash": inner["validation_keys_hash"],
                        }
                    )
                    train_keys = [V.key(r) for r in inner["train"]]
                    training_keys[E.digest(train_keys)] = train_keys
                    for r, probability in zip(inner["validation"], p, strict=True):
                        oof.append(
                            {
                                "security_id": r["security_id"],
                                "decision_at": r["decision_at"],
                                "actual_target": r["actual_target"],
                                "label_available_at": r["label_available_at"],
                                "p": float(probability),
                                "prediction_kind": "CAUSAL_INNER_OOF",
                                "inner_fit_at": inner["fit_at"],
                                "base_train_keys_hash": E.digest(train_keys),
                            }
                        )
                from sklearn.metrics import brier_score_loss, log_loss

                y, inner_probabilities = [r["actual_target"] for r in oof], [r["p"] for r in oof]
                scores[c] = float(log_loss(y, inner_probabilities, labels=[0, 1]))
                candidates[str(c)] = {
                    "log_loss": scores[c],
                    "brier": float(brier_score_loss(y, inner_probabilities)),
                    "inner_models": fitted,
                    "training_keys": training_keys,
                    "oof": oof,
                }
            selected = V.select_c(scores)
            p, base = V.fit_base(fold["TRAIN"], fold["TEST"], names, selected)
            calibrator = V.fit_platt(
                candidates[str(selected)]["oof"],
                fold["fit_at"],
                candidates[str(selected)]["training_keys"],
            )
            if calibrator["status"] != "AVAILABLE":
                raise ValueError(calibrator["status"])
            pc = V.apply_platt(p, calibrator)
            artifacts[fid + "-" + model] = {
                "selected_c": selected,
                "candidates": candidates,
                "base": base,
                "calibrator": calibrator,
            }
            templates = {V.key(r): r for r in refs["M3"] if int(r["fold_id"]) == fold["index"]}
            for r, prob, calibrated in zip(fold["TEST"], p, pc, strict=True):
                template = templates[V.key(r)]
                for name, value in ((model, prob), (model + "C", calibrated)):
                    predictions[name].append(
                        {
                            **template,
                            "experiment_id": V.EXPERIMENT,
                            "model_id": name,
                            "created_at": manifest["created_at"],
                            "code_sha": manifest["code_sha"],
                            "status": V.STATUS,
                            "predicted_probability": float(value),
                            "raw_score": float(value),
                        }
                    )
            print(fid, model, "C", selected, "Platt", calibrator["slope"], flush=True)
    merged = {**refs, **predictions}
    common = {V.key(r) for r in refs["M3"]}
    if any({V.key(r) for r in rs} != common or len(rs) != len(common) for rs in merged.values()):
        raise ValueError("common cohort changed STOP")
    old_report = json.loads((DOCS / "FIRST_EQUITY_ML_12M_V0_REPORT.json").read_text())

    def evaluate_model(model: str, rows: list[dict[str, Any]], scope: str) -> dict[str, Any]:
        if model not in refs:
            return V.evaluate(rows)
        if scope == "POOLED":
            frozen = old_report["POOLED_DEV_OOF"][model]
        elif scope.startswith("F"):
            frozen = old_report["per_fold"][int(scope[1:]) - 1]["models"][model]
        else:
            frozen = next(r for r in old_report["monthly"][model] if r["month"] == scope)
        probabilities = [r["predicted_probability"] for r in rows]
        return {
            **frozen,
            "probability_distribution": dict(
                zip(
                    ("min", "p05", "p25", "median", "p75", "p95", "max"),
                    np.quantile(probabilities, [0, 0.05, 0.25, 0.5, 0.75, 0.95, 1]).tolist(),
                    strict=True,
                )
            ),
            "mean_probability": float(np.mean(probabilities)),
        }

    per_fold = {
        "F" + str(i): {
            m: evaluate_model(m, [r for r in rs if int(r["fold_id"]) == i], "F" + str(i))
            for m, rs in merged.items()
        }
        for i in (1, 2, 3)
    }
    for models in per_fold.values():
        for m in ("M3R", "M4R"):
            for metric in ("auc", "ap", "rank_ic"):
                if not np.isclose(models[m][metric], models[m + "C"][metric], atol=1e-12, rtol=0):
                    raise ValueError("ranking invariant failed STOP")
            if models[m]["quintiles"] != models[m + "C"]["quintiles"]:
                raise ValueError("quintile invariant failed STOP")
    report = {
        "experiment_id": V.EXPERIMENT,
        "manifest_hash": manifest["manifest_hash"],
        "status": V.STATUS,
        "dev_adaptive_iteration": 1,
        "per_fold": per_fold,
        "POOLED_DEV_OOF": {m: evaluate_model(m, rs, "POOLED") for m, rs in merged.items()},
        "monthly": {
            m: {
                month: evaluate_model(m, [r for r in rs if r["decision_at"][:7] == month], month)
                for month in sorted({r["decision_at"][:7] for r in rs})
            }
            for m, rs in merged.items()
        },
        "bootstrap": V.bootstrap({m: merged[m] for m in ("M3", "M4", *predictions)}),
        "holdout_outcome_rows_accessed": 0,
        "oot_outcome_rows_accessed": 0,
        "promoted": False,
        "base_rate_shift": {
            "F" + str(f["index"]): {
                "train": E.train_base_rate(f["TRAIN"]),
                "test": E.train_base_rate(f["TEST"]),
            }
            for f in data["folds"]
        },
    }
    report["oof_hash"] = E.immutable_json(
        DOCS / (PREFIX + "_OOF.json"), [r for rs in predictions.values() for r in rs]
    )
    report["model_hash"] = E.immutable_json(DOCS / (PREFIX + "_MODELS.json"), artifacts)
    E.immutable_json(DOCS / (PREFIX + "_REPORT.json"), report)
    if ledger() != manifest["v0_ledger"]:
        raise ValueError("V0 modified STOP")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["freeze", "run"])
    args = parser.parse_args()
    freeze() if args.action == "freeze" else run()
