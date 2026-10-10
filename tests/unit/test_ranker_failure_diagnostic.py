"""Forensic tests only; deliberately no estimator imports or fits."""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from pitquant.research.ranking_preregistration import digest, file_digest

ROOT = Path(__file__).resolve().parents[2]
ID = "FIRST_EQUITY_CROSS_SECTIONAL_RANK_12M_V0R1_FAILURE_DIAGNOSTIC"


def helper() -> Any:
    spec = importlib.util.spec_from_file_location(
        "forensic_only", ROOT / "scripts/audit_invalidated_ranker.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_target_statistics_are_descriptive_only() -> None:
    result = helper().label_statistics(np.arange(10, dtype=float))
    assert result["distinct"] == 10 and result["nonfinite"] == 0
    assert result["relevance_grades_distinct"] == 10
    assert result["sd_population_ddof0"] == np.std(np.arange(10, dtype=float), ddof=0)
    with pytest.raises(ValueError):
        helper().label_statistics(np.array([1.0, np.nan]))
    with pytest.raises(ValueError):
        helper().label_statistics(np.array([1.0]))


def test_missing_predictions_are_never_filled_with_zero_or_constant() -> None:
    scores = helper().unavailable_scores()
    for key in (
        "distinct",
        "sd_population_ddof0",
        "min",
        "max",
        "identical_pct_modal_share",
        "nonfinite",
    ):
        assert scores[key] is None


def test_diagnostic_source_has_no_estimator_or_execution_calls() -> None:
    tree = ast.parse((ROOT / "scripts/audit_invalidated_ranker.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module not in (
                "xgboost",
                "sklearn",
                "pitquant.research.ranker_adapters",
                "pitquant.research.equity_baseline",
                "pitquant.research.equity_v1",
            )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in ("fit", "predict", "predict_proba", "load_model")


def test_report_is_immutable_and_does_not_claim_causal_proof() -> None:
    report = json.loads((ROOT / "docs" / (ID + ".json")).read_bytes())
    assert digest({k: v for k, v in report.items() if k != "sha256"}) == report["sha256"]
    assert report["classification"] == "F — INSUFFICIENT_EVIDENCE"
    assert (
        report["new_fits"]
        == report["holdout_outcomes_accessed"]
        == report["oot_outcomes_accessed"]
        == 0
    )
    assert report["recommendation"] == "FIX_IMPLEMENTATION_BUG"
    assert not report["scientific_progress_claimed"]
    for path, sha in report["artifact_inventory"].items():
        # Shared local ignored inputs are not required for future clean checkouts.
        if not path.startswith("data/"):
            assert file_digest(ROOT / path) == sha
    assert len(report["monthly"]) == 6
    for month in report["monthly"]:
        assert month["targets"]["distinct"] == month["rows"] > 1
        assert month["targets"]["sd_population_ddof0"] > 0
        assert month["scores"]["distinct"] is None
        assert month["constant_predictions_confirmed"] is None


def test_frozen_executor_aborts_before_remaining_candidates() -> None:
    tree = ast.parse((ROOT / "scripts/run_revised_equity_ranker.py").read_text())
    run = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run")
    raises = [
        n
        for n in ast.walk(run)
        if isinstance(n, ast.Raise)
        and isinstance(n.exc, ast.Call)
        and n.exc.args
        and isinstance(n.exc.args[0], ast.Constant)
        and n.exc.args[0].value == "no defined inner IC"
    ]
    assert len(raises) == 1
    assert not any(isinstance(n, ast.Try) for n in ast.walk(run))
    # No candidate-discard/continue branch exists in the frozen run implementation.
    assert not any(isinstance(n, ast.Continue) for n in ast.walk(run))
