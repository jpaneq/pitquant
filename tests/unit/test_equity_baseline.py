"""SYNTHETIC fixtures: baseline isolation, provenance and immutable artifacts."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from pitquant.research import equity_baseline as E


def rows() -> list[dict]:
    return [
        {
            "security_id": f"SYN{i}",
            "decision_at": "2017-01-01T00:00:00+00:00",
            "features": {"x": {"value": float(i)}},
            "actual_target": i % 2,
        }
        for i in range(40)
    ]


@pytest.mark.pit
def test_test_values_never_change_preprocessing_or_model() -> None:
    train = rows()
    test = deepcopy(train[:5])
    p, artifact = E.fit_logistic(train, test, ("x",))
    test[0]["features"]["x"]["value"] = 1e10
    test[0]["actual_target"] = 1 - test[0]["actual_target"]
    p2, artifact2 = E.fit_logistic(train, test, ("x",))
    assert artifact == artifact2
    assert np.array_equal(p[1:], p2[1:])
    assert artifact["status"] == ["RESEARCH_DEV_ONLY", "RETROSPECTIVE_UNVALIDATED"]
    assert artifact["params"]["class_weight"] is None
    assert artifact["params"]["C"] == 1


@pytest.mark.pit
def test_optional_missing_train_median_and_indicator() -> None:
    processor = E.TrainPreprocessor(np.array([[1.0, 10.0], [3.0, np.nan], [5.0, 30.0]]))
    before = deepcopy(processor.parameters())
    transformed = processor.transform(np.array([[np.nan, 10000.0]]))
    assert processor.median.tolist() == [3.0, 20.0]
    assert transformed[0, 2:].tolist() == [1.0, 0.0]
    assert before == processor.parameters()


def test_all_missing_feature_stops_without_removal() -> None:
    with pytest.raises(ValueError, match="all-missing"):
        E.TrainPreprocessor(np.array([[1.0, np.nan], [2.0, np.nan]]))


def test_manifest_and_oof_immutable(tmp_path: Path) -> None:
    p = tmp_path / "oof.json"
    assert E.immutable_json(p, {"x": 1}) == E.immutable_json(p, {"x": 1})
    with pytest.raises(ValueError, match="immutable"):
        E.immutable_json(p, {"x": 2})
    assert E.digest({"a": 1, "b": 2}) == E.digest({"b": 2, "a": 1})


@pytest.mark.pit
@pytest.mark.parametrize("change", ["feature", "filing", "holdout", "oot", "maturity", "overlap"])
def test_pit_guard_rejects_contamination(change: str) -> None:
    r = {
        "decision_at": "2017-01-01T00:00:00+00:00",
        "target_end": "2018-01-01T00:00:00+00:00",
        "label_available_at": "2018-01-02T00:00:00+00:00",
        "actual_target": 1,
        "excess_return": 0.1,
        "features": {"x": {"value": 1.0, "available_at": "2016-12-31T00:00:00+00:00"}},
    }
    if change == "feature":
        r["features"]["x"]["available_at"] = "2017-01-02T00:00:00+00:00"
    elif change == "filing":
        r["features"]["x"]["provenance"] = [{"available_at": "2017-01-02T00:00:00+00:00"}]
    elif change == "holdout":
        r["target_end"] = "2022-10-01T00:00:00+00:00"
    elif change == "oot":
        r["decision_at"] = "2025-10-01T00:00:00+00:00"
    elif change == "maturity":
        r["label_available_at"] = "2018-10-02T00:00:00+00:00"
    else:
        r["target_end"] = "2018-10-02T00:00:00+00:00"
    with pytest.raises(ValueError):
        E.assert_row(r, "TRAIN", "2018-10-01T00:00:00+00:00")


def test_m1_no_probability_metrics() -> None:
    rs = [
        {"actual_target": i % 2, "raw_score": float(i), "future_excess_return_12m": i / 100}
        for i in range(10)
    ]
    result = E.metrics(rs, False)
    assert result["probability_metric_status"] == E.NA
    assert result["brier"] is None and result["log_loss"] is None
    assert result["auc"] is not None


def test_constant_score_has_no_top_bottom_portfolio() -> None:
    rs = [
        {
            "decision_at": "2020-01-01",
            "actual_target": i % 2,
            "raw_score": 0.5,
            "future_excess_return_12m": i / 100,
        }
        for i in range(40)
    ]
    assert E.buckets(rs, 5)["mean_month_spread"] is None


def test_ties_never_split_by_issuer() -> None:
    rs = [
        {
            "decision_at": "2020-01-01",
            "actual_target": i % 2,
            "raw_score": float(i // 10),
            "future_excess_return_12m": i / 100,
        }
        for i in range(40)
    ]
    a, b = E.buckets(rs, 5), E.buckets(list(reversed(rs)), 5)
    assert [x["n"] for x in a["table"]] == [x["n"] for x in b["table"]]
    for x, y in zip(a["table"], b["table"], strict=True):
        assert x["mean_excess_return"] == pytest.approx(y["mean_excess_return"])


@pytest.mark.pit
def test_naive_base_rate_uses_only_train() -> None:
    train = [{"actual_target": 1}, {"actual_target": 1}, {"actual_target": 0}]
    assert E.train_base_rate(train) == pytest.approx(2 / 3)


def test_fixed_families_cannot_contain_outcomes() -> None:
    from pitquant.research import first_ml_contract as C

    assert (len(C.M2.features), len(C.M3.features), len(C.M4.features)) == (18, 18, 44)
    assert not any("future" in n or "target" in n or "outperform" in n for n in C.M4.features)
    assert E.PREPROCESSING["classification_threshold"] == 0.5


def test_paired_bootstrap_preserves_matching_months() -> None:
    rs = [
        {
            "decision_at": f"2020-0{month}-01",
            "actual_target": i % 2,
            "raw_score": i / 40,
            "predicted_probability": i / 40,
            "future_excess_return_12m": i / 100,
        }
        for month in (1, 2, 3)
        for i in range(40)
    ]
    predictions = {name: deepcopy(rs) for name in ("M0", "M1", "M2", "M3", "M4")}
    result = E.bootstrap(predictions, repetitions=8)
    for values in result["paired_deltas"].values():
        for interval in values.values():
            assert interval["low"] == 0 and interval["high"] == 0


@pytest.mark.pit
def test_all_models_share_test_keys_and_fold_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    from pitquant.research import first_ml_contract as C

    folds = []
    for index in (1, 2, 3):
        fit = f"{2017 + index}-10-01T00:00:00+00:00"
        fold = {
            "index": index,
            "fit_at": fit,
            "test_cohort_hash": "SYNTHETIC",
            "TRAIN": [],
            "TEST": [],
        }
        for role, count in (("TRAIN", 24), ("TEST", 4)):
            for i in range(count):
                at = "2017-01-01T00:00:00+00:00" if role == "TRAIN" else fit
                fold[role].append(
                    {
                        "security_id": f"SYN{i}",
                        "issuer_id": f"SYNI{i}",
                        "decision_at": at,
                        "target_end": "2018-01-01T00:00:00+00:00"
                        if role == "TRAIN"
                        else f"{2018 + index}-09-01T00:00:00+00:00",
                        "label_available_at": "2018-01-02T00:00:00+00:00"
                        if role == "TRAIN"
                        else f"{2018 + index}-09-02T00:00:00+00:00",
                        "actual_target": int(i % 3 != 0) if role == "TRAIN" else i % 2,
                        "excess_return": i / 100,
                        "features": {
                            n: {"value": float(i + j), "available_at": "2016-12-31T00:00:00+00:00"}
                            for j, n in enumerate(C.M4.features)
                        },
                        "v0_score": float(i),
                        "benchmark_id": "SYNBENCH",
                        "snapshot_id": "SYN-SNAPSHOT",
                        "regime": "SYNTHETIC",
                    }
                )
        folds.append(fold)
    monkeypatch.setattr(E, "bootstrap", lambda _: {"method": "SYNTHETIC_TEST_NOT_REAL_BOOTSTRAP"})
    manifest = {
        "experiment_id": "SYN",
        "created_at": "2026-01-01T00:00:00+00:00",
        "code_sha": "SYN",
        "data_snapshot_hash": "SYN",
    }
    report, predictions, artifacts = E.run_models({"folds": folds}, manifest)
    for model in ("M0", "M1", "M2", "M3", "M4"):
        assert [
            (r["security_id"], r["decision_at"]) for r in predictions if r["model_id"] == model
        ] == [(r["security_id"], r["decision_at"]) for r in predictions if r["model_id"] == "M0"]
    assert all(
        r["predicted_probability"] == pytest.approx(2 / 3)
        for r in predictions
        if r["model_id"] == "M0"
    )
    assert len(artifacts) == 9
    assert report["holdout_outcome_rows_accessed"] == report["oot_outcome_rows_accessed"] == 0
