# ruff: noqa: E501
"""Prediction contract + Strategy Engine tables (ADR-0038 / ADR-0039). Imported at the end of ``models`` so the metadata is complete.

Relation with the older tables (see ADR-0038):
* ``predictions`` / ``live_predictions`` (signal BUY/HOLD/SELL, requires a model_versions row) are LEGACY and untouched: ``PredictionSnapshot`` has NO signal.
* ``research_predictions`` (provenance of a fold prediction, needs an experiment + feature snapshot) is untouched: a forward/synthetic snapshot has neither.
* the label of a resolved prediction stays in ``realized_outcomes`` (label engine); ``prediction_outcomes`` is a thin link that adds the prediction error.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy import false as sa_false
from sqlalchemy.orm import Mapped, mapped_column

from pitquant.core.timeutils import utc_now
from pitquant.db.base import Base, UTCDateTime
from pitquant.db.models import ID, new_id

PREDICTION_STATUSES = (
    "NOT_YET_VALIDATED",
    "SYNTHETIC_FIXTURE",
)  # nothing in this build can write VALIDATED


class PredictionSnapshot(Base):
    """A model output for (security, decision_at, horizon). NO BUY/HOLD/SELL. While ``NOT_YET_VALIDATED`` every predictive field is NULL (CHECK).
    ``SYNTHETIC_FIXTURE`` rows exist only for tests/E2E and are always ``is_synthetic``. Append-only: a new model version = a new row."""

    __tablename__ = "prediction_snapshots"

    prediction_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.security_id"), index=True)
    decision_at: Mapped[datetime] = mapped_column(UTCDateTime)
    generated_at: Mapped[datetime] = mapped_column(UTCDateTime)
    horizon_months: Mapped[int] = mapped_column(Integer)
    model_id: Mapped[str] = mapped_column(String(80))
    model_version: Mapped[str] = mapped_column(String(80))
    feature_set_version: Mapped[str] = mapped_column(String(80))
    dataset_version: Mapped[str | None] = mapped_column(String(80))
    expected_excess_return: Mapped[float | None] = mapped_column(Float)
    p_outperform: Mapped[float | None] = mapped_column(Float)
    return_quantile_10: Mapped[float | None] = mapped_column(Float)
    return_quantile_25: Mapped[float | None] = mapped_column(Float)
    return_quantile_50: Mapped[float | None] = mapped_column(Float)
    return_quantile_75: Mapped[float | None] = mapped_column(Float)
    return_quantile_90: Mapped[float | None] = mapped_column(Float)
    uncertainty: Mapped[dict[str, Any] | None] = mapped_column(
        JSON(none_as_null=True)
    )  # SQL NULL, not JSON 'null' (the CHECK needs it)
    benchmark: Mapped[str] = mapped_column(String(60))
    data_quality: Mapped[dict[str, Any]] = mapped_column(JSON)
    feature_contributions: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    warnings: Mapped[list[str]] = mapped_column(JSON)
    prediction_status: Mapped[str] = mapped_column(String(24), default="NOT_YET_VALIDATED")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_false())
    data_available_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime
    )  # latest available_at among the inputs (<= decision_at)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON)
    commit_sha: Mapped[str | None] = mapped_column(String(48))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)

    __table_args__ = (
        CheckConstraint("decision_at <= generated_at", name="decision_before_generation"),
        CheckConstraint("horizon_months IN (6, 12)", name="horizon_values"),
        CheckConstraint(
            "prediction_status IN ('NOT_YET_VALIDATED','SYNTHETIC_FIXTURE')", name="status_values"
        ),
        CheckConstraint(
            "(prediction_status = 'SYNTHETIC_FIXTURE') = is_synthetic",
            name="synthetic_iff_fixture_status",
        ),
        CheckConstraint(
            "data_available_at IS NULL OR data_available_at <= decision_at",
            name="inputs_known_at_decision",
        ),
        CheckConstraint(
            "p_outperform IS NULL OR (p_outperform >= 0 AND p_outperform <= 1)", name="p_range"
        ),
        CheckConstraint(
            "prediction_status <> 'NOT_YET_VALIDATED' OR (expected_excess_return IS NULL AND p_outperform IS NULL AND return_quantile_10 IS NULL AND return_quantile_25 IS NULL "
            "AND return_quantile_50 IS NULL AND return_quantile_75 IS NULL AND return_quantile_90 IS NULL AND uncertainty IS NULL AND feature_contributions IS NULL)",
            name="no_invented_predictions",
        ),
        Index("ix_prediction_snapshot_lookup", "security_id", "decision_at", "horizon_months"),
    )


class PredictionOutcome(Base):
    """What actually happened for a prediction (thin row; the label itself lives in ``realized_outcomes``). Append-only: PENDING = no row yet."""

    __tablename__ = "prediction_outcomes"

    outcome_row_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    prediction_id: Mapped[str] = mapped_column(
        ForeignKey("prediction_snapshots.prediction_id"), index=True, unique=True
    )
    realized_outcome_id: Mapped[str | None] = mapped_column(
        ForeignKey("realized_outcomes.outcome_id")
    )
    source: Mapped[str] = mapped_column(String(24))  # LABEL_ENGINE | SYNTHETIC_FIXTURE
    resolved_at: Mapped[datetime] = mapped_column(UTCDateTime)
    actual_return: Mapped[float | None] = mapped_column(Float)
    benchmark_return: Mapped[float | None] = mapped_column(Float)
    actual_excess_return: Mapped[float | None] = mapped_column(Float)
    actual_outperform: Mapped[bool | None] = mapped_column(Boolean)
    predicted_excess_return: Mapped[float | None] = mapped_column(Float)
    prediction_error: Mapped[float | None] = mapped_column(Float)  # actual - predicted
    predicted_outperform: Mapped[bool | None] = mapped_column(Boolean)
    classification_correct: Mapped[bool | None] = mapped_column(Boolean)
    direction_correct: Mapped[bool | None] = mapped_column(Boolean)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_false())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)


class StrategyDefinition(Base):
    """A versioned strategy spec. Editing = a NEW version (append-only). Parameters are experimental (UNVALIDATED_STRATEGY_PARAMETER)."""

    __tablename__ = "strategy_definitions"

    strategy_row_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    strategy_id: Mapped[str] = mapped_column(String(80), index=True)
    strategy_version: Mapped[int] = mapped_column(Integer)
    family: Mapped[str] = mapped_column(
        String(20)
    )  # TRADE_PLAN_ONLY | PREDICTION_ONLY | HYBRID | BUY_AND_HOLD
    name: Mapped[str] = mapped_column(String(120))
    prediction_horizon_months: Mapped[int | None] = mapped_column(Integer)
    prediction_model_requirement: Mapped[dict[str, Any]] = mapped_column(JSON)
    entry_rules: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    exit_rules: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    risk_rules: Mapped[dict[str, Any]] = mapped_column(JSON)
    trade_plan_rules: Mapped[dict[str, Any]] = mapped_column(JSON)
    rebalance_frequency: Mapped[str] = mapped_column(String(20))
    max_positions: Mapped[int] = mapped_column(Integer)
    position_sizing: Mapped[dict[str, Any]] = mapped_column(JSON)
    costs: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(
        String(28)
    )  # EXPERIMENTAL | DISABLED_NOT_VALIDATED | BASELINE
    parent_version: Mapped[int | None] = mapped_column(Integer)
    spec_hash: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)

    __table_args__ = (
        UniqueConstraint("strategy_id", "strategy_version", name="uq_strategy_version"),
        CheckConstraint(
            "family IN ('TRADE_PLAN_ONLY','PREDICTION_ONLY','HYBRID','BUY_AND_HOLD')",
            name="family_values",
        ),
        CheckConstraint("max_positions >= 1", name="max_positions_positive"),
    )


class StrategyRun(Base):
    """One test run of an EXACT strategy version. Immutable; its lifecycle lives in ``strategy_run_events``. ``activated_at`` (FORWARD_PAPER) is
    server time and is never taken from a request."""

    __tablename__ = "strategy_runs"

    run_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    run_kind: Mapped[str] = mapped_column(String(14))  # HISTORICAL | FORWARD_PAPER | SYNTHETIC
    strategy_row_id: Mapped[str] = mapped_column(
        ForeignKey("strategy_definitions.strategy_row_id"), index=True
    )
    strategy_id: Mapped[str] = mapped_column(String(80))
    strategy_version: Mapped[int] = mapped_column(Integer)
    universe: Mapped[list[str]] = mapped_column(JSON)
    activated_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    dataset_version: Mapped[str | None] = mapped_column(String(80))
    model_id: Mapped[str | None] = mapped_column(String(80))
    model_version: Mapped[str | None] = mapped_column(String(80))
    simulation_engine_version: Mapped[str] = mapped_column(String(20))
    commit_sha: Mapped[str] = mapped_column(String(48))
    readiness: Mapped[dict[str, Any]] = mapped_column(
        JSON
    )  # the data gates at creation (evaluated ONCE per run)
    blocked_reasons: Mapped[list[str]] = mapped_column(JSON)
    params: Mapped[dict[str, Any]] = mapped_column(JSON)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_false())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)

    __table_args__ = (
        CheckConstraint(
            "run_kind IN ('HISTORICAL','FORWARD_PAPER','SYNTHETIC')", name="run_kind_values"
        ),
    )


class StrategyRunEvent(Base):
    __tablename__ = "strategy_run_events"

    event_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("strategy_runs.run_id"), index=True)
    event_type: Mapped[str] = mapped_column(
        String(20)
    )  # CREATED | BLOCKED | ACTIVATED | TICK | COMPLETED | STOPPED
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)


class StrategyDecision(Base):
    """The immutable record of ONE rule evaluation: its inputs, which rules ran / passed / failed, and the decision."""

    __tablename__ = "strategy_decisions"

    decision_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("strategy_runs.run_id"), index=True)
    strategy_id: Mapped[str] = mapped_column(String(80))
    strategy_version: Mapped[int] = mapped_column(Integer)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.security_id"), index=True)
    decision_at: Mapped[datetime] = mapped_column(UTCDateTime)
    prediction_snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("prediction_snapshots.prediction_id")
    )
    trade_plan_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    trade_plan_hash: Mapped[str | None] = mapped_column(String(64))
    rule_inputs: Mapped[dict[str, Any]] = mapped_column(JSON)
    rules_evaluated: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    rules_passed: Mapped[list[str]] = mapped_column(JSON)
    rules_failed: Mapped[list[str]] = mapped_column(JSON)
    decision: Mapped[str] = mapped_column(String(10))  # ENTER | HOLD | EXIT | NO_ACTION
    exit_reason: Mapped[str | None] = mapped_column(String(30))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_false())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)

    __table_args__ = (
        CheckConstraint("decision IN ('ENTER','HOLD','EXIT','NO_ACTION')", name="decision_values"),
    )


class StrategySimulationLink(Base):
    """decision -> paper trade. ``simulations`` is untouched (plus ``is_synthetic``): the authority to create an AUTO_PAPER trade lives here."""

    __tablename__ = "strategy_simulation_links"

    link_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    decision_id: Mapped[str] = mapped_column(
        ForeignKey("strategy_decisions.decision_id"), index=True
    )
    simulation_id: Mapped[str] = mapped_column(ForeignKey("simulations.simulation_id"), index=True)
    role: Mapped[str] = mapped_column(String(8))  # ENTRY | EXIT
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)


class StrategyRunResult(Base):
    """A materialised evaluation of a run (append-only: a re-evaluation is a new row). Carries the hash of the prediction series it consumed."""

    __tablename__ = "strategy_run_results"

    result_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("strategy_runs.run_id"), index=True)
    evaluated_at: Mapped[datetime] = mapped_column(UTCDateTime)
    prediction_series_hash: Mapped[str] = mapped_column(String(64))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON)
    flags: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
