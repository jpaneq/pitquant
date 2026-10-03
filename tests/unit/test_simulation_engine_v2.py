# ruff: noqa: E501
"""Simulation Lab engine v2 (ADR-0036): entry fills, gaps, ambiguity, exit policies, excursions, event log + independent fold.
SYNTHETIC bars. PAPER TRADE, NO REAL MONEY."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from pitquant.simulation.engine import PlanLevels, SimState, evaluate, fold_events

T0 = date(2024, 1, 2)


def bars(rows: list[tuple[str, float, float, float, float]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["d", "open", "high", "low", "close"])
    df.index = [date.fromisoformat(x) for x in df.pop("d")]
    return df


def limit(p: float = 100.0, **kw: object) -> PlanLevels:
    base: dict[str, object] = {
        "stop": 95.0,
        "target_1": 110.0,
        "target_2": 120.0,
        "exit_policy": "TRACK_TARGETS_ONLY",
    }
    base.update(kw)
    return PlanLevels("LIMIT", p, p, **base)  # type: ignore[arg-type]


def zone(lo: float = 98.0, hi: float = 100.0, **kw: object) -> PlanLevels:
    base: dict[str, object] = {
        "stop": 90.0,
        "target_1": 112.0,
        "target_2": 120.0,
        "exit_policy": "TRACK_TARGETS_ONLY",
    }
    base.update(kw)
    return PlanLevels("ENTRY_ZONE", lo, hi, **base)  # type: ignore[arg-type]


def etypes(ev) -> list[str]:  # type: ignore[no-untyped-def]
    return [e["type"] for e in ev.events]


# ───────────────────────────────────────────── explicit limit
def test_limit_open_below_the_limit_fills_at_the_open_favourable_gap() -> None:
    ev = evaluate(limit(), bars([("2024-01-03", 97, 99, 96, 98)]), T0)
    assert ev.entry_price == 97.0 and ev.entry_method == "FAVORABLE_GAP"


def test_limit_touched_intraday_fills_at_the_limit_and_never_at_the_close() -> None:
    ev = evaluate(limit(), bars([("2024-01-03", 103, 104, 99, 102)]), T0)
    assert ev.entry_price == 100.0 and ev.entry_method == "EXPLICIT_LIMIT"


def test_limit_open_exactly_at_the_limit_is_explicit_limit() -> None:
    ev = evaluate(limit(), bars([("2024-01-03", 100, 101, 99, 100)]), T0)
    assert ev.entry_price == 100.0 and ev.entry_method == "EXPLICIT_LIMIT"


def test_limit_not_touched_keeps_waiting() -> None:
    ev = evaluate(limit(), bars([("2024-01-03", 103, 105, 101, 104)]), T0)
    assert ev.state is SimState.WAITING_ENTRY and ev.entry_price is None


# ───────────────────────────────────────────── entry zone
def test_zone_open_inside_the_zone_fills_at_the_open() -> None:
    ev = evaluate(zone(), bars([("2024-01-03", 99, 101, 98.5, 100)]), T0)
    assert (ev.entry_price, ev.entry_method) == (99.0, "OPEN_WITHIN_ZONE")


def test_zone_open_below_the_zone_is_a_favourable_gap_at_the_open() -> None:
    ev = evaluate(zone(), bars([("2024-01-03", 95, 99, 94, 98)]), T0)
    assert (ev.entry_price, ev.entry_method) == (95.0, "FAVORABLE_GAP")


def test_zone_entered_from_above_fills_at_the_zone_high() -> None:
    ev = evaluate(zone(), bars([("2024-01-03", 104, 105, 99, 103)]), T0)
    assert (ev.entry_price, ev.entry_method) == (100.0, "FIRST_ZONE_TOUCH")


def test_zone_never_reached_does_not_fill() -> None:
    ev = evaluate(zone(), bars([("2024-01-03", 104, 105, 101, 103)]), T0)
    assert ev.entry_price is None


def test_market_reference_enters_at_t0_with_the_stored_price_not_a_later_close() -> None:
    plan = PlanLevels(
        "MARKET_REFERENCE", 100.0, 100.0, 95.0, 110.0, exit_policy="TRACK_TARGETS_ONLY"
    )
    ev = evaluate(plan, bars([("2024-01-03", 101, 103, 99, 102)]), T0, reference_price=100.0)
    assert (ev.entry_date, ev.entry_price, ev.entry_method) == (T0, 100.0, "MARKET_REFERENCE")
    assert etypes(ev)[:3] == ["SIMULATION_CREATED", "ENTRY_TRIGGERED", "ENTRY_FILLED"]


# ───────────────────────────────────────────── stops, targets, gaps
def test_stop_gap_fills_at_the_open_and_records_the_method() -> None:
    ev = evaluate(
        limit(), bars([("2024-01-03", 100, 101, 99.5, 100), ("2024-01-04", 90, 92, 88, 91)]), T0
    )
    assert (
        ev.state is SimState.STOPPED
        and ev.exits[0]["method"] == "STOP_GAP"
        and ev.exits[0]["price"] == 90.0
    )
    assert "STOP_GAP" in etypes(ev)


def test_stop_inside_the_bar_fills_at_the_stop() -> None:
    ev = evaluate(
        limit(), bars([("2024-01-03", 100, 101, 99.5, 100), ("2024-01-04", 99, 100, 94, 96)]), T0
    )
    assert ev.exits[0]["method"] == "STOP_LEVEL" and ev.exits[0]["price"] == 95.0


def test_target_gap_fills_at_the_open_under_partial_fractions() -> None:
    plan = limit(exit_policy="PARTIAL_FRACTIONS", exit_fractions=(1.0, 0.0, 0.0), target_2=None)
    ev = evaluate(
        plan, bars([("2024-01-03", 100, 101, 99.5, 100), ("2024-01-04", 112, 114, 111, 113)]), T0
    )
    assert (
        ev.state is SimState.TP1
        and ev.exits[0]["method"] == "TARGET_GAP"
        and ev.exits[0]["price"] == 112.0
    )


# ───────────────────────────────────────────── exit policy
def test_track_targets_only_records_the_touch_but_the_position_stays_complete() -> None:
    ev = evaluate(
        limit(), bars([("2024-01-03", 100, 101, 99.5, 100), ("2024-01-04", 101, 111, 100, 109)]), T0
    )
    assert (
        ev.state is SimState.ENTERED and ev.exits == [] and ev.details["position_remaining"] == 1.0
    )
    assert (
        ev.details["targets_touched"] == [1]
        and "TP1_TOUCHED" in etypes(ev)
        and "PARTIAL_EXIT" not in etypes(ev)
    )
    assert ev.metrics["realized_return"] == pytest.approx(
        0.09
    )  # mark-to-market of the whole position, not a target exit
    assert ev.metrics["mark_to_market_return"] == pytest.approx(0.09)


def test_partial_fractions_register_each_fill_and_the_remaining_position() -> None:
    plan = limit(exit_policy="PARTIAL_FRACTIONS", exit_fractions=(0.25, 0.25, 0.0))
    ev = evaluate(
        plan, bars([("2024-01-03", 100, 101, 99.5, 100), ("2024-01-04", 101, 111, 100, 109)]), T0
    )
    assert ev.state is SimState.PARTIAL_TP and ev.details["position_remaining"] == pytest.approx(
        0.75
    )
    assert [e["payload"]["remaining"] for e in ev.events if e["type"] == "PARTIAL_EXIT"] == [0.75]
    # initial risk 5: realised on 25% at 110 = 0.25*2 = 0.5R, the 75% still open marked at 109 = 0.75*1.8
    assert ev.metrics["realized_r"] == pytest.approx(0.25 * 2 + 0.75 * 1.8)


def test_realized_r_with_partials_uses_the_initial_risk_and_does_not_double_count() -> None:
    plan = limit(exit_policy="PARTIAL_FRACTIONS", exit_fractions=(0.5, 0.5, 0.0))
    rows = [
        ("2024-01-03", 100, 101, 99.5, 100),
        ("2024-01-04", 101, 111, 100, 109),
        ("2024-01-05", 109, 121, 108, 120),
    ]
    ev = evaluate(plan, bars(rows), T0)
    assert ev.state is SimState.TP2 and ev.metrics["realized_r"] == pytest.approx(0.5 * 2 + 0.5 * 4)
    assert sum(x["fraction"] for x in ev.exits) == pytest.approx(1.0)


def test_fraction_validation() -> None:
    with pytest.raises(ValueError, match="sum"):
        limit(exit_policy="PARTIAL_FRACTIONS", exit_fractions=(0.7, 0.5, 0.0)).validate()
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        limit(exit_policy="PARTIAL_FRACTIONS", exit_fractions=(-0.1, 0.5, 0.0)).validate()
    with pytest.raises(ValueError, match="target"):
        limit(
            target_2=None, exit_policy="PARTIAL_FRACTIONS", exit_fractions=(0.2, 0.2, 0.0)
        ).validate()
    with pytest.raises(ValueError, match="only apply"):
        limit(exit_fractions=(0.2, 0.2, 0.0)).validate()  # TRACK_TARGETS_ONLY with fractions


def test_third_target_and_ordering_are_validated() -> None:
    with pytest.raises(ValueError):
        limit(target_3=119.0).validate()
    limit(target_3=130.0).validate()


# ───────────────────────────────────────────── ambiguity
def test_entry_and_stop_in_the_same_bar_is_ambiguous_with_both_readings_kept() -> None:
    ev = evaluate(limit(), bars([("2024-01-03", 103, 104, 94, 100)]), T0)
    assert ev.state is SimState.AMBIGUOUS_INTRABAR
    amb = ev.details["ambiguity"]
    assert (
        amb["kind"] == "ENTRY_AND_EXIT_SAME_BAR"
        and amb["stop_reached"]
        and amb["scenarios"][0]["order"] == "ENTRY_THEN_STOP"
    )


def test_entry_and_target_in_the_same_bar_is_ambiguous() -> None:
    ev = evaluate(limit(), bars([("2024-01-03", 103, 112, 99, 105)]), T0)
    assert ev.state is SimState.AMBIGUOUS_INTRABAR and ev.details["ambiguity"][
        "targets_reached"
    ] == [1]


def test_stop_and_target_in_the_same_bar_under_partial_fractions_is_ambiguous_with_scenarios() -> (
    None
):
    plan = limit(exit_policy="PARTIAL_FRACTIONS", exit_fractions=(0.5, 0.5, 0.0))
    ev = evaluate(
        plan, bars([("2024-01-03", 100, 101, 99.5, 100), ("2024-01-04", 100, 112, 94, 100)]), T0
    )
    assert ev.state is SimState.AMBIGUOUS_INTRABAR
    sc = {s["order"]: s["realized_r"] for s in ev.details["ambiguity"]["scenarios"]}
    assert sc["STOP_FIRST"] == pytest.approx(-1.0) and sc["TARGET_FIRST"] == pytest.approx(
        0.5 * 2 + 0.5 * -1
    )
    assert "AMBIGUOUS_INTRABAR" in etypes(ev) and ev.is_closed


def test_two_targets_and_the_stop_in_one_bar_is_ambiguous() -> None:
    plan = limit(exit_policy="PARTIAL_FRACTIONS", exit_fractions=(0.3, 0.3, 0.0))
    ev = evaluate(
        plan, bars([("2024-01-03", 100, 101, 99.5, 100), ("2024-01-04", 100, 125, 94, 100)]), T0
    )
    assert ev.state is SimState.AMBIGUOUS_INTRABAR and ev.details["ambiguity"]["scenarios"][1][
        "targets"
    ] == [1, 2]


def test_track_only_stop_and_touch_in_one_bar_is_a_stop_with_unknown_touch_order() -> None:
    ev = evaluate(
        limit(), bars([("2024-01-03", 100, 101, 99.5, 100), ("2024-01-04", 100, 112, 94, 100)]), T0
    )
    assert ev.state is SimState.STOPPED and ev.details["touch_order_unknown"]["targets"] == [1]


# ───────────────────────────────────────────── excursions, R
def test_mae_mfe_formulas_and_the_initial_risk_denominator() -> None:
    rows = [
        ("2024-01-03", 100, 101, 99.5, 100),
        ("2024-01-04", 100, 108, 97, 106),
        ("2024-01-05", 106, 107, 98, 99),
    ]
    ev = evaluate(limit(), bars(rows), T0)
    m = ev.metrics
    assert m["mfe_pct"] == pytest.approx(108 / 100 - 1) and m["mae_pct"] == pytest.approx(
        97 / 100 - 1
    )  # MAE is NEGATIVE
    assert m["mfe_r"] == pytest.approx((108 - 100) / 5) and m["mae_r"] == pytest.approx(
        (97 - 100) / 5
    )
    assert m["initial_risk_per_unit"] == 5.0


def test_an_intrabar_entry_does_not_count_the_part_of_the_bar_that_may_precede_it() -> None:
    ev = evaluate(
        limit(), bars([("2024-01-03", 103, 108, 99, 102)]), T0
    )  # entry at 100: the 108 high may have happened BEFORE the entry
    assert ev.metrics["mfe_pct"] == pytest.approx(0.02) and ev.metrics["mae_pct"] == pytest.approx(
        0.0
    )


# ───────────────────────────────────────────── other transitions
def test_invalidation_after_the_entry_closes_at_the_close_and_is_not_a_stop() -> None:
    plan = limit(invalidation=97.0)
    ev = evaluate(
        plan, bars([("2024-01-03", 100, 101, 99.5, 100), ("2024-01-04", 99, 99.5, 96, 96.5)]), T0
    )
    assert (
        ev.state is SimState.INVALIDATED
        and ev.exits[0]["method"] == "INVALIDATION_CLOSE"
        and ev.exits[0]["price"] == 96.5
    )


def test_expiration_with_a_position_records_the_mark_to_market() -> None:
    plan = limit(expiration=date(2024, 1, 10))
    ev = evaluate(
        plan,
        bars(
            [
                ("2024-01-03", 100, 101, 99.5, 100),
                ("2024-01-08", 100, 104, 99, 103),
                ("2024-01-11", 103, 104, 100, 101),
            ]
        ),
        T0,
    )
    assert ev.state is SimState.EXPIRED and ev.details[
        "mark_to_market_return_at_expiration"
    ] == pytest.approx(0.03)


def test_cancellation_only_before_the_entry() -> None:
    ev = evaluate(
        limit(), bars([("2024-01-03", 103, 105, 101, 104)]), T0, cancel_on=date(2024, 1, 3)
    )
    assert ev.state is SimState.CANCELLED and "CANCELLED" in etypes(ev)


def test_observation_events_at_t_plus_1_5_20_60() -> None:
    rows = [(f"2024-02-{d:02d}", 100.0, 101.0, 99.5, 100.0) for d in range(1, 29)]
    ev = evaluate(limit(), bars(rows), T0)
    assert [e["payload"]["horizon"] for e in ev.events if e["type"] == "OBSERVATION_RECORDED"] == [
        "T+1",
        "T+5",
        "T+20",
    ]


# ───────────────────────────────────────────── event log: determinism, prefix stability, independent fold
SCENARIOS = {
    "stop": [("2024-01-03", 100, 101, 99.5, 100), ("2024-01-04", 99, 100, 94, 96)],
    "stop_gap": [("2024-01-03", 100, 101, 99.5, 100), ("2024-01-04", 90, 92, 88, 91)],
    "track_open": [
        ("2024-01-03", 100, 101, 99.5, 100),
        ("2024-01-04", 101, 111, 100, 109),
        ("2024-01-05", 109, 110, 105, 106),
    ],
    "ambiguous": [("2024-01-03", 103, 104, 94, 100)],
    "waiting": [("2024-01-03", 103, 105, 101, 104)],
}


@pytest.mark.parametrize("name", sorted(SCENARIOS))
@pytest.mark.parametrize("policy", ["TRACK_TARGETS_ONLY", "PARTIAL_FRACTIONS"])
def test_the_fold_of_the_events_equals_the_evaluation(name: str, policy: str) -> None:
    plan = limit(
        exit_policy=policy,
        exit_fractions=(0.5, 0.5, 0.0) if policy == "PARTIAL_FRACTIONS" else (0.0, 0.0, 0.0),
    )
    ev = evaluate(plan, bars(SCENARIOS[name]), T0)
    f = fold_events(ev.events, plan)
    assert f["state"] == ev.state.value and f["is_closed"] == ev.is_closed
    assert (
        f["entry_price"] == ev.entry_price
        and f["position_remaining"] == ev.details["position_remaining"]
    )
    for k in ("realized_return", "realized_r", "mfe", "mae", "max_drawdown"):
        assert (
            f.get(k) == pytest.approx(ev.metrics[k])
            if ev.metrics[k] is not None
            else f.get(k) is None
        )


def test_events_of_a_shorter_history_are_a_prefix_of_the_longer_one() -> None:
    rows = SCENARIOS["track_open"]
    a = evaluate(limit(), bars(rows[:2]), T0).events
    b = evaluate(limit(), bars(rows), T0).events
    assert b[: len(a)] == a  # nothing already recorded is rewritten when new bars arrive


def test_the_engine_is_deterministic() -> None:
    rows = SCENARIOS["track_open"]
    assert evaluate(limit(), bars(rows), T0).events == evaluate(limit(), bars(rows), T0).events


def test_legacy_plans_keep_the_v0_half_at_target_one_behaviour() -> None:
    plan = PlanLevels(
        "LIMIT", 98.0, 100.0, 95.0, 110.0, 120.0
    )  # no exit policy given -> LEGACY_HALF_AT_TP1
    ev = evaluate(
        plan, bars([("2024-01-03", 101, 102, 99, 100), ("2024-01-04", 100, 111, 100, 109)]), T0
    )
    assert ev.state is SimState.PARTIAL_TP and ev.details["position_remaining"] == pytest.approx(
        0.5
    )
