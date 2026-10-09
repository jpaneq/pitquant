"""Execute only the final preregistered ranker and mandatory paired control."""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from pitquant.research import equity_baseline as E
from pitquant.research import equity_v1 as V
from pitquant.research import ranking_evaluation as R
from pitquant.research.feature_availability import require_feature_availability as require_trainable
from pitquant.research.ranker_adapters import XGBRankerAdapter
from pitquant.research.ranking_preregistration import (
    EXPERIMENT as ORIGINAL_EXPERIMENT,
)
from pitquant.research.ranking_preregistration import (
    digest,
    encoded,
    file_digest,
    verify_frozen_dataset,
    verify_manifest,
    write_once,
)

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ORIGINAL_EXPERIMENT + "R1"
WORK = ROOT / "data/research/equity-ranking-v0r1"


def arrays(
    rows: list[dict[str, Any]], names: tuple[str, ...]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if rows != sorted(rows, key=lambda r: (r["month"], r["issuer_id"])):
        raise ValueError("query serialization order")
    months = sorted({r["month"] for r in rows})
    qid = np.array([months.index(r["month"]) for r in rows], dtype=np.int64)
    x = E.matrix(rows, names)
    y = np.zeros(len(rows))
    for i in range(len(months)):
        mask = qid == i
        y[mask] = R.grades(np.array([r["excess_return"] for r in rows if r["month"] == months[i]]))
    return x, y, qid


def diagnostics(rows: list[dict[str, Any]], score: np.ndarray) -> list[dict[str, Any]]:
    return [
        R.monthly(
            [r for r in rows if r["month"] == month],
            score[np.array([r["month"] == month for r in rows])],
        )
        for month in sorted({r["month"] for r in rows})
    ]


def assert_groups(
    rows: list[dict[str, Any]], expected: dict[str, int], fit_at: str, role: str
) -> None:
    if dict(sorted(Counter(r["month"] for r in rows).items())) != expected:
        raise ValueError("complete month cohort contract violated")
    for row in rows:
        E.assert_row(row, role, fit_at)


def run(destination: Path) -> dict[str, Any]:
    lock = json.loads((ROOT / "docs" / (EXPERIMENT + "_EXECUTION_LOCK.json")).read_bytes())
    if digest({k: v for k, v in lock.items() if k != "sha256"}) != lock["sha256"]:
        raise ValueError("execution lock altered")
    for path, sha in lock["code_hashes"].items():
        if file_digest(ROOT / path) != sha:
            raise ValueError("execution code changed after lock")
    manifest = json.loads((ROOT / "docs" / (EXPERIMENT + "_MANIFEST.json")).read_bytes())
    verify_manifest(manifest)
    if manifest["manifest_sha256"] != lock["manifest_sha256"]:
        raise ValueError("manifest differs from execution lock")
    for path, sha in lock["original_artifacts"].items():
        if file_digest(ROOT / path) != sha:
            raise ValueError("original V0 artifact changed")
    audit = json.loads(
        (ROOT / "docs/TRAIN_FEATURE_AVAILABILITY_CONTRACT_V1_AUDIT.json").read_bytes()
    )
    if digest({k: v for k, v in audit.items() if k != "sha256"}) != audit["sha256"]:
        raise ValueError("feature availability audit changed")
    if audit["sha256"] != manifest["contracts"]["features"]["availability_audit_sha256"]:
        raise ValueError("feature audit binding changed")
    completion = json.loads(
        (ROOT / "docs" / (ORIGINAL_EXPERIMENT + "_IMPLEMENTATION_COMPLETION.json")).read_bytes()
    )
    if digest({k: v for k, v in completion.items() if k != "sha256"}) != completion["sha256"]:
        raise ValueError("implementation completion changed")
    if completion["sha256"] != manifest["implementation_completion_sha256"]:
        raise ValueError("implementation completion binding changed")
    integrity = json.loads((WORK / "inputs-integrity.json").read_bytes())
    if file_digest(WORK / "inputs.json.gz") != integrity["compressed_sha256"]:
        raise ValueError("inputs altered")
    data = json.loads(gzip.decompress((WORK / "inputs.json.gz").read_bytes()))
    if (
        digest(data) != integrity["sha256"]
        or data["dataset_sha256"] != manifest["contracts"]["dataset"]["sha256"]
    ):
        raise ValueError("input dataset hash mismatch")
    dataset = json.loads(
        (ROOT / "docs/US_LARGE_CAP_RESEARCH_DATASET_V1_FROZEN_MANIFEST.json").read_bytes()
    )
    verify_frozen_dataset(dataset, ROOT)
    if dataset["dataset_sha256"] != data["dataset_sha256"]:
        raise ValueError("frozen dataset changed")
    for path, sha in manifest["contracts"]["features"]["engine_hashes"].items():
        if file_digest(ROOT / path) != sha:
            raise ValueError("frozen scientific engine changed")
    if manifest["feature_contract_sha256"] != digest(manifest["contracts"]["features"]):
        raise ValueError("revised feature hash mismatch")
    if digest(data) != lock["input_sha256"]:
        raise ValueError("revised inputs differ from execution lock")
    names = tuple(manifest["contracts"]["features"]["names"])
    all_rows = data["rows"]
    require_trainable(all_rows, manifest["contracts"], names)
    outer = {name: [] for name in ("L2R_M4", "EXPANDED_M4R_CONTROL", "EQUAL_INFORMATION_BASELINE")}
    selection = {}
    predictions = []
    fits = {}
    for f in manifest["contracts"]["cohorts"]:
        fid = f"F{f['fold']}"
        train = [r for r in all_rows if r["month"] in f["TRAIN"]["monthly_rows"]]
        test = [r for r in all_rows if r["month"] in f["TEST"]["monthly_rows"]]
        assert_groups(train, f["TRAIN"]["monthly_rows"], f["fit_at"], "TRAIN")
        assert_groups(test, f["TEST"]["monthly_rows"], f["fit_at"], "TEST")
        inners = V.inner_folds({"TRAIN": train, "TEST": test, "fit_at": f["fit_at"]})
        geometry = manifest["contracts"]["inner_cv"]["geometry"][fid]
        if len(inners) != len(geometry):
            raise ValueError("inner geometry altered")
        candidates = []
        for index, grid in enumerate(manifest["contracts"]["grid"]):
            months = []
            for block, declared in zip(inners, geometry, strict=True):
                tr, va = block["train"], block["validation"]
                if (
                    sorted({r["month"] for r in tr}) != declared["TRAIN"]
                    or sorted({r["month"] for r in va}) != declared["VALIDATION"]
                ):
                    raise ValueError("inner month cohort changed")
                # No eligible row can disappear via maturity/sort/join.
                if len(tr) != sum(f["TRAIN"]["monthly_rows"][m] for m in declared["TRAIN"]):
                    raise ValueError("inner row loss")
                x, y, q = arrays(tr, names)
                xt, _, qt = arrays(va, names)
                model = XGBRankerAdapter({**completion["parameters_fixed"], **grid})
                write_once(
                    destination / "first-real-fit.json",
                    encoded(
                        {
                            "dev_adaptive_iteration": 3,
                            "first_fit": "XGBRanker",
                            "manifest_sha256": manifest["manifest_sha256"],
                            "preflight": "PASSED",
                            "replay": destination.name == "replay",
                        }
                    ),
                )
                model.fit(x, y, q)
                months.extend(diagnostics(va, model.predict(xt, qt)))
            defined = [m["ic"] for m in months if m["ic"] is not None]
            if not defined:
                raise ValueError("no defined inner IC")
            candidates.append(
                {
                    "index": index,
                    "parameters": grid,
                    "mean_monthly_ic": float(
                        np.mean([m["ic"] if m["ic"] is not None else 0.0 for m in months])
                    ),
                    "ndcg20": float(
                        np.mean([m["ndcg20"] if m["ndcg20"] is not None else 0.0 for m in months])
                    ),
                    "monthly": months,
                }
            )
        best = max(r["mean_monthly_ic"] for r in candidates)
        tied = [r for r in candidates if r["mean_monthly_ic"] >= best - 1e-12]
        ndcg = max(r["ndcg20"] for r in tied)
        selected = min([r for r in tied if r["ndcg20"] >= ndcg - 1e-12], key=lambda r: r["index"])
        selection[fid] = {
            "selected_index": selected["index"],
            "parameters": selected["parameters"],
            "candidates": candidates,
        }
        x, y, q = arrays(train, names)
        xt, _, qt = arrays(test, names)
        model = XGBRankerAdapter({**completion["parameters_fixed"], **selected["parameters"]})
        model.fit(x, y, q)
        scores = model.predict(xt, qt)
        fits[fid] = model.serialize(destination / fid)
        if not np.array_equal(scores, XGBRankerAdapter.load(destination / fid).predict(xt, qt)):
            raise ValueError("reload prediction mismatch")
        control, control_meta = V.fit_base(train, test, names, 0.01)
        write_once(destination / fid / "control.json", encoded(control_meta))
        for name, values in [
            ("L2R_M4", scores),
            ("EXPANDED_M4R_CONTROL", control),
            ("EQUAL_INFORMATION_BASELINE", np.zeros(len(test))),
        ]:
            outer[name].extend(diagnostics(test, values))
            predictions.extend(
                {
                    "model": name,
                    "fold": fid,
                    "security_id": r["security_id"],
                    "issuer_id": r["issuer_id"],
                    "month": r["month"],
                    "score": float(s),
                }
                for r, s in zip(test, values, strict=True)
            )
        print("Completed", fid, "selected grid", selected["index"], flush=True)
    metrics = {
        name: {
            **{f"F{i + 1}": R.aggregate(months[i * 12 : (i + 1) * 12]) for i in range(3)},
            "combined": R.aggregate(months),
        }
        for name, months in outer.items()
    }
    label = R.classify(metrics["L2R_M4"], metrics["EXPANDED_M4R_CONTROL"])
    holdout = R.holdout_conditions(metrics["L2R_M4"])
    paths = {
        "ROBUST_CROSS_SECTIONAL_SIGNAL": "HUMAN_REVIEW_FOR_HOLDOUT_CONSIDERATION",
        "PROMISING_CROSS_SECTIONAL_SIGNAL": "HUMAN_REVIEW_FOR_HOLDOUT_CONSIDERATION",
        "TEMPORALLY_UNSTABLE_SIGNAL": "EVALUATE_DOUBLEENSEMBLE_OR_TRA_DESIGN",
        "SECTOR_DRIVEN_SIGNAL": "DESIGN_SECTOR_RELATIVE_OR_RELATIONAL_MODEL",
        "NO_MEANINGFUL_RANKING_SIGNAL": "STOP_ALGORITHM_SEARCH_AND_ADD_NEW_INFORMATION",
    }
    result = {
        "experiment_id": EXPERIMENT,
        "status": ["RESEARCH_DEV_ONLY", "ADAPTIVE_DEV_ITERATION_3", "RETROSPECTIVE_UNVALIDATED"],
        "dataset_sha256": data["dataset_sha256"],
        "input_sha256": integrity["sha256"],
        "feature_contract_sha256": manifest["feature_contract_sha256"],
        "raw_feature_count": len(names),
        "control_transformed_feature_count": 2 * len(names),
        "preregistration_sha256": manifest["manifest_sha256"],
        "implementation_completion_sha256": completion["sha256"],
        "selection": selection,
        "metrics": metrics,
        "monthly": outer,
        "predictions": predictions,
        "model_artifacts": fits,
        "bootstrap": R.bootstrap(outer["L2R_M4"], outer["EXPANDED_M4R_CONTROL"]),
        "classification": label,
        "holdout_consideration_conditions_met": holdout,
        "recommendation": paths[label],
        "holdout_outcomes_accessed": 0,
        "oot_outcomes_accessed": 0,
        "dev_adaptive_iteration": 3,
        "FINAL_STRUCTURAL_DEV_EXPERIMENT": "completed",
        "real_data_challengers": ["XGBRanker"],
        "mandatory_control": "EXPANDED_M4R_CONTROL",
        "other_adapter_real_data_fits": 0,
        "bug_status": "NONE_DETECTED",
        "portfolio_status": "DIAGNOSTIC_NOT_BACKTEST",
    }
    write_once(destination / "result.json", encoded(result))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    destination = WORK / ("replay" if args.replay else "run")
    if (destination / "started.json").exists():
        raise ValueError("execution already attempted; do not silently rerun or repair")
    write_once(destination / "started.json", encoded({"status": "STARTED", "replay": args.replay}))
    try:
        result = run(destination)
    except Exception as exc:
        write_once(
            destination / "invalidated.json", encoded({"status": "INVALIDATED", "reason": str(exc)})
        )
        raise
    if args.replay:
        original = json.loads((WORK / "run/result.json").read_bytes())
        # Model reload metadata carries identical contents; output directories are not embedded.
        if encoded(result) != encoded(original):
            raise ValueError("full replay mismatch")
        write_once(
            ROOT / "docs" / (EXPERIMENT + "_REPRODUCTION.json"),
            encoded(
                {
                    "status": "EXACT_REPLAY_MATCH",
                    "result_sha256": digest(result),
                    "selected_parameters_equal": True,
                    "predictions_equal": True,
                    "scores_equal": True,
                    "classification_equal": True,
                    "tolerance": 0.0,
                    "holdout_outcomes_accessed": 0,
                    "oot_outcomes_accessed": 0,
                }
            ),
        )
    print("Finished", result["classification"], digest(result))


if __name__ == "__main__":
    main()
