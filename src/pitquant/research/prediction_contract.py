# ruff: noqa: E501
"""Prediction provenance contract (future; ADR-0030). A prediction is data about a MODEL OUTPUT, never a
trading signal: there is no BUY/HOLD/SELL field."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from pitquant.core.errors import PITQuantError
from pitquant.core.timeutils import require_aware


@dataclass(frozen=True)
class PredictionRecord:
    experiment_id: str
    model_id: str
    model_version: str
    generated_at: datetime
    decision_at: datetime
    security_id: str
    feature_snapshot_id: str  # the EXACT immutable snapshot the model saw
    expected_excess_return: float | None
    probability: float | None
    uncertainty: dict[str, float | None] = field(
        default_factory=dict
    )  # e.g. p10..p90, interval width
    calibration_version: str | None = None

    def __post_init__(self) -> None:
        require_aware(self.generated_at, "generated_at")
        require_aware(self.decision_at, "decision_at")
        if self.decision_at > self.generated_at:
            raise PITQuantError("a prediction cannot be generated before its decision_at")
        if self.probability is not None and not 0.0 <= self.probability <= 1.0:
            raise PITQuantError("probability must be in [0, 1]")
        if self.probability is not None and self.calibration_version is None:
            raise PITQuantError(
                "a probability must name the calibration version that makes it a probability"
            )
