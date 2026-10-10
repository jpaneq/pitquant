#!/usr/bin/env python3
"Freeze existing opaque inputs and outcome-free contracts; no training entry point."

from __future__ import annotations

import gzip
import importlib.metadata
import itertools
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from pitquant.research import first_ml_contract as C
from pitquant.research.ranking_preregistration import (
    DATASET,
    EXPERIMENT,
    digest,
    encoded,
    file_digest,
    verify_manifest,
    write_once,
)

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "data/research/us-targeted-closure-v1"
FROZEN = ROOT / "data/research/us-large-cap-frozen-v1"
INITIAL = "9929b0d6c6090e0bdcb0da1df7c083cb132bf4ca"


def load(path: Path) -> Any:
    return json.loads(path.read_bytes())


def availability(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "NOT_INSTALLED"


def freeze_database() -> dict[str, Any]:
    """Opaque byte snapshot only: no SELECT, no label/outcome deserialization."""
    source = WORK / "candidate.db"
    for suffix in ("-wal", "-journal"):
        if Path(str(source) + suffix).exists():
            raise ValueError("candidate has an active SQLite sidecar; stop freeze")
    destination = FROZEN / "candidate.db"
    FROZEN.mkdir(parents=True, exist_ok=True)
    original_hash = file_digest(source)
    if not destination.exists():
        # APFS clone has independent inode/blocks on mutation, unlike a hard link.
        subprocess.run(["cp", "-c", str(source), str(destination)], check=True)
        destination.chmod(0o444)
    if file_digest(destination) != original_hash:
        raise ValueError("frozen database integrity conflict")
    return {
        "path": str(destination.relative_to(ROOT)),
        "sha256": original_hash,
        "bytes": destination.stat().st_size,
        "format": "SQLITE_OPAQUE_READ_ONLY_SNAPSHOT",
        "access": "mode=ro; immutable=1; execution must use this copy, not candidate.db",
        "outcome_policy": (
            "Byte hashing is not outcome access. No SQL in this task. Future "
            "execution must whitelist DEV inputs and exclude sealed outcome "
            "tables."
        ),
    }


def inner_geometry(months: list[str]) -> list[dict[str, Any]]:
    # Exact V1 geometry: min18 train months, gap13, validation6, step6.
    result = []
    start = 17 + 13
    while start + 5 < len(months):
        result.append(
            {
                "TRAIN": months[: start - 12],
                "VALIDATION": months[start : start + 6],
                "excluded_decision_months": months[start - 12 : start],
                "train_condition": (
                    "month_index(t)+13 <= month_index(validation_start) AND "
                    "target_end < fit_at AND label_available_at < fit_at"
                ),
                "fit_at": "first XNYS session open of validation_start",
            }
        )
        start += 6
    return result


def main() -> None:
    report = load(ROOT / "docs/US_LARGE_CAP_RESEARCH_TARGETED_CLOSURE_V1.json")
    universe_path = WORK / "aliases/US_LARGE_CAP_RESEARCH_UNIVERSE_V1.json"
    universe = load(universe_path)
    candidate_path = ROOT / "docs" / report["candidate"]["path"]
    if file_digest(candidate_path) != report["candidate"]["sha256"]:
        raise ValueError("targeted candidate changed")
    candidate = json.loads(gzip.decompress(candidate_path.read_bytes()))
    if candidate["has_targets"]:
        raise ValueError("target-free source required")
    eligible = [r for r in candidate["scientific_rows"] if r["combined_scientific_eligible"]]
    keys = [(r["month"], r["issuer_id"]) for r in eligible]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate scientific issuer-month; cannot freeze silently")
    for path, sha in report["frozen_artifact_hashes"].items():
        if file_digest(ROOT / path) != sha:
            raise ValueError("protected experiment artifact changed")
    db = freeze_database()
    monthly = report["scientific"]["months"]
    coverage = {
        **report["proposed_contract"],
        "status": "FROZEN_ENGINEERING_BREADTH_GATE",
        "defined_without_model_outcomes": True,
        "downsampling": "NONE_ALL_ELIGIBLE",
    }
    if len(monthly) != 85 or not all(
        m["scientific_issuers"] >= 100
        and m["membership_coverage_fraction"] >= 0.5
        and m["represented_sectors"] >= 5
        and m["largest_sector_share"] <= 0.6
        and m["top3_sector_share"] <= 0.9
        for m in monthly
    ):
        raise ValueError("frozen coverage gate failed")
    cohorts: list[dict[str, Any]] = []
    for f in report["folds"]:
        roles = {}
        for role in ("TRAIN", "TEST"):
            months = f["months"][role]
            observations = [r for r in eligible if r["month"] in months]
            rows_by_month = Counter(r["month"] for r in observations)
            roles[role] = {
                "rows": len(observations),
                "months": len(months),
                "monthly_rows": dict(sorted(rows_by_month.items())),
                "issuer_distribution": f["scientific_coverage"][role],
                "sector_breadth": [m for m in monthly if m["month"] in months],
                "keys_sha256": digest(
                    sorted((r["month"], r["issuer_id"], r["security_id"]) for r in observations)
                ),
            }
        cohorts.append(
            {"fold": f["index"] + 1, "geometry": f["dates"], "fit_at": f["fit_at"], **roles}
        )
    source_refs = [
        s for s in universe["source_index"] if s.get("status") == 200 and s.get("sha256")
    ]
    # Original sources are content addressed. Freeze their hashes, not parsed future values.
    source_inventory = sorted({s["sha256"] for s in source_refs})
    for sha in source_inventory:
        path = ROOT / "data/archive" / sha[:2] / sha[2:4] / sha
        if file_digest(path) != sha:
            raise ValueError("raw archive integrity failure")
    sources = {
        "index": source_refs,
        "raw_object_sha256": source_inventory,
        "original_sources_contain_post_DEV_records": True,
        "opaque_hash_verification_only": True,
        "future_value_parsing": (
            "FORBIDDEN_IN_THIS_TASK; timestamps/null metadata already frozen separately"
        ),
    }
    engine_paths = [
        "src/pitquant/research/first_ml_contract.py",
        "src/pitquant/research/features_v1.py",
        "src/pitquant/research/fundamentals_v1.py",
        "src/pitquant/research/targets_v1.py",
        "src/pitquant/research/targets_v2.py",
        "src/pitquant/research/benchmark_contract.py",
        "src/pitquant/research/equity_baseline.py",
        "src/pitquant/research/equity_v1.py",
        "src/pitquant/research/us_targeted_closure.py",
        "src/pitquant/features/v0/fundamentals.py",
        "scripts/audit_us_scientific_constructibility.py",
    ]
    engines = {p: file_digest(ROOT / p) for p in engine_paths}
    layers = {
        "membership": {
            "sha256": universe["hashes"]["membership"],
            "evidence": universe["evidence_manifest"],
        },
        "identity": {"sha256": universe["hashes"]["identity"], "roster": universe["roster"]},
        "price": {
            "sha256": universe["hashes"]["price_universe"],
            "qa": universe["price_audits"],
            "baseline_series_sha256": candidate["baseline_price_series_sha256"],
            "baseline_series_path": "docs/US_LARGE_CAP_RESEARCH_DATASET_V1.json.gz",
            "baseline_series_file_sha256": file_digest(
                ROOT / "docs/US_LARGE_CAP_RESEARCH_DATASET_V1.json.gz"
            ),
            "additional_series": candidate["additional_price_series"],
        },
        "fundamentals": {
            "sha256": universe["hashes"]["fundamental_universe"],
            "facts_snapshot": db,
            "ingestion": universe["sec_ingestion"],
            "availability_rows_sha256": digest(candidate["rows"]),
        },
        "corporate_actions": {
            "facts_snapshot": db,
            "qa_sources": {k: v.get("source_hash") for k, v in universe["price_audits"].items()},
            "semantics": (
                "native actions known strictly before T0; no successor price "
                "splice; distribution/class exceptions remain frozen in "
                "scientific auditor"
            ),
        },
        "sec_mapping": {
            "version": "sec-tags-5",
            "engine_sha256": engines["src/pitquant/research/us_targeted_closure.py"],
            "correction_requires": ["NEW_DATASET_VERSION", "NEW_EXPERIMENT_VERSION"],
        },
        "benchmark": {
            "ticker": "SPY",
            "exchange": "XNYS",
            "currency": "USD",
            "type": "ETF_PROXY",
            "return_basis": (
                "same comparable TOTAL_RETURN basis as security; no price-only fallback"
            ),
            "engine_hashes": {
                k: v for k, v in engines.items() if "target" in k or "benchmark" in k
            },
        },
        "feature_eligibility": {
            "scientific_sha256": report["candidate"]["scientific_sha256"],
            "engine_hashes": engines,
        },
        "label_constructibility": {
            "scientific_sha256": report["candidate"]["scientific_sha256"],
            "audit": "timestamps/null masks only; no returns constructed",
        },
        "scientific_cohort": {
            "rows": len(eligible),
            "months": 85,
            "keys_sha256": digest(sorted(keys)),
            "selection": (
                "every existing combined_scientific_eligible row; no downsample "
                "or class substitution"
            ),
        },
    }
    frozen = {
        "dataset_id": DATASET,
        "version": 1,
        "status": "FROZEN",
        "initial_head": INITIAL,
        "candidate": {
            "path": str(candidate_path.relative_to(ROOT)),
            "sha256": file_digest(candidate_path),
        },
        "database_snapshot": db,
        "sources": sources,
        "layers": layers,
        "layer_hashes": {k: digest(v) for k, v in layers.items()},
        "coverage": coverage,
        "cohorts": cohorts,
        "protected_artifacts": report["frozen_artifact_hashes"],
        "source_universe": {
            "path": str(universe_path.relative_to(ROOT)),
            "sha256": file_digest(universe_path),
        },
        "mutation_policy": "write-once; any changed layer requires a new dataset and experiment ID",
    }
    frozen["dataset_sha256"] = digest(frozen)
    frozen_path = ROOT / "docs" / (DATASET + "_MANIFEST.json")
    write_once(frozen_path, encoded(frozen))
    grid = [
        {"max_depth": depth, "learning_rate": lr, "reg_lambda": reg}
        for depth, lr, reg in itertools.product((2, 3), (0.03, 0.05), (1.0, 10.0))
    ]
    contracts: dict[str, Any] = {
        "dataset": {
            "id": DATASET,
            "sha256": frozen["dataset_sha256"],
            "manifest": str(frozen_path.relative_to(ROOT)),
        },
        "features": {
            "names": list(C.M4.features),
            "base_count": len(C.M4.features),
            "semantics": (
                "exact RAW M4 families; no added ranks, interactions, sector, macro or selection"
            ),
            "engine_hashes": engines,
        },
        "target": {
            "economic_target": "future_excess_total_return_12m",
            "horizon_months": 12,
            "return_contract": layers["benchmark"],
            "entry": "LAST_CLOSE_KNOWN_AT_DECISION",
            "exit": "last closed session <= decision_at+12 calendar months",
            "maturity": "target_end AND label_available_at strictly before fit_at",
            "percentile": (
                "(average_rank_ascending_excess-1)/(N-1); exact equal values "
                "share midrank; N<2 fails"
            ),
            "relevance": (
                "min(9,floor(10*percentile)); integer decile 0..9; tied outcomes "
                "share grade; ties can leave grades empty"
            ),
            "predicted_ties": (
                "average ranks; boundary ties receive fractional bin allocation, "
                "never issuer/ticker tie-break; constant scores yield equal "
                "weighted top/bottom and zero spread; IC undefined, report null "
                "with undefined count, never fabricate zero IC"
            ),
            "values_computed": False,
        },
        "folds": report["folds"],
        "coverage": coverage,
        "cohorts": cohorts,
        "library": {
            "selected": "xgboost.XGBRanker",
            "version": "3.1.3",
            "availability": "PROPOSED_NOT_INSTALLED",
            "audit": {
                "lightgbm": availability("lightgbm"),
                "xgboost": availability("xgboost"),
                "scikit-learn": availability("scikit-learn"),
            },
            "choice": (
                "existing project optional ml dependency xgboost>=2.0 takes "
                "precedence over introducing LightGBM; no installation in this "
                "task"
            ),
            "sources": [
                "https://github.com/dmlc/xgboost/releases/tag/v3.1.3",
                ("https://xgboost.readthedocs.io/en/release_3.1.0/tutorials/learning_to_rank.html"),
                "https://xgboost.readthedocs.io/en/release_3.1.0/parameter.html",
            ],
            "execution_requirement": (
                "human approval to implement/install exact version; CPU "
                "platform/OpenMP/package wheels must be recorded and "
                "deterministic repeat verified before execution"
            ),
        },
        "models": {
            "L2R_M4": {
                "objective": "rank:ndcg",
                "algorithm": "LambdaMART",
                "qid": (
                    "decision_month sorted ascending; full monthly groups; stable "
                    "issuer_id row serialization only, never used as predictor or "
                    "evaluation tiebreak"
                ),
                "params": {
                    "n_estimators": 200,
                    "tree_method": "hist",
                    "device": "cpu",
                    "n_jobs": 1,
                    "random_state": 20261009,
                    "subsample": 1.0,
                    "colsample_bytree": 1.0,
                    "min_child_weight": 10,
                    "reg_alpha": 0.0,
                    "max_bin": 256,
                    "grow_policy": "depthwise",
                    "lambdarank_pair_method": "mean",
                    "lambdarank_num_pair_per_sample": 8,
                    "lambdarank_unbiased": False,
                    "lambdarank_normalization": True,
                    "lambdarank_score_normalization": True,
                    "ndcg_exp_gain": False,
                },
                "preprocessing": (
                    "raw 44 features; native NaN missing branch; infinities fail; no "
                    "imputation/scaling/clipping; all-missing TRAIN feature fails; no "
                    "early stopping or additional tuning"
                ),
            },
            "EXPANDED_M4R_CONTROL": {
                "architecture": "V1 uncalibrated LogisticRegression L2 M4R",
                "library": "scikit-learn==1.7.2",
                "target": "outperform_12m",
                "params": {
                    "penalty": "l2",
                    "C": 0.01,
                    "solver": "lbfgs",
                    "class_weight": None,
                    "max_iter": 5000,
                    "tol": 1e-4,
                    "fit_intercept": True,
                    "random_state": 20261006,
                },
                "preprocessing": (
                    "TRAIN median; TRAIN 1/99 percentile clipping; TRAIN mean/std "
                    "scaling; 44 missing indicators = 88 transformed columns; zero "
                    "variance scale=1; all-missing TRAIN feature fails"
                ),
                "calibration": "NONE_M4R; no M4RC; no C retune",
                "comparison": "strict paired identical rows/44 raw features with L2R_M4",
            },
            "EQUAL_INFORMATION_BASELINE": {
                "score": 0.0,
                "trainable": False,
                "IC": "undefined/null with count",
                "spread": "0 via fractional tie weights",
                "NDCG": "tie-averaged DCG; no random ranking",
            },
            "old_M4R_comparison": (
                "contextual only: different cohorts; no strict paired CI; do not retrain old models"
            ),
        },
        "grid": grid,
        "inner_cv": {
            "geometry": {
                f"F{f['index'] + 1}": inner_geometry(f["months"]["TRAIN"]) for f in report["folds"]
            },
            "minimum_train_months": 18,
            "validation_months": 6,
            "step_months": 6,
            "separation_months": 13,
            "selection": (
                "largest equal-month mean Spearman IC over all inner validation "
                "months; undefined IC contributes 0 for selection only, with "
                "count reported; at least one defined month required"
            ),
            "secondary_tie": (
                "largest equal-month NDCG@20%; tolerance 1e-12 then first grid "
                "index; never outer outcomes"
            ),
            "maturity": (
                "strict target_end and label_available_at < inner fit_at; full "
                "validation months only; no random securities splits"
            ),
        },
        "metrics": {
            "primary": "MEAN_MONTHLY_CROSS_SECTIONAL_SPEARMAN_IC",
            "aggregation": (
                "equal TEST month weight; 36 pooled months and F1/F2/F3 "
                "separately; undefined IC excluded with explicit count; "
                "classification requires all 36 defined for trainable models"
            ),
            "global": [
                "mean/median/std(ddof=1) monthly IC",
                "positive_IC_month_percentage denominator all months, undefined not positive",
                "top20-bottom20 mean/median/positive_month_percentage",
                "Q1-Q5 future_excess mean/median/outperform_rate/N and effective fractional N",
                (
                    "NDCG@ceil(.10*N), NDCG@ceil(.20*N) linear integer decile gains; "
                    "tie-averaged DCG; zero IDCG null"
                ),
            ],
            "spread": (
                "fractional average-rank bin allocation to exactly .20*N top and "
                "bottom; arithmetic weighted future excess difference per month; "
                "units decimal return; quintiles same tie policy"
            ),
            "sector": {
                "minimum_N": 10,
                "group": (
                    "decision_month + frozen broad SIC sector "
                    "CURRENT_PROFILE_NOT_PIT; descriptive evaluation only, never "
                    "predictor"
                ),
                "IC": "equal sector-month group weighted primary; observation-N weighted secondary",
                "demeaned": (
                    "within same sector-month y-mean(y), evaluation only; global "
                    "monthly Spearman(prediction, demeaned_y) on eligible sector "
                    "groups; no training"
                ),
                "spread": (
                    "within-sector top/bottom20 same fractional ties; equal eligible "
                    "sector weight within month then equal month aggregate"
                ),
                "small_groups": "excluded only sector diagnostics; retained global",
                "undefined": (
                    "explicit count; paired comparisons use identical defined month intersection"
                ),
            },
            "concentration": (
                "monthly issuer/sector counts, largest-sector/top3 shares already "
                "frozen in cohorts; entropy not implemented, not added"
            ),
            "F3": (
                "all monthly IC, positive months, top-bottom, within-sector IC, "
                "sector-neutral spread explicitly reported"
            ),
            "portfolio_claim": "DIAGNOSTIC_NOT_BACKTEST",
        },
        "bootstrap": {
            "samples": 1000,
            "seed": 20261009,
            "rng": "numpy.Generator(PCG64)",
            "unit": (
                "one complete TEST decision month, all rows/models/sectors "
                "together; iid month-block bootstrap, not row IID, not moving "
                "blocks"
            ),
            "resampling": (
                "stratified by F1/F2/F3: 12 month draws with replacement per fold "
                "per sample; pooled equal weight across resulting 36 draws; also "
                "per-fold paired intervals"
            ),
            "paired_differences": [
                "monthly IC",
                "top20-bottom20",
                "monthly equal-sector IC",
                "monthly equal-sector spread",
            ],
            "CI": ("2.5/97.5 percentile, numpy quantile method=linear, no multiplicity correction"),
            "interpretation": (
                "ADAPTIVE_DEV_EXPLORATORY; overlapping H12 outcomes induce serial "
                "dependence; this bootstrap does not establish independent-month "
                "confirmatory inference"
            ),
            "missing": (
                "common valid month intersection per metric; print counts; <6 "
                "paired months in any fold => CI NOT_ESTIMABLE; no cohort edits"
            ),
        },
        "classification": {
            "units": (
                "IC correlation; spread decimal 12M excess return; thresholds "
                "chosen prospectively without outcome inspection"
            ),
            "material_negative_IC": -0.02,
            "material_negative_spread": -0.02,
            "precedence": [
                {
                    "label": "NO_MEANINGFUL_RANKING_SIGNAL",
                    "when": (
                        "PIT/data bug, post-fit tuning, any missing required evaluation, "
                        "OR pooled global mean IC <= 0 OR pooled global top-bottom mean "
                        "<= 0"
                    ),
                },
                {
                    "label": "TEMPORALLY_UNSTABLE_SIGNAL",
                    "when": (
                        "otherwise any fold mean IC <= 0 OR any fold mean top-bottom < "
                        "-0.02 (explicit F3 included)"
                    ),
                },
                {
                    "label": "SECTOR_DRIVEN_SIGNAL",
                    "when": (
                        "otherwise pooled equal-sector mean IC <= 0 OR pooled "
                        "sector-neutral mean spread <= 0"
                    ),
                },
                {
                    "label": "ROBUST_CROSS_SECTIONAL_SIGNAL",
                    "when": (
                        "otherwise all folds mean IC >= .02, all fold top-bottom mean > "
                        "0, pooled mean IC >= .03, each fold positive-IC-month fraction "
                        ">= .5, all folds equal-sector mean IC > 0 and sector-neutral "
                        "mean spread > 0; pooled paired L2R-control differences in IC and "
                        "spread >= 0, at least one strictly >0, pooled paired sector "
                        "IC/spread >=0"
                    ),
                },
                {
                    "label": "PROMISING_CROSS_SECTIONAL_SIGNAL",
                    "when": (
                        "all remaining complete, positive global/economic, "
                        "all-fold-positive-IC, within-sector-positive cases; control "
                        "inconsistency and F3 weakness must be disclosed"
                    ),
                },
            ],
            "assigned_label": None,
            "automatic_next_experiment": False,
        },
        "holdout_decision": {
            "necessary": (
                "all three fold mean IC >0; F3 mean IC >=-.02; pooled mean IC >0; "
                "pooled and every fold mean top-bottom >0 OR pooled spread >0 and "
                "no fold mean spread < -.02; pooled sector IC and sector-neutral "
                "spread >0 and F3 sector IC/spread >=0; complete evaluation; no "
                "PIT/data bug; no post-fit tuning"
            ),
            "permission": (
                "NEVER_AUTOMATIC; human review may consider a separate authorized task only"
            ),
            "holdout": ["2022-10-01", "2025-09-30"],
            "OOT_start": "2025-10-01",
            "access": 0,
        },
    }
    manifest = {
        "experiment_id": EXPERIMENT,
        "initial_head": INITIAL,
        "status": "PREREGISTERED_NOT_RUN",
        "state": "NOT_RUN",
        "FINAL_STRUCTURAL_DEV_EXPERIMENT": True,
        "current_dev_adaptive_iteration": 2,
        "future_dev_adaptive_iteration": 3,
        "future_artifact_status": [
            "RESEARCH_DEV_ONLY",
            "ADAPTIVE_DEV_ITERATION_3",
            "RETROSPECTIVE_UNVALIDATED",
        ],
        "counters": dict.fromkeys(
            [
                "models_trained",
                "outer_test_predictions",
                "ranking_metrics_computed",
                "future_returns_computed",
                "holdout_outcomes_accessed",
                "oot_outcomes_accessed",
            ],
            0,
        ),
        "contracts": contracts,
        "contract_hashes": {k: digest(v) for k, v in contracts.items()},
        "layer_hashes": frozen["layer_hashes"],
        "execution_blocker": (
            "XGBoost 3.1.3 is not installed; human approval and separate "
            "execution implementation required. This task provides no fitter."
        ),
        "prohibited_outputs": [
            "model binaries",
            "outer TEST predictions",
            "realized ranking metrics",
            "future return values",
        ],
    }
    manifest["manifest_sha256"] = digest(manifest)
    verify_manifest(manifest)
    write_once(ROOT / "docs" / (EXPERIMENT + "_MANIFEST.json"), encoded(manifest))
    print(
        json.dumps(
            {
                "dataset_sha256": frozen["dataset_sha256"],
                "manifest_sha256": manifest["manifest_sha256"],
                "scientific_rows": len(eligible),
                "fold_rows": [{k: f[k]["rows"] for k in ("TRAIN", "TEST")} for f in cohorts],
                "status": manifest["status"],
            }
        )
    )


if __name__ == "__main__":
    main()
