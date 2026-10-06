"""Synthetic PIT-safe continuous targets, nested tuning and monthly research metrics."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from sklearn.linear_model import ElasticNet

from pitquant.research import equity_baseline as E
from pitquant.research import equity_return as R
from pitquant.research import equity_v1 as V
from tests.unit.test_equity_v1 import synthetic_fold


def train() -> list[dict]:
    rows = synthetic_fold()["TRAIN"][:120]
    for i, row in enumerate(rows):
        row["excess_return"] = (i % 17 - 8) / 10
    return rows


@pytest.mark.pit
def test_continuous_target_guard_no_winsorization() -> None:
    rows = train()
    rows[0]["excess_return"] = 200.0
    assert R.target(rows)[0] == 200.0
    assert R.distribution(rows)["max"] == 200.0
    changed = deepcopy(rows[0])
    changed["target_end"] = "2022-10-01T00:00:00+00:00"
    with pytest.raises(ValueError, match="holdout"):
        E.assert_row(changed, "TRAIN", "2019-10-01T00:00:00+00:00")
    changed["decision_at"] = "2025-10-01T00:00:00+00:00"
    with pytest.raises(ValueError):
        E.assert_row(changed, "TEST", "2026-10-01T00:00:00+00:00")


@pytest.mark.pit
def test_r0_uses_train_mean_without_test_input() -> None:
    rows = train()
    assert R.train_mean(rows) == float(np.mean([r["excess_return"] for r in rows]))
    untouched = R.train_mean(rows)
    test = deepcopy(rows[:5])
    test[0]["excess_return"] = -1000.0
    assert R.train_mean(rows) == untouched


@pytest.mark.pit
def test_inner_temporal_cv_and_outer_exclusion() -> None:
    fold = synthetic_fold()
    for inner in V.inner_folds(fold):
        assert max(V.month_index(r["decision_at"]) for r in inner["train"]) + 13 <= V.month_index(
            inner["fit_at"]
        )
        assert all(r["label_available_at"] < inner["fit_at"] for r in inner["train"])
    fold["TEST"] = [deepcopy(fold["TRAIN"][0])]
    with pytest.raises(ValueError, match="contamination"):
        V.inner_folds(fold)


@pytest.mark.pit
@pytest.mark.parametrize("ratio", [0.0, 0.5, 1.0])
def test_fit_train_only_deterministic_and_targets_uncapped(ratio: float) -> None:
    rows = train()
    test = deepcopy(rows[:8])
    p, a = R.fit_model(rows, test, ("x",), 0.01, ratio)
    test[0]["excess_return"] = 1e6
    test[0]["features"]["x"]["value"] = 1e9
    p2, b = R.fit_model(rows, test, ("x",), 0.01, ratio)
    assert a == b
    assert np.array_equal(p[1:], p2[1:])
    assert a["target_transform"] == "NONE"
    assert a["target_values_hash"] == E.digest(R.target(rows).tolist())
    assert a["reproduction_max_abs_difference"] == 0


def test_ridge_equivalence_to_elastic_objective() -> None:
    rows = train()
    test = rows[:10]
    p, artifact = R.fit_model(rows, test, ("x",), 0.03, 0.0)
    processor = E.TrainPreprocessor(E.matrix(rows, ("x",)))
    x = processor.transform(E.matrix(rows, ("x",)))
    # Independent coordinate descent solves the same objective at l1_ratio=0.
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        reference = ElasticNet(
            alpha=0.03, l1_ratio=0.0, fit_intercept=True, max_iter=100000, tol=1e-10
        ).fit(x, R.target(rows))
    expected = reference.predict(processor.transform(E.matrix(test, ("x",))))
    assert np.allclose(p, expected, atol=1e-7, rtol=0)
    assert artifact["estimator_params"]["alpha"] == len(rows) * 0.03


def test_grid_tie_rule_deterministic() -> None:
    scores = [
        {"alpha": a, "l1_ratio": ratio, "mae": 0.2, "mean_nonzero_count": 10} for a, ratio in R.GRID
    ]
    assert R.choose(scores) == (1.0, 0.0)
    next(s for s in scores if s["alpha"] == 1.0 and s["l1_ratio"] == 0.5)["mean_nonzero_count"] = 2
    assert R.choose(scores) == (1.0, 0.5)
    scores[0]["mae"] = 0.1
    assert R.choose(scores) == (0.001, 0.0)
    with pytest.raises(ValueError):
        R.choose(scores[:-1])


def observations() -> list[dict]:
    return [
        {
            "security_id": f"SYN{i}",
            "decision_at": f"2019-{month:02d}-01T00:00:00+00:00",
            "predicted_excess_return": float(i),
            "realized_excess_return": float(i),
            "raw_score": float(i),
            "future_excess_return_12m": float(i),
            "actual_target": int(i > 10),
        }
        for month in (1, 2)
        for i in range(20)
    ]


def test_monthly_ranks_ties_and_constant_baseline() -> None:
    rows = observations()
    R.assign_ranks(rows)
    assert rows[0]["rank"] == 1.0
    assert rows[19]["rank"] == 20.0
    got = R.metrics(rows)
    assert got["mean_monthly_cross_sectional_ic"]["mean"] == 1.0
    assert got["monthly_spread"]["mean"] == 16.0
    assert got["mae"] == got["rmse"] == 0
    assert got["r2"] == 1.0
    for row in rows:
        row["raw_score"] = row["predicted_excess_return"] = 1.0
    got = R.metrics(rows)
    assert got["monthly_spread"]["mean"] is None
    assert got["mean_monthly_cross_sectional_ic"]["mean"] is None
    assert got["pearson"] is None


def test_immutable_predictions_and_compressed_parameters(tmp_path: Path) -> None:
    p = tmp_path / "pred.json"
    E.immutable_json(p, {"predicted_excess_return": -1.5})
    with pytest.raises(ValueError):
        E.immutable_json(p, {"predicted_excess_return": 1.5})
    q = tmp_path / "model.json.gz"
    assert R.immutable_gzip(q, {"coef": [1.0]}) == R.immutable_gzip(q, {"coef": [1.0]})
    with pytest.raises(ValueError):
        R.immutable_gzip(q, {"coef": [2.0]})


def test_bootstrap_constant_ranking_stays_na() -> None:
    rows = observations()
    constant = deepcopy(rows)
    for row in constant:
        row["raw_score"] = row["predicted_excess_return"] = 10.0
    predictions = {"R0": constant, "R2": rows, "R3": rows, "R4": rows}
    first = R.bootstrap(predictions, 10)
    assert first == R.bootstrap(predictions, 10)
    assert first["paired_deltas"]["R2-R0"]["monthly_rank_ic"]["low"] is None
    assert first["paired_deltas"]["R4-R3"]["spread"]["low"] == 0.0


@pytest.mark.pit
def test_frozen_common_cohort_and_target_contract() -> None:
    import gzip
    import json

    root = Path(__file__).resolve().parents[2]
    data = json.loads(
        gzip.decompress((root / "docs/FIRST_EQUITY_ML_12M_V0_DATASET.json.gz").read_bytes())
    )
    manifest = json.loads((root / "docs/FIRST_EQUITY_ML_12M_V0_MANIFEST.json").read_text())
    assert E.digest(data) == V.DATA_HASH
    assert E.digest(manifest["contracts"]["fold"]) == V.FOLD_HASH
    assert data["holdout_outcome_rows_accessed"] == data["oot_outcome_rows_accessed"] == 0
    for f in data["folds"]:
        for role in ("TRAIN", "TEST"):
            assert np.array_equal(R.target(f[role]), [r["excess_return"] for r in f[role]])
            for row in f[role]:
                E.assert_row(row, role, f["fit_at"])
                assert row["source_meta"]["currency"] == "USD"
                assert row["source_meta"]["return_type"] == "TOTAL_RETURN"
                assert row["source_meta"]["benchmark"] == "SPY"


def test_complete_report_handles_na_and_explicit_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts import report_equity_return as D

    monkeypatch.setattr(D, "DOCS", tmp_path)
    rows = observations()
    constant = deepcopy(rows)
    for row in constant:
        row["raw_score"] = row["predicted_excess_return"] = 1.0
    predictions = {"R0": constant, "R2": rows, "R3": rows, "R4": rows}
    metrics = {m: R.metrics(rs) for m, rs in predictions.items()}
    ranking = R.ranking(rows)
    report = {
        "per_fold": {f"F{i}": metrics for i in (1, 2, 3)},
        "POOLED_DEV_OOF": metrics,
        "direction_ranking_reference": {
            "per_fold": {f"F{i}": ranking for i in (1, 2, 3)},
            "pooled": ranking,
        },
        "bootstrap": R.bootstrap(predictions, 10),
        "classification": "SYNTHETIC_REPORT_FIXTURE",
    }
    base = {
        "coefficients": [0.0, 0.0],
        "features": ["SYNx"],
        "transformed_features": ["SYNx", "SYNx__missing"],
        "alpha": 0.1,
        "l1_ratio": 0.5,
        "nonzero_count": 0,
        "l1_norm": 0.0,
        "l2_norm": 0.0,
    }
    models = {f"F{i}-{m}": {"base": base} for i in (1, 2, 3) for m in ("R2", "R3", "R4")}
    distribution = {k: float(i) for i, k in enumerate(D.DISTRIBUTION_COLUMNS)}
    E.immutable_json(
        tmp_path / (R.EXPERIMENT + "_TARGET_DISTRIBUTIONS.json"),
        {"F1": {"TRAIN": distribution, "TEST": distribution}},
    )
    E.immutable_json(tmp_path / (R.EXPERIMENT + "_REPORT.json"), report)
    R.immutable_gzip(tmp_path / (R.EXPERIMENT + "_MODELS.json.gz"), models)
    D.main()
    first = (tmp_path / (R.EXPERIMENT + "_REPORT.md")).read_text()
    D.main()
    assert first == (tmp_path / (R.EXPERIMENT + "_REPORT.md")).read_text()
    assert "NA" in first
    row = next(line for line in first.splitlines() if line.startswith("| F1 | TRAIN |"))
    assert [float(v.strip()) for v in row.split("|")[3:-1]] == list(
        range(len(D.DISTRIBUTION_COLUMNS))
    )


def test_classification_does_not_hide_undefined_months() -> None:
    from scripts.run_equity_return import classify

    good = {
        "mae": 0.1,
        "rmse": 0.2,
        "monthly_spread": {"mean": 0.1, "n_available": 12},
        "mean_monthly_cross_sectional_ic": {"mean": 0.1, "n_available": 12},
    }
    values = {
        "R0": {"mae": 0.3, "rmse": 0.4},
        "R2": deepcopy(good),
        "R3": deepcopy(good),
        "R4": deepcopy(good),
    }
    report = {
        "per_fold": {f"F{i}": deepcopy(values) for i in (1, 2, 3)},
        "POOLED_DEV_OOF": deepcopy(values),
        "bootstrap": {
            "paired_deltas": {
                m + "-R0": {k: {"high": -0.01} for k in ("mae", "rmse")} for m in ("R2", "R3", "R4")
            }
        },
    }
    assert classify(report) == "ROBUST_RETURN_SIGNAL"
    for m in ("R2", "R3", "R4"):
        report["per_fold"]["F3"][m]["monthly_spread"]["n_available"] = 0
    assert classify(report) == "RETURN_SIGNAL_UNSTABLE"
