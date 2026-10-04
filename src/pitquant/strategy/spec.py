# ruff: noqa: E501
"""Strategy definitions (ADR-0039). A strategy answers «what would we DO given these predictions / this trade plan?» and never mixes with the Prediction Engine.

* Versioned and append-only: any edit is a NEW ``strategy_version``; a version that already has runs/decisions can never change.
* Families: TRADE_PLAN_ONLY (works without a model), PREDICTION_ONLY and HYBRID (DISABLED_NOT_VALIDATED until a validated model exists), BUY_AND_HOLD (baseline).
* Every threshold is an experimental configuration labelled ``UNVALIDATED_STRATEGY_PARAMETER``: nothing here is truth, and nothing is optimised automatically.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pitquant.core.errors import PITQuantError
from pitquant.core.hashing import content_hash
from pitquant.db.models_lab import StrategyDecision, StrategyDefinition, StrategyRun

FAMILIES = ("TRADE_PLAN_ONLY", "PREDICTION_ONLY", "HYBRID", "BUY_AND_HOLD")
PREDICTION_FAMILIES = ("PREDICTION_ONLY", "HYBRID")
UNVALIDATED = "UNVALIDATED_STRATEGY_PARAMETER"
DECISIONS = ("ENTER", "HOLD", "EXIT", "NO_ACTION")
EXIT_REASONS = (
    "STOP",
    "TARGET",
    "THESIS_INVALIDATION",
    "PREDICTION_DETERIORATION",
    "HORIZON_EXPIRY",
    "RISK_REGIME",
)
OPS = {">=": operator.ge, "<=": operator.le, ">": operator.gt, "<": operator.lt, "==": operator.eq}
PREDICTION_METRICS = frozenset(
    {
        "p_outperform",
        "expected_excess_return",
        "prediction_drop_from_entry",
        "expected_return_drop_from_entry",
        "prediction_available",
    }
)
METRICS = PREDICTION_METRICS | {
    "trade_plan_available",
    "trade_plan_risk_reward_1",
    "data_quality_ok",
    "risk_regime_ok",
    "holding_sessions",
    "volatility_63d",
}
REBALANCE = ("DAILY", "WEEKLY", "MONTHLY")


class StrategyError(PITQuantError):
    pass


def rule(
    rule_id: str,
    metric: str,
    op: str,
    value: Any,
    *,
    kind: str = "ENTRY",
    exit_reason: str | None = None,
) -> dict[str, Any]:
    r = {
        "id": rule_id,
        "kind": kind,
        "metric": metric,
        "op": op,
        "value": value,
        "label": UNVALIDATED
        if isinstance(value, int | float) and not isinstance(value, bool)
        else "STRUCTURAL",
    }
    if exit_reason:
        r["exit_reason"] = exit_reason
    return r


@dataclass
class StrategySpec:
    strategy_id: str
    family: str
    name: str
    prediction_horizon_months: int | None = None
    prediction_model_requirement: dict[str, Any] = field(default_factory=dict)
    entry_rules: list[dict[str, Any]] = field(default_factory=list)
    exit_rules: list[dict[str, Any]] = field(default_factory=list)
    risk_rules: dict[str, Any] = field(default_factory=dict)
    trade_plan_rules: dict[str, Any] = field(default_factory=dict)
    rebalance_frequency: str = "DAILY"
    max_positions: int = 5
    position_sizing: dict[str, Any] = field(
        default_factory=lambda: {"mode": "RISK_BASED", "capital": 100_000.0, "risk_pct": 1.0}
    )
    costs: dict[str, Any] = field(
        default_factory=lambda: {"commission_bps": 0.0, "slippage_bps": 0.0}
    )

    def canonical(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id, "family": self.family, "prediction_horizon_months": self.prediction_horizon_months, "prediction_model_requirement": self.prediction_model_requirement,
            "entry_rules": self.entry_rules, "exit_rules": self.exit_rules, "risk_rules": self.risk_rules, "trade_plan_rules": self.trade_plan_rules, "rebalance_frequency": self.rebalance_frequency,
            "max_positions": self.max_positions, "position_sizing": self.position_sizing, "costs": self.costs,
        }  # fmt: skip


def validate_spec(s: StrategySpec) -> None:
    if s.family not in FAMILIES:
        raise StrategyError(f"family must be one of {FAMILIES}")
    if s.rebalance_frequency not in REBALANCE:
        raise StrategyError(f"rebalance_frequency must be one of {REBALANCE}")
    if s.max_positions < 1:
        raise StrategyError("max_positions must be at least 1")
    if s.family in PREDICTION_FAMILIES and s.prediction_horizon_months not in (6, 12):
        raise StrategyError("a prediction-based strategy needs prediction_horizon_months = 6 or 12")
    if s.family == "TRADE_PLAN_ONLY" and s.prediction_horizon_months is not None:
        raise StrategyError("TRADE_PLAN_ONLY does not use a prediction")
    for r in [*s.entry_rules, *s.exit_rules]:
        if r.get("metric") not in METRICS or r.get("op") not in OPS:
            raise StrategyError(f"unknown rule metric/op in {r.get('id')!r}")
        uses_pred = r["metric"] in PREDICTION_METRICS
        if uses_pred and s.family == "TRADE_PLAN_ONLY":
            raise StrategyError(
                f"rule {r['id']!r} uses a prediction but the family is TRADE_PLAN_ONLY"
            )
        if r.get("exit_reason") and r["exit_reason"] not in EXIT_REASONS:
            raise StrategyError(f"unknown exit_reason {r['exit_reason']!r}")
    if s.family == "PREDICTION_ONLY" and not any(
        r["metric"] in PREDICTION_METRICS for r in s.entry_rules
    ):
        raise StrategyError("PREDICTION_ONLY needs an entry rule on the prediction")
    c = s.costs
    if any(float(c.get(k, 0.0)) < 0 for k in ("commission_bps", "slippage_bps")):
        raise StrategyError("costs must be >= 0 bps")


def status_for(family: str) -> str:
    return (
        "DISABLED_NOT_VALIDATED"
        if family in PREDICTION_FAMILIES
        else "BASELINE"
        if family == "BUY_AND_HOLD"
        else "EXPERIMENTAL"
    )


def _next_version(session: Session, strategy_id: str) -> int:
    return (
        int(
            session.scalar(
                select(func.coalesce(func.max(StrategyDefinition.strategy_version), 0)).where(
                    StrategyDefinition.strategy_id == strategy_id
                )
            )
            or 0
        )
        + 1
    )


def save_strategy(
    session: Session, s: StrategySpec, created_by: str, *, parent_version: int | None = None
) -> StrategyDefinition:
    validate_spec(s)
    row = StrategyDefinition(
        strategy_id=s.strategy_id, strategy_version=_next_version(session, s.strategy_id), family=s.family, name=s.name, prediction_horizon_months=s.prediction_horizon_months,
        prediction_model_requirement=s.prediction_model_requirement, entry_rules=s.entry_rules, exit_rules=s.exit_rules, risk_rules=s.risk_rules, trade_plan_rules=s.trade_plan_rules,
        rebalance_frequency=s.rebalance_frequency, max_positions=s.max_positions, position_sizing=s.position_sizing, costs=s.costs, status=status_for(s.family), parent_version=parent_version,
        spec_hash=content_hash(s.canonical()), created_by=created_by,
    )  # fmt: skip
    session.add(row)
    session.flush()
    return row


def spec_of(row: StrategyDefinition) -> StrategySpec:
    return StrategySpec(
        row.strategy_id, row.family, row.name, row.prediction_horizon_months, row.prediction_model_requirement, row.entry_rules, row.exit_rules, row.risk_rules, row.trade_plan_rules,
        row.rebalance_frequency, row.max_positions, row.position_sizing, row.costs,
    )  # fmt: skip


def get_strategy(
    session: Session, strategy_id: str, version: int | None = None
) -> StrategyDefinition:
    q = select(StrategyDefinition).where(StrategyDefinition.strategy_id == strategy_id)
    q = (
        q.where(StrategyDefinition.strategy_version == version)
        if version is not None
        else q.order_by(StrategyDefinition.strategy_version.desc())
    )
    row = session.scalars(q).first()
    if row is None:
        raise StrategyError(f"unknown strategy {strategy_id!r} version {version}")
    return row


def in_use(session: Session, row: StrategyDefinition) -> bool:
    """A version that has runs or decisions is HISTORICAL: it can never be edited (editing creates a new version anyway)."""
    return bool(
        session.scalar(
            select(func.count())
            .select_from(StrategyRun)
            .where(StrategyRun.strategy_row_id == row.strategy_row_id)
        )
    ) or bool(
        session.scalar(
            select(func.count())
            .select_from(StrategyDecision)
            .where(
                StrategyDecision.strategy_id == row.strategy_id,
                StrategyDecision.strategy_version == row.strategy_version,
            )
        )
    )


def new_version(
    session: Session, strategy_id: str, changes: dict[str, Any], created_by: str
) -> StrategyDefinition:
    """The ONLY way to «edit»: copy the latest version with ``changes`` into version+1. The parent is untouched."""
    parent = get_strategy(session, strategy_id)
    base = spec_of(parent)
    forbidden = {"strategy_id", "family"} & set(changes)
    if forbidden:
        raise StrategyError(
            f"{sorted(forbidden)} cannot change between versions: create another strategy"
        )
    for k, v in changes.items():
        if not hasattr(base, k):
            raise StrategyError(f"unknown strategy field {k!r}")
        setattr(base, k, v)
    return save_strategy(session, base, created_by, parent_version=parent.strategy_version)


# ───────────────────────────────────────────── presets (experimental parameters, never truth)
def preset_trade_plan_only(
    strategy_id: str = "TRADE_PLAN_ONLY_V0", min_rr1: float = 1.0
) -> StrategySpec:
    return StrategySpec(
        strategy_id, "TRADE_PLAN_ONLY", "Trade Plan only (entry zone, stop, targets, invalidation)", None, {"requires_prediction": False},
        [rule("plan_available", "trade_plan_available", "==", True, kind="GATE"), rule("quality_gate", "data_quality_ok", "==", True, kind="GATE"), rule("risk_gate_rr1", "trade_plan_risk_reward_1", ">=", min_rr1, kind="GATE")],
        [], {"max_holding_sessions": 20}, {"profile": "BASE"},
    )  # fmt: skip


def preset_prediction_only(
    strategy_id: str = "PREDICTION_ONLY_V0", horizon: int = 6
) -> StrategySpec:
    return StrategySpec(
        strategy_id, "PREDICTION_ONLY", f"Prediction only ({horizon}M)", horizon, {"requires_validated": True, "horizon_months": horizon},
        [rule("p_entry", "p_outperform", ">=", 0.65), rule("er_entry", "expected_excess_return", ">=", 0.05), rule("quality_gate", "data_quality_ok", "==", True, kind="GATE")],
        [rule("p_exit", "p_outperform", "<=", 0.50, kind="EXIT", exit_reason="PREDICTION_DETERIORATION"), rule("p_drop", "prediction_drop_from_entry", ">=", 0.20, kind="EXIT", exit_reason="PREDICTION_DETERIORATION"),
         rule("risk_regime", "risk_regime_ok", "==", False, kind="EXIT", exit_reason="RISK_REGIME")],
        {"catastrophic_stop_pct": 0.25, "target_pct": 2.0, "max_holding_sessions": 126},
        {"note": "no trade plan: a catastrophic stop (UNVALIDATED) and TRACK_TARGETS_ONLY keep the paper trade valid; exits are the prediction and the horizon"},
    )  # fmt: skip


def preset_hybrid(strategy_id: str = "HYBRID_V0", horizon: int = 6) -> StrategySpec:
    return StrategySpec(
        strategy_id, "HYBRID", f"Hybrid ({horizon}M selection, Trade Plan timing and risk)", horizon, {"requires_validated": True, "horizon_months": horizon},
        [rule("p_entry", "p_outperform", ">=", 0.65), rule("plan_available", "trade_plan_available", "==", True, kind="GATE"), rule("quality_gate", "data_quality_ok", "==", True, kind="GATE")],
        [rule("p_exit", "p_outperform", "<=", 0.50, kind="EXIT", exit_reason="PREDICTION_DETERIORATION")], {"max_holding_sessions": 126}, {"profile": "BASE"},
    )  # fmt: skip


def preset_buy_and_hold(strategy_id: str = "BUY_AND_HOLD") -> StrategySpec:
    return StrategySpec(
        strategy_id,
        "BUY_AND_HOLD",
        "Buy and hold (baseline: analytic, never trades)",
        None,
        {"requires_prediction": False},
        [],
        [],
        {},
        {},
    )
