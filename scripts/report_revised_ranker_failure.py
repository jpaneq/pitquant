# ruff: noqa: E501
"""Preserve the invalidated first real fit; never replay or repair outcome results."""

from __future__ import annotations

import copy
import gzip
import json
from pathlib import Path

from pitquant.research.feature_availability import audit_feature_availability
from pitquant.research.ranking_preregistration import digest, encoded, write_once

ROOT = Path(__file__).resolve().parents[1]
ID = "FIRST_EQUITY_CROSS_SECTIONAL_RANK_12M_V0R1"
WORK = ROOT / "data/research/equity-ranking-v0r1"


def main() -> None:
    manifest = json.loads((ROOT / "docs" / (ID + "_MANIFEST.json")).read_bytes())
    audit = json.loads(
        (ROOT / "docs/TRAIN_FEATURE_AVAILABILITY_CONTRACT_V1_AUDIT.json").read_bytes()
    )
    inputs = json.loads(gzip.decompress((WORK / "inputs.json.gz").read_bytes()))
    integrity = json.loads((WORK / "inputs-integrity.json").read_bytes())
    invalidated = json.loads((WORK / "run/invalidated.json").read_bytes())
    first_fit = json.loads((WORK / "run/first-real-fit.json").read_bytes())
    if invalidated["reason"] != "no defined inner IC" or (WORK / "run/result.json").exists():
        raise ValueError("unexpected execution history; do not manufacture this report")
    names = tuple(manifest["contracts"]["features"]["names"])
    projected = audit_feature_availability(inputs["rows"], manifest["contracts"], names)
    if projected["removed"]:
        raise ValueError("revised feature preflight did not pass")
    corrected = copy.deepcopy(manifest)
    corrected.pop("manifest_sha256")
    corrected["implementation_metadata_revision"] = 2
    corrected["supersedes_metadata_manifest_sha256"] = manifest["manifest_sha256"]
    corrected["execution_permission"] = (
        "HUMAN_REVIEW_REQUIRED_AFTER_INVALIDATED_REAL_FIT; NOT_EXECUTED"
    )
    n = len(names)
    models = corrected["contracts"]["models"]
    models["L2R_M4"]["preprocessing"] = models["L2R_M4"]["preprocessing"].replace(
        "raw 44 features", f"raw {n} features"
    )
    models["EXPANDED_M4R_CONTROL"]["comparison"] = models["EXPANDED_M4R_CONTROL"][
        "comparison"
    ].replace("44 raw", f"{n} raw")
    models["EXPANDED_M4R_CONTROL"]["preprocessing"] = models["EXPANDED_M4R_CONTROL"][
        "preprocessing"
    ].replace(
        "44 missing indicators = 88 transformed columns",
        f"{n} missing indicators = {2 * n} transformed columns",
    )
    for name in ("L2R_M4", "EXPANDED_M4R_CONTROL"):
        models[name]["raw_feature_count"] = n
        models[name]["raw_feature_contract_sha256"] = manifest["feature_contract_sha256"]
    models["EXPANDED_M4R_CONTROL"]["transformed_feature_count"] = 2 * n
    corrected["contract_hashes"] = {k: digest(v) for k, v in corrected["contracts"].items()}
    corrected["manifest_sha256"] = digest(corrected)
    write_once(ROOT / "docs" / (ID + "_MANIFEST_METADATA_REVISION_2.json"), encoded(corrected))
    reproduction = {
        "experiment_id": ID,
        "status": "NOT_REPLAYED_INVALIDATED_EXECUTION",
        "reason": invalidated["reason"],
        "selected_params_verified": False,
        "outer_predictions_verified": False,
        "metrics_verified": False,
        "classification_verified": False,
        "no_silent_rerun": True,
        "holdout_outcomes_accessed": 0,
        "oot_outcomes_accessed": 0,
    }
    write_once(ROOT / "docs" / (ID + "_REPRODUCTION.json"), encoded(reproduction))
    failure = {
        "experiment_id": ID,
        "status": "INVALIDATED",
        "runtime_failure": invalidated,
        "first_real_fit": first_fit,
        "exception_log": Path("/tmp/ranker-r1-run.log").read_text(),
        "manifest_metadata_bug": "inherited descriptions said 44 RAW / 88 transformed; actual common matrix was 43 RAW, intended M4R 86 transformed; M4R was never fitted",
        "correction": "immutable metadata revision 2; no parameters/features/folds/labels changed; no new fit",
        "corrected_metadata_manifest_sha256": corrected["manifest_sha256"],
    }
    failure["sha256"] = digest(failure)
    write_once(ROOT / "docs" / (ID + "_EXECUTION_FAILURE.json"), encoded(failure))
    report = {
        "experiment_id": ID,
        "status": "INVALIDATED_REAL_FIT_NO_DEFINED_INNER_IC_AND_MANIFEST_METADATA_ERROR",
        "initial_head": "819cabea74ab73f1a24a1f20441729c8f4961f64",
        "dataset_sha256": inputs["dataset_sha256"],
        "dataset_changed": False,
        "original_feature_sha256": audit["original_feature_sha256"],
        "feature_contract_sha256": manifest["feature_contract_sha256"],
        "attempted_manifest_sha256": manifest["manifest_sha256"],
        "corrected_metadata_manifest_sha256": corrected["manifest_sha256"],
        "input_sha256": integrity["sha256"],
        "feature_availability_audit_sha256": audit["sha256"],
        "root_cause": audit["root_cause"],
        "original_feature_count": 44,
        "revised_raw_feature_count": len(names),
        "control_transformed_feature_count_if_fitted": 2 * len(names),
        "removed": audit["removed"],
        "added": [],
        "original_audit_cells": len(audit["cells"]),
        "revised_audit": projected,
        "unchanged": [
            "dataset",
            "row_cohort",
            "non_feature_row_provenance",
            "targets",
            "folds",
            "inner_geometry",
            "purge",
            "embargo",
            "XGBoost_parameters",
            "grid",
            "metrics",
            "bootstrap",
            "classification_rules",
        ],
        "V0_original_artifacts_preserved": True,
        "V0R1_frozen_before_first_real_fit": True,
        "models_fitted_on_real_data": 1,
        "mandatory_control_real_fits": 0,
        "first_attempt": {
            "fold": "F1",
            "candidate_index": 0,
            "parameters": manifest["contracts"]["grid"][0],
            "inner_blocks": 1,
            "validation_months": manifest["contracts"]["inner_cv"]["geometry"]["F1"][0][
                "VALIDATION"
            ],
            "defined_IC_months": 0,
            "undefined_IC_months": 6,
        },
        "inner_predictions_were_evaluated": True,
        "inner_scores_or_model_retained": False,
        "outer_predictions": 0,
        "selected_candidates": None,
        "metrics": None,
        "bootstrap": None,
        "classification": None,
        "F3_conclusion": "NOT_EVALUATED; no evidence on historical collapse",
        "holdout_consideration_conditions_met": False,
        "holdout_outcomes_accessed": 0,
        "oot_outcomes_accessed": 0,
        "dev_adaptive_iteration": 3,
        "FINAL_STRUCTURAL_DEV_EXPERIMENT": "INVALIDATED_NOT_COMPLETED",
        "replay": reproduction,
        "other_adapter_real_data_fits": 0,
        "recommendation": "HUMAN_REVIEW_INVALIDATED_INNER_IC_EXECUTION_BEFORE_ANY_NEW_FIT",
        "performance_decision_tree": "NOT_APPLICABLE_WITHOUT_VALID_OUTER_RESULT",
        "failure": failure,
    }
    report["sha256"] = digest(report)
    write_once(ROOT / "docs" / (ID + "_REPORT.json"), encoded(report))
    lines = [
        "# FIRST_EQUITY_CROSS_SECTIONAL_RANK_12M_V0R1 — invalidated first execution",
        "",
        "**No valid final ranking result. One real inner fit; zero outer predictions; no control fit.**",
        "",
        "## Feature correction",
        "",
        "All 44 frozen features were audited in 9 inner plus 3 outer TRAIN blocks (528 cells). "
        "Only `val_pe_own_pct` failed. The 43 retained features pass every block (516 cells). "
        "No arbitrary percentage coverage threshold was introduced.",
        "",
        "Frozen PE is prior raw close × split-aligned cover shares / positive visible TTM "
        "earnings. Zero/negative/unresolved earnings and stale/unresolved shares do not create PE. "
        "Own history requires 24 finite native PE observations from earlier decisions; the current "
        "point is added afterwards. It uses the last 60 valid decision observations, not elapsed "
        "calendar months. Facts are cut strictly before decision_at; prices close before decision. "
        "Histories are per security with issuer-resolved facts, just as the frozen dataset specifies.",
        "",
        "History begins at frozen COMBINED decisions in 2014-09. First theoretical and "
        "observed scientific availability is 2016-09. Full native replay matched every value and "
        "provenance in all 16,717 scientific rows. No construction bug was found.",
        "",
        "| Block | Rows | Issuers | PE valid / missing | PE coverage | Percentile valid | Issuers ≥24 prior PE |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for b in audit["root_cause"]["affected_blocks"]:
        pe = next(c for c in b["coverage"] if c["feature"] == "val_pe")
        lines.append(
            f"| {b['block']} | {b['rows']} | {b['issuers']} | {pe['finite_count']} / {pe['missing_count']} | {pe['coverage_pct']:.2f}% | 0 | {b['issuers_with_at_least_24_prior_valid_pe_points']} |"
        )
    lines.extend(
        [
            "",
            "The 18-month windows have at most 17 prior valid points; 24-month windows at most "
            "23. Percentile coverage is 0%, although PE itself has 88–90% coverage. This is warm-up, "
            "not a complete absence of source PE.",
            "",
            "REMOVE: `val_pe_own_pct`. ADD: nothing. XGB received 43 RAW columns. "
            "M4R was intended to receive the same 43 RAW plus 43 missing indicators (86); it was not fitted.",
            "",
            f"Dataset unchanged: `{inputs['dataset_sha256']}`.",
            "",
            f"Old feature hash: `{audit['original_feature_sha256']}`.",
            "",
            f"New feature hash: `{manifest['feature_contract_sha256']}`.",
            "",
            f"Attempted manifest: `{manifest['manifest_sha256']}`.",
            "",
            f"Corrected metadata manifest (not executed): `{corrected['manifest_sha256']}`.",
            "",
            f"Derived input: `{integrity['sha256']}`.",
            "",
            "## Execution failure and bug history",
            "",
            "All revised trainability/PIT/cohort/hash checks passed. The first real fit was "
            "F1/candidate 0: max_depth=2, learning_rate=0.03, reg_lambda=1; all other parameters "
            "were unchanged. All six inner validation-month ICs were undefined. The frozen "
            "selection contract requires at least one defined month. The runner raised "
            "`ValueError: no defined inner IC` and wrote an INVALIDATED record.",
            "",
            "This is an observed inner-execution failure, not evidence for a final negative "
            "ranking classification. No candidate was selected; F2/F3, outer TEST and M4R were "
            "not executed. Inner predictions were evaluated but their scores/model were not "
            "persisted before failure. The report does not fabricate them or assert an unverified "
            "causal explanation such as a Hessian threshold. No real fit was repeated.",
            "",
            "A second implementation error was discovered in inherited manifest descriptions: "
            "they still said 44 RAW/88 transformed while the execution used the 43-column projection. "
            "The attempted manifest remains immutable. A separate metadata revision 2 corrects "
            "43/86 and adds explicit feature-hash/count bindings, without changing parameters "
            "or outcomes. Its full 43-feature preflight passes, but it has not been executed. "
            "This technical fix is not permission for an additional adaptive search.",
            "",
            "## Scientific state",
            "",
            "V0 is preserved as aborted before fit. V0R1 is INVALIDATED after one real inner fit. "
            "Adaptive iteration = 3. Final structural experiment = INVALIDATED_NOT_COMPLETED. "
            "F1/F2/F3/combined metrics, paired comparison, quintiles, sector diagnostics, bootstrap "
            "and classification are null. No replay of an invalidated execution.",
            "",
            "Holdout outcomes = 0; OOT outcomes = 0; other challengers = 0. "
            "Conditions for holdout consideration are not met.",
            "",
            "One next step: `HUMAN_REVIEW_INVALIDATED_INNER_IC_EXECUTION_BEFORE_ANY_NEW_FIT`. "
            "A performance-based recommendation cannot be assigned without valid outer results.",
        ]
    )
    write_once(ROOT / "docs" / (ID + "_REPORT.md"), ("\n".join(lines) + "\n").encode())
    write_once(
        ROOT / "docs" / (ID + "_CONCLUSIONS.md"),
        (
            "# Conclusions — V0R1\\n\\n".replace("\\n", "\n")
            + "The TRAIN availability revision is deterministic and structurally justified: only "
            "val_pe_own_pct is excluded, preserving the frozen dataset and every observation.\n\n"
            "The first real fit failed the unchanged defined-inner-IC requirement. A manifest "
            "description/count bug was also recorded and corrected in a separate immutable "
            "metadata revision. No valid final signal classification or F3 conclusion exists.\n\n"
            "Iteration 3 has been consumed by a real fit. Do not silently rerun, discard a candidate, "
            "reduce min_child_weight, change normalization or weaken the IC guard. Human review "
            "is required before any new fit. Holdout/OOT remain sealed.\n"
        ).encode(),
    )
    print("Invalidated execution preserved", report["sha256"])


if __name__ == "__main__":
    main()
