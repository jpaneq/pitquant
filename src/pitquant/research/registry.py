# ruff: noqa: E501
"""Experiment registry (ADR-0030): everything needed to reproduce an experiment months later.

``define_experiment`` stores the commit SHA, dataset hash, feature/label/model/universe/benchmark versions,
train/validation dates, purge/embargo, seed and library versions. An experiment whose data gates are not
met is stored as ``BLOCKED`` with the reasons (it is NOT trained). Rows are append-only; nothing is faked.
"""

from __future__ import annotations

import platform
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date
from importlib import metadata
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.backtest.targets import BENCHMARK_NAME, BENCHMARK_TYPE, LABEL_VERSION
from pitquant.core.hashing import content_hash
from pitquant.db.models import (
    DatasetVersion,
    FeatureSetVersion,
    LabelDefinition,
    ModelConfig,
    ResearchExperiment,
)
from pitquant.features.v0.engine import FEATURE_NAMES, FEATURE_VERSION
from pitquant.features.v0.fundamentals import TAG_MAP_VERSION
from pitquant.research.baselines import BaselineConfig
from pitquant.research.dataset_builder import DatasetResult
from pitquant.research.walkforward import WalkForwardConfig

ROOT = Path(__file__).resolve().parents[3]


def commit_sha() -> str:
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10
            ).stdout.strip()
            or "UNKNOWN"
        )
    except Exception:
        return "UNKNOWN"


def library_versions() -> dict[str, str]:
    out = {"python": platform.python_version(), "platform": sys.platform}
    for lib in ("pandas", "numpy", "sqlalchemy", "pydantic", "fastapi", "scikit-learn"):
        try:
            out[lib] = metadata.version(lib)
        except metadata.PackageNotFoundError:
            out[lib] = "NOT_INSTALLED"
    return out


def get_or_create_feature_set(
    s: Session, names: tuple[str, ...] = FEATURE_NAMES, name: str = "raw-v0"
) -> FeatureSetVersion:
    h = content_hash(
        {"names": list(names), "feature_version": FEATURE_VERSION, "tag_map": TAG_MAP_VERSION}
    )
    row = s.scalars(select(FeatureSetVersion).where(FeatureSetVersion.set_hash == h)).first()
    if row is None:
        row = FeatureSetVersion(
            name=name,
            feature_version=FEATURE_VERSION,
            tag_map_version=TAG_MAP_VERSION,
            features=list(names),
            set_hash=h,
        )
        s.add(row)
        s.flush()
    return row


def get_or_create_label(
    s: Session,
    horizon: int,
    benchmark: str = BENCHMARK_NAME,
    benchmark_type: str = BENCHMARK_TYPE,
    target_kind: str = "EXCESS_TOTAL_RETURN",
) -> LabelDefinition:
    d = {
        "label_version": LABEL_VERSION,
        "horizon_months": horizon,
        "target_kind": target_kind,
        "benchmark": benchmark,
        "benchmark_type": benchmark_type,
        "entry": "open(T)",
        "exit": "close(first NYSE session on/after T + horizon months)",
        "total_return": "raw prices + splits + dividends (engine), no vendor adjusted close",
    }
    h = content_hash(d)
    row = s.scalars(select(LabelDefinition).where(LabelDefinition.definition_hash == h)).first()
    if row is None:
        row = LabelDefinition(
            label_version=LABEL_VERSION,
            horizon_months=horizon,
            target_kind=target_kind,
            benchmark=benchmark,
            benchmark_type=benchmark_type,
            definition=d,
            definition_hash=h,
        )
        s.add(row)
        s.flush()
    return row


def get_or_create_model_config(s: Session, cfg: BaselineConfig) -> ModelConfig:
    row = s.scalars(select(ModelConfig).where(ModelConfig.config_hash == cfg.config_hash)).first()
    if row is None:
        row = ModelConfig(
            kind=cfg.kind,
            name=cfg.name,
            params={
                **cfg.params,
                "target": cfg.target,
                "horizons": list(cfg.horizons),
                "transformers": list(cfg.transformers),
                "version": cfg.version,
            },
            grid={k: list(v) for k, v in cfg.grid.items()},
            config_hash=cfg.config_hash,
        )
        s.add(row)
        s.flush()
    return row


def persist_dataset(
    s: Session, res: DatasetResult, fs: FeatureSetVersion, label: LabelDefinition
) -> DatasetVersion:
    row = s.scalars(
        select(DatasetVersion).where(DatasetVersion.dataset_hash == res.dataset_hash)
    ).first()
    if row is None:
        sp = res.spec
        row = DatasetVersion(
            dataset_hash=res.dataset_hash,
            universe=sp.universe,
            universe_version=sp.universe_version,
            start_date=sp.start_date,
            end_date=sp.end_date,
            snapshot_frequency=sp.snapshot_frequency,
            feature_set_version_id=fs.feature_set_version_id,
            label_definition_id=label.label_definition_id,
            benchmark=f"{sp.benchmark_name} ({sp.benchmark_type})",
            n_rows=res.summary["n_rows"],
            n_eligible=res.summary["n_eligible"],
            n_securities=res.summary["n_securities"],
            holdout_dates_excluded=res.holdout_dates_excluded,
            builder_version="dataset-builder-1",
            rows_path=res.path,
            summary=res.summary,
        )
        s.add(row)
        s.flush()
    return row


@dataclass(frozen=True)
class ExperimentSpec:
    name: str
    model: BaselineConfig
    walk_forward: WalkForwardConfig
    horizon_months: int
    universe_version: str
    benchmark_version: str
    train_start: date | None = None
    train_end: date | None = None
    validation_start: date | None = None
    validation_end: date | None = None
    seed: int = 20261001


def define_experiment(
    s: Session, spec: ExperimentSpec, dataset: DatasetResult | None, gates: dict[str, bool]
) -> ResearchExperiment:
    fs = get_or_create_feature_set(s, dataset.spec.feature_set if dataset else FEATURE_NAMES)
    label = get_or_create_label(
        s,
        spec.horizon_months,
        target_kind="OUTPERFORM" if spec.model.target == "outperform" else "EXCESS_TOTAL_RETURN",
    )
    mc = get_or_create_model_config(s, spec.model)
    dv = persist_dataset(s, dataset, fs, label) if dataset else None
    blocked = [f"gate {k} = false" for k, v in gates.items() if not v]
    if dataset is not None and dataset.summary["n_eligible"] == 0:
        blocked.append("dataset has 0 ELIGIBLE rows")
    canon = {
        "name": spec.name,
        "model": spec.model.config_hash,
        "wf": asdict(spec.walk_forward),
        "horizon": spec.horizon_months,
        "universe": spec.universe_version,
        "benchmark": spec.benchmark_version,
        "dataset": dataset.dataset_hash if dataset else None,
        "feature_set": fs.set_hash,
        "label": label.definition_hash,
        "seed": spec.seed,
        "dates": [
            str(spec.train_start),
            str(spec.train_end),
            str(spec.validation_start),
            str(spec.validation_end),
        ],
    }
    h = content_hash(canon)
    ex = s.scalars(select(ResearchExperiment).where(ResearchExperiment.spec_hash == h)).first()
    if ex is not None:
        return ex
    ex = ResearchExperiment(
        name=spec.name,
        status="BLOCKED" if blocked else "DEFINED",
        commit_sha=commit_sha(),
        dataset_version_id=dv.dataset_version_id if dv else None,
        dataset_hash=dataset.dataset_hash if dataset else None,
        feature_set_version_id=fs.feature_set_version_id,
        label_definition_id=label.label_definition_id,
        model_config_id=mc.model_config_id,
        universe_version=spec.universe_version,
        benchmark_version=spec.benchmark_version,
        train_start=spec.train_start,
        train_end=spec.train_end,
        validation_start=spec.validation_start,
        validation_end=spec.validation_end,
        purge_months=spec.walk_forward.purge_months,
        embargo_months=spec.walk_forward.embargo_months,
        window_kind=spec.walk_forward.window_kind,
        seed=spec.seed,
        library_versions=library_versions(),
        spec=canon,
        spec_hash=h,
        blocked_reasons=blocked,
    )
    s.add(ex)
    s.flush()
    return ex
