# ruff: noqa: E501
"""Simulation Lab state machine and metrics (ADR-0034) on SYNTHETIC bars. PAPER TRADE, NO REAL MONEY."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from pitquant.simulation.engine import PlanLevels, SimState, evaluate

T0 = date(2024, 1, 2)
PLAN = PlanLevels(
    "LIMIT", 98.0, 100.0, 95.0, 110.0, 120.0, invalidation=94.0, expiration=date(2024, 1, 31)
)


def bars(rows: list[tuple[str, float, float, float, float]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["d", "open", "high", "low", "close"])
    df.index = [date.fromisoformat(x) for x in df.pop("d")]
    return df


def test_waits_for_the_entry_and_enters_at_the_limit() -> None:
    ev = evaluate(
        PLAN, bars([("2024-01-03", 105, 108, 102, 106), ("2024-01-04", 103, 104, 99, 100)]), T0
    )
    assert (
        ev.state is SimState.ENTERED
        and ev.entry_price == 100.0
        and ev.entry_date == date(2024, 1, 4)
        and ev.metrics["days_to_entry"] == 2
    )
    assert [t["state"] for t in ev.timeline][:3] == ["CREATED", "WAITING_ENTRY", "ENTERED"]


def test_stop_trigger_after_entry_and_realized_r() -> None:
    ev = evaluate(
        PLAN, bars([("2024-01-03", 101, 102, 99, 100), ("2024-01-04", 99, 100, 94, 95)]), T0
    )
    assert ev.state is SimState.STOPPED and ev.metrics["days_to_stop"] == 2
    assert ev.metrics["realized_r"] == pytest.approx(-1.0) and ev.metrics[
        "realized_return"
    ] == pytest.approx(-0.05)


def test_target_triggers_partial_then_second_target() -> None:
    ev = evaluate(
        PLAN,
        bars(
            [
                ("2024-01-03", 101, 102, 99, 100),
                ("2024-01-04", 100, 111, 100, 110),
                ("2024-01-05", 110, 121, 109, 120),
            ]
        ),
        T0,
    )
    assert (
        ev.state is SimState.TP2
        and ev.metrics["days_to_tp1"] == 2
        and ev.metrics["days_to_tp2"] == 3
    )
    # half at 110 (+10%), half at 120 (+20%) on a 100 entry with a 5 risk: R = 0.5*2 + 0.5*4 = 3
    assert ev.metrics["realized_r"] == pytest.approx(3.0) and ev.metrics[
        "realized_return"
    ] == pytest.approx(0.15)


def test_partial_tp_state_while_the_rest_is_open() -> None:
    ev = evaluate(
        PLAN, bars([("2024-01-03", 101, 102, 99, 100), ("2024-01-04", 100, 111, 100, 109)]), T0
    )
    assert (
        ev.state is SimState.PARTIAL_TP
        and not ev.is_closed
        and ev.details["return_basis"].startswith("UNREALIZED")
    )


def test_expiration_without_entry_and_with_open_position() -> None:
    ev = evaluate(
        PLAN, bars([("2024-01-03", 105, 108, 102, 106), ("2024-02-01", 105, 108, 102, 106)]), T0
    )
    assert (
        ev.state is SimState.EXPIRED
        and ev.entry_date is None
        and ev.metrics["realized_return"] is None
    )
    ev2 = evaluate(
        PLAN,
        bars(
            [
                ("2024-01-03", 101, 102, 99, 100),
                ("2024-01-10", 100, 104, 99, 103),
                ("2024-02-01", 103, 104, 100, 101),
            ]
        ),
        T0,
    )
    assert (
        ev2.state is SimState.EXPIRED
        and ev2.is_closed
        and ev2.metrics["realized_return"] == pytest.approx(0.03)
    )  # closed at the last close inside the horizon


def test_invalidation_before_entry() -> None:
    ev = evaluate(
        PLAN, bars([("2024-01-03", 106, 108, 103, 93)]), T0
    )  # closes below 94 without ever touching the 100 limit
    assert ev.state is SimState.INVALIDATED and ev.entry_date is None and ev.is_closed


def test_ambiguous_daily_bar_is_never_resolved_favourably() -> None:
    entered = bars([("2024-01-03", 101, 102, 99, 100)])
    same_bar = bars([("2024-01-04", 100, 112, 94, 100)])  # stop 95 AND target 110 inside one bar
    ev = evaluate(PLAN, pd.concat([entered, same_bar]), T0)
    assert ev.state is SimState.AMBIGUOUS_INTRABAR and ev.is_closed
    ev2 = evaluate(
        PLAN, bars([("2024-01-03", 102, 112, 94, 100)]), T0
    )  # entry + stop/target in the entry bar
    assert ev2.state is SimState.AMBIGUOUS_INTRABAR


def test_gap_through_the_stop_fills_at_the_open() -> None:
    ev = evaluate(
        PLAN, bars([("2024-01-03", 101, 102, 99, 100), ("2024-01-04", 90, 92, 88, 91)]), T0
    )
    assert ev.state is SimState.STOPPED and ev.metrics["realized_r"] == pytest.approx(
        -2.0
    )  # filled at 90, not at the 95 stop


def test_mfe_mae_drawdown_and_benchmark_excess() -> None:
    b = bars(
        [
            ("2024-01-03", 101, 102, 99, 100),
            ("2024-01-04", 100, 108, 97, 106),
            ("2024-01-05", 106, 107, 98, 99),
        ]
    )
    bench = pd.Series([200.0, 202.0, 204.0], index=b.index)
    ev = evaluate(PLAN, b, T0, benchmark=bench)
    assert ev.metrics["mfe"] == pytest.approx(0.08) and ev.metrics["mae"] == pytest.approx(0.03)
    assert ev.metrics["max_drawdown"] == pytest.approx((106 - 99) / 106)
    assert ev.metrics["excess_return_vs_benchmark"] == pytest.approx(
        ev.metrics["realized_return"] - 0.02
    )  # type: ignore[operator]


def test_manual_close_and_no_trading_of_t0_or_earlier() -> None:
    b = bars(
        [
            ("2024-01-03", 101, 102, 99, 100),
            ("2024-01-04", 100, 104, 99, 103),
            ("2024-01-05", 103, 105, 101, 104),
        ]
    )
    ev = evaluate(PLAN, b, T0, manual_close=(date(2024, 1, 4), 103.0))
    assert (
        ev.state is SimState.CLOSED_MANUAL
        and ev.exit_date == date(2024, 1, 4)
        and ev.metrics["realized_return"] == pytest.approx(0.03)
    )
    with pytest.raises(ValueError, match="strictly after"):
        evaluate(PLAN, bars([("2024-01-02", 100, 101, 99, 100)]), T0)


def test_plan_levels_are_validated() -> None:
    with pytest.raises(ValueError):
        PlanLevels("LIMIT", 98, 100, 101, 110).validate()  # stop above the entry
