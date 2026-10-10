"""Synthetic tests only: no adapter test reads scientific DEV outcomes."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from pitquant.research import ranking_evaluation as R
from pitquant.research.ranker_adapters import (
    FutureRankerSpecification,
    XGBRankerAdapter,
    validate_inputs,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.pit
def test_ties_do_not_invent_constant_spread() -> None:
    score = np.zeros(20)
    y = np.arange(20, dtype=float)
    top = R.bin_weights(score, 0.8, 1)
    bottom = R.bin_weights(score, 0, 0.2)
    assert np.allclose(top, bottom)
    assert np.average(y, weights=top) == np.average(y, weights=bottom)
    assert R.ic(score, y) is None
    for i in range(5):
        assert np.isclose(R.bin_weights(score, i / 5, (i + 1) / 5).sum(), 4)


@pytest.mark.pit
def test_grade_order_magnitude_and_ties() -> None:
    y = np.array([-2.0, -2.0, 0.0, 1.0, 6.0, 10.0])
    a = R.grades(y)
    assert np.array_equal(a, R.grades(np.exp(y)))
    assert a[0] == a[1] and a.min() >= 0 and a.max() <= 9
    assert np.array_equal(R.grades(np.zeros(5)), np.full(5, 5.0))


@pytest.mark.pit
def test_tie_diagnostics_permutation_invariant() -> None:
    y = np.array([1.0, 9.0, 3.0, 0.0, 8.0, 2.0])
    s = np.array([2.0, 2.0, 2.0, 1.0, 1.0, 0.0])
    perm = np.array([2, 4, 1, 0, 5, 3])
    assert R.ndcg(s, R.grades(y), 0.2) == R.ndcg(s[perm], R.grades(y[perm]), 0.2)
    assert np.allclose(R.bin_weights(s, 0.8, 1)[perm], R.bin_weights(s[perm], 0.8, 1))


@pytest.mark.pit
def test_bad_groups_and_labels_are_rejected() -> None:
    x = np.ones((3, 2))
    with pytest.raises(ValueError, match="qid"):
        validate_inputs(x, np.array([1, 0, 1]))
    with pytest.raises(ValueError, match="relevance"):
        validate_inputs(x, np.array([0, 0, 1]), np.array([0.0, 0.5, 1.0]))
    with pytest.raises(ValueError, match="shape"):
        validate_inputs(x, np.array([0, 0]))


def test_future_adapters_cannot_fit() -> None:
    registry = json.loads((ROOT / "docs/PITQUANT_OPEN_SOURCE_MODEL_REGISTRY.json").read_bytes())
    for model in registry["models"]:
        if model["name"] == "XGBRanker":
            continue
        spec = FutureRankerSpecification(model["name"], model["capabilities"])
        with pytest.raises(NotImplementedError):
            spec.fit(np.ones((2, 2)), np.ones(2), np.zeros(2))
        assert model["real_DEV_outcomes_accessed"] == 0


@pytest.mark.pit
def test_xgboost_synthetic_round_trip(tmp_path: Path) -> None:
    params = {
        "objective": "rank:ndcg",
        "ndcg_exp_gain": False,
        "lambdarank_unbiased": False,
        "n_estimators": 5,
        "max_depth": 2,
        "device": "cpu",
        "tree_method": "hist",
        "n_jobs": 1,
        "random_state": 1,
        "base_score": 0.5,
    }
    x = np.arange(60, dtype=float).reshape(20, 3)
    y = np.tile(np.arange(10, dtype=float), 2)
    g = np.repeat(np.arange(2), 10)
    a = XGBRankerAdapter(params)
    a.fit(x, y, g)
    p = a.predict(x, g)
    a.serialize(tmp_path)
    assert np.array_equal(p, XGBRankerAdapter.load(tmp_path).predict(x, g))
    b = XGBRankerAdapter(params)
    b.fit(x, y, g)
    assert np.array_equal(p, b.predict(x, g))


def fixture() -> dict:
    one = {
        "ic": {"mean": 0.05, "defined": 12, "positive_fraction": 0.7},
        "spread": {"mean": 0.1},
        "sector_ic": {"mean": 0.04},
        "within_sector_equal_group_ic": 0.04,
        "sector_spread": {"mean": 0.04},
    }
    result = {f"F{i}": copy.deepcopy(one) for i in (1, 2, 3)}
    result["combined"] = copy.deepcopy(one)
    result["combined"]["ic"]["defined"] = 36
    return result


@pytest.mark.pit
def test_frozen_classification_precedence_and_holdout() -> None:
    ltr = fixture()
    control = fixture()
    control["combined"]["ic"]["mean"] = 0.03
    assert R.classify(ltr, control) == "ROBUST_CROSS_SECTIONAL_SIGNAL"
    assert R.holdout_conditions(ltr)
    ltr["F3"]["ic"]["mean"] = -0.001
    assert R.classify(ltr, control) == "TEMPORALLY_UNSTABLE_SIGNAL"
    assert not R.holdout_conditions(ltr)
    ltr = fixture()
    ltr["combined"]["within_sector_equal_group_ic"] = -0.01
    assert R.classify(ltr, control) == "SECTOR_DRIVEN_SIGNAL"
    ltr["combined"]["ic"]["mean"] = 0
    assert R.classify(ltr, control) == "NO_MEANINGFUL_RANKING_SIGNAL"
    ltr = fixture()
    ltr["combined"]["ic"]["mean"] = 0.01
    assert R.classify(ltr, control) == "PROMISING_CROSS_SECTIONAL_SIGNAL"


@pytest.mark.pit
def test_preflight_finds_inner_only_all_missing_feature_before_fit() -> None:
    from datetime import UTC, datetime

    from dateutil.relativedelta import relativedelta

    from pitquant.research import first_ml_contract as C
    from pitquant.research.ranking_preflight import audit_inputs, require_trainable

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
    train = {r["month"]: 1 for r in rows[:37]}
    test = {r["month"]: 1 for r in rows[49:61]}
    contracts = {
        "cohorts": [
            {
                "fold": 1,
                "fit_at": rows[49]["decision_at"],
                "TRAIN": {"monthly_rows": train},
                "TEST": {"monthly_rows": test},
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
    result = audit_inputs(rows, contracts)
    assert result["status"] == "BLOCKED_FROZEN_ALL_MISSING_TRAIN_FEATURE"
    assert result["findings"][0]["all_missing_features"] == ["val_pe_own_pct"]
    assert result["models_fitted_on_real_data"] == 0
    with pytest.raises(ValueError, match="blocks real fits"):
        require_trainable(rows, contracts)


def test_blocked_report_cannot_claim_real_results() -> None:
    from pitquant.research.ranking_preregistration import EXPERIMENT, digest

    report = json.loads((ROOT / "docs" / (EXPERIMENT + "_REPORT.json")).read_bytes())
    assert (
        digest({k: v for k, v in report.items() if k != "report_sha256"}) == report["report_sha256"]
    )
    assert len(report["preflight"]["findings"]) == 5
    assert report["classification"] is None
    assert report["real_models_trained"] == report["real_control_models_trained"] == 0
    assert report["outer_predictions"] == report["ranking_metrics_computed"] == 0
    assert report["holdout_outcomes_accessed"] == report["oot_outcomes_accessed"] == 0
    assert report["dev_adaptive_iteration"] == 2
    assert report["L2R_metrics"] is None and report["M4R_metrics"] is None


@pytest.mark.pit
def test_real_runner_preflight_precedes_every_fit() -> None:
    import ast

    tree = ast.parse((ROOT / "scripts/run_frozen_equity_ranker.py").read_bytes())
    run = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run")
    calls = [n for n in ast.walk(run) if isinstance(n, ast.Call)]
    guard = next(
        n for n in calls if isinstance(n.func, ast.Name) and n.func.id == "require_trainable"
    )
    fits = [n for n in calls if isinstance(n.func, ast.Attribute) and n.func.attr == "fit"]
    assert fits and all(guard.lineno < fit.lineno for fit in fits)
