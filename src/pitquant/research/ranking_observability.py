"""Atomic, backend-neutral ranking evidence. Proposal execution is synthetic-only."""

from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
from collections import Counter
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, cast

import numpy as np
from numpy.typing import NDArray

from pitquant.research import ranking_evaluation as R
from pitquant.research.ranking_preregistration import digest, encoded, file_digest

Matrix = NDArray[np.float64]
RowKey = tuple[str, str, str]
Writer = Callable[[Path, bytes], None]


class ArtifactKind(StrEnum):
    TRAINING_ARTIFACT = "TRAINING_ARTIFACT"
    VALIDATION_DIAGNOSTIC = "VALIDATION_DIAGNOSTIC"
    OUTER_TEST_RESULT = "OUTER_TEST_RESULT"
    SCIENTIFIC_CONCLUSION = "SCIENTIFIC_CONCLUSION"


class TechnicalInvalid(ValueError):
    """Evidence cannot support a valid execution; never skip this as a weak model."""


class PersistenceError(TechnicalInvalid):
    pass


class PendingHumanApproval(PermissionError):
    pass


class NoValidRankingCandidate(ValueError):
    pass


def require_synthetic_scope(scope: str) -> None:
    if scope != "SYNTHETIC_FIXTURE":
        raise PendingHumanApproval("V0R2 is PROPOSED_NOT_APPROVED; real execution is disabled")


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as target:
        target.write(data)
        target.flush()
        os.fsync(target.fileno())


def _sync(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class AtomicArchive:
    """Commit an immutable phase directory only after all files verify; same-filesystem rename."""

    def __init__(self, root: Path, writer: Writer = _write) -> None:
        self.root = root
        self.writer = writer

    def commit(
        self,
        phase: str,
        kind: ArtifactKind,
        payload: dict[str, Any],
        arrays: dict[str, Any] | None = None,
        serialize: Callable[[Path], Any] | None = None,
    ) -> Path:
        if kind in (ArtifactKind.OUTER_TEST_RESULT, ArtifactKind.SCIENTIFIC_CONCLUSION):
            raise PendingHumanApproval("observability artifacts are not scientific results")
        if not phase or Path(phase).name != phase:
            raise PersistenceError("invalid archive phase")
        self.root.mkdir(parents=True, exist_ok=True)
        destination = self.root / phase
        lock = self.root / ("." + phase + ".lock")
        try:
            lock.mkdir()
        except FileExistsError as exc:
            raise PersistenceError("concurrent archive writer") from exc
        staging: Path | None = None
        try:
            if destination.exists():
                raise PersistenceError(
                    "archive phase already exists; no overwrite or silent replay"
                )
            staging = Path(tempfile.mkdtemp(prefix="." + phase + ".staging-", dir=self.root))
            if serialize is not None:
                serialize(staging / "model")
            self.writer(staging / "payload.json", encoded(payload))
            if arrays is not None:
                buffer = io.BytesIO()
                np.savez(buffer, **arrays)
                self.writer(staging / "arrays.npz", buffer.getvalue())
            files = sorted(p for p in staging.rglob("*") if p.is_file())
            if any(p.is_symlink() for p in staging.rglob("*")):
                raise PersistenceError("symlink in model archive")
            envelope = {
                "kind": kind.value,
                "phase": phase,
                "files": {str(p.relative_to(staging)): file_digest(p) for p in files},
                "scientific_result": False,
            }
            envelope["sha256"] = digest(envelope)
            self.writer(staging / "COMMIT.json", encoded(envelope))
            self.verify(staging)
            for directory in sorted(
                [p for p in staging.rglob("*") if p.is_dir()],
                key=lambda p: len(p.parts),
                reverse=True,
            ):
                _sync(directory)
            _sync(staging)
            os.rename(staging, destination)
            staging = None
            _sync(self.root)
            self.verify(destination)
            return destination
        except Exception as exc:
            # Retain incomplete staging for forensic use, never advertise it as committed evidence.
            if staging is not None:
                with suppress(Exception):
                    self.writer(staging / "PERSISTENCE_FAILURE.json", encoded({"error": str(exc)}))
            if isinstance(exc, PersistenceError):
                raise
            raise PersistenceError(f"atomic archive failed: {exc}") from exc
        finally:
            with suppress(Exception):
                shutil.rmtree(lock)

    @staticmethod
    def verify(directory: Path) -> dict[str, Any]:
        envelope = json.loads((directory / "COMMIT.json").read_bytes())
        if digest({k: v for k, v in envelope.items() if k != "sha256"}) != envelope["sha256"]:
            raise PersistenceError("archive commit integrity failure")
        actual = {str(p.relative_to(directory)) for p in directory.rglob("*") if p.is_file()}
        if actual != set(envelope["files"]) | {"COMMIT.json"}:
            raise PersistenceError("archive file inventory mismatch")
        for name, sha in envelope["files"].items():
            path = directory / name
            if path.is_symlink() or file_digest(path) != sha:
                raise PersistenceError("archive payload integrity failure")
        return cast(dict[str, Any], envelope)


@dataclass(frozen=True)
class GroupedData:
    x: Matrix
    target: Matrix
    relevance: Matrix
    qid: NDArray[np.int64]
    keys: tuple[RowKey, ...]  # (decision_month, issuer_id, security_id)

    def arrays(self) -> dict[str, Any]:
        return {
            "features": self.x,
            "target": self.target,
            "relevance": self.relevance,
            "qid": self.qid,
            "decision_month": np.array([k[0] for k in self.keys]),
            "issuer_id": np.array([k[1] for k in self.keys]),
            "security_id": np.array([k[2] for k in self.keys]),
        }

    def validate(self, feature_count: int, training: bool = True) -> None:
        n = len(self.keys)
        if (
            not n
            or self.x.shape != (n, feature_count)
            or self.target.shape != (n,)
            or self.relevance.shape != (n,)
            or self.qid.shape != (n,)
        ):
            raise TechnicalInvalid("GROUP_ALIGNMENT_ERROR: input shape/row loss")
        if self.keys != tuple(sorted(self.keys)):
            raise TechnicalInvalid("GROUP_ALIGNMENT_ERROR: row order")
        for index in (1, 2):
            if len({(k[0], k[index]) for k in self.keys}) != n:
                raise TechnicalInvalid("GROUP_ALIGNMENT_ERROR: duplicate issuer/security-month")
        months = sorted({k[0] for k in self.keys})
        expected = np.array([months.index(k[0]) for k in self.keys], dtype=np.int64)
        if self.qid.dtype.kind not in "iu" or not np.array_equal(self.qid, expected):
            raise TechnicalInvalid("GROUP_ALIGNMENT_ERROR: qid/month correspondence")
        if not np.isfinite(self.target).all():
            raise TechnicalInvalid("NONFINITE_TARGET")
        if (
            not np.isfinite(self.relevance).all()
            or (self.relevance < 0).any()
            or (self.relevance > 9).any()
            or (self.relevance != np.floor(self.relevance)).any()
        ):
            raise TechnicalInvalid("corrupt relevance labels")
        for month in months:
            mask = np.array([k[0] == month for k in self.keys])
            if int(mask.sum()) < 2:
                raise TechnicalInvalid("INSUFFICIENT_ROWS")
            if not np.array_equal(self.relevance[mask], R.grades(self.target[mask])):
                raise TechnicalInvalid(
                    "corrupt relevance: differs from frozen target transformation"
                )
        if np.isinf(self.x).any() or (training and np.isnan(self.x).all(axis=0).any()):
            raise TechnicalInvalid("invalid TRAIN feature availability")


@dataclass(frozen=True)
class ScoredRows:
    scores: Matrix
    keys: tuple[RowKey, ...]


class ObservableBackend(Protocol):
    def fit(self, x: Matrix, y: Matrix, qid: NDArray[np.int64]) -> None: ...
    def predict(self, data: GroupedData) -> ScoredRows: ...
    def serialize(self, path: Path) -> Any: ...
    def metadata(self) -> dict[str, Any]: ...


def numeric_statistics(values: Matrix) -> dict[str, Any]:
    finite = values[np.isfinite(values)]
    counts = Counter(float(v) for v in finite)
    return {
        "N": len(values),
        "nonfinite": len(values) - len(finite),
        "distinct": len(counts),
        "sd_population": float(np.std(finite)) if len(finite) else None,
        "min": float(np.min(finite)) if len(finite) else None,
        "max": float(np.max(finite)) if len(finite) else None,
        "identical_pct_modal_share": 100.0 * max(counts.values()) / len(values) if counts else None,
    }


def monthly_diagnostics(
    data: GroupedData,
    predictions: ScoredRows,
    metric: Callable[[Matrix, Matrix], float | None] = R.ic,
    evaluate: bool = True,
) -> list[dict[str, Any]]:
    aligned = predictions.keys == data.keys and predictions.scores.shape == data.target.shape
    result = []
    for month in sorted({k[0] for k in data.keys}):
        mask = np.array([k[0] == month for k in data.keys])
        target = data.target[mask]
        score = predictions.scores[mask] if aligned else np.array([], dtype=float)
        reason = None
        if not aligned:
            reason = "GROUP_ALIGNMENT_ERROR"
        elif not np.isfinite(score).all():
            reason = "NONFINITE_SCORES"
        elif not np.isfinite(target).all():
            reason = "NONFINITE_TARGET"
        elif len(target) < 2:
            reason = "INSUFFICIENT_ROWS"
        elif np.ptp(target) == 0:
            reason = "CONSTANT_TARGET"
        elif np.ptp(score) == 0:
            reason = "CONSTANT_SCORES"
        value = metric(score, target) if evaluate and reason is None else None
        if value is not None and not np.isfinite(value):
            value = None
        if evaluate and value is None and reason is None:
            reason = "OTHER"
        result.append(
            {
                "month": month,
                "N": len(target),
                "scores": numeric_statistics(score),
                "targets": numeric_statistics(target),
                "relevance_distinct": len(np.unique(data.relevance[mask])),
                "IC": value,
                "IC_evaluated": evaluate,
                "undefined_reason": reason,
                "ndcg20": R.ndcg(score, data.relevance[mask], 0.2)
                if evaluate and aligned and reason in (None, "CONSTANT_SCORES")
                else None,
            }
        )
    return result


def candidate_summary(months: list[dict[str, Any]], candidate: int) -> dict[str, Any]:
    if not months:
        raise TechnicalInvalid("empty validation geometry")
    reasons = [m["undefined_reason"] for m in months if m["IC"] is None]
    if any(r != "CONSTANT_SCORES" for r in reasons):
        raise TechnicalInvalid(f"TECHNICAL_INVALID: {reasons}")
    defined = [m["IC"] for m in months if m["IC"] is not None]
    return {
        "candidate": candidate,
        "status": "EVALUABLE" if defined else "NON_RANKING_CANDIDATE",
        "required_months": len(months),
        "defined_months": len(defined),
        "undefined_months": len(months) - len(defined),
        "monthly": months,
        # Inherit V0 partial-undefined composite explicitly; never publish null monthly IC as zero.
        "selection_composite": sum(defined) / len(months) if defined else None,
        "selection_composite_is_observed_IC": False,
        "ndcg20": float(np.mean([m["ndcg20"] for m in months])) if defined else None,
    }


def select_synthetic_proposal(candidates: list[dict[str, Any]], scope: str) -> int:
    require_synthetic_scope(scope)
    if any(c["status"] == "TECHNICAL_INVALID" for c in candidates):
        raise TechnicalInvalid("TECHNICAL_INVALID: stop immediately")
    valid = [c for c in candidates if c["status"] == "EVALUABLE"]
    if not valid:
        raise NoValidRankingCandidate("NO_VALID_RANKING_CANDIDATE")
    best = max(c["selection_composite"] for c in valid)
    tied = [c for c in valid if c["selection_composite"] >= best - 1e-12]
    ndcg = max(c["ndcg20"] for c in tied)
    return int(min(c["candidate"] for c in tied if c["ndcg20"] >= ndcg - 1e-12))


def inspect_xgb(adapter: Any) -> dict[str, Any]:
    """Inspect an already-fitted booster only; never fit, reload or invent missing diagnostics."""
    booster = adapter.model.get_booster()
    trees = [json.loads(t) for t in booster.get_dump(dump_format="json", with_stats=True)]
    split_count = leaf_count = stump_count = 0
    gains = []
    for tree in trees:
        stack = [tree]
        tree_splits = 0
        while stack:
            node = stack.pop()
            if "leaf" in node:
                leaf_count += 1
            else:
                tree_splits += 1
                gains.append(float(node["gain"]))
                stack.extend(node["children"])
        split_count += tree_splits
        stump_count += tree_splits == 0
    return {
        "backend": "xgboost",
        "effective_boosted_rounds": booster.num_boosted_rounds(),
        "trees": len(trees),
        "trees_without_splits": stump_count,
        "trees_with_splits": len(trees) - stump_count,
        "splits": split_count,
        "leaves": leaf_count,
        "gain_total": sum(gains),
        "importance_available": True,
        "feature_importance": {
            k: booster.get_score(importance_type=k)
            for k in ("weight", "gain", "total_gain", "cover", "total_cover")
        },
        "tree_dump": trees,
    }


class ObservedXGBBackend:
    """Composition preserves the frozen adapter and permits archiving invalid raw predictions."""

    def __init__(self, adapter: Any) -> None:
        self.adapter = adapter

    def fit(self, x: Matrix, y: Matrix, qid: NDArray[np.int64]) -> None:
        self.adapter.fit(x, y, qid)

    def predict(self, data: GroupedData) -> ScoredRows:
        return ScoredRows(np.asarray(self.adapter.model.predict(data.x), dtype=float), data.keys)

    def serialize(self, path: Path) -> Any:
        return self.adapter.serialize(path)

    def metadata(self) -> dict[str, Any]:
        return cast(dict[str, Any], self.adapter.metadata())

    def diagnostics(self) -> dict[str, Any]:
        return inspect_xgb(self.adapter)


def fit_synthetic_inner(
    backend: ObservableBackend,
    train: GroupedData,
    validation: GroupedData,
    archive: AtomicArchive,
    context: dict[str, Any],
    metric: Callable[[Matrix, Matrix], float | None] = R.ic,
    after_fit_archive: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Repaired lifecycle. Real-data execution deliberately unavailable pending approval."""
    require_synthetic_scope(context.get("scope", ""))
    if any(
        not k[1].startswith("synthetic:") or not k[2].startswith("synthetic:")
        for k in (*train.keys, *validation.keys)
    ):
        raise PendingHumanApproval("only explicitly identified synthetic fixtures are executable")
    phase = "INPUTS_BEFORE_FIT"
    try:
        archive.commit(
            "inputs",
            ArtifactKind.TRAINING_ARTIFACT,
            {"context": context, "trained": False},
            {
                **{"train_" + k: v for k, v in train.arrays().items()},
                **{"validation_" + k: v for k, v in validation.arrays().items()},
            },
        )
        train.validate(len(context["feature_names"]))
        validation.validate(len(context["feature_names"]), training=False)
        if set(train.keys) & set(validation.keys):
            raise TechnicalInvalid("TRAIN/validation overlap")
        for name, data in [("train", train), ("validation", validation)]:
            if dict(Counter(k[0] for k in data.keys)) != context["expected_" + name + "_counts"]:
                raise TechnicalInvalid("GROUP_ALIGNMENT_ERROR: declared cohort row loss")
        phase = "FIT"
        backend.fit(train.x, train.relevance, train.qid)
        phase = "POST_FIT_ARCHIVE"
        # First durable action after fit: model and complete metadata, before prediction/evaluation.
        archive.commit(
            "model",
            ArtifactKind.TRAINING_ARTIFACT,
            {"context": context, "trained": True, "code_sha256": file_digest(Path(__file__))},
            serialize=backend.serialize,
        )
        if after_fit_archive is not None:
            after_fit_archive()
        diagnostics = getattr(backend, "diagnostics", None)
        ensemble = (
            diagnostics()
            if diagnostics is not None
            else {"available": False, "backend_specific": "NOT_PROVIDED"}
        )
        metadata = backend.metadata()
        if metadata.get("parameters") != context["parameters"]:
            raise TechnicalInvalid("backend parameters differ from declared context")
        archive.commit(
            "training",
            ArtifactKind.TRAINING_ARTIFACT,
            {
                "context": context,
                "backend": metadata,
                "ensemble": ensemble,
                "trained": True,
                "model_reference": "model/COMMIT.json",
            },
        )
        phase = "PREDICT"
        predictions = backend.predict(validation)
        phase = "VALIDATION_ARCHIVE_BEFORE_SPEARMAN"
        archive.commit(
            "validation",
            ArtifactKind.VALIDATION_DIAGNOSTIC,
            {
                "context": context,
                "target_row_keys": validation.keys,
                "score_row_keys": predictions.keys,
            },
            {**validation.arrays(), "scores": predictions.scores},
        )
        phase = "DESCRIPTIVE_DIAGNOSTICS_BEFORE_SPEARMAN"
        raw = monthly_diagnostics(validation, predictions, evaluate=False)
        archive.commit(
            "descriptive",
            ArtifactKind.VALIDATION_DIAGNOSTIC,
            {"monthly": raw, "IC_evaluated": False},
        )
        technical_reasons = [
            m["undefined_reason"]
            for m in raw
            if m["undefined_reason"] not in (None, "CONSTANT_SCORES")
        ]
        if technical_reasons:
            raise TechnicalInvalid(f"TECHNICAL_INVALID: {technical_reasons}")
        phase = "SPEARMAN"
        months = monthly_diagnostics(validation, predictions, metric=metric)
        archive.commit(
            "diagnostics",
            ArtifactKind.VALIDATION_DIAGNOSTIC,
            {"context": context, "monthly": months, "ensemble_reference": "training/payload.json"},
        )
        phase = "PROPOSED_CANDIDATE_POLICY_SYNTHETIC_ONLY"
        summary = candidate_summary(months, context["candidate"])
        archive.commit("candidate", ArtifactKind.VALIDATION_DIAGNOSTIC, summary)
        return summary
    except Exception as exc:
        with suppress(Exception):
            archive.commit(
                "failure",
                ArtifactKind.VALIDATION_DIAGNOSTIC,
                {
                    "status": "TECHNICAL_INVALID",
                    "phase": phase,
                    "exception_type": type(exc).__name__,
                    "message": str(exc),
                    "context": context,
                    "scientific_result": False,
                },
            )
        raise
