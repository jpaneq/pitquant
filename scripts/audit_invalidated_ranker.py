# ruff: noqa: E501
"""Read-only forensic statistics. No estimator imports, fits, predictions or dataset rebuild."""

from __future__ import annotations

import gzip
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from pitquant.research.ranking_preregistration import digest, encoded, file_digest, write_once

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = "FIRST_EQUITY_CROSS_SECTIONAL_RANK_12M_V0R1"
DIAGNOSTIC = EXPERIMENT + "_FAILURE_DIAGNOSTIC"
INITIAL_HEAD = "a44ecc0853109fa268b77d694361fa14acfdc6b6"


def label_statistics(values: NDArray[np.float64]) -> dict[str, Any]:
    finite = np.isfinite(values)
    if len(values) < 2 or not finite.all():
        raise ValueError("invalid archived validation labels")
    # Exact frozen average-rank percentile -> decile, used only for descriptive counts.
    from scipy.stats import rankdata

    percentile = (rankdata(values, method="average") - 1) / (len(values) - 1)
    grades = np.minimum(9, np.floor(10 * percentile))
    return {
        "distinct": len(np.unique(values)),
        "sd_population_ddof0": float(np.std(values, ddof=0)),
        "min": float(values.min()),
        "max": float(values.max()),
        "nonfinite": int((~finite).sum()),
        "relevance_grades_distinct": len(np.unique(grades)),
        "relevance_grade_counts": dict(Counter(str(int(g)) for g in grades)),
        "grade_evidence": "derived descriptively from archived target using frozen transformation; runtime grade array not retained",
    }


def unavailable_scores() -> dict[str, Any]:
    return {
        "distinct": None,
        "sd_population_ddof0": None,
        "min": None,
        "max": None,
        "identical_pct_modal_share": None,
        "nonfinite": None,
        "reason": "NO_INVALIDATED_RUN_PREDICTIONS_ARCHIVED",
    }


def month_record(month: str, rows: list[dict[str, Any]], qid: int) -> dict[str, Any]:
    labels = np.array([r["excess_return"] for r in rows], dtype=float)
    dates = {r["decision_at"] for r in rows}
    if len(dates) != 1 or len({r["issuer_id"] for r in rows}) != len(rows):
        raise ValueError("invalid archived month identity")
    if any(r["month"] != month for r in rows):
        raise ValueError("archived month group mismatch")
    if any(r["target_end"][:10] >= "2022-10-01" for r in rows):
        raise ValueError("holdout/OOT label prohibited")
    return {
        "month": month,
        "decision_at": next(iter(dates)),
        "rows": len(rows),
        "issuers": len({r["issuer_id"] for r in rows}),
        "qid_from_frozen_input_order": qid,
        "targets": label_statistics(labels),
        "outperform_binary_target_distinct": len({r["actual_target"] for r in rows}),
        "scores": unavailable_scores(),
        "IC": None,
        "IC_evidence": "undefined reported by invalidated execution; per-month metric array not retained",
        "monthly_cause_classification": "OTHER",
        "cause_detail": "INSUFFICIENT_EVIDENCE: prediction array unavailable; not an observed alternative numeric cause",
        "ruled_out_in_archived_inputs": [
            "CONSTANT_TARGET",
            "INSUFFICIENT_ROWS",
            "NONFINITE_TARGET_VALUES",
        ],
        "constant_predictions_confirmed": None,
        "row_key_sha256": digest([(r["issuer_id"], r["security_id"], r["month"]) for r in rows]),
        "target_binding_sha256": digest(
            [(r["issuer_id"], r["month"], r["excess_return"]) for r in rows]
        ),
    }


def audit(root: Path) -> dict[str, Any]:
    work = root / "data/research/equity-ranking-v0r1"
    manifest_path = root / "docs" / (EXPERIMENT + "_MANIFEST.json")
    manifest = json.loads(manifest_path.read_bytes())
    lock = json.loads((root / "docs" / (EXPERIMENT + "_EXECUTION_LOCK.json")).read_bytes())
    if digest({k: v for k, v in lock.items() if k != "sha256"}) != lock["sha256"]:
        raise ValueError("frozen execution lock changed")
    if manifest["manifest_sha256"] != lock["manifest_sha256"]:
        raise ValueError("forensic manifest/lock binding mismatch")
    for path, sha in {**lock["original_artifacts"], **lock["code_hashes"]}.items():
        if file_digest(root / path) != sha:
            raise ValueError("frozen forensic code/artifact changed")
    if (
        digest({k: v for k, v in manifest.items() if k != "manifest_sha256"})
        != manifest["manifest_sha256"]
    ):
        raise ValueError("attempted manifest changed")
    integrity = json.loads((work / "inputs-integrity.json").read_bytes())
    if file_digest(work / "inputs.json.gz") != integrity["compressed_sha256"]:
        raise ValueError("archived execution input changed")
    payload = json.loads(gzip.decompress((work / "inputs.json.gz").read_bytes()))
    if digest(payload) != lock["input_sha256"] or digest(payload) != integrity["sha256"]:
        raise ValueError("archived input binding mismatch")
    if (
        payload["dataset_sha256"] != manifest["contracts"]["dataset"]["sha256"]
        or payload["feature_contract_sha256"] != manifest["feature_contract_sha256"]
    ):
        raise ValueError("forensic dataset/feature binding mismatch")
    fail_path = root / "docs" / (EXPERIMENT + "_EXECUTION_FAILURE.json")
    failure = json.loads(fail_path.read_bytes())
    if digest({k: v for k, v in failure.items() if k != "sha256"}) != failure["sha256"]:
        raise ValueError("archived failure altered")
    files = sorted(p for p in (work / "run").rglob("*") if p.is_file())
    if {p.name for p in files} != {"started.json", "first-real-fit.json", "invalidated.json"}:
        raise ValueError("run inventory differs; investigate new artifacts before classifying")
    invalidated = json.loads((work / "run/invalidated.json").read_bytes())
    if invalidated != failure["runtime_failure"] or invalidated["reason"] != "no defined inner IC":
        raise ValueError("unexpected invalidation")
    geometry = manifest["contracts"]["inner_cv"]["geometry"]["F1"][0]
    months = geometry["VALIDATION"]
    # Read archived DEV inputs only. Never query a provider, raw source or frozen database.
    validation = [r for r in payload["rows"] if r["month"] in months]
    if validation != sorted(validation, key=lambda r: (r["month"], r["issuer_id"])):
        raise ValueError("validation serialization changed")
    keys = [(r["issuer_id"], r["month"]) for r in validation]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate archived issuer-month")
    expected = {m: manifest["contracts"]["cohorts"][0]["TRAIN"]["monthly_rows"][m] for m in months}
    if dict(Counter(r["month"] for r in validation)) != expected:
        raise ValueError("archived complete-group count mismatch")
    records = [
        month_record(m, [r for r in validation if r["month"] == m], i) for i, m in enumerate(months)
    ]
    paths = [
        manifest_path,
        fail_path,
        work / "inputs.json.gz",
        work / "inputs-integrity.json",
        *files,
    ]
    inventory = {str(p.relative_to(root)): file_digest(p) for p in paths}
    params = json.loads(
        (
            root / "docs/FIRST_EQUITY_CROSS_SECTIONAL_RANK_12M_V0_IMPLEMENTATION_COMPLETION.json"
        ).read_bytes()
    )["parameters_fixed"]
    selection = manifest["contracts"]["inner_cv"]["selection"]
    return {
        "diagnostic_id": DIAGNOSTIC,
        "initial_head": INITIAL_HEAD,
        "scope": "EXCLUSIVELY_DIAGNOSTIC_NO_NEW_FIT",
        "artifact_inventory": inventory,
        "archive_sufficiency": {
            "inputs_and_validation_targets": True,
            "validation_predictions": False,
            "runtime_qid_array": False,
            "inner_model": False,
            "inner_metric_array": False,
            "note": "synthetic V0 smoke model is excluded; it is not the invalidated real model",
        },
        "monthly": records,
        "qid": {
            "status": "ARCHIVED_INPUT_GROUPS_AND_STATIC_ALIGNMENT_PASS_RUNTIME_SCORES_UNVERIFIABLE",
            "validation_rows": len(validation),
            "monthly_qids_from_static_contract": list(range(len(months))),
            "monthly_group_counts": expected,
            "sorted": True,
            "duplicate_issuer_months": 0,
            "duplicate_security_months": len(validation)
            - len({(r["security_id"], r["month"]) for r in validation}),
            "complete_groups": True,
            "runtime_score_target_binding": "NOT_VERIFIABLE_WITHOUT_PREDICTIONS",
            "static_evidence": "arrays constructs X/grades/qid in one row order; diagnostics uses identical month mask for rows and score vector; predict rejects nonfinite or wrong-shaped scores",
        },
        "model": {
            "configured_n_estimators": params["n_estimators"],
            "actual_built_trees": None,
            "trees_with_splits": None,
            "trees_without_splits": None,
            "total_leaves": None,
            "feature_importance": None,
            "score_distribution": None,
            "learned_vs_evaluation_failed": "UNDETERMINABLE_NO_MODEL_OR_SCORES_ARCHIVED",
        },
        "hyperparameters": {**params, **manifest["contracts"]["grid"][0]},
        "hyperparameter_review": {
            "min_child_weight": "threshold on summed child Hessian, not row count. 10 can reject every proposed split if child Hessians are too small; actual gradients/Hessians not archived",
            "mean_pairs_8_and_normalization": "mean samples pairs and normalization scales gradient/Hessian by inverse pair count; interaction with the child threshold is possible, not established for this fit",
            "max_depth": "2 caps depth, does not require or forbid a root split",
            "reg_lambda": "1 adds L2 regularization to leaf weight/gain; may reduce gains; not evidence all gains were nonpositive",
            "learning_rate": "0.03 shrinks tree contributions; nonzero rate alone does not force unsplit trees",
            "causal_assignment": "NONE_WITHOUT_MODEL_OR_GRADIENT_ARTIFACTS",
            "sources": [
                "https://raw.githubusercontent.com/dmlc/xgboost/v3.1.3/src/tree/hist/evaluate_splits.h",
                "https://raw.githubusercontent.com/dmlc/xgboost/v3.1.3/src/tree/param.h",
                "https://raw.githubusercontent.com/dmlc/xgboost/v3.1.3/src/objective/lambdarank_obj.cc",
            ],
        },
        "selection_audit": {
            "frozen_rule": selection,
            "one_month_undefined": "0 contributes to candidate selection mean only; metric stays null; candidate must have another defined month",
            "all_candidate_months_undefined": "raise ValueError before candidate append; uncaught until run-level invalidation; no continue to next candidate",
            "remaining_candidates": "NOT_EXECUTED_AND_UNREACHABLE_AFTER_THIS_EXCEPTION; no claim about their scores or performance",
            "contract_text_scope": "minimum one defined month is explicit; text alone does not explicitly distinguish rejecting candidate from aborting whole experiment",
            "operative_frozen_code": "unambiguously aborts whole execution; no predeclared candidate-discard path",
            "reinterpretation_allowed": False,
            "revision_if_discard_candidates": "METHODOLOGICAL_CHANGE_REQUIRES_NEW_PREREGISTRATION",
        },
        "classification": "F — INSUFFICIENT_EVIDENCE",
        "primary_cause": "missing retained model, scores and per-month metric arrays prevents exact attribution of undefined IC",
        "secondary_findings": [
            "failure-path observability defect: inner outputs existed in memory but exception archive stores reason only; serialization happens only after outer fitting",
            "44/88 description mismatch already recorded/corrected separately; no evidence it caused undefined IC",
            "textual candidate-invalidity scope incomplete; frozen code enforces global abort; no numerical evaluation bug demonstrated",
        ],
        "constant_predictions": "NOT_CONFIRMED; compatible with frozen control flow, not measured",
        "technical_repair": "prospective persistence of inner model/config, row-key-bound score/target/qid arrays and diagnostic reasons before abort; cannot recover this attempt; NOT_IMPLEMENTED",
        "method_revision": "only if future human review changes treatment of wholly undefined candidate; NOT_AUTHORIZED_OR_IMPLEMENTED",
        "hyperparameter_change": "would be a new scientific experiment, not a technical repair; no value proposed or tried",
        "reexecution": "NOT_AUTHORIZED; no silent replay; prospective exact instrumented reexecution needs a distinct attempt identity and human approval, cannot verify equivalence to missing old outputs",
        "recommendation": "FIX_IMPLEMENTATION_BUG",
        "recommendation_scope": "repair failure-path artifact retention only; not an assertion about model/evaluation cause; recommendation NOT_EXECUTED",
        "holdout_outcomes_accessed": 0,
        "oot_outcomes_accessed": 0,
        "new_fits": 0,
        "scientific_progress_claimed": False,
        "dev_adaptive_iteration": 3,
        "FINAL_STRUCTURAL_DEV_EXPERIMENT": "INVALIDATED_NOT_COMPLETED",
    }


def main() -> None:
    report = audit(ROOT)
    # Output is new, append-only diagnostic evidence; original artifacts remain byte-identical.
    report["sha256"] = digest(report)
    write_once(ROOT / "docs" / (DIAGNOSTIC + ".json"), encoded(report))
    for path, sha in report["artifact_inventory"].items():
        if file_digest(ROOT / path) != sha:
            raise ValueError("forensic audit mutated an input artifact")
    lines = [
        "# XGBRanker V0R1 — diagnostic audit",
        "",
        "**F — INSUFFICIENT_EVIDENCE. No new fits. No exact causal attribution is possible from the retained artifacts.**",
        "",
        "## Retained evidence",
        "",
        "The failed run contains started.json, first-real-fit.json and invalidated.json only. "
        "Archived inputs bind each issuer/month to its validation target and 43 feature values. "
        "No inner model, prediction vector, native tree dump, runtime qid or monthly metric array "
        "was persisted. Synthetic smoke models are not evidence of this real fit.",
        "",
        "All input and frozen code hashes match the attempted execution lock. This audit did "
        "not open the frozen database, raw market sources, holdout/OOT or any other model.",
        "",
        "## Six validation months",
        "",
        "Target is archived H12 excess total return, in return fractions; SD is population ddof=0. "
        "Relevance-grade counts are descriptive application of the frozen transformation to "
        "those archived labels, not a recovered runtime grade array.",
        "",
        "| Month | Decision UTC | Issuers | Distinct targets | Target SD | Distinct grades | Score distinct / SD / min / max / identical % | Monthly cause |",
        "|---|---|---:|---:|---:|---:|---|---|",
    ]
    for r in report["monthly"]:
        lines.append(
            f"| {r['month']} | {r['decision_at']} | {r['issuers']} | {r['targets']['distinct']} | {r['targets']['sd_population_ddof0']:.9f} | {r['targets']['relevance_grades_distinct']} | unavailable / unavailable / unavailable / unavailable / unavailable | OTHER: missing scores |"
        )
    lines.extend(
        [
            "",
            "None of the six archived target groups is constant, nonfinite or too small. "
            "OTHER denotes unavailable causal evidence, not proof of an additional numerical cause. "
            "Constant scores are compatible with the frozen IC function/control flow, but their "
            "actual distinct count, spread, extrema and modal identical percentage cannot be measured. "
            "We do not assign CONSTANT_PREDICTIONS without the prediction vector.",
            "",
            "## Trees and alignment",
            "",
            "Configured trees: 200. Actual constructed trees, splits, leaves, feature importance "
            "and score distribution: unavailable. Even a confirmed constant validation vector "
            "would not by itself prove every tree is a stump. Learned model versus failed "
            "evaluation cannot be distinguished here.",
            "",
            f"The archived validation has {report['qid']['validation_rows']} rows, qids 0–5 in "
            "month order, complete expected groups and no issuer-month or security-month duplicates. "
            "The frozen source constructs X/grades/qid in the same row order and masks rows and "
            "scores with the same monthly selector. No static alignment bug was found; actual "
            "score/target correspondence cannot be certified without runtime predictions.",
            "",
            "## Static parameter review",
            "",
            "First candidate: depth=2, lambda=1, learning_rate=0.03. min_child_weight=10 thresholds "
            "child Hessian sums, not ten rows; small child Hessians can block every split. "
            "[XGBoost 3.1.3 split evaluator](https://raw.githubusercontent.com/dmlc/xgboost/v3.1.3/src/tree/hist/evaluate_splits.h).",
            "",
            "Mean pair sampling uses eight pairs; the enabled normalization scales pair gradients "
            "and Hessians. Its interaction with the child threshold is a possible mechanism, "
            "not evidence of this fit's cause. [LambdaRank source](https://raw.githubusercontent.com/dmlc/xgboost/v3.1.3/src/objective/lambdarank_obj.cc).",
            "",
            "Depth caps growth; L2 changes leaf weight/gain; positive learning_rate shrinks updates. "
            "None alone demonstrates that this model had no splits. No alternative value was "
            "tried. [Tree parameter source](https://raw.githubusercontent.com/dmlc/xgboost/v3.1.3/src/tree/param.h).",
            "",
            "## Selection contract",
            "",
            "An undefined month contributes zero only to selection if another month is defined; "
            "the published IC remains null. A wholly undefined candidate raises before append, "
            "invalidating the entire run. Candidates 1–7 and all later folds/control were unreachable "
            "after this exception; no performance claim about them can be made.",
            "",
            "The preregistration states a minimum of one defined month but does not explicitly "
            "spell out whole-experiment abort versus candidate rejection. The pre-fit frozen "
            "executor unequivocally implements global abort. Discarding a candidate and continuing "
            "would change the operative policy and requires a new methodological preregistration. "
            "This audit does not change that policy or demonstrate a numerical Spearman bug.",
            "",
            "## Classification and next step",
            "",
            "Exactly one classification: **F — INSUFFICIENT_EVIDENCE**. A proven secondary "
            "observability defect is that inner scores/model/monthly diagnostics were lost on "
            "exception. The previous 44/88 metadata-description error is separate; there is no "
            "evidence tying it to undefined IC.",
            "",
            "Exactly one recommendation: **FIX_IMPLEMENTATION_BUG**, limited to prospective "
            "failure-path artifact retention. Save model/config and row-key-bound scores, targets, "
            "grades and qid, with per-month diagnostic reasons, before throwing. This repair "
            "cannot recover historical outputs and has NOT been implemented in this task.",
            "",
            "Instrumenting persistence without changing numerical behavior is a technical repair. "
            "Changing candidate-invalidity policy is methodological; changing hyperparameters "
            "is a new scientific experiment. Any future exact reexecution needs human authorization "
            "and a distinct attempt identifier; it cannot be called a verified replay of outputs "
            "that were not saved. No reexecution or new experiment is authorized here.",
            "",
            "New fits = 0; holdout outcomes = 0; OOT outcomes = 0. Iteration remains 3. "
            "Final experiment remains INVALIDATED_NOT_COMPLETED. No scientific progress claimed.",
        ]
    )
    write_once(ROOT / "docs" / (DIAGNOSTIC + ".md"), ("\n".join(lines) + "\n").encode())
    print(report["classification"], report["recommendation"], "new fits", report["new_fits"])


if __name__ == "__main__":
    main()
