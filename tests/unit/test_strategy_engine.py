# ruff: noqa: E501
"""Strategy Engine (ADR-0039): pure rule evaluation, versioning, disabled families. SYNTHETIC inputs only."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from pitquant.core.errors import ImmutableRecordError
from pitquant.strategy.engine import evaluate_strategy, prediction_usable
from pitquant.strategy.spec import (
    PREDICTION_FAMILIES,
    StrategyError,
    StrategySpec,
    get_strategy,
    new_version,
    preset_buy_and_hold,
    preset_hybrid,
    preset_prediction_only,
    preset_trade_plan_only,
    rule,
    save_strategy,
    status_for,
    validate_spec,
)


def inputs(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "prediction_status": "SYNTHETIC_FIXTURE", "prediction_available": True, "p_outperform": 0.72, "expected_excess_return": 0.08, "prediction_drop_from_entry": None, "trade_plan_available": True,
        "trade_plan_risk_reward_1": 1.8, "data_quality_ok": True, "risk_regime_ok": True, "holding_sessions": 3,
    }  # fmt: skip
    base.update(over)
    return base


# ───────────────────────────────────────────── ENTER / HOLD / EXIT / NO_ACTION
def test_trade_plan_only_enters_when_every_gate_passes_and_records_the_audit() -> None:
    r = evaluate_strategy(preset_trade_plan_only(), inputs(), in_position=False)
    assert r.decision == "ENTER" and r.exit_reason is None
    assert (
        r.rules_passed == ["plan_available", "quality_gate", "risk_gate_rr1"]
        and r.rules_failed == []
    )
    assert [e["observed"] for e in r.rules_evaluated] == [True, True, 1.8] and all(
        e["passed"] for e in r.rules_evaluated
    )
    assert (
        r.rule_inputs["trade_plan_risk_reward_1"] == 1.8
    )  # the inputs are stored with the decision


def test_a_failed_gate_means_no_action_and_names_the_failed_rule() -> None:
    r = evaluate_strategy(
        preset_trade_plan_only(), inputs(trade_plan_risk_reward_1=0.7), in_position=False
    )
    assert (
        r.decision == "NO_ACTION"
        and r.rules_failed == ["risk_gate_rr1"]
        and "plan_available" in r.rules_passed
    )


def test_a_missing_input_fails_the_rule_it_never_passes_by_default() -> None:
    r = evaluate_strategy(
        preset_trade_plan_only(), inputs(trade_plan_risk_reward_1=None), in_position=False
    )
    assert r.decision == "NO_ACTION" and "risk_gate_rr1" in r.rules_failed


def test_in_position_without_an_exit_rule_holds() -> None:
    assert (
        evaluate_strategy(preset_trade_plan_only(), inputs(), in_position=True).decision == "HOLD"
    )


def test_max_positions_blocks_a_new_entry() -> None:
    s = preset_trade_plan_only()
    s.max_positions = 2
    r = evaluate_strategy(s, inputs(), in_position=False, positions_open=2)
    assert r.decision == "NO_ACTION" and "MAX_POSITIONS" in r.rules_failed


# ───────────────────────────────────────────── prediction families: disabled until a usable prediction exists
@pytest.mark.parametrize("preset", [preset_prediction_only, preset_hybrid])
def test_prediction_strategies_never_act_on_an_unvalidated_or_missing_prediction(preset) -> None:  # type: ignore[no-untyped-def]
    s = preset()
    for status, avail in (("NOT_YET_VALIDATED", False), (None, False), ("NOT_YET_VALIDATED", True)):
        r = evaluate_strategy(
            s, inputs(prediction_status=status, prediction_available=avail), in_position=False
        )
        assert r.decision == "NO_ACTION" and "PREDICTION_NOT_VALIDATED" in r.rules_failed
    assert (
        evaluate_strategy(
            s, inputs(prediction_status=None, prediction_available=False), in_position=True
        ).decision
        == "HOLD"
    )  # a missing prediction never closes a position


def test_a_synthetic_fixture_prediction_is_usable_only_when_the_run_allows_it() -> None:
    s = preset_prediction_only()
    assert (
        evaluate_strategy(s, inputs(), in_position=False).decision == "NO_ACTION"
    )  # a real run: fixture is not a validated prediction
    assert (
        evaluate_strategy(s, inputs(), in_position=False, allow_synthetic=True).decision == "ENTER"
    )
    assert (
        prediction_usable("SYNTHETIC_FIXTURE", True, False) is False
        and prediction_usable("SYNTHETIC_FIXTURE", True, True) is True
        and prediction_usable("VALIDATED", True, False) is True
    )


def test_prediction_only_entry_thresholds_are_labelled_unvalidated_parameters() -> None:
    s = preset_prediction_only()
    numeric = [
        r
        for r in s.entry_rules + s.exit_rules
        if isinstance(r["value"], int | float) and not isinstance(r["value"], bool)
    ]
    assert numeric and all(r["label"] == "UNVALIDATED_STRATEGY_PARAMETER" for r in numeric)
    low = evaluate_strategy(s, inputs(p_outperform=0.60), in_position=False, allow_synthetic=True)
    assert (
        low.decision == "NO_ACTION"
        and "p_entry" in low.rules_failed
        and "er_entry" in low.rules_passed
    )


def test_prediction_deterioration_exits_with_its_reason() -> None:
    s = preset_prediction_only()
    r = evaluate_strategy(
        s,
        inputs(p_outperform=0.48, prediction_drop_from_entry=0.24),
        in_position=True,
        allow_synthetic=True,
    )
    assert r.decision == "EXIT" and r.exit_reason == "PREDICTION_DETERIORATION"
    assert set(r.rules_passed) >= {"PREDICTION_NOT_VALIDATED", "p_exit", "p_drop"}


def test_the_drop_from_entry_rule_exits_even_when_the_level_threshold_is_not_reached() -> None:
    """entry P=0.72, now P=0.52: above the 0.50 level exit, but the version also defines a drop-from-entry rule (>= 0.20)."""
    r = evaluate_strategy(
        preset_prediction_only(),
        inputs(p_outperform=0.52, prediction_drop_from_entry=0.20),
        in_position=True,
        allow_synthetic=True,
    )
    assert (
        r.decision == "EXIT"
        and r.exit_reason == "PREDICTION_DETERIORATION"
        and "p_exit" in r.rules_failed
        and "p_drop" in r.rules_passed
    )


def test_without_a_deterioration_the_position_is_held() -> None:
    r = evaluate_strategy(
        preset_prediction_only(),
        inputs(p_outperform=0.70, prediction_drop_from_entry=0.02),
        in_position=True,
        allow_synthetic=True,
    )
    assert r.decision == "HOLD" and r.exit_reason is None


def test_risk_regime_exit_carries_its_own_reason() -> None:
    r = evaluate_strategy(
        preset_prediction_only(),
        inputs(risk_regime_ok=False),
        in_position=True,
        allow_synthetic=True,
    )
    assert r.decision == "EXIT" and r.exit_reason == "RISK_REGIME"


def test_horizon_exit_rule_is_expressible_in_the_spec() -> None:
    s = preset_trade_plan_only()
    s.exit_rules = [
        rule("max_hold", "holding_sessions", ">=", 20, kind="EXIT", exit_reason="HORIZON_EXPIRY")
    ]
    assert evaluate_strategy(s, inputs(holding_sessions=19), in_position=True).decision == "HOLD"
    r = evaluate_strategy(s, inputs(holding_sessions=20), in_position=True)
    assert r.decision == "EXIT" and r.exit_reason == "HORIZON_EXPIRY"


def test_buy_and_hold_enters_once_and_holds() -> None:
    s = preset_buy_and_hold()
    assert (
        evaluate_strategy(s, {}, in_position=False).decision == "ENTER"
        and evaluate_strategy(s, {}, in_position=True).decision == "HOLD"
    )


# ───────────────────────────────────────────── versioning and families
def test_family_status_and_the_disabled_families() -> None:
    assert (
        status_for("TRADE_PLAN_ONLY") == "EXPERIMENTAL" and status_for("BUY_AND_HOLD") == "BASELINE"
    )
    assert all(status_for(f) == "DISABLED_NOT_VALIDATED" for f in PREDICTION_FAMILIES)


def test_validation_rejects_incoherent_specs() -> None:
    with pytest.raises(StrategyError, match="TRADE_PLAN_ONLY"):
        validate_spec(
            StrategySpec(
                "x", "TRADE_PLAN_ONLY", "x", None, {}, [rule("a", "p_outperform", ">=", 0.6)]
            )
        )
    with pytest.raises(StrategyError, match="horizon"):
        validate_spec(
            StrategySpec(
                "x", "PREDICTION_ONLY", "x", None, {}, [rule("a", "p_outperform", ">=", 0.6)]
            )
        )
    with pytest.raises(StrategyError, match="entry rule on the prediction"):
        validate_spec(
            StrategySpec(
                "x", "PREDICTION_ONLY", "x", 6, {}, [rule("a", "data_quality_ok", "==", True)]
            )
        )
    with pytest.raises(StrategyError, match="unknown rule"):
        validate_spec(
            StrategySpec("x", "TRADE_PLAN_ONLY", "x", None, {}, [rule("a", "astrology", ">=", 1)])
        )
    with pytest.raises(StrategyError, match="unknown exit_reason"):
        validate_spec(
            StrategySpec(
                "x",
                "TRADE_PLAN_ONLY",
                "x",
                None,
                {},
                [],
                [rule("a", "holding_sessions", ">=", 1, kind="EXIT", exit_reason="VIBES")],
            )
        )
    s = preset_trade_plan_only()
    s.costs = {"commission_bps": -1, "slippage_bps": 0}
    with pytest.raises(StrategyError, match="costs"):
        validate_spec(s)


def test_editing_a_strategy_creates_a_new_version_and_the_old_one_is_untouched(
    session: Session,
) -> None:
    v1 = save_strategy(session, preset_trade_plan_only(), "tester")
    assert (v1.strategy_version, v1.status, v1.parent_version) == (1, "EXPERIMENTAL", None)
    rules = [
        rule("plan_available", "trade_plan_available", "==", True, kind="GATE"),
        rule("risk_gate_rr1", "trade_plan_risk_reward_1", ">=", 1.5, kind="GATE"),
    ]
    v2 = new_version(
        session, "TRADE_PLAN_ONLY_V0", {"entry_rules": rules, "max_positions": 3}, "tester"
    )
    assert (v2.strategy_version, v2.parent_version, v2.max_positions) == (
        2,
        1,
        3,
    ) and v2.spec_hash != v1.spec_hash
    old = get_strategy(session, "TRADE_PLAN_ONLY_V0", 1)
    assert (
        old.max_positions == 5
        and len(old.entry_rules) == 3
        and get_strategy(session, "TRADE_PLAN_ONLY_V0").strategy_version == 2
    )


def test_a_saved_version_cannot_be_edited_in_place(session: Session) -> None:
    v1 = save_strategy(session, preset_trade_plan_only("EDIT_GUARD"), "tester")
    sp = session.begin_nested()
    v1.max_positions = 99
    with pytest.raises(ImmutableRecordError):
        session.flush()
    sp.rollback()
    session.refresh(v1)
    assert v1.max_positions == 5


def test_family_and_id_cannot_change_between_versions(session: Session) -> None:
    save_strategy(session, preset_trade_plan_only("FAM"), "tester")
    with pytest.raises(StrategyError, match="cannot change"):
        new_version(session, "FAM", {"family": "HYBRID"}, "tester")
    with pytest.raises(StrategyError, match="unknown strategy field"):
        new_version(session, "FAM", {"astrology": 1}, "tester")


def test_costs_default_to_zero_and_the_contract_carries_them(session: Session) -> None:
    v = save_strategy(session, preset_trade_plan_only("COSTS"), "tester")
    assert v.costs == {"commission_bps": 0.0, "slippage_bps": 0.0}
    v2 = new_version(
        session, "COSTS", {"costs": {"commission_bps": 1.0, "slippage_bps": 2.5}}, "tester"
    )
    assert v2.costs["slippage_bps"] == 2.5
