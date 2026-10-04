"""Strategy metrics on SYNTHETIC return series with known arithmetic (ADR-0039)."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from pitquant.strategy.metrics import (
    costs_flag,
    equity_stats,
    max_drawdown,
    round_trip_cost,
    trade_stats,
)


def series(vals: list[float], start: str = "2024-01-02") -> pd.Series:
    return pd.Series(vals, index=pd.bdate_range(start, periods=len(vals)).date)


def test_total_return_drawdown_and_exposure() -> None:
    s = equity_stats(
        series([0.10, -0.10, 0.05]), pd.Series([1.0, 0.5, 0.5], index=series([0, 0, 0]).index)
    )
    assert (
        s["total_return"] == pytest.approx(1.1 * 0.9 * 1.05 - 1)
        and s["max_drawdown"] == pytest.approx(0.10)
        and s["exposure"] == pytest.approx(2 / 3)
    )
    assert (
        s["cagr"] is None and s["volatility"] is None
    )  # a 3-day window has no annualised figures: nothing is extrapolated


def test_cagr_volatility_sharpe_and_sortino_on_a_long_series() -> None:
    r = series([0.001, -0.0005, 0.002, -0.0012] * 65)
    s = equity_stats(r, legs_weight=0.4)
    assert s["cagr"] is not None and s["volatility"] == pytest.approx(
        float(r.std(ddof=1)) * math.sqrt(252)
    )
    assert (
        s["sharpe"] == pytest.approx(float(r.mean() / r.std(ddof=1)) * math.sqrt(252))
        and s["sortino"] is not None
        and s["turnover_annualised"] is not None
    )


def test_no_downside_means_no_sortino_and_an_empty_series_has_no_numbers() -> None:
    assert equity_stats(series([0.01] * 20))["sortino"] is None
    assert (
        equity_stats(pd.Series(dtype=float))["total_return"] is None
        and equity_stats(pd.Series(dtype=float))["days"] == 0
    )


def test_max_drawdown() -> None:
    assert (
        max_drawdown([1.0, 1.2, 0.9, 1.1]) == pytest.approx((1.2 - 0.9) / 1.2)
        and max_drawdown([]) is None
    )


def test_trade_stats_need_ten_trades_and_always_report_n() -> None:
    few = trade_stats([{"ret": 0.1, "r": 1.0, "closed": True}] * 5)
    assert (
        few["n_trades"] == 5
        and few["sample"] == "INSUFFICIENT_SAMPLE"
        and few["hit_rate"] is None
        and few["mean_r"] is None
    )
    trades = (
        [{"ret": 0.10, "r": 2.0, "mae": -0.02, "mfe": 0.12, "closed": True}] * 6
        + [{"ret": -0.05, "r": -1.0, "mae": -0.06, "mfe": 0.01, "closed": True}] * 4
        + [{"ret": None, "r": None, "closed": False}]
    )
    t = trade_stats(trades)
    assert (
        t["n_trades"] == 10
        and t["hit_rate"] == pytest.approx(0.6)
        and t["profit_factor"] == pytest.approx(0.6 / 0.2)
        and t["mean_r"] == pytest.approx((12 - 4) / 10)
        and t["median_r"] == pytest.approx(2.0)
    )
    assert t["mean_mae"] == pytest.approx((-0.02 * 6 - 0.06 * 4) / 10) and t[
        "mean_mfe"
    ] == pytest.approx((0.12 * 6 + 0.01 * 4) / 10)


def test_profit_factor_is_none_without_losses() -> None:
    assert trade_stats([{"ret": 0.01, "r": 0.5, "closed": True}] * 10)["profit_factor"] is None


def test_costs_are_flagged_when_not_modeled_and_applied_when_set() -> None:
    assert (
        costs_flag({"commission_bps": 0, "slippage_bps": 0}) == ["COSTS_NOT_MODELED"]
        and costs_flag({"commission_bps": 1.0, "slippage_bps": 0}) == []
    )
    assert (
        round_trip_cost({"commission_bps": 1.0, "slippage_bps": 2.0}) == pytest.approx(2 * 3 / 1e4)
        and round_trip_cost({}) == 0.0
    )
