# ruff: noqa: E501
"""The ONLY writer of ``SYNTHETIC_FIXTURE`` prediction snapshots (ADR-0038). Lives in the TEST tree on purpose: no endpoint, CLI or product module can create a
synthetic prediction against a real database. Every row is labelled «SYNTHETIC TEST DATA», ``is_synthetic`` and carries NO model: it only feeds tests / the E2E fixture."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from pitquant.db.models_lab import PredictionSnapshot
from pitquant.prediction.contract import (
    SYNTHETIC_FIXTURE,
    SYNTHETIC_WARNING,
    PredictionFields,
    write_snapshot,
)

FIXTURE_MODEL_ID = "SYNTHETIC_FIXTURE_MODEL"
FIXTURE_MODEL_VERSION = "synthetic-fixture-1"


def synthetic_prediction(
    session: Session, security_id: str, decision_at: datetime, horizon: int = 6, *, p: float | None = 0.72, expected: float | None = 0.08, generated_at: datetime | None = None,
    quantiles: tuple[float, float, float, float, float] | None = (-0.10, -0.03, 0.06, 0.12, 0.25), data_available_at: datetime | None = None, contributions: dict[str, float] | None = None,
) -> PredictionSnapshot:  # fmt: skip
    q = quantiles or (None, None, None, None, None)
    f = PredictionFields(
        security_id, decision_at, generated_at or decision_at, horizon, FIXTURE_MODEL_ID, FIXTURE_MODEL_VERSION, "synthetic-features", expected_excess_return=expected, p_outperform=p,
        return_quantile_10=q[0], return_quantile_25=q[1], return_quantile_50=q[2], return_quantile_75=q[3], return_quantile_90=q[4], uncertainty={"width_p10_p90": (q[4] - q[0]) if q[0] is not None else None},
        data_quality={"label": "SYNTHETIC"}, feature_contributions=contributions if contributions is not None else {"synthetic_feature_a": 0.02, "synthetic_feature_b": -0.01},
        warnings=[SYNTHETIC_WARNING], data_available_at=data_available_at, provenance={"synthetic": True, "note": "fixture, not a model output"},
    )  # fmt: skip
    return write_snapshot(session, f, SYNTHETIC_FIXTURE)
