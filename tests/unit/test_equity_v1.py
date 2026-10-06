"""Synthetic causal nested CV and calibrator isolation tests."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from pitquant.research import equity_baseline as E
from pitquant.research import equity_v1 as V


def synthetic_fold() -> dict:
    rows = []
    for i in range(48):
        year, month = divmod(2014 * 12 + 8 + i, 12)
        at = f"{year}-{month + 1:02d}-01T14:30:00+00:00"
        end = f"{year + 1}-{month + 1:02d}-01T14:30:00+00:00"
        for j in range(4):
            rows.append(
                {
                    "security_id": f"SYN{j}",
                    "decision_at": at,
                    "target_end": end,
                    "label_available_at": end,
                    "actual_target": j % 2,
                    "excess_return": j / 100,
                    "features": {"x": {"value": float(j + i), "available_at": at}},
                }
            )
    return {"TRAIN": rows, "TEST": [], "fit_at": "2019-10-01T14:30:00+00:00"}


@pytest.mark.pit
def test_inner_causal_purge_no_outer_test() -> None:
    fold = synthetic_fold()
    inners = V.inner_folds(fold)
    assert len(inners) == 3
    for inner in inners:
        assert len({r["decision_at"][:7] for r in inner["validation"]}) == 6
        for r in inner["train"]:
            assert V.month_index(r["decision_at"]) + 13 <= V.month_index(inner["fit_at"])
            assert r["label_available_at"] < inner["fit_at"]
        assert not {V.key(r) for r in inner["train"]} & {V.key(r) for r in inner["validation"]}
    fold["TEST"] = [deepcopy(fold["TRAIN"][0])]
    with pytest.raises(ValueError, match="contamination"):
        V.inner_folds(fold)


@pytest.mark.pit
@pytest.mark.parametrize("change", ["holdout", "oot", "maturity", "feature"])
def test_inner_rejects_future_data(change: str) -> None:
    fold = synthetic_fold()
    r = fold["TRAIN"][0]
    if change == "holdout":
        r["target_end"] = "2022-10-01T00:00:00+00:00"
    elif change == "oot":
        r["decision_at"] = "2025-10-01T00:00:00+00:00"
    elif change == "maturity":
        r["label_available_at"] = "2019-10-02T00:00:00+00:00"
    else:
        r["features"]["x"]["available_at"] = "2014-09-02T00:00:00+00:00"
    with pytest.raises(ValueError):
        V.inner_folds(fold)


def test_grid_tie_and_no_outer_metric_selection() -> None:
    assert V.select_c(dict.fromkeys(V.GRID, 0.7)) == 0.01
    scores = dict.fromkeys(V.GRID, 0.7)
    scores[0.3] = 0.6
    assert V.select_c(scores) == 0.3
    with pytest.raises(ValueError):
        V.select_c({10: 0.1})


def oof() -> list[dict]:
    return [
        {
            "security_id": f"SYN{i}",
            "decision_at": "2017-01-01T00:00:00+00:00",
            "inner_fit_at": "2017-01-01T00:00:00+00:00",
            "label_available_at": "2018-01-01T00:00:00+00:00",
            "base_train_keys_hash": "train",
            "prediction_kind": "CAUSAL_INNER_OOF",
            "actual_target": int(i >= 5),
            "p": (i + 1) / 11,
        }
        for i in range(10)
    ]


@pytest.mark.pit
@pytest.mark.parametrize("change", ["insample", "kind", "future_label", "future_fit"])
def test_calibrator_rejects_noncausal_oof(change: str) -> None:
    rows = oof()
    keys: dict[str, list[tuple[str, str]]] = {"train": []}
    if change == "insample":
        keys["train"] = [V.key(rows[0])]
    elif change == "kind":
        rows[0]["prediction_kind"] = "IN_SAMPLE"
    elif change == "future_label":
        rows[0]["label_available_at"] = "2018-10-02T00:00:00+00:00"
    else:
        rows[0]["inner_fit_at"] = "2017-02-01T00:00:00+00:00"
    with pytest.raises(ValueError):
        V.fit_platt(rows, "2018-10-01T00:00:00+00:00", keys)


def test_platt_preserves_ranks_buckets_and_determinism() -> None:
    p = np.array([0.05, 0.1, 0.1, 0.5, 0.9, 0.95])
    c = {"intercept": -0.3, "slope": 0.4}
    calibrated = V.apply_platt(p, c)
    from scipy.stats import rankdata

    assert np.array_equal(rankdata(p), rankdata(calibrated))
    with pytest.raises(ValueError, match="ranking"):
        V.apply_platt(p, {"intercept": 0.0, "slope": -1.0})
    fold = synthetic_fold()
    train, test = fold["TRAIN"][:100], fold["TRAIN"][100:120]
    first, a = V.fit_base(train, test, ("x",), 0.03)
    test2 = deepcopy(test)
    for r in test2:
        r["actual_target"] = 1 - r["actual_target"]
    second, b = V.fit_base(train, test2, ("x",), 0.03)
    assert np.array_equal(first, second)
    assert a == b


def test_unavailable_calibration_and_immutable(tmp_path: Path) -> None:
    rows = oof()
    for r in rows:
        r["actual_target"] = 1
    assert V.fit_platt(rows, "2018-10-01T00:00:00+00:00", {"train": []})["status"].startswith(
        "CALIBRATION_NOT_AVAILABLE"
    )
    p = tmp_path / "prediction.json"
    E.immutable_json(p, {"p": 0.2})
    with pytest.raises(ValueError, match="immutable"):
        E.immutable_json(p, {"p": 0.3})


def test_frozen_hash_constants() -> None:
    assert V.DATA_HASH == "5d31e90b0026b222db01068364fa9a19c04ccb2b7c2fa497d0c489ce09fc3833"
    assert V.FOLD_HASH == "f33b4daffb1dc2e1cbb32fe740178533a14f289df33612d567c447eafac99944"
    assert V.GRID == (0.01, 0.03, 0.1, 0.3, 1.0)


@pytest.mark.pit
def test_archived_dataset_and_fold_contract_are_exact() -> None:
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
    assert [len(V.inner_folds(f)) for f in data["folds"]] == [1, 3, 5]


def test_selected_oof_calibration_is_reproducible() -> None:
    rows = oof()
    # Mixed labels avoid separability; labels are only matured inner validation labels.
    for i, r in enumerate(rows):
        r["actual_target"] = i % 2
    a = V.fit_platt(rows, "2018-10-01T00:00:00+00:00", {"train": []})
    b = V.fit_platt(rows, "2018-10-01T00:00:00+00:00", {"train": []})
    assert a == b
    assert a["slope"] > 0
