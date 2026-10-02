# ruff: noqa: E501
"""Research Lab HTTP surface (ADR-0030). READ-ONLY, real rows or empty lists, never invented results.

The sealed holdout is never exposed: nothing here reads returns/labels inside it, and the status
endpoint always states ``holdout: SEALED``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import select

from pitquant.api.analyzer import DB
from pitquant.config.settings import Settings
from pitquant.db.models import (
    DatasetVersion,
    FeatureSetVersion,
    LabelDefinition,
    MetricSet,
    ModelConfig,
    ResearchExperiment,
    ResearchFold,
)
from pitquant.features.v0.engine import FEATURE_NAMES
from pitquant.research.baselines import BASELINES
from pitquant.research_readiness import research_readiness


def _rows(session: Any, model: Any, limit: int = 200) -> list[dict[str, Any]]:
    out = []
    for r in session.scalars(select(model).limit(limit)):
        out.append(
            {
                c.key: (v.isoformat() if hasattr(v, "isoformat") else v)
                for c in r.__table__.columns
                for v in [getattr(r, c.key)]
            }
        )
    return out


def make_research_router(cfg: Settings) -> APIRouter:
    r = APIRouter(prefix="/research", tags=["research"])
    ho = cfg.validation.final_holdout

    @r.get("/status")
    def status(db: DB) -> dict[str, Any]:
        rf = research_readiness(db, cfg)
        return {
            "holdout": "SEALED",
            "holdout_range": [str(ho.start), str(ho.end)],
            "flags": {
                k: rf.flags.get(k)
                for k in (
                    "RESEARCH_LAB_IMPLEMENTED",
                    "RESEARCH_DATA_READY",
                    "FEATURE_RESEARCH_READY_US",
                    "LABEL_ENGINE_READY_US",
                    "BASELINE_MODEL_READY",
                )
            },
            "reasons": {
                k: rf.reasons.get(k, []) for k in ("RESEARCH_DATA_READY", "BASELINE_MODEL_READY")
            },
        }

    @r.get("/experiments")
    def experiments(db: DB) -> list[dict[str, Any]]:
        return _rows(db, ResearchExperiment)

    @r.get("/datasets")
    def datasets(db: DB) -> list[dict[str, Any]]:
        return _rows(db, DatasetVersion)

    @r.get("/features")
    def features(db: DB) -> dict[str, Any]:
        return {
            "catalog": list(FEATURE_NAMES),
            "feature_sets": _rows(db, FeatureSetVersion),
            "labels": _rows(db, LabelDefinition),
        }

    @r.get("/models")
    def models(db: DB) -> dict[str, Any]:
        return {
            "predefined_baselines": [
                {
                    "kind": c.kind,
                    "target": c.target,
                    "horizons": list(c.horizons),
                    "grid": {k: list(v) for k, v in c.grid.items()},
                    "config_hash": c.config_hash,
                    "trained": False,
                }
                for c in BASELINES.values()
            ],
            "registered": _rows(db, ModelConfig),
        }

    @r.get("/backtests")
    def backtests(db: DB) -> dict[str, Any]:
        return {"folds": _rows(db, ResearchFold), "metric_sets": _rows(db, MetricSet)}

    @r.get("/audit")
    def audit(request: Request, db: DB) -> dict[str, Any]:
        rf = research_readiness(db, cfg)
        return {
            "holdout": "SEALED",
            "holdout_range": [str(ho.start), str(ho.end)],
            "gates": rf.reasons.get("FEATURE_RESEARCH_READY_US", []),
            "rules": [
                "decision_at mandatory; available_at <= decision_at (PITGuard)",
                "label window must also end before the holdout",
                "transformers fitted on the train fold only",
                "ineligible rows are kept with a reason",
                "human analysis labels are never a target or a feature",
            ],
        }

    return r
