# ruff: noqa: E501
"""Pure rule evaluation (ADR-0039): inputs + strategy spec ⇒ ENTER / HOLD / EXIT / NO_ACTION, with the full audit of which rules ran, passed and failed.

* A prediction-based strategy acts ONLY on a usable prediction: ``VALIDATED`` (impossible in this build) or, when the run explicitly allows it (SYNTHETIC runs),
  ``SYNTHETIC_FIXTURE``. A ``NOT_YET_VALIDATED`` snapshot or no snapshot ⇒ ``NO_ACTION`` with the failed rule ``PREDICTION_NOT_VALIDATED`` (never a guess).
* Exits by prediction deterioration are defined by the strategy VERSION (``p_outperform <= x``, ``expected_excess_return <= x``, ``prediction_drop_from_entry >= x``).
* The engine neither creates simulations nor reads data: callers pass the inputs. Stop, target, invalidation and horizon are evaluated by the Simulation Lab engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pitquant.strategy.spec import OPS, PREDICTION_FAMILIES, PREDICTION_METRICS, StrategySpec


@dataclass
class DecisionResult:
    decision: str
    exit_reason: str | None = None
    rule_inputs: dict[str, Any] = field(default_factory=dict)
    rules_evaluated: list[dict[str, Any]] = field(default_factory=list)
    rules_passed: list[str] = field(default_factory=list)
    rules_failed: list[str] = field(default_factory=list)


def prediction_usable(status: str | None, available: bool, allow_synthetic: bool) -> bool:
    return bool(available) and (
        status == "VALIDATED" or (allow_synthetic and status == "SYNTHETIC_FIXTURE")
    )


def _eval(r: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    obs = inputs.get(r["metric"])
    passed = False if obs is None else bool(OPS[r["op"]](obs, r["value"]))
    return {
        "id": r["id"],
        "kind": r["kind"],
        "metric": r["metric"],
        "op": r["op"],
        "value": r["value"],
        "observed": obs,
        "passed": passed,
        "label": r.get("label"),
        "exit_reason": r.get("exit_reason"),
    }


def evaluate_strategy(
    spec: StrategySpec,
    inputs: dict[str, Any],
    *,
    in_position: bool,
    allow_synthetic: bool = False,
    positions_open: int = 0,
) -> DecisionResult:
    res = DecisionResult("NO_ACTION", rule_inputs=dict(inputs))

    def record(ev: dict[str, Any]) -> None:
        res.rules_evaluated.append(ev)
        (res.rules_passed if ev["passed"] else res.rules_failed).append(ev["id"])

    if spec.family == "BUY_AND_HOLD":
        res.decision = "HOLD" if in_position else "ENTER"
        record(
            {
                "id": "BUY_AND_HOLD",
                "kind": "STRUCTURAL",
                "metric": "in_position",
                "op": "==",
                "value": False,
                "observed": in_position,
                "passed": not in_position,
                "label": "STRUCTURAL",
                "exit_reason": None,
            }
        )
        return res
    uses_prediction = spec.family in PREDICTION_FAMILIES
    usable = prediction_usable(
        inputs.get("prediction_status"), bool(inputs.get("prediction_available")), allow_synthetic
    )
    if uses_prediction:
        record(
            {
                "id": "PREDICTION_NOT_VALIDATED",
                "kind": "GATE",
                "metric": "prediction_usable",
                "op": "==",
                "value": True,
                "observed": usable,
                "passed": usable,
                "label": "STRUCTURAL",
                "exit_reason": None,
            }
        )
        if not usable:
            res.decision = (
                "HOLD" if in_position else "NO_ACTION"
            )  # a missing / unvalidated prediction never opens or closes a position
            return res
    if in_position:
        res.decision = "HOLD"
        for r in spec.exit_rules:
            if r["metric"] in PREDICTION_METRICS and not usable:
                continue
            ev = _eval(r, inputs)
            record(ev)
            if ev["passed"] and res.decision == "HOLD":
                res.decision, res.exit_reason = (
                    "EXIT",
                    r.get("exit_reason") or "PREDICTION_DETERIORATION",
                )
        return res
    ok = True
    for r in spec.entry_rules:
        ev = _eval(r, inputs)
        record(ev)
        ok = ok and ev["passed"]
    if ok and positions_open >= spec.max_positions:
        record(
            {
                "id": "MAX_POSITIONS",
                "kind": "GATE",
                "metric": "positions_open",
                "op": "<",
                "value": spec.max_positions,
                "observed": positions_open,
                "passed": False,
                "label": "STRUCTURAL",
                "exit_reason": None,
            }
        )
        ok = False
    res.decision = "ENTER" if ok and spec.entry_rules else "NO_ACTION"
    return res
