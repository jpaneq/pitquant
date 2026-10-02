# ruff: noqa: E501
"""Trade-plan backtest CONTRACT (ADR-0030). No mass backtest is run here: this fixes the semantics so a
future one cannot cheat.

For a historical date T: (1) generate the plan with ONLY data known at T (``AnalyzerService.trade_plan``
with ``as_of=T``); (2) freeze entry zone, stop, targets and expiry; (3) then observe the OHLC bars AFTER T.

States: NOT_TRIGGERED (never entered before expiry), ENTERED (entered, still open), STOPPED, TP1, TP2,
EXPIRED (entered, neither stop nor target before expiry), AMBIGUOUS_INTRABAR, plus PENDING (not enough
observed bars to decide). With DAILY bars only, when stop and target (or entry and stop) are both inside
the same candle and the order cannot be known, the state is ``AMBIGUOUS_INTRABAR``: the order is NEVER
assumed in the plan's favour. Gaps through a level are resolved at the OPEN (known order).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Literal

import pandas as pd


class PlanState(StrEnum):
    NOT_TRIGGERED = "NOT_TRIGGERED"
    ENTERED = "ENTERED"
    STOPPED = "STOPPED"
    TP1 = "TP1"
    TP2 = "TP2"
    EXPIRED = "EXPIRED"
    AMBIGUOUS_INTRABAR = "AMBIGUOUS_INTRABAR"
    PENDING = "PENDING"


@dataclass(frozen=True)
class PlanSpec:
    decision_date: date
    entry: float
    entry_kind: Literal[
        "LIMIT_BELOW", "STOP_ABOVE"
    ]  # limit order under the price / buy-stop above it
    stop: float
    target_1: float
    target_2: float
    expiry_sessions: int = 20
    rules_version: str = "trade-plan-v0.1"


@dataclass
class PlanEvaluation:
    state: PlanState
    entered_on: date | None = None
    resolved_on: date | None = None
    fill_price: float | None = None
    notes: list[str] = field(default_factory=list)
    bars_observed: int = 0


def evaluate_plan(spec: PlanSpec, bars: pd.DataFrame) -> PlanEvaluation:
    """``bars``: daily OHLC with a date index, STRICTLY AFTER ``decision_date`` (the caller must not pass T itself)."""
    if len(bars) and bars.index[0] <= spec.decision_date:
        raise ValueError("bars must start strictly after the decision date")
    ev = PlanEvaluation(PlanState.PENDING)
    window = bars.iloc[: spec.expiry_sessions]
    tp1_hit = False
    for i, (d, b) in enumerate(window.iterrows()):
        ev.bars_observed = i + 1
        o, h, lo = float(b["open"]), float(b["high"]), float(b["low"])
        if ev.entered_on is None:
            fills = (lo <= spec.entry) if spec.entry_kind == "LIMIT_BELOW" else (h >= spec.entry)
            if not fills:
                continue
            gap_fill = (o <= spec.entry) if spec.entry_kind == "LIMIT_BELOW" else (o >= spec.entry)
            ev.entered_on, ev.fill_price = d, (o if gap_fill else spec.entry)
            ev.notes.append(f"entered on {d} at {ev.fill_price} ({'gap' if gap_fill else 'level'})")
            if o <= spec.stop:
                ev.state, ev.resolved_on = PlanState.STOPPED, d
                ev.notes.append("opened beyond the stop: stopped at the open")
                return ev
            # the entry candle: the intrabar order of entry vs stop/target is unknown with daily bars
            if (lo <= spec.stop or h >= spec.target_1) and not gap_fill:
                ev.state, ev.resolved_on = PlanState.AMBIGUOUS_INTRABAR, d
                ev.notes.append(
                    "entry and stop/target inside the same daily candle: order unknowable without intraday data"
                )
                return ev
            ev.state = PlanState.ENTERED
            continue
        # after entry: stop checked against targets candle by candle
        if o <= spec.stop:
            ev.state, ev.resolved_on = (PlanState.TP1 if tp1_hit else PlanState.STOPPED), d
            ev.notes.append("gap down through the stop: filled at the open")
            return ev
        hit_stop, hit_t1, hit_t2 = lo <= spec.stop, h >= spec.target_1, h >= spec.target_2
        if not tp1_hit:
            if o >= spec.target_2:
                ev.state, ev.resolved_on = PlanState.TP2, d
                return ev
            if hit_stop and hit_t1:
                ev.state, ev.resolved_on = PlanState.AMBIGUOUS_INTRABAR, d
                ev.notes.append("stop and target_1 inside the same candle: order unknowable")
                return ev
            if hit_stop:
                ev.state, ev.resolved_on = PlanState.STOPPED, d
                return ev
            if hit_t2:
                ev.state, ev.resolved_on = PlanState.TP2, d
                return ev
            if hit_t1:
                tp1_hit = True
                ev.state, ev.resolved_on = PlanState.TP1, d
                ev.notes.append("target_1 reached; still tracking target_2")
        else:
            if hit_stop and hit_t2:
                ev.notes.append("after TP1: stop and target_2 in the same candle: TP2 not claimed")
                return ev
            if hit_t2:
                ev.state, ev.resolved_on = PlanState.TP2, d
                return ev
            if hit_stop:
                ev.notes.append("TP1 was reached before the stop")
                return ev
    if ev.entered_on is None:
        if len(bars) >= spec.expiry_sessions:
            ev.state = PlanState.NOT_TRIGGERED
        return ev
    if tp1_hit:
        return ev
    if len(bars) >= spec.expiry_sessions:
        ev.state, ev.resolved_on = PlanState.EXPIRED, window.index[-1]
    return ev
