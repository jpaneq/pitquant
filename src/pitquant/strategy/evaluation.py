# ruff: noqa: E501
"""Run evaluation and strategy comparison (ADR-0039). Metrics come from the Simulation Lab outcomes of the run's paper trades; nothing is recomputed from scratch.

* ``input_series_hash``: a hash of what the run CONSUMED (securities, decision instants, prediction snapshot ids, trade-plan hashes), not of what it decided. Two runs are
  comparable only when their hashes are equal: otherwise ``NOT_COMPARABLE_INPUTS``.
* BUY_AND_HOLD is ALWAYS part of a comparison: the same securities from the same entry fill, never sold, over the same window. A strategy that earns money but loses to it is flagged
  ``UNDERPERFORMS_BUY_AND_HOLD``. The benchmark (SPY total-return proxy) is NULL when no benchmark prices exist.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.analyzer.market import benchmark_security, load_market
from pitquant.config.settings import Settings
from pitquant.core.hashing import content_hash
from pitquant.core.timeutils import utc_now
from pitquant.db.models import Simulation
from pitquant.db.models_lab import (
    PredictionSnapshot,
    StrategyDecision,
    StrategyDefinition,
    StrategyRun,
    StrategyRunResult,
    StrategySimulationLink,
)
from pitquant.simulation import service as sim
from pitquant.strategy import service as strat
from pitquant.strategy.metrics import (
    MIN_TRADES,
    costs_flag,
    equity_stats,
    round_trip_cost,
    trade_stats,
)


def input_series_hash(session: Session, run: StrategyRun) -> str:
    """What the run CONSUMED, independent of what the strategy did with it: the decision instants, the securities and every prediction snapshot that existed (and had been
    generated) for them. Strategies run over the same predictions and dates share the hash; any difference in dates, universe or predictions changes it."""
    dates = sorted(
        {
            d.decision_at.isoformat()
            for d in session.scalars(
                select(StrategyDecision).where(StrategyDecision.run_id == run.run_id)
            )
        }
    )
    snaps = sorted(
        (
            p.security_id,
            p.decision_at.isoformat(),
            p.horizon_months,
            p.model_version,
            p.prediction_id,
        )
        for p in session.scalars(
            select(PredictionSnapshot).where(PredictionSnapshot.security_id.in_(list(run.universe)))
        )
        if p.decision_at.isoformat() in dates
        and p.generated_at.isoformat() <= p.decision_at.isoformat()
    )
    return content_hash({"universe": sorted(run.universe), "dates": dates, "predictions": snaps})


def _buy_hold_positions(
    session: Session, run: StrategyRun, as_of: datetime
) -> list[dict[str, Any]]:
    """BUY_AND_HOLD strategy runs hold no paper trade: each ENTER decision buys at the close of its session and holds to the end of the window."""
    out = []
    for d in session.scalars(
        select(StrategyDecision).where(
            StrategyDecision.run_id == run.run_id, StrategyDecision.decision == "ENTER"
        )
    ):
        bars = load_market(session, d.security_id, as_of).bars["close"].astype(float)
        c = bars[bars.index >= d.decision_at.date()]
        if len(c) < 2:
            continue
        r = c.pct_change()
        r.iloc[0] = 0.0
        out.append(
            {
                "returns": r,
                "closes": c,
                "entry_date": c.index[0],
                "end": c.index[-1],
                "closed": False,
                "ret": float(c.iloc[-1] / c.iloc[0] - 1.0),
                "r": None,
                "mae": None,
                "mfe": None,
                "entry_price": float(c.iloc[0]),
                "exit_reason": None,
            }
        )
    return out


def _position_series(session: Session, sm: Simulation, as_of: datetime) -> dict[str, Any] | None:
    out = sim.latest_outcome(session, sm.simulation_id)
    if out is None or out.entry_date is None or out.entry_price is None:
        return None
    bars, _ = sim._bars_after(session, sm, as_of)
    end = (
        out.exit_date
        if out.is_closed and out.exit_date
        else (bars.index[-1] if len(bars) else out.entry_date)
    )
    b = bars[(bars.index >= out.entry_date) & (bars.index <= end)]
    if not len(b):
        return None
    closes = b["close"].astype(float)
    rets = closes.pct_change()
    rets.iloc[0] = closes.iloc[0] / out.entry_price - 1.0
    if out.is_closed and out.realized_return is not None:
        before = float((1.0 + rets.iloc[:-1]).prod()) if len(rets) > 1 else 1.0
        rets.iloc[-1] = (1.0 + out.realized_return) / before - 1.0
    ex = (out.details or {}).get("metrics_extra") or {}
    return {
        "returns": rets, "entry_date": out.entry_date, "end": end, "closed": out.is_closed, "ret": out.realized_return, "r": out.realized_r, "mae": ex.get("mae_pct"), "mfe": ex.get("mfe_pct"),
        "entry_price": out.entry_price, "closes": closes, "simulation_id": sm.simulation_id, "exit_reason": strat.exit_reason_for(session, sm.simulation_id),
    }  # fmt: skip


def _portfolio(
    positions: list[dict[str, Any]], weight: float, cost_rt: float, hold: bool
) -> dict[str, Any]:
    """Equal-weight sleeves. ``hold`` = buy and hold: each position keeps earning until the common end of the window."""
    if not positions:
        return {**equity_stats(pd.Series(dtype=float)), "series_days": 0}
    end_all = max(p["end"] for p in positions)
    idx = sorted(
        {d for p in positions for d in p["returns"].index}
        | ({d for p in positions for d in p["closes"].index} if hold else set())
    )
    if hold:
        idx = [d for d in idx if d <= end_all]
    daily = pd.Series(0.0, index=pd.Index(idx))
    expo = pd.Series(0.0, index=pd.Index(idx))
    for p in positions:
        if hold:
            c = p["closes"][p["closes"].index >= p["entry_date"]]
            r = c.pct_change()
            r.iloc[0] = c.iloc[0] / p["entry_price"] - 1.0
        else:
            r = p["returns"]
        daily.loc[r.index] += weight * r
        expo.loc[r.index] += weight
        daily.loc[r.index[0]] -= weight * cost_rt / 2.0  # entry leg
        if not hold and p["closed"]:
            daily.loc[r.index[-1]] -= weight * cost_rt / 2.0  # exit leg
    return equity_stats(
        daily,
        expo,
        legs_weight=weight
        * (len(positions) + (0 if hold else sum(1 for p in positions if p["closed"]))),
    )


def _benchmark_return(session: Session, as_of: datetime, start: Any, end: Any) -> float | None:
    b = benchmark_security(session)
    if b is None:
        return None
    bars = load_market(session, b[0], as_of).bars["close"].astype(float)
    w = bars[(bars.index >= start) & (bars.index <= end)]
    return float(w.iloc[-1] / w.iloc[0] - 1.0) if len(w) >= 2 else None


def run_metrics(
    session: Session, settings: Settings, run: StrategyRun, as_of: datetime | None = None
) -> tuple[dict[str, Any], list[str]]:
    as_of = as_of or utc_now()
    strategy = session.get_one(StrategyDefinition, run.strategy_row_id)
    flags: list[str] = []
    sims = [
        session.get_one(Simulation, link.simulation_id)
        for link in session.scalars(
            select(StrategySimulationLink)
            .join(
                StrategyDecision, StrategyDecision.decision_id == StrategySimulationLink.decision_id
            )
            .where(StrategyDecision.run_id == run.run_id, StrategySimulationLink.role == "ENTRY")
        )
    ]
    positions = (
        _buy_hold_positions(session, run, as_of)
        if strategy.family == "BUY_AND_HOLD"
        else [p for sm in sims if (p := _position_series(session, sm, as_of)) is not None]
    )
    weight = 1.0 / strategy.max_positions
    cost_rt = round_trip_cost(strategy.costs)
    trades = [
        {**p, "ret": (p["ret"] - cost_rt) if p["ret"] is not None else None} for p in positions
    ]
    strat_p, bh_p = (
        _portfolio(positions, weight, cost_rt, hold=False),
        _portfolio(positions, weight, cost_rt, hold=True),
    )
    metrics: dict[str, Any] = {
        "strategy": f"{run.strategy_id} v{run.strategy_version}", "family": strategy.family, "run_kind": run.run_kind, "n_decisions": len(list(session.scalars(select(StrategyDecision.decision_id).where(StrategyDecision.run_id == run.run_id)))),
        "trades": trade_stats(trades), "portfolio": strat_p, "buy_and_hold": bh_p, "portfolio_definition": "EQUAL_WEIGHT_SLEEVES (1/max_positions per open trade, idle sleeves in cash)", "risk_free": "RF_ZERO",
        "exit_reasons": {r: sum(1 for p in positions if p["exit_reason"] == r) for r in sorted({p["exit_reason"] for p in positions if p["exit_reason"]})},
        "costs": strategy.costs, "benchmark_return": None, "excess_vs_benchmark": None, "excess_vs_buy_and_hold": None,
    }  # fmt: skip
    if positions:
        start = min(p["entry_date"] for p in positions)
        end = max(p["end"] for p in positions)
        metrics["benchmark_return"] = _benchmark_return(session, as_of, start, end)
        if metrics["benchmark_return"] is not None and strat_p["total_return"] is not None:
            metrics["excess_vs_benchmark"] = strat_p["total_return"] - metrics["benchmark_return"]
    if strat_p["total_return"] is not None and bh_p["total_return"] is not None:
        metrics["excess_vs_buy_and_hold"] = strat_p["total_return"] - bh_p["total_return"]
        if strat_p["total_return"] < bh_p["total_return"]:
            flags.append("UNDERPERFORMS_BUY_AND_HOLD")
    if metrics["benchmark_return"] is None:
        flags.append("NO_BENCHMARK")
    if metrics["trades"]["n_trades"] < MIN_TRADES:
        flags.append("INSUFFICIENT_SAMPLE")
    flags += costs_flag(strategy.costs)
    if run.is_synthetic:
        flags.append("SYNTHETIC_TEST_DATA")
    return metrics, flags


def evaluate_run(
    session: Session, settings: Settings, run: StrategyRun, as_of: datetime | None = None
) -> StrategyRunResult:
    """Materialise the metrics of a run as of ``as_of`` (append-only: a re-evaluation is a new row)."""
    as_of = as_of or utc_now()
    metrics, flags = run_metrics(session, settings, run, as_of)
    res = StrategyRunResult(
        run_id=run.run_id,
        evaluated_at=as_of,
        prediction_series_hash=input_series_hash(session, run),
        metrics=metrics,
        flags=flags,
    )
    session.add(res)
    session.flush()
    return res


def compare_runs(
    session: Session, settings: Settings, run_ids: Sequence[str], as_of: datetime | None = None
) -> dict[str, Any]:
    """Side by side over the SAME inputs: refuses to present runs with different input series as comparable (every row says so)."""
    as_of = as_of or utc_now()
    runs = [session.get_one(StrategyRun, r) for r in run_ids]
    rows, hashes = [], {}
    for run in runs:
        m, fl = run_metrics(session, settings, run, as_of)
        h = input_series_hash(session, run)
        hashes[run.run_id] = h
        rows.append(
            {
                "run_id": run.run_id,
                "strategy": m["strategy"],
                "family": m["family"],
                "run_kind": run.run_kind,
                "input_series_hash": h,
                "metrics": m,
                "flags": fl,
            }
        )
    comparable = len(set(hashes.values())) <= 1
    if not comparable:
        for r in rows:
            r["flags"] = [*r["flags"], "NOT_COMPARABLE_INPUTS"]
    base = rows[0]["metrics"] if rows else None
    baseline = {
        "name": "BUY_AND_HOLD",
        "definition": "same securities, same entry fills as the first run, never sold, same window",
        "portfolio": base["buy_and_hold"] if base else None,
        "benchmark_return": base["benchmark_return"] if base else None,
    }
    return {
        "comparable": comparable,
        "input_hashes": hashes,
        "rows": rows,
        "baseline": baseline,
        "synthetic": any(r.is_synthetic for r in runs),
        "note": "descriptive comparison of paper trades; costs and portfolio definition are stated in each row",
    }
