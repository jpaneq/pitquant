"""Freeze outcome-free common feature revision before the first expanded-dataset fit."""

from __future__ import annotations

import copy
import gzip
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pitquant.research import first_ml_contract as C
from pitquant.research.feature_availability import (
    audit_feature_availability,
    require_feature_availability,
    training_blocks,
)
from pitquant.research.ranking_preregistration import (
    DATASET,
    EXPERIMENT,
    digest,
    encoded,
    file_digest,
    verify_frozen_dataset,
    verify_manifest,
    write_once,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/research/equity-ranking-v0r1"
REVISION = EXPERIMENT + "R1"


def main() -> None:
    old = json.loads((ROOT / "docs" / (EXPERIMENT + "_MANIFEST.json")).read_bytes())
    verify_manifest(old)
    dataset = json.loads((ROOT / "docs" / (DATASET + "_MANIFEST.json")).read_bytes())
    verify_frozen_dataset(dataset, ROOT)
    if dataset["dataset_sha256"] != old["contracts"]["dataset"]["sha256"]:
        raise ValueError("frozen dataset binding changed")
    for path, sha in old["contracts"]["features"]["engine_hashes"].items():
        if file_digest(ROOT / path) != sha:
            raise ValueError("scientific engine changed")
    previous = ROOT / "data/research/equity-ranking-v0"
    integrity = json.loads((previous / "inputs-integrity.json").read_bytes())
    if file_digest(previous / "inputs.json.gz") != integrity["compressed_sha256"]:
        raise ValueError("previous input altered")
    data = json.loads(gzip.decompress((previous / "inputs.json.gz").read_bytes()))
    if digest(data) != integrity["sha256"]:
        raise ValueError("original input payload changed")
    hi = json.loads((OUT / "history-integrity.json").read_bytes())
    if file_digest(OUT / "history.json.gz") != hi["compressed_sha256"]:
        raise ValueError("history replay altered")
    history = json.loads(gzip.decompress((OUT / "history.json.gz").read_bytes()))
    if digest(history) != hi["sha256"]:
        raise ValueError("history payload altered")
    histories = {(r["security_id"], r["month"]): r for r in history["rows"]}
    rows = data["rows"]
    if set(histories) != {(r["security_id"], r["month"]) for r in rows}:
        raise ValueError("history replay cohort mismatch")
    for r in rows:
        h = histories[(r["security_id"], r["month"])]
        if h["val_pe_own_pct"] != r["features"]["val_pe_own_pct"]:
            raise ValueError("percentile replay differs")
        value = h["val_pe_own_pct"]["value"]
        if value is not None and h["prior_valid_native_pe_points"] < 24:
            raise ValueError("historical minimum violated")
        if h["native_pe"] is not None and h["prior_valid_native_pe_points"] >= 24 and value is None:
            raise ValueError("availability bug; STOP before revision or fitting")
    audit = audit_feature_availability(rows, old["contracts"], C.M4.features)
    affected = []
    for block, selected in training_blocks(rows, old["contracts"]):
        if not any(c["block"] == block and not c["finite_count"] for c in audit["cells"]):
            continue
        pe_history = [histories[(r["security_id"], r["month"])] for r in selected]
        affected.append(
            {
                "block": block,
                "rows": len(selected),
                "issuers": len({r["issuer_id"] for r in selected}),
                "issuers_with_at_least_24_prior_valid_pe_points": len(
                    {r["issuer_id"] for r in pe_history if r["prior_valid_native_pe_points"] >= 24}
                ),
                "max_prior_valid_pe_points": max(
                    r["prior_valid_native_pe_points"] for r in pe_history
                ),
                "native_pe_missing_rows": sum(r["native_pe"] is None for r in pe_history),
                "native_vs_core_pe_differing_rows": sum(
                    r["native_pe"] != r["frozen_val_pe"] for r in pe_history
                ),
                "coverage": [
                    c
                    for c in audit["cells"]
                    if c["block"] == block and c["feature"] in ("val_pe", "val_pe_own_pct")
                ],
            }
        )
    first = min(r["month"] for r in history["rows"] if r["val_pe_own_pct"]["value"] is not None)
    audit["root_cause"] = {
        "classification": "STRUCTURALLY_UNAVAILABLE_IN_REQUIRED_TRAIN_WINDOWS",
        "bug": False,
        "source": (
            "valuation_point: raw prior close * split-aligned cover shares / "
            "visible positive TTM net income"
        ),
        "current_pe_invalid": (
            "zero/negative or unresolved earnings; unresolved/stale cover "
            "shares; no future fact rescue"
        ),
        "shares_max_age_days": 400,
        "history": (
            "one ValuationHistory per price security, issuer-resolved facts; "
            "finite native PE added AFTER percentile; last 60 valid prior "
            "decision points; minimum 24"
        ),
        "history_clock_note": (
            "frozen research implementation counts valid decision "
            "observations, not elapsed calendar months; no semantics changed"
        ),
        "percentile": "100 * count(prior_PE <= current_PE) / prior_point_count; ties included",
        "pit": (
            "facts strictly available_at < decision_at; price close before "
            "decision; history only earlier sorted decisions"
        ),
        "construction_start": (
            "2014-09; existing frozen COMBINED-eligible decision history only; no pre-start warming"
        ),
        "earliest_theoretical_month": "2016-09 after 24 valid monthly prior points",
        "first_observed_scientific_month": first,
        "affected_blocks": affected,
        "replay_feature_values_and_provenance_equal": True,
        "replay_history_sha256": hi["sha256"],
        "audit_checks": {
            k: "NO_BUG_DETECTED"
            for k in (
                "date_boundary",
                "expanding_history",
                "future_requirement",
                "join",
                "security_issuer_mapping",
                "missing_propagation",
                "history_reset",
                "minimum_history_vs_frozen_specification",
            )
        },
    }
    audit["original_feature_sha256"] = old["contract_hashes"]["features"]
    audit["dataset_sha256"] = dataset["dataset_sha256"]
    audit["sha256"] = digest(audit)
    write_once(ROOT / "docs/TRAIN_FEATURE_AVAILABILITY_CONTRACT_V1_AUDIT.json", encoded(audit))
    manifest = copy.deepcopy(old)
    manifest.pop("manifest_sha256")
    manifest["experiment_id"] = REVISION
    manifest["frozen_at"] = datetime.now(UTC).isoformat()
    manifest["supersedes"] = {
        "experiment_id": EXPERIMENT,
        "manifest_sha256": old["manifest_sha256"],
        "normalized_status": "ABORTED_PREFLIGHT_FEATURE_AVAILABILITY",
        "original_report_sha256": file_digest(ROOT / "docs" / (EXPERIMENT + "_REPORT.json")),
        "reason": "deterministic TRAIN feature availability; no prior real fit/prediction/metric",
    }
    names = tuple(audit["retained"])
    manifest["contracts"]["features"].update(
        names=list(names),
        base_count=len(names),
        semantics="original RAW M4 subset; deterministic all-TRAIN availability exclusion only",
        availability_contract="TRAIN_FEATURE_AVAILABILITY_CONTRACT_V1",
        availability_audit_sha256=audit["sha256"],
        removed=audit["removed"],
        added=[],
        original_feature_sha256=old["contract_hashes"]["features"],
    )
    manifest["contract_hashes"] = {k: digest(v) for k, v in manifest["contracts"].items()}
    manifest["feature_contract_sha256"] = manifest["contract_hashes"]["features"]
    manifest["implementation_completion_sha256"] = json.loads(
        (ROOT / "docs" / (EXPERIMENT + "_IMPLEMENTATION_COMPLETION.json")).read_bytes()
    )["sha256"]
    manifest["availability_revision_uses_model_outcomes"] = False
    manifest["manifest_sha256"] = digest(manifest)
    verify_manifest(manifest)
    # Projection changes only predictor columns. Every row, target and provenance survives.
    revised: dict[str, Any] = copy.deepcopy(data)
    revised["experiment_id"] = REVISION
    revised["feature_contract_sha256"] = manifest["feature_contract_sha256"]
    for row in revised["rows"]:
        row["features"] = {n: row["features"][n] for n in names}
    require_feature_availability(revised["rows"], manifest["contracts"], names)
    for a, b in zip(rows, revised["rows"], strict=True):
        if {k: v for k, v in a.items() if k != "features"} != {
            k: v for k, v in b.items() if k != "features"
        }:
            raise ValueError("row/label/cohort changed")
    write_once(OUT / "inputs.json.gz", gzip.compress(encoded(revised), mtime=0))
    write_once(
        OUT / "inputs-integrity.json",
        encoded(
            {
                "sha256": digest(revised),
                "compressed_sha256": file_digest(OUT / "inputs.json.gz"),
                "rows": len(rows),
                "frozen_dataset_sha256": dataset["dataset_sha256"],
                "parent_input_sha256": integrity["sha256"],
                "feature_contract_sha256": manifest["feature_contract_sha256"],
            }
        ),
    )
    write_once(ROOT / "docs" / (REVISION + "_MANIFEST.json"), encoded(manifest))
    write_once(
        ROOT / "docs" / (REVISION + "_PREREGISTRATION.md"),
        (
            "# FIRST_EQUITY_CROSS_SECTIONAL_RANK_12M_V0R1\n\n"
            "Status: PREREGISTERED_NOT_RUN; frozen before the first real fit.\n\n"
            "Supersedes V0, aborted before fitting for TRAIN feature availability. "
            "The original artifacts are immutable. This revision uses TRAIN availability only.\n\n"
            f"Dataset unchanged: `{dataset['dataset_sha256']}`.\n\n"
            f"Manifest: `{manifest['manifest_sha256']}`.\n\n"
            f"Feature contract: `{manifest['feature_contract_sha256']}`.\n\n"
            f"Removed: `{audit['removed']}`. Added: nothing. RAW count: {len(names)}.\n\n"
            "Eligibility requires at least one finite value in every required inner and outer "
            "TRAIN. No other coverage threshold. "
            "Partial missingness retains original processing.\n\n"
            "XGB and M4R use identical RAW features and issuer-month rows. "
            "M4R has one TRAIN-derived missingness indicator per retained feature.\n\n"
            "Dataset, targets, cohorts, 1/3/5 inner geometry, outer folds, purge and embargo "
            "are unchanged. XGBoost 3.1.3 parameters, eight candidates, selection, metrics, "
            "sector N>=10, bootstrap 1000/PCG64/20261009, classification and holdout rules "
            "are copied exactly from V0 and its implementation completion; "
            "see the full manifest.\n\n"
            "Current adaptive iteration is 2; first real fit increments it to 3. "
            "No other challenger, holdout or OOT is authorized.\n"
        ).encode(),
    )
    paths = [
        "scripts/run_revised_equity_ranker.py",
        "src/pitquant/research/feature_availability.py",
        "src/pitquant/research/ranker_adapters.py",
        "src/pitquant/research/ranking_evaluation.py",
        "src/pitquant/research/ranking_preregistration.py",
        "scripts/freeze_revised_ranker.py",
        "scripts/audit_ranker_feature_history.py",
        "pyproject.toml",
    ]
    lock = {
        "experiment_id": REVISION,
        "manifest_sha256": manifest["manifest_sha256"],
        "input_sha256": digest(revised),
        "code_hashes": {p: file_digest(ROOT / p) for p in paths},
        "implementation_completion_sha256": manifest["implementation_completion_sha256"],
        "preflight": "PASSED_BEFORE_ANY_REAL_FIT",
        "dev_adaptive_iteration": 2,
        "original_artifacts": {
            str(p.relative_to(ROOT)): file_digest(p)
            for p in sorted((ROOT / "docs").glob(EXPERIMENT + "_*"))
        },
    }
    lock["sha256"] = digest(lock)
    write_once(ROOT / "docs" / (REVISION + "_EXECUTION_LOCK.json"), encoded(lock))
    print(
        "V0R1 frozen before fits", manifest["manifest_sha256"], "features", len(names), flush=True
    )


if __name__ == "__main__":
    main()
