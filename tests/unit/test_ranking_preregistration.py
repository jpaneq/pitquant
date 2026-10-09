"""Preregistration must stay immutable and cannot carry execution outputs."""

from __future__ import annotations

import ast
import copy
import gzip
import json
from collections import Counter
from pathlib import Path

import pytest

from pitquant.research import first_ml_contract as C
from pitquant.research.ranking_preregistration import (
    DATASET,
    EXPERIMENT,
    assert_not_run,
    digest,
    verify_frozen_dataset,
    verify_manifest,
    write_once,
)

ROOT = Path(__file__).resolve().parents[2]


def manifest() -> dict:
    return json.loads((ROOT / "docs" / (EXPERIMENT + "_MANIFEST.json")).read_bytes())


def dataset() -> dict:
    return json.loads((ROOT / "docs" / (DATASET + "_MANIFEST.json")).read_bytes())


@pytest.mark.pit
def test_no_execution_and_contract_integrity() -> None:
    m = manifest()
    verify_manifest(m)
    assert m["current_dev_adaptive_iteration"] == 2
    assert m["future_dev_adaptive_iteration"] == 3
    assert m["FINAL_STRUCTURAL_DEV_EXPERIMENT"] is True
    assert m["contracts"]["classification"]["assigned_label"] is None
    assert set(m["counters"].values()) == {0}


@pytest.mark.parametrize(
    "counter",
    [
        "models_trained",
        "outer_test_predictions",
        "ranking_metrics_computed",
        "future_returns_computed",
        "holdout_outcomes_accessed",
        "oot_outcomes_accessed",
    ],
)
@pytest.mark.pit
def test_execution_counter_is_rejected(counter: str) -> None:
    m = manifest()
    m["counters"][counter] = 1
    with pytest.raises(ValueError, match="forbidden"):
        assert_not_run(m)


@pytest.mark.pit
def test_nested_execution_output_is_rejected() -> None:
    m = manifest()
    m["contracts"]["models"]["L2R_M4"]["outer_predictions"] = []
    with pytest.raises(ValueError, match="output forbidden"):
        assert_not_run(m)


def test_contract_and_dataset_tampering_detected() -> None:
    m = manifest()
    m["contracts"]["grid"][0]["max_depth"] = 99
    with pytest.raises(ValueError, match="contract integrity"):
        verify_manifest(m)
    d = dataset()
    verify_frozen_dataset(d)
    d["layers"]["sec_mapping"]["version"] = "sec-tags-6"
    with pytest.raises(ValueError, match="dataset integrity"):
        verify_frozen_dataset(d)


def test_revision_cannot_be_overwritten(tmp_path: Path) -> None:
    p = tmp_path / "revision.json"
    write_once(p, b"original")
    write_once(p, b"original")
    with pytest.raises(ValueError, match="immutable revision conflict"):
        write_once(p, b"changed")
    assert p.read_bytes() == b"original"


@pytest.mark.pit
def test_all_scientific_rows_preserved_and_exact_folds() -> None:
    d = dataset()
    payload = json.loads(gzip.decompress((ROOT / d["candidate"]["path"]).read_bytes()))
    eligible = [r for r in payload["scientific_rows"] if r["combined_scientific_eligible"]]
    assert len(eligible) == 16717
    assert len({(r["month"], r["issuer_id"]) for r in eligible}) == len(eligible)
    for f in d["cohorts"]:
        for role in ("TRAIN", "TEST"):
            counts = Counter(r["month"] for r in eligible if r["month"] in f[role]["monthly_rows"])
            assert dict(sorted(counts.items())) == f[role]["monthly_rows"]
            assert sum(counts.values()) == f[role]["rows"]
    assert len(d["cohorts"]) == 3
    assert [f["TRAIN"]["months"] for f in d["cohorts"]] == [37, 49, 61]
    assert all(f["TEST"]["months"] == 12 for f in d["cohorts"])
    m = manifest()
    assert m["contracts"]["features"]["names"] == list(C.M4.features)
    assert len(m["contracts"]["grid"]) == 8
    assert m["contracts"]["models"]["EXPANDED_M4R_CONTROL"]["params"]["C"] == 0.01


@pytest.mark.pit
def test_temporal_inner_months_and_guards() -> None:
    cv = manifest()["contracts"]["inner_cv"]
    assert [len(cv["geometry"][f"F{i}"]) for i in (1, 2, 3)] == [1, 3, 5]

    def index(month: str) -> int:
        return int(month[:4]) * 12 + int(month[5:]) - 1

    for blocks in cv["geometry"].values():
        for block in blocks:
            assert len(block["TRAIN"]) >= 18
            assert len(block["VALIDATION"]) == 6
            assert index(block["VALIDATION"][0]) - index(block["TRAIN"][-1]) == 13
            assert not set(block["TRAIN"]) & set(block["VALIDATION"])
            assert "label_available_at < fit_at" in block["train_condition"]


@pytest.mark.pit
def test_declarative_task_cannot_import_training_or_outcome_builders() -> None:
    forbidden_modules = {
        "xgboost",
        "lightgbm",
        "sklearn",
        "equity_baseline",
        "equity_v1",
        "targets_v1",
        "targets_v2",
        "equity_return",
    }
    forbidden_calls = {
        "fit",
        "predict",
        "predict_proba",
        "fit_transform",
        "build_targets",
        "spearman",
        "spearmanr",
        "train",
        "execute",
    }
    for path in (
        "scripts/freeze_equity_ranking_preregistration.py",
        "src/pitquant/research/ranking_preregistration.py",
    ):
        tree = ast.parse((ROOT / path).read_text())
        for n in ast.walk(tree):
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in n.names] + (
                    [n.module or ""] if isinstance(n, ast.ImportFrom) else []
                )
                assert not any(set(name.split(".")) & forbidden_modules for name in names)
            if isinstance(n, ast.Call):
                name = (
                    n.func.attr
                    if isinstance(n.func, ast.Attribute)
                    else n.func.id
                    if isinstance(n.func, ast.Name)
                    else ""
                )
                assert name not in forbidden_calls


def test_old_artifacts_remain_byte_identical() -> None:
    import hashlib

    for path, sha in dataset()["protected_artifacts"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha


def test_rehash_cannot_hide_bad_state() -> None:
    m = copy.deepcopy(manifest())
    m["state"] = "RUN"
    m["manifest_sha256"] = digest({k: v for k, v in m.items() if k != "manifest_sha256"})
    with pytest.raises(ValueError, match="state changed"):
        verify_manifest(m)
