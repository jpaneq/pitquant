# ruff: noqa: E501
"""Prediction contract V1 (ADR-0038). A ``PredictionSnapshot`` is data about a MODEL OUTPUT for (security, decision_at, horizon): no BUY/HOLD/SELL.

Rules enforced here AND by CHECK constraints:
* while ``NOT_YET_VALIDATED`` every predictive field is NULL (nothing is invented);
* ``SYNTHETIC_FIXTURE`` rows are fixtures for tests / E2E (always ``is_synthetic``, always warned «SYNTHETIC TEST DATA») and are written ONLY by test helpers:
  no endpoint, CLI or product module creates them (``tests/support/synthetic_predictions.py``);
* NOTHING in this build writes ``VALIDATED``: promotion needs a validated model, which does not exist yet;
* PIT: ``decision_at <= generated_at`` and the inputs were available no later than ``decision_at``;
* append-only: a new model version is a new row, never an edit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from itertools import pairwise
from typing import Any

from sqlalchemy.orm import Session

from pitquant.core.errors import PITQuantError
from pitquant.core.timeutils import require_aware
from pitquant.db.models_lab import PREDICTION_STATUSES, PredictionSnapshot

HORIZONS = (6, 12)
NOT_YET_VALIDATED = "NOT_YET_VALIDATED"
SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"
SYNTHETIC_WARNING = "SYNTHETIC TEST DATA"
BENCHMARK = "SPY_TOTAL_RETURN_PROXY"
PREDICTIVE_FIELDS = (
    "expected_excess_return", "p_outperform", "return_quantile_10", "return_quantile_25", "return_quantile_50", "return_quantile_75", "return_quantile_90",
    "uncertainty", "feature_contributions",
)  # fmt: skip
QUANTILES = (
    "return_quantile_10",
    "return_quantile_25",
    "return_quantile_50",
    "return_quantile_75",
    "return_quantile_90",
)


class PredictionContractError(PITQuantError):
    pass


@dataclass
class PredictionFields:
    security_id: str
    decision_at: datetime
    generated_at: datetime
    horizon_months: int
    model_id: str
    model_version: str
    feature_set_version: str
    dataset_version: str | None = None
    expected_excess_return: float | None = None
    p_outperform: float | None = None
    return_quantile_10: float | None = None
    return_quantile_25: float | None = None
    return_quantile_50: float | None = None
    return_quantile_75: float | None = None
    return_quantile_90: float | None = None
    uncertainty: dict[str, Any] | None = None
    benchmark: str = BENCHMARK
    data_quality: dict[str, Any] = field(default_factory=dict)
    feature_contributions: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    data_available_at: datetime | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
    commit_sha: str | None = None


def validate(f: PredictionFields, status: str) -> None:
    """Raises ``PredictionContractError`` unless the fields satisfy the contract for ``status``."""
    if status not in PREDICTION_STATUSES:
        raise PredictionContractError(
            f"prediction_status must be one of {PREDICTION_STATUSES}: nothing in this build can write {status!r}"
        )
    require_aware(f.decision_at, "decision_at")
    require_aware(f.generated_at, "generated_at")
    if f.decision_at > f.generated_at:
        raise PredictionContractError("a prediction cannot be generated before its decision_at")
    if f.horizon_months not in HORIZONS:
        raise PredictionContractError(f"horizon must be one of {HORIZONS} months")
    if f.data_available_at is not None:
        require_aware(f.data_available_at, "data_available_at")
        if f.data_available_at > f.decision_at:
            raise PredictionContractError(
                "look-ahead: an input was available only after decision_at"
            )
    if status == NOT_YET_VALIDATED:
        filled = [k for k in PREDICTIVE_FIELDS if getattr(f, k) is not None]
        if filled:
            raise PredictionContractError(
                f"NOT_YET_VALIDATED: predictive fields must be NULL (found {filled}); nothing is invented"
            )
        return
    # SYNTHETIC_FIXTURE
    if SYNTHETIC_WARNING not in f.warnings:
        raise PredictionContractError(
            "a synthetic fixture must carry the warning 'SYNTHETIC TEST DATA'"
        )
    if f.p_outperform is not None and not 0.0 <= f.p_outperform <= 1.0:
        raise PredictionContractError("p_outperform must be in [0, 1]")
    q = [getattr(f, k) for k in QUANTILES]
    if any(v is not None for v in q) and (
        any(v is None for v in q) or any(a > b for a, b in pairwise(q))
    ):
        raise PredictionContractError(
            "return quantiles must all be present and non-decreasing (P10 <= ... <= P90)"
        )


def write_snapshot(session: Session, f: PredictionFields, status: str) -> PredictionSnapshot:
    """Validate and append one snapshot. Product code calls ``record_not_yet_validated``; the synthetic status is written only by test helpers."""
    validate(f, status)
    row = PredictionSnapshot(
        security_id=f.security_id, decision_at=f.decision_at, generated_at=f.generated_at, horizon_months=f.horizon_months, model_id=f.model_id, model_version=f.model_version,
        feature_set_version=f.feature_set_version, dataset_version=f.dataset_version, expected_excess_return=f.expected_excess_return, p_outperform=f.p_outperform,
        return_quantile_10=f.return_quantile_10, return_quantile_25=f.return_quantile_25, return_quantile_50=f.return_quantile_50, return_quantile_75=f.return_quantile_75,
        return_quantile_90=f.return_quantile_90, uncertainty=f.uncertainty, benchmark=f.benchmark, data_quality=f.data_quality, feature_contributions=f.feature_contributions,
        warnings=list(f.warnings), prediction_status=status, is_synthetic=status == SYNTHETIC_FIXTURE, data_available_at=f.data_available_at, provenance=f.provenance, commit_sha=f.commit_sha,
    )  # fmt: skip
    session.add(row)
    session.flush()
    return row


def record_not_yet_validated(
    session: Session, security_id: str, decision_at: datetime, horizon_months: int, *, generated_at: datetime, model_id: str, model_version: str, feature_set_version: str,
    data_quality: dict[str, Any] | None = None, provenance: dict[str, Any] | None = None, data_available_at: datetime | None = None, commit_sha: str | None = None,
) -> PredictionSnapshot:  # fmt: skip
    """The ONLY product writer: a snapshot that states «no validated model», every predictive field NULL."""
    f = PredictionFields(
        security_id, decision_at, generated_at, horizon_months, model_id, model_version, feature_set_version, data_quality=data_quality or {},
        warnings=["NOT_YET_VALIDATED: no validated model exists; no prediction is made"], data_available_at=data_available_at, provenance=provenance or {}, commit_sha=commit_sha,
    )  # fmt: skip
    return write_snapshot(session, f, NOT_YET_VALIDATED)
