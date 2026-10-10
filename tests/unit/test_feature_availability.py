"""Synthetic feature availability and causal own-history regressions."""

from __future__ import annotations

import ast
import copy
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from dateutil.relativedelta import relativedelta

from pitquant.research import first_ml_contract as C
from pitquant.research.feature_availability import (
    audit_feature_availability,
    require_feature_availability,
)
from pitquant.research.fundamentals_v1 import ValuationHistory


def fixture() -> tuple[list[dict], dict]:
    rows = []
    for i in range(61):
        at = datetime(2014, 9, 1, tzinfo=UTC) + relativedelta(months=i)
        rows.append(
            {
                "security_id": "synthetic",
                "issuer_id": "synthetic",
                "month": at.strftime("%Y-%m"),
                "decision_at": at.isoformat(),
                "target_end": (at + relativedelta(months=12)).isoformat(),
                "label_available_at": (at + relativedelta(months=12, days=1)).isoformat(),
                "actual_target": 1,
                "excess_return": 0.1,
                "features": {
                    n: {
                        "value": None if n == "val_pe_own_pct" and i < 24 else 1.0,
                        "missing_reason": "INSUFFICIENT_HISTORY"
                        if n == "val_pe_own_pct" and i < 24
                        else None,
                        "available_at": at.isoformat(),
                    }
                    for n in C.M4.features
                },
            }
        )
    contracts = {
        "cohorts": [
            {
                "fold": 1,
                "fit_at": rows[49]["decision_at"],
                "TRAIN": {"monthly_rows": {r["month"]: 1 for r in rows[:37]}},
                "TEST": {"monthly_rows": {r["month"]: 1 for r in rows[49:61]}},
            }
        ],
        "inner_cv": {
            "geometry": {
                "F1": [
                    {
                        "TRAIN": [r["month"] for r in rows[:18]],
                        "VALIDATION": [r["month"] for r in rows[30:36]],
                    }
                ]
            }
        },
    }
    return rows, contracts


@pytest.mark.pit
def test_global_projection_preserves_cohort_and_removes_indicator() -> None:
    rows, contracts = fixture()
    audit = audit_feature_availability(rows, contracts, C.M4.features)
    assert audit["removed"] == ["val_pe_own_pct"]
    assert audit["training_blocks"] == 2 and len(audit["cells"]) == 88
    with pytest.raises(ValueError, match="all-missing"):
        require_feature_availability(rows, contracts, C.M4.features)
    names = tuple(audit["retained"])
    projected = copy.deepcopy(rows)
    for row in projected:
        row["features"] = {n: row["features"][n] for n in names}
    require_feature_availability(projected, contracts, names)
    assert len(names) == 43 and len(projected) == len(rows)
    from pitquant.research.equity_baseline import TrainPreprocessor, matrix

    processor = TrainPreprocessor(matrix(projected[:18], names))
    assert processor.transform(matrix(projected[:18], names)).shape == (18, 86)


@pytest.mark.pit
def test_any_additional_all_missing_feature_uses_same_rule() -> None:
    rows, contracts = fixture()
    for row in rows:
        row["features"]["ret_1m"].update(value=None, missing_reason="UNAVAILABLE")
    assert audit_feature_availability(rows, contracts, C.M4.features)["removed"] == [
        "ret_1m",
        "val_pe_own_pct",
    ]


@pytest.mark.pit
def test_one_finite_observation_suffices_without_new_coverage_threshold() -> None:
    rows, contracts = fixture()
    for row in rows:
        row["features"]["val_pe_own_pct"].update(value=None, missing_reason="UNAVAILABLE")
    rows[0]["features"]["val_pe_own_pct"].update(value=0.5, missing_reason=None)
    require_feature_availability(rows, contracts, C.M4.features)


@pytest.mark.pit
def test_duplicate_row_loss_and_future_provenance_abort() -> None:
    rows, contracts = fixture()
    with pytest.raises(ValueError, match="duplicate"):
        audit_feature_availability([*rows, rows[0]], contracts, C.M4.features)
    with pytest.raises(ValueError, match="month contract"):
        audit_feature_availability(rows[1:], contracts, C.M4.features)
    rows[0]["features"]["ret_1m"]["available_at"] = rows[1]["decision_at"]
    with pytest.raises(ValueError, match="future feature"):
        audit_feature_availability(rows, contracts, C.M4.features)


@pytest.mark.pit
def test_history_minimum_and_current_observation_exclusion() -> None:
    history = ValuationHistory()
    for i in range(24):
        assert history.percentile("pe", 100.0) == (None, "INSUFFICIENT_HISTORY")
        history.add({"pe": float(i + 1)})
    assert history.percentile("pe", 12.0) == (50.0, None)
    assert history.percentile("pe", None) == (None, "METRIC_NOT_MEANINGFUL")
    history.add({"pe": np.nan})
    assert len(history.pts["pe"]) == 24


@pytest.mark.pit
def test_revised_runner_guards_before_real_fits() -> None:
    root = Path(__file__).resolve().parents[2]
    source = ast.parse((root / "scripts/run_revised_equity_ranker.py").read_text())
    calls = [node for node in ast.walk(source) if isinstance(node, ast.Call)]
    guard = next(
        n.lineno for n in calls if isinstance(n.func, ast.Name) and n.func.id == "require_trainable"
    )
    fits = [
        n.lineno
        for n in calls
        if (isinstance(n.func, ast.Attribute) and n.func.attr in ("fit", "fit_base"))
    ]
    assert fits and min(fits) > guard
    assert "C.M4.features" not in (root / "scripts/run_revised_equity_ranker.py").read_text()


@pytest.mark.pit
def test_feature_selection_does_not_depend_on_return_or_control_label() -> None:
    rows, contracts = fixture()
    before = audit_feature_availability(rows, contracts, C.M4.features)
    changed = copy.deepcopy(rows)
    for i, row in enumerate(changed):
        row["excess_return"] = float(i * -100)
        row["actual_target"] = 0
    assert before == audit_feature_availability(changed, contracts, C.M4.features)


@pytest.mark.pit
def test_explicit_manifest_binding_rejects_inherited_column_counts() -> None:
    from pitquant.research.ranker_manifest_contract import assert_ranker_feature_binding
    from pitquant.research.ranking_preregistration import digest

    features = {"names": ["a", "b"], "base_count": 2}
    sha = digest(features)
    binding = {"raw_feature_count": 2, "raw_feature_contract_sha256": sha}
    m = {
        "feature_contract_sha256": sha,
        "contracts": {
            "features": features,
            "models": {
                "L2R_M4": dict(binding),
                "EXPANDED_M4R_CONTROL": {**binding, "transformed_feature_count": 4},
            },
        },
    }
    assert_ranker_feature_binding(m)
    m["contracts"]["models"]["L2R_M4"]["raw_feature_count"] = 44
    with pytest.raises(ValueError, match="RAW feature count"):
        assert_ranker_feature_binding(m)
    m["contracts"]["models"]["L2R_M4"]["raw_feature_count"] = 2
    m["contracts"]["models"]["EXPANDED_M4R_CONTROL"]["transformed_feature_count"] = 88
    with pytest.raises(ValueError, match="indicator"):
        assert_ranker_feature_binding(m)


def test_invalidated_revision_cannot_claim_success_or_erase_original() -> None:
    import json

    from pitquant.research.ranking_preregistration import digest, file_digest, verify_manifest

    root = Path(__file__).resolve().parents[2]
    exp = "FIRST_EQUITY_CROSS_SECTIONAL_RANK_12M_V0R1"
    report = json.loads((root / "docs" / (exp + "_REPORT.json")).read_bytes())
    assert digest({k: v for k, v in report.items() if k != "sha256"}) == report["sha256"]
    assert report["models_fitted_on_real_data"] == 1
    assert report["classification"] is None and report["metrics"] is None
    assert report["outer_predictions"] == 0 and report["mandatory_control_real_fits"] == 0
    assert report["dev_adaptive_iteration"] == 3
    assert report["FINAL_STRUCTURAL_DEV_EXPERIMENT"] == "INVALIDATED_NOT_COMPLETED"
    lock = json.loads((root / "docs" / (exp + "_EXECUTION_LOCK.json")).read_bytes())
    for name, sha in {**lock["original_artifacts"], **lock["code_hashes"]}.items():
        assert file_digest(root / name) == sha
    correction = json.loads(
        (root / "docs" / (exp + "_MANIFEST_METADATA_REVISION_2.json")).read_bytes()
    )
    verify_manifest(correction)
    from pitquant.research.ranker_manifest_contract import assert_ranker_feature_binding

    assert_ranker_feature_binding(correction)
