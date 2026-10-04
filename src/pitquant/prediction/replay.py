# ruff: noqa: E501
"""Prediction Replay (ADR-0038): for (security, historical decision date, horizon) reproduce EXACTLY what was knowable at T.

1. features: the Feature Engine at T (PIT context: bars before the decision session, filings with ``available_at <= decision_at``) — ``max_available_at`` is checked;
2. model: only a frozen model whose every training label was known at T (``model_eligible_at``); none today;
3. prediction: never invented — without an eligible validated model the replay says ``NOT_YET_VALIDATED`` and every predictive field is NULL.

A prediction produced here by an injected ``predictor`` (tests only) is returned in memory, labelled ``UNVALIDATED_MODEL_OUTPUT``, and can NOT be persisted:
``VALIDATED`` does not exist in this build. Nothing in this module reads data after the decision date, and the sealed holdout is refused.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from pitquant.analyzer.market import benchmark_security
from pitquant.config.settings import Settings
from pitquant.core.errors import HoldoutAccessError, PITQuantError
from pitquant.core.timeutils import utc_now
from pitquant.db.models_lab import PredictionSnapshot
from pitquant.features.v0.engine import FEATURE_VERSION, build_snapshot
from pitquant.prediction.contract import record_not_yet_validated
from pitquant.prediction.models import MODEL_SPECS, TrainedModelRecord, model_eligible_at
from pitquant.research.registry import commit_sha

Predictor = Callable[[TrainedModelRecord, dict[str, float | None]], dict[str, Any]]


@dataclass
class PredictionReplay:
    security_id: str
    decision_at: datetime
    horizon_months: int
    status: str  # NOT_YET_VALIDATED | UNVALIDATED_MODEL_OUTPUT
    features: dict[str, Any]
    model: dict[str, Any] | None
    prediction: dict[str, Any] | None
    reasons: list[str] = field(default_factory=list)
    lookahead_checks: dict[str, bool] = field(default_factory=dict)
    snapshot: PredictionSnapshot | None = None


def replay_prediction(
    session: Session,
    settings: Settings,
    security_id: str,
    decision_session: date,
    horizon_months: int,
    *,
    models: Sequence[TrainedModelRecord] = (),
    predictor: Predictor | None = None,
    persist: bool = False,
    generated_at: datetime | None = None,
) -> PredictionReplay:
    ho = settings.validation.final_holdout
    if ho.start <= decision_session <= ho.end:
        raise HoldoutAccessError(
            f"the decision date {decision_session} is inside the sealed holdout {ho.start}..{ho.end}"
        )
    bench = benchmark_security(session)
    fs = build_snapshot(
        session, security_id, decision_session, benchmark_security_id=bench[0] if bench else None
    )
    decision_at = fs.as_of
    checks = {
        "features_available_at_le_decision_at": fs.max_available_at is None
        or fs.max_available_at <= decision_at
    }
    if not checks["features_available_at_le_decision_at"]:
        raise PITQuantError("look-ahead: a feature input was available after the decision date")
    features = {
        "feature_version": fs.feature_version, "data_version": fs.data_version, "content_hash": fs.content_hash, "n_features": len(fs.features),
        "n_missing": sum(1 for v in fs.features.values() if v is None), "max_available_at": fs.max_available_at.isoformat() if fs.max_available_at else None, "is_synthetic": fs.is_synthetic,
    }  # fmt: skip
    spec = MODEL_SPECS[f"EQUITY_{horizon_months}M_BASELINE"]
    reasons: list[str] = []
    eligible: list[TrainedModelRecord] = []
    for m in models:
        ok, why = model_eligible_at(m, decision_at)
        if m.horizon_months == horizon_months and ok:
            eligible.append(m)
        else:
            reasons.append(
                f"{m.model_id} {m.model_version}: {why if m.horizon_months == horizon_months else 'other horizon'}"
            )
    checks["model_labels_known_at_decision"] = True  # only eligible models are ever used
    chosen = max(eligible, key=lambda m: m.label_known_by) if eligible else None
    gen = generated_at or utc_now()
    if chosen is None or predictor is None:
        reasons.append(f"no eligible validated model for {spec.model_id}: nothing is predicted")
        rep = PredictionReplay(
            security_id,
            decision_at,
            horizon_months,
            "NOT_YET_VALIDATED",
            features,
            None,
            None,
            reasons,
            checks,
        )
        if persist:
            rep.snapshot = record_not_yet_validated(
                session, security_id, decision_at, horizon_months, generated_at=max(gen, decision_at), model_id=spec.model_id, model_version="NOT_TRAINED", feature_set_version=f"{FEATURE_VERSION}:{len(fs.features)}f",
                provenance={"replay": True, "features": features, "reasons": reasons}, data_available_at=fs.max_available_at, commit_sha=commit_sha(),
            )  # fmt: skip
        return rep
    if persist:
        raise PITQuantError(
            "a model output cannot be persisted: no model is validated in this build (VALIDATED does not exist)"
        )
    out = predictor(chosen, dict(fs.features))
    return PredictionReplay(
        security_id, decision_at, horizon_months, "UNVALIDATED_MODEL_OUTPUT", features, {"model_id": chosen.model_id, "model_version": chosen.model_version, "label_known_by": chosen.label_known_by.isoformat()}, out, reasons, checks
    )  # fmt: skip
