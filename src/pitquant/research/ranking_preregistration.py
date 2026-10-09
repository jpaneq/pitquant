"""Outcome-free, append-only preregistration. Deliberately contains no execution API."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

EXPERIMENT = "FIRST_EQUITY_CROSS_SECTIONAL_RANK_12M_V0"
DATASET = "US_LARGE_CAP_RESEARCH_DATASET_V1_FROZEN"
FORBIDDEN = frozenset(
    {"fitted_model", "outer_predictions", "ranking_results", "future_return_results"}
)


def encoded(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(encoded(value)).hexdigest()


def file_digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def write_once(path: Path, content: bytes) -> None:
    """Identical replay is allowed; a revision cannot overwrite any existing bytes."""
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError(f"immutable revision conflict: {path.name}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as target:
        target.write(content)
        target.flush()
        os.fsync(target.fileno())


def assert_not_run(manifest: dict[str, Any]) -> None:
    """Reject execution outputs anywhere in this task's declarative manifest."""
    if manifest.get("status") != "PREREGISTERED_NOT_RUN":
        raise ValueError("this task cannot execute the experiment")
    if manifest.get("state") != "NOT_RUN":
        raise ValueError("experiment state changed")
    counters = manifest["counters"]
    for name in (
        "models_trained",
        "outer_test_predictions",
        "ranking_metrics_computed",
        "future_returns_computed",
        "holdout_outcomes_accessed",
        "oot_outcomes_accessed",
    ):
        if counters.get(name) != 0:
            raise ValueError(f"execution forbidden: {name}")

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if FORBIDDEN & value.keys():
                raise ValueError("execution output forbidden")
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(manifest)


def verify_manifest(manifest: dict[str, Any]) -> None:
    assert_not_run(manifest)
    for name, value in manifest["contracts"].items():
        if digest(value) != manifest["contract_hashes"][name]:
            raise ValueError(f"contract integrity failure: {name}")
    body = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    if digest(body) != manifest["manifest_sha256"]:
        raise ValueError("manifest integrity failure")


def verify_frozen_dataset(dataset: dict[str, Any], root: Path | None = None) -> None:
    """Verify committed layers; optionally verify retained opaque local inputs too."""
    if dataset.get("dataset_id") != DATASET or dataset.get("status") != "FROZEN":
        raise ValueError("unregistered dataset")
    body = {k: v for k, v in dataset.items() if k != "dataset_sha256"}
    if digest(body) != dataset["dataset_sha256"]:
        raise ValueError("dataset integrity failure")
    for name, value in dataset["layers"].items():
        if digest(value) != dataset["layer_hashes"][name]:
            raise ValueError(f"dataset layer integrity failure: {name}")
    if root is not None:
        for item in (dataset["candidate"], dataset["database_snapshot"]):
            if file_digest(root / item["path"]) != item["sha256"]:
                raise ValueError("retained input integrity failure")
        for sha in dataset["sources"]["raw_object_sha256"]:
            if file_digest(root / "data/archive" / sha[:2] / sha[2:4] / sha) != sha:
                raise ValueError("raw source integrity failure")
