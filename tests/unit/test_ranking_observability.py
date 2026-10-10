"""A–J synthetic-only observability, atomic archival and proposed candidate policy."""

from __future__ import annotations

import importlib.util
import json
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from pitquant.research import ranking_evaluation as R
from pitquant.research.ranker_adapters import XGBRankerAdapter
from pitquant.research.ranking_observability import (
    ArtifactKind,
    AtomicArchive,
    GroupedData,
    NoValidRankingCandidate,
    ObservedXGBBackend,
    PendingHumanApproval,
    PersistenceError,
    ScoredRows,
    TechnicalInvalid,
    _write,
    candidate_summary,
    fit_synthetic_inner,
    monthly_diagnostics,
    select_synthetic_proposal,
)

ROOT = Path(__file__).resolve().parents[2]


def fixture(months: tuple[str, ...]) -> GroupedData:
    n = 10
    target = np.tile(np.arange(n, dtype=float), len(months))
    keys = tuple(
        (m, f"synthetic:issuer:{i:02}", f"synthetic:security:{i:02}")
        for m in months
        for i in range(n)
    )
    return GroupedData(
        x=np.column_stack((target, np.sin(target))),
        target=target,
        relevance=np.tile(R.grades(np.arange(n, dtype=float)), len(months)),
        qid=np.repeat(np.arange(len(months), dtype=np.int64), n),
        keys=keys,
    )


class SyntheticBackend:
    def __init__(self, mode: str = "variable") -> None:
        self.mode = mode
        self.fits = 0

    def fit(self, _x: np.ndarray, _y: np.ndarray, _qid: np.ndarray) -> None:
        self.fits += 1

    def predict(self, data: GroupedData) -> ScoredRows:
        scores = data.target.copy()
        keys = data.keys
        if self.mode == "index":
            scores = np.arange(len(data.keys), dtype=float)
        elif self.mode == "constant":
            scores[:] = 0.5
        elif self.mode == "nonfinite":
            scores[0] = np.nan
        elif self.mode == "misaligned":
            keys = tuple(reversed(keys))
        return ScoredRows(scores, keys)

    def metadata(self) -> dict[str, Any]:
        return {
            "backend": "SYNTHETIC_FIXTURE_BACKEND_NOT_A_CHALLENGER",
            "parameters": {},
            "version": "1",
        }

    def serialize(self, path: Path) -> None:
        _write(path / "synthetic-model.json", b'{"synthetic":true,"fitted":true}')


def context(train: GroupedData, val: GroupedData, candidate: int = 0) -> dict[str, Any]:
    return {
        "scope": "SYNTHETIC_FIXTURE",
        "fold": "SYNTHETIC_F1",
        "inner_block": 0,
        "candidate": candidate,
        "parameters": {},
        "feature_names": ["synthetic_a", "synthetic_b"],
        "expected_train_counts": dict(Counter(k[0] for k in train.keys)),
        "expected_validation_counts": dict(Counter(k[0] for k in val.keys)),
        "dataset": "SYNTHETIC_NO_REAL_DATASET",
        "scientific_result": False,
    }


def arrays(path: Path) -> dict[str, Any]:
    AtomicArchive.verify(path)
    with np.load(path / "arrays.npz", allow_pickle=False) as data:
        return {k: data[k].copy() for k in data.files}


@pytest.mark.pit
def test_a_valid_ic_requires_committed_model_and_scores_before_metric(tmp_path: Path) -> None:
    train, val = fixture(("2000-01",)), fixture(("2001-01", "2001-02"))
    archive = AtomicArchive(tmp_path)

    def metric(x: np.ndarray, y: np.ndarray) -> float | None:
        for phase in ("model", "training", "validation", "descriptive"):
            AtomicArchive.verify(tmp_path / phase)
        saved = arrays(tmp_path / "validation")
        assert np.array_equal(saved["target"], val.target)
        assert np.array_equal(saved["scores"], val.target)
        return R.ic(x, y)

    summary = fit_synthetic_inner(
        SyntheticBackend(), train, val, archive, context(train, val), metric=metric
    )
    assert summary["status"] == "EVALUABLE" and summary["defined_months"] == 2
    assert summary["selection_composite"] == pytest.approx(1)


@pytest.mark.pit
def test_b_constant_scores_are_non_ranking_not_technical_or_zero_ic(tmp_path: Path) -> None:
    train, val = fixture(("2000-01",)), fixture(("2001-01",))
    summary = fit_synthetic_inner(
        SyntheticBackend("constant"), train, val, AtomicArchive(tmp_path), context(train, val)
    )
    assert summary["status"] == "NON_RANKING_CANDIDATE"
    assert summary["selection_composite"] is None and summary["monthly"][0]["IC"] is None
    assert summary["monthly"][0]["undefined_reason"] == "CONSTANT_SCORES"
    assert summary["monthly"][0]["scores"]["distinct"] == 1
    assert summary["monthly"][0]["scores"]["identical_pct_modal_share"] == 100
    assert not (tmp_path / "failure").exists()


@pytest.mark.pit
def test_c_constant_targets_archive_evidence_then_abort(tmp_path: Path) -> None:
    train, val = fixture(("2000-01",)), fixture(("2001-01",))
    val = replace(val, target=np.zeros(10), relevance=np.full(10, 5.0))
    with pytest.raises(TechnicalInvalid, match="CONSTANT_TARGET"):
        fit_synthetic_inner(
            SyntheticBackend("index"), train, val, AtomicArchive(tmp_path), context(train, val)
        )
    saved = arrays(tmp_path / "validation")
    assert np.ptp(saved["target"]) == 0
    assert np.ptp(saved["scores"]) > 0
    raw = json.loads((tmp_path / "descriptive/payload.json").read_bytes())
    assert raw["monthly"][0]["undefined_reason"] == "CONSTANT_TARGET"


@pytest.mark.pit
def test_d_nonfinite_scores_are_archived_and_never_evaluated(tmp_path: Path) -> None:
    train, val = fixture(("2000-01",)), fixture(("2001-01",))

    def forbidden(_x: np.ndarray, _y: np.ndarray) -> None:
        pytest.fail("Spearman must not run for technical invalid data")

    with pytest.raises(TechnicalInvalid, match="NONFINITE_SCORES"):
        fit_synthetic_inner(
            SyntheticBackend("nonfinite"),
            train,
            val,
            AtomicArchive(tmp_path),
            context(train, val),
            metric=forbidden,
        )
    assert np.isnan(arrays(tmp_path / "validation")["scores"][0])


@pytest.mark.pit
def test_e_corrupt_qid_aborts_before_fit_with_input_evidence(tmp_path: Path) -> None:
    train, val = fixture(("2000-01",)), fixture(("2001-01", "2001-02"))
    wrong = replace(val, qid=val.qid[::-1].copy())
    backend = SyntheticBackend()
    with pytest.raises(TechnicalInvalid, match="qid/month"):
        fit_synthetic_inner(backend, train, wrong, AtomicArchive(tmp_path), context(train, wrong))
    assert backend.fits == 0
    assert np.array_equal(arrays(tmp_path / "inputs")["validation_qid"], wrong.qid)


@pytest.mark.pit
def test_f_nonranking_candidate_cannot_win_but_other_candidate_can(tmp_path: Path) -> None:
    train, val = fixture(("2000-01",)), fixture(("2001-01",))
    results = [
        fit_synthetic_inner(
            SyntheticBackend(mode),
            train,
            val,
            AtomicArchive(tmp_path / str(i)),
            context(train, val, i),
        )
        for i, mode in enumerate(("constant", "variable"))
    ]
    assert select_synthetic_proposal(results, "SYNTHETIC_FIXTURE") == 1


@pytest.mark.pit
def test_g_all_nonranking_candidates_abort_without_a_winner() -> None:
    val = fixture(("2001-01",))
    months = monthly_diagnostics(val, ScoredRows(np.zeros(10), val.keys))
    candidates = [candidate_summary(months, i) for i in range(8)]
    with pytest.raises(NoValidRankingCandidate, match="NO_VALID_RANKING_CANDIDATE"):
        select_synthetic_proposal(candidates, "SYNTHETIC_FIXTURE")


@pytest.mark.pit
def test_h_post_fit_exception_keeps_model_and_params(tmp_path: Path) -> None:
    train, val = fixture(("2000-01",)), fixture(("2001-01",))

    def injected() -> None:
        raise RuntimeError("synthetic post-fit exception")

    with pytest.raises(RuntimeError, match="post-fit"):
        fit_synthetic_inner(
            SyntheticBackend(),
            train,
            val,
            AtomicArchive(tmp_path),
            context(train, val),
            after_fit_archive=injected,
        )
    AtomicArchive.verify(tmp_path / "model")
    assert (tmp_path / "model/model/synthetic-model.json").exists()
    assert (
        json.loads((tmp_path / "failure/payload.json").read_bytes())["phase"] == "POST_FIT_ARCHIVE"
    )


@pytest.mark.pit
def test_i_spearman_exception_keeps_scores_labels_and_month_statistics(tmp_path: Path) -> None:
    train, val = fixture(("2000-01",)), fixture(("2001-01",))

    def injected(_x: np.ndarray, _y: np.ndarray) -> None:
        raise RuntimeError("synthetic Spearman failure")

    with pytest.raises(RuntimeError, match="Spearman failure"):
        fit_synthetic_inner(
            SyntheticBackend(),
            train,
            val,
            AtomicArchive(tmp_path),
            context(train, val),
            metric=injected,
        )
    saved = arrays(tmp_path / "validation")
    assert np.array_equal(saved["scores"], val.target)
    assert len(saved["issuer_id"]) == 10
    raw = json.loads((tmp_path / "descriptive/payload.json").read_bytes())
    assert raw["monthly"][0]["scores"]["distinct"] == 10
    assert raw["monthly"][0]["IC_evaluated"] is False
    assert raw["monthly"][0]["undefined_reason"] is None


@pytest.mark.pit
def test_j_write_failure_prevents_evaluation_and_preserves_previous_commit(tmp_path: Path) -> None:
    train, val = fixture(("2000-01",)), fixture(("2001-01",))

    def writer(path: Path, value: bytes) -> None:
        if "validation.staging" in str(path.parent) and path.name == "arrays.npz":
            raise OSError("synthetic disk failure")
        _write(path, value)

    def forbidden(_x: np.ndarray, _y: np.ndarray) -> None:
        pytest.fail("no metric before successful persistence")

    with pytest.raises(PersistenceError, match="disk failure"):
        fit_synthetic_inner(
            SyntheticBackend(),
            train,
            val,
            AtomicArchive(tmp_path, writer),
            context(train, val),
            metric=forbidden,
        )
    AtomicArchive.verify(tmp_path / "model")
    assert not (tmp_path / "validation").exists()
    assert list(tmp_path.glob(".validation.staging-*/PERSISTENCE_FAILURE.json"))


@pytest.mark.pit
def test_alignment_row_loss_labels_and_scope_are_technical(tmp_path: Path) -> None:
    train, val = fixture(("2000-01",)), fixture(("2001-01",))
    with pytest.raises(TechnicalInvalid, match="GROUP_ALIGNMENT_ERROR"):
        fit_synthetic_inner(
            SyntheticBackend("misaligned"),
            train,
            val,
            AtomicArchive(tmp_path / "alignment"),
            context(train, val),
        )
    bad = context(train, val)
    bad["expected_validation_counts"] = {"2001-01": 11}
    with pytest.raises(TechnicalInvalid, match="row loss"):
        fit_synthetic_inner(SyntheticBackend(), train, val, AtomicArchive(tmp_path / "loss"), bad)
    with pytest.raises(TechnicalInvalid, match="NONFINITE_TARGET"):
        fit_synthetic_inner(
            SyntheticBackend(),
            train,
            replace(val, target=np.full(10, np.nan)),
            AtomicArchive(tmp_path / "labels"),
            context(train, val),
        )
    with pytest.raises(PendingHumanApproval):
        fit_synthetic_inner(
            SyntheticBackend(),
            train,
            val,
            AtomicArchive(tmp_path / "real"),
            {**context(train, val), "scope": "PITQUANT_REAL_DEV"},
        )
    assert not (tmp_path / "real").exists()


@pytest.mark.pit
def test_partial_undefined_month_keeps_full_selection_denominator() -> None:
    data = fixture(("2001-01", "2001-02"))
    score = data.target.copy()
    score[:10] = 0
    months = monthly_diagnostics(data, ScoredRows(score, data.keys))
    result = candidate_summary(months, 0)
    assert result["required_months"] == 2 and result["undefined_months"] == 1
    assert result["selection_composite"] == pytest.approx(0.5)
    assert months[0]["IC"] is None and months[1]["IC"] == pytest.approx(1)


@pytest.mark.pit
def test_archive_detects_tampering_refuses_overwrite_and_scientific_promotion(
    tmp_path: Path,
) -> None:
    archive = AtomicArchive(tmp_path)
    path = archive.commit("phase", ArtifactKind.TRAINING_ARTIFACT, {"synthetic": True})
    with pytest.raises(PersistenceError, match="already exists"):
        archive.commit("phase", ArtifactKind.TRAINING_ARTIFACT, {})
    (path / "payload.json").write_text("{}")
    with pytest.raises(PersistenceError, match="integrity"):
        archive.verify(path)
    with pytest.raises(PendingHumanApproval):
        archive.commit("outer", ArtifactKind.OUTER_TEST_RESULT, {})


@pytest.mark.pit
def test_native_xgb_uses_exact_frozen_params_and_archives_real_booster_diagnostics(
    tmp_path: Path,
) -> None:
    completion = json.loads(
        (
            ROOT / "docs/FIRST_EQUITY_CROSS_SECTIONAL_RANK_12M_V0_IMPLEMENTATION_COMPLETION.json"
        ).read_bytes()
    )
    params = {**completion["parameters_fixed"], **completion["grid"][0]}
    train = fixture(tuple(f"2000-{i:02}" for i in range(1, 13)))
    val = fixture(("2001-01", "2001-02"))
    backend = ObservedXGBBackend(XGBRankerAdapter(params))
    ctx = {**context(train, val), "parameters": params}
    fit_synthetic_inner(backend, train, val, AtomicArchive(tmp_path), ctx)
    payload = json.loads((tmp_path / "training/payload.json").read_bytes())
    ensemble = payload["ensemble"]
    assert payload["backend"]["parameters"] == params
    assert ensemble["trees"] == ensemble["effective_boosted_rounds"] == 200
    assert ensemble["trees_with_splits"] + ensemble["trees_without_splits"] == 200
    assert ensemble["leaves"] == ensemble["splits"] + ensemble["trees"]
    assert ensemble["importance_available"] and "gain" in ensemble["feature_importance"]
    AtomicArchive.verify(tmp_path / "model")
    assert (tmp_path / "model/model/model.ubj").exists()


@pytest.mark.pit
def test_draft_real_executor_is_blocked_before_loading_inputs() -> None:
    spec = importlib.util.spec_from_file_location(
        "draft_executor", ROOT / "scripts/run_observed_equity_ranker.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(PendingHumanApproval, match="PROPOSED_NOT_APPROVED"):
        module.run()


@pytest.mark.pit
@pytest.mark.parametrize(
    "reason",
    [
        "CONSTANT_SCORES",
        "CONSTANT_TARGET",
        "INSUFFICIENT_ROWS",
        "NONFINITE_SCORES",
        "NONFINITE_TARGET",
        "GROUP_ALIGNMENT_ERROR",
        "OTHER",
    ],
)
def test_all_undefined_reasons_are_explicit(reason: str) -> None:
    data = fixture(("2001-01",))
    scores, keys = data.target.copy(), data.keys
    if reason == "CONSTANT_SCORES":
        scores[:] = 0
    elif reason == "CONSTANT_TARGET":
        data = replace(data, target=np.zeros(10))
    elif reason == "INSUFFICIENT_ROWS":
        data = replace(
            data,
            x=data.x[:1],
            target=data.target[:1],
            relevance=data.relevance[:1],
            qid=data.qid[:1],
            keys=data.keys[:1],
        )
        scores, keys = scores[:1], data.keys
    elif reason == "NONFINITE_SCORES":
        scores[0] = np.inf
    elif reason == "NONFINITE_TARGET":
        data = replace(data, target=np.full(10, np.nan))
    elif reason == "GROUP_ALIGNMENT_ERROR":
        keys = tuple(reversed(keys))
    metric = (lambda _x, _y: None) if reason == "OTHER" else R.ic
    result = monthly_diagnostics(data, ScoredRows(scores, keys), metric=metric)
    assert result[0]["IC"] is None
    assert result[0]["undefined_reason"] == reason


@pytest.mark.pit
def test_historical_artifacts_and_proposal_gate_are_preserved() -> None:
    import hashlib

    report = json.loads((ROOT / "docs/RANKING_EXECUTION_OBSERVABILITY_V1.json").read_bytes())
    for name, expected in report["historical_file_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
    assert report["proposal_status"] == "PROPOSED_NOT_APPROVED"
    assert report["dev_adaptive_iteration"] == 3
    assert report["real_fits"] == report["dev_predictions"] == 0
    assert report["holdout_outcomes_accessed"] == report["oot_outcomes_accessed"] == 0
