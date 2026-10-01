"""Sealed holdout: explicit, logged, once-per-frozen-model evaluation (ADR-0014)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.config.settings import Settings
from pitquant.core.errors import HoldoutAccessError
from pitquant.db.models import HoldoutAccessLog, HoldoutEvaluation, ModelRow, ModelVersion
from pitquant.validation.holdout import (
    evaluate_candidate_on_holdout,
    guard_analytics_range,
    read_sealed_evaluation,
)

pytestmark = pytest.mark.pit


def _model(session: Session, version: str, frozen: bool) -> None:
    if session.get(ModelRow, "m12") is None:
        session.add(ModelRow(model_id="m12", horizon="12m", kind="baseline"))
    session.add(
        ModelVersion(
            model_version=version,
            model_id="m12",
            scoring_version="s",
            feature_version="f",
            code_version="c",
            config_hash="h",
            seed=1,
            frozen=frozen,
        )
    )
    session.flush()


def _eval(start: date, end: date) -> tuple[dict[str, Any], int]:
    assert (start, end) == (date(2022, 10, 1), date(2025, 9, 30))
    return {"ic_mean": 0.031, "brier": 0.247}, 1234


def test_holdout_requires_frozen_model(session: Session, settings: Settings) -> None:
    _model(session, "v-dev", frozen=False)
    with pytest.raises(HoldoutAccessError):
        evaluate_candidate_on_holdout(
            session,
            settings,
            model_version="v-dev",
            requested_by="jairo",
            reason="final",
            evaluate=_eval,
        )
    assert session.scalars(select(HoldoutEvaluation)).all() == []


def test_holdout_evaluation_logged_and_once_per_model(session: Session, settings: Settings) -> None:
    _model(session, "v1", frozen=True)
    res = evaluate_candidate_on_holdout(
        session,
        settings,
        model_version="v1",
        requested_by="jairo",
        reason="promotion review",
        evaluate=_eval,
    )
    assert res.metrics["ic_mean"] == 0.031 and res.candidates_evaluated_so_far == 1
    logs = session.scalars(select(HoldoutAccessLog)).all()
    assert len(logs) == 1 and logs[0].reason == "promotion review"
    with pytest.raises(HoldoutAccessError):  # no re-rolling the dice on the same model
        evaluate_candidate_on_holdout(
            session,
            settings,
            model_version="v1",
            requested_by="jairo",
            reason="again",
            evaluate=_eval,
        )
    ev = read_sealed_evaluation(
        session, res.evaluation_id, requested_by="auditor", reason="committee"
    )
    assert ev.metrics_hash and len(session.scalars(select(HoldoutAccessLog)).all()) == 2


def test_development_analytics_cannot_touch_holdout(settings: Settings) -> None:
    guard_analytics_range(settings, date(2010, 1, 1), date(2022, 9, 30))
    with pytest.raises(HoldoutAccessError):
        guard_analytics_range(settings, date(2020, 1, 1), date(2023, 1, 1))


def test_api_exposes_no_holdout_metrics(market_factory, settings: Settings) -> None:  # type: ignore[no-untyped-def]
    from pitquant.api.app import create_app

    app = create_app(market_factory, settings)
    paths = [getattr(r, "path", "") for r in app.routes]
    assert not any("holdout" in p.lower() for p in paths)
