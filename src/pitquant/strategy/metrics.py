# ruff: noqa: E501
"""Strategy / portfolio metrics (ADR-0039). PURE functions over return series and trade lists; the data comes from the Simulation Lab outcomes.

PORTFOLIO DEFINITION (the only one, written down so it is never mistaken for a real portfolio): EQUAL-WEIGHT SLEEVES. Capital is split in ``max_positions``
sleeves; each open paper trade occupies one sleeve (weight 1/max_positions) and idle sleeves stay in cash at 0 %. The daily portfolio return is the sum of the
sleeve weights times each open trade's daily return (close to close; entry fill to first close; exit fill on the exit day). No leverage, no rebalancing between
sleeves, costs only as basis points per leg (0 by default ⇒ ``COSTS_NOT_MODELED``). Sharpe / Sortino use a ZERO risk-free rate (labelled ``RF_ZERO``).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

MIN_TRADES = 10
TRADING_DAYS = 252


def max_drawdown(equity: Sequence[float]) -> float | None:
    if not len(equity):
        return None
    peak, dd = equity[0], 0.0
    for v in equity:
        peak = max(peak, v)
        dd = max(dd, (peak - v) / peak if peak > 0 else 0.0)
    return dd


def equity_stats(
    daily: pd.Series, exposure: pd.Series | None = None, legs_weight: float = 0.0
) -> dict[str, Any]:
    """``daily``: portfolio daily returns indexed by date. ``legs_weight``: sum of sleeve weights traded (entries + exits)."""
    out: dict[str, Any] = {
        "days": len(daily),
        "total_return": None,
        "cagr": None,
        "volatility": None,
        "sharpe": None,
        "sortino": None,
        "max_drawdown": None,
        "turnover_total": legs_weight,
        "turnover_annualised": None,
        "exposure": None,
    }
    if len(daily) == 0:
        return out
    r = daily.to_numpy(float)
    eq = np.cumprod(1.0 + r)
    out["total_return"] = float(eq[-1] - 1.0)
    span = max((daily.index[-1] - daily.index[0]).days, 0) + 1
    years = span / 365.0
    if span >= 30 and eq[-1] > 0:
        out["cagr"] = float(eq[-1] ** (1.0 / years) - 1.0)
    if legs_weight and span >= 30:
        out["turnover_annualised"] = legs_weight / years
    out["max_drawdown"] = max_drawdown([1.0, *eq.tolist()])
    if len(r) >= 5:
        sd = float(np.std(r, ddof=1))
        out["volatility"] = sd * math.sqrt(TRADING_DAYS)
        if sd > 0:
            out["sharpe"] = float(np.mean(r) / sd * math.sqrt(TRADING_DAYS))
        down = r[r < 0]
        if len(down) >= 2 and float(np.std(down, ddof=1)) > 0:
            out["sortino"] = float(
                np.mean(r) / float(np.std(down, ddof=1)) * math.sqrt(TRADING_DAYS)
            )
    if exposure is not None and len(exposure):
        out["exposure"] = float(exposure.mean())
    return out


def trade_stats(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """``trades``: {ret, r, mae, mfe, closed}. Statistics only with at least MIN_TRADES entered trades; N is always reported."""
    entered = [t for t in trades if t.get("ret") is not None]
    n = len(entered)
    out: dict[str, Any] = {
        "n_trades": n,
        "n_closed": sum(1 for t in entered if t.get("closed")),
        "sample": "OK" if n >= MIN_TRADES else "INSUFFICIENT_SAMPLE",
        "hit_rate": None,
        "profit_factor": None,
        "mean_return": None,
        "mean_r": None,
        "median_r": None,
        "mean_mae": None,
        "mean_mfe": None,
    }
    if n < MIN_TRADES:
        return out
    rets = [float(t["ret"]) for t in entered]
    wins, losses = sum(x for x in rets if x > 0), -sum(x for x in rets if x < 0)
    rs = [float(t["r"]) for t in entered if t.get("r") is not None]
    out.update(
        hit_rate=sum(1 for x in rets if x > 0) / n,
        profit_factor=(wins / losses) if losses > 0 else None,
        mean_return=float(np.mean(rets)),
    )
    if rs:
        out.update(mean_r=float(np.mean(rs)), median_r=float(np.median(rs)))
    for k, key in (("mean_mae", "mae"), ("mean_mfe", "mfe")):
        v = [float(t[key]) for t in entered if t.get(key) is not None]
        if v:
            out[k] = float(np.mean(v))
    return out


def costs_flag(costs: dict[str, Any]) -> list[str]:
    return (
        ["COSTS_NOT_MODELED"]
        if float(costs.get("commission_bps", 0.0)) == 0.0
        and float(costs.get("slippage_bps", 0.0)) == 0.0
        else []
    )


def round_trip_cost(costs: dict[str, Any]) -> float:
    """Fractional cost of one round trip: 2 legs x (commission + slippage) bps."""
    return (
        2.0
        * (float(costs.get("commission_bps", 0.0)) + float(costs.get("slippage_bps", 0.0)))
        / 1e4
    )
