"""Audit metric/lineage checks. Synthetic fixtures never represent market history."""

from __future__ import annotations

import ast
import copy
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from scripts import audit_equity_return as script

from pitquant.research import return_failure_audit as A

ROOT = Path(__file__).resolve().parents[2]


def rows(n: int = 100) -> list[dict]:
    return [
        {
            "security_id": f"SYN{i:03}",
            "issuer_id": f"SYN{i:03}",
            "decision_at": "2018-01-01T00:00:00+00:00",
            "excess_return": float(i),
            "source_meta": {"sector_group": "SYN_FIXTURE"},
        }
        for i in range(n)
    ]


def test_selection_margin_raw_and_relative() -> None:
    scores = [
        {"mae": 0.20, "alpha": 1, "l1_ratio": 0.25},
        {"mae": 0.21, "alpha": 0.1, "l1_ratio": 0},
        {"mae": 0.22, "alpha": 0.01, "l1_ratio": 0},
    ]
    result = A.margin(scores)
    assert result["absolute"] == pytest.approx(0.01)
    assert result["relative_percent"] == pytest.approx(5)
    scores[1]["mae"] = 0.20
    assert A.margin(scores)["numeric_tie_1e_12"]


def test_pareto_dominance_and_undefined() -> None:
    candidates = [
        {"candidate": str(i), "validation": {"mae": mae, "spearman": ic}}
        for i, (mae, ic) in enumerate([(1, 0.2), (2, 0.1), (2, 0.4), (1, None), (1, 0.2)])
    ]
    result = A.pareto(candidates)
    assert result["non_dominated"] == ["0", "2", "4"]
    assert result["dominated"] == ["1"]
    assert result["undefined_ic"] == ["3"]


def test_loss_bins_conserve_all_rows_and_losses() -> None:
    result = A.loss_decomposition(np.arange(100, dtype=float), np.zeros(100), rows())
    bins = result["bins_0_90_90_95_95_99_99_100"]
    assert [b["n"] for b in bins] == [90, 5, 4, 1]
    assert sum(b["squared_error_share"] for b in bins) == pytest.approx(1)
    assert sum(b["absolute_error_share"] for b in bins) == pytest.approx(1)
    assert result["top_tail_squared_share"]["0.01"] == pytest.approx(
        99**2 / sum(i**2 for i in range(100))
    )


def test_constant_correlations_are_na_not_zero() -> None:
    assert A.correlation(np.ones(100), np.arange(100, dtype=float)) is None
    assert A.monthly_ic(rows(), np.ones(100))["summary"]["mean"] is None


def test_sector_diagnostic_is_monthly_and_no_artificial_ranks() -> None:
    data = rows(10)
    before = copy.deepcopy(data)
    result = A.sector_diagnostics(
        data, {"SYN_CONSTANT": np.ones(10), "SYN_SCORE": np.arange(10, dtype=float)}
    )
    assert result["models"]["SYN_CONSTANT"]["within_sector_summary"]["mean"] is None
    assert result["models"]["SYN_SCORE"]["within_sector_summary"]["mean"] == pytest.approx(1)
    assert data == before


def test_saved_transform_replay_no_fit() -> None:
    parameters = {
        "features": ["SYN_FEATURE"],
        "preprocessing": {
            "median": [2.0],
            "low": [0.0],
            "high": [4.0],
            "mean": [2.0],
            "scale": [2.0],
        },
        "coefficients": [3.0, 1.0],
        "intercept": 0.5,
    }
    data = [
        {"features": {"SYN_FEATURE": {"value": None}}},
        {"features": {"SYN_FEATURE": {"value": 4.0}}},
    ]
    x, pred = A.replay(parameters, data)
    np.testing.assert_array_equal(x, [[0.0, 1.0], [1.0, 0.0]])
    np.testing.assert_array_equal(pred, [1.5, 3.5])


def test_audit_sources_forbid_fit_database_and_sealed_loaders() -> None:
    for module in (A, script):
        source = Path(module.__file__).read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else node.func.id
                    if isinstance(node.func, ast.Name)
                    else ""
                )
                assert name not in {
                    "fit",
                    "fit_model",
                    "partial_fit",
                    "create_engine",
                    "evaluate_candidate_on_holdout",
                    "TrainPreprocessor",
                }
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(("sklearn", "pitquant.db"))


@pytest.mark.pit
@pytest.mark.parametrize("field", ["holdout_outcome_rows_accessed", "oot_outcome_rows_accessed"])
def test_sealed_access_rejected(field: str) -> None:
    data = {"holdout_outcome_rows_accessed": 0, "oot_outcome_rows_accessed": 0, "folds": []}
    data[field] = 1
    with pytest.raises(ValueError, match="sealed"):
        A.safe_rows(data)


@pytest.mark.pit
def test_raw_feature_ic_only_after_causal_guard() -> None:
    data = json.loads(
        gzip.decompress((ROOT / "docs/FIRST_EQUITY_ML_12M_V0_DATASET.json.gz").read_bytes())
    )
    A.safe_rows(data)
    row = copy.deepcopy(data["folds"][0]["TEST"][0])
    feature = next(k for k, v in row["features"].items() if v["value"] is not None)
    row["features"][feature]["available_at"] = "2021-01-01T00:00:00+00:00"
    data["folds"][0]["TEST"] = [row]
    with pytest.raises(ValueError):
        A.safe_rows(data)


def test_frozen_ledger_matches_initial_experiments() -> None:
    design = json.loads((ROOT / "docs" / (script.PREFIX + "_DESIGN.json")).read_text())
    assert design["initial_head"].startswith("ce2e539")
    for name, digest in design["frozen_files"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    assert design["dev_adaptive_iteration"] == 2


def test_complete_archived_candidate_surface() -> None:
    models = json.loads(
        gzip.decompress((ROOT / "docs/FIRST_EQUITY_RETURN_12M_V0_MODELS.json.gz").read_bytes())
    )
    models = [v for v in models.values() if "candidates" in v]
    assert len(models) == 9
    assert sum(len(m["candidates"]) for m in models) == 315
    assert sum(len(c["inner_models"]) for m in models for c in m["candidates"].values()) == 945


def test_missing_surface_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(A.V, "inner_folds", lambda _: [])
    with pytest.raises(ValueError, match="grid incomplete"):
        A.candidate_surface({"index": 1, "TRAIN": []}, {"F1-R2": {"candidates": {}}})


def test_deterministic_metrics_and_pareto() -> None:
    y = np.arange(100, dtype=float)
    first = A.loss_decomposition(y, y / 2, rows())
    assert first == A.loss_decomposition(y, y / 2, rows())
    assert A.metrics(y, y / 2) == A.metrics(y, y / 2)


def test_zero_optimum_kkt_threshold_saved_scaling() -> None:
    parameters = {
        "features": ["SYN_FEATURE"],
        "transformed_features": ["SYN_FEATURE", "SYN_FEATURE__missing"],
        "preprocessing": {
            "median": [0.0],
            "low": [-1.0],
            "high": [1.0],
            "mean": [0.0],
            "scale": [1.0],
        },
        "coefficients": [0.0, 0.0],
        "intercept": 0.0,
        "alpha": 1.0,
        "l1_ratio": 0.25,
        "nonzero_count": 0,
    }
    data = [
        {"features": {"SYN_FEATURE": {"value": x}}, "excess_return": x * 0.1} for x in (-1.0, 1.0)
    ]
    result = A.kkt(parameters, data)
    assert result["max_gradient"] == pytest.approx(0.1)
    assert result["zero_optimum_condition"]
    parameters["alpha"] = 0.1
    assert not A.kkt(parameters, data)["zero_optimum_condition"]


def test_final_audit_complete_and_frozen_iteration() -> None:
    path = ROOT / "docs" / (script.PREFIX + ".json")
    if not path.exists():
        pytest.fail("committed audit artifact required")
    report = json.loads(path.read_text())
    assert report["candidate_count"] == 315
    assert report["inner_model_count"] == 945
    assert report["new_fits"] == 0
    assert report["dev_adaptive_iteration"] == 2
    assert report["holdout_outcomes_accessed"] == report["oot_outcomes_accessed"] == 0
    for details in report["folds"].values():
        for surface in details["surface"].values():
            assert len(surface["candidates"]) == 35
            for candidate in surface["candidates"]:
                assert candidate["validation"]["mae"] >= 0
                assert (
                    sum(
                        b["n"] for b in candidate["validation_loss"]["bins_0_90_90_95_95_99_99_100"]
                    )
                    == candidate["validation"]["n"]
                )
                for inner in candidate["inners"]:
                    assert "train_in_sample" in inner
                    assert inner["validation"]["n"] > 0
