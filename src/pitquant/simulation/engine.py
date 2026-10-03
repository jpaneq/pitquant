# ruff: noqa: E501
"""Paper-trade state machine and outcome metrics (ADR-0034). PURE: a plan and DAILY bars in, a timeline and metrics out.

PAPER TRADE, NO REAL MONEY. Long only in V0. With daily bars the order of events INSIDE a bar is unknowable: when an entry and a stop/target (or a
stop and a target) can both happen in the same bar and the order cannot be determined, the state is ``AMBIGUOUS_INTRABAR``; the favourable reading is
never chosen. Gaps are resolved at the open. Bars must start strictly AFTER the decision session (nothing at or before T0 is traded).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any

import pandas as pd


class SimState(StrEnum):
    CREATED = "CREATED"
    WAITING_ENTRY = "WAITING_ENTRY"
    ENTERED = "ENTERED"
    PARTIAL_TP = "PARTIAL_TP"
    TP1 = "TP1"
    TP2 = "TP2"
    STOPPED = "STOPPED"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"
    CLOSED_MANUAL = "CLOSED_MANUAL"
    AMBIGUOUS_INTRABAR = "AMBIGUOUS_INTRABAR"


CLOSED = {
    SimState.TP1,
    SimState.TP2,
    SimState.STOPPED,
    SimState.INVALIDATED,
    SimState.EXPIRED,
    SimState.CLOSED_MANUAL,
    SimState.AMBIGUOUS_INTRABAR,
}
FIRST_TARGET_FRACTION = 0.5  # with two targets, half of the position is closed at target 1


@dataclass(frozen=True)
class PlanLevels:
    entry_type: str  # LIMIT | STOP_BUY | MARKET
    entry_low: float
    entry_high: float
    stop: float
    target_1: float
    target_2: float | None = None
    invalidation: float | None = None
    expiration: date | None = None  # last session on which the simulation is alive

    def validate(self) -> None:
        if self.entry_type not in ("LIMIT", "STOP_BUY", "MARKET"):
            raise ValueError("entry_type must be LIMIT, STOP_BUY or MARKET")
        if not (0 < self.stop < self.entry_low <= self.entry_high < self.target_1):
            raise ValueError(
                "levels must satisfy 0 < stop < entry_low <= entry_high < target_1 (long only)"
            )
        if self.target_2 is not None and self.target_2 <= self.target_1:
            raise ValueError("target_2 must be above target_1")
        if self.invalidation is not None and self.invalidation <= 0:
            raise ValueError("invalidation must be positive")


@dataclass
class Evaluation:
    state: SimState
    timeline: list[dict[str, Any]] = field(default_factory=list)
    entry_date: date | None = None
    entry_price: float | None = None
    exit_date: date | None = None
    tp1_date: date | None = None
    tp2_date: date | None = None
    stop_date: date | None = None
    last_bar: date | None = None
    metrics: dict[str, float | int | None] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_closed(self) -> bool:
        return self.state in CLOSED


def _t(ev: Evaluation, d: date, state: SimState, note: str) -> None:
    ev.timeline.append({"date": str(d), "state": state.value, "note": note})


def evaluate(
    plan: PlanLevels,
    bars: pd.DataFrame,
    decision_date: date,
    *,
    benchmark: pd.Series | None = None,
    manual_close: tuple[date, float] | None = None,
) -> Evaluation:
    """``bars``: daily OHLC indexed by session date (the caller passes only completed bars known at the evaluation instant)."""
    plan.validate()
    if len(bars) and bars.index[0] <= decision_date:
        raise ValueError(
            "bars must start strictly after the decision date (no data of T0 or earlier is traded)"
        )
    ev = Evaluation(SimState.CREATED)
    _t(ev, decision_date, SimState.CREATED, "paper trade created (no real money)")
    ev.state = SimState.WAITING_ENTRY
    _t(ev, decision_date, SimState.WAITING_ENTRY, "waiting for the entry")
    tp1_hit = False
    exit_price: float | None = None
    realised_parts: list[tuple[float, float]] = []  # (fraction, price)
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    risk = None
    for d, b in bars.iterrows():
        o, h, lo, c = float(b["open"]), float(b["high"]), float(b["low"]), float(b["close"])
        if manual_close and d > manual_close[0] and ev.entry_date is not None:
            break
        ev.last_bar = d
        if ev.entry_date is None:
            if plan.expiration and d > plan.expiration:
                ev.state = SimState.EXPIRED
                _t(ev, d, SimState.EXPIRED, "expired before the entry")
                break
            if plan.invalidation is not None and c < plan.invalidation:
                ev.state = SimState.INVALIDATED
                _t(
                    ev,
                    d,
                    SimState.INVALIDATED,
                    f"close {c:.2f} below the invalidation level {plan.invalidation:.2f} before the entry",
                )
                break
            fill: float | None = None
            if plan.entry_type == "MARKET":
                fill = o
            elif plan.entry_type == "LIMIT" and lo <= plan.entry_high:
                fill = min(o, plan.entry_high)  # a gap below the limit fills at the open
            elif plan.entry_type == "STOP_BUY" and h >= plan.entry_high:
                fill = max(o, plan.entry_high)
            if fill is None:
                continue
            gap = fill == o and plan.entry_type != "MARKET"
            ev.entry_date, ev.entry_price = d, fill
            risk = fill - plan.stop
            _t(
                ev,
                d,
                SimState.ENTERED,
                f"entered at {fill:.2f} ({'gap at the open' if gap else 'level'})",
            )
            ev.state = SimState.ENTERED
            if risk <= 0:
                ev.state = SimState.STOPPED
                ev.stop_date = d
                exit_price = fill
                realised_parts.append((1.0, fill))
                _t(ev, d, SimState.STOPPED, "filled at or below the stop")
                break
            if o <= plan.stop:
                ev.state, ev.stop_date, exit_price = SimState.STOPPED, d, o
                realised_parts.append((1.0, o))
                _t(ev, d, SimState.STOPPED, "opened beyond the stop: stopped at the open")
                break
            if not gap and plan.entry_type != "MARKET" and (lo <= plan.stop or h >= plan.target_1):
                ev.state = SimState.AMBIGUOUS_INTRABAR
                _t(
                    ev,
                    d,
                    SimState.AMBIGUOUS_INTRABAR,
                    "entry and stop/target inside the same daily bar: order unknowable with daily data",
                )
                break
            highs, lows, closes = [h], [lo], [c]
            if plan.entry_type == "MARKET" and (lo <= plan.stop or h >= plan.target_1):
                ev.state = SimState.AMBIGUOUS_INTRABAR
                _t(
                    ev,
                    d,
                    SimState.AMBIGUOUS_INTRABAR,
                    "market entry at the open with a stop/target also reachable in the same bar",
                )
                break
            if gap and o >= plan.target_1:
                tp1_hit, ev.tp1_date = True, d
                if plan.target_2 is None:
                    ev.state = SimState.TP1
                    realised_parts.append((1.0, o))
                    _t(ev, d, SimState.TP1, "gapped through target 1 at the entry")
                    break
            continue
        # after the entry
        highs.append(h)
        lows.append(lo)
        closes.append(c)
        if plan.expiration and d > plan.expiration:
            ev.state = SimState.TP1 if tp1_hit else SimState.EXPIRED
            exit_price = closes[-2] if len(closes) > 1 else c
            realised_parts.append(
                (1.0 - (FIRST_TARGET_FRACTION if tp1_hit and plan.target_2 else 0.0), exit_price)
            )
            _t(ev, d, ev.state, "horizon reached: closed at the last close inside the horizon")
            break
        assert risk is not None
        if o <= plan.stop:
            ev.state, ev.stop_date, exit_price = SimState.STOPPED, d, o
            realised_parts.append(
                (1.0 - (FIRST_TARGET_FRACTION if tp1_hit and plan.target_2 else 0.0), o)
            )
            _t(ev, d, SimState.STOPPED, "gap down through the stop: filled at the open")
            break
        hit_stop, hit_t1 = lo <= plan.stop, h >= plan.target_1
        hit_t2 = plan.target_2 is not None and h >= plan.target_2
        if not tp1_hit:
            if hit_stop and hit_t1:
                if o >= plan.target_1:
                    pass  # gap above target 1: the target fills first
                else:
                    ev.state = SimState.AMBIGUOUS_INTRABAR
                    _t(
                        ev,
                        d,
                        SimState.AMBIGUOUS_INTRABAR,
                        "stop and target 1 inside the same daily bar: order unknowable",
                    )
                    break
            if hit_stop and not hit_t1:
                ev.state, ev.stop_date, exit_price = SimState.STOPPED, d, plan.stop
                realised_parts.append((1.0, plan.stop))
                _t(ev, d, SimState.STOPPED, f"stop {plan.stop:.2f} hit")
                break
            if hit_t1:
                tp1_hit, ev.tp1_date = True, d
                fill1 = max(o, plan.target_1)
                if plan.target_2 is None:
                    ev.state = SimState.TP1
                    realised_parts.append((1.0, fill1))
                    _t(ev, d, SimState.TP1, f"target 1 {plan.target_1:.2f} hit")
                    break
                realised_parts.append((FIRST_TARGET_FRACTION, fill1))
                ev.state = SimState.PARTIAL_TP
                _t(
                    ev,
                    d,
                    SimState.PARTIAL_TP,
                    f"target 1 hit: {int(FIRST_TARGET_FRACTION * 100)}% closed at {fill1:.2f}",
                )
                if hit_t2:
                    ev.state, ev.tp2_date = SimState.TP2, d
                    realised_parts.append(
                        (1.0 - FIRST_TARGET_FRACTION, max(o, plan.target_2 or 0.0))
                    )
                    _t(ev, d, SimState.TP2, "target 2 also reached in the same bar")
                    break
        else:
            rest = 1.0 - (FIRST_TARGET_FRACTION if plan.target_2 else 0.0)
            if hit_stop and hit_t2 and o < (plan.target_2 or 0.0):
                ev.state = SimState.AMBIGUOUS_INTRABAR
                _t(
                    ev,
                    d,
                    SimState.AMBIGUOUS_INTRABAR,
                    "stop and target 2 inside the same daily bar: order unknowable",
                )
                break
            if hit_stop:
                ev.state, ev.stop_date = SimState.STOPPED, d
                realised_parts.append((rest, plan.stop))
                _t(ev, d, SimState.STOPPED, "stop hit after target 1 (remaining half)")
                break
            if hit_t2:
                ev.state, ev.tp2_date = SimState.TP2, d
                realised_parts.append((rest, max(o, plan.target_2 or 0.0)))
                _t(ev, d, SimState.TP2, f"target 2 {plan.target_2} hit")
                break
    if manual_close and ev.entry_date is not None and not ev.is_closed:
        md, mp = manual_close
        ev.state = SimState.CLOSED_MANUAL
        rest = 1.0 - sum(f for f, _ in realised_parts)
        realised_parts.append((rest, mp))
        ev.exit_date = md
        _t(ev, md, SimState.CLOSED_MANUAL, f"closed manually at {mp:.2f}")
    if ev.is_closed and ev.exit_date is None:
        ev.exit_date = ev.last_bar
    ev.tp1_date = ev.tp1_date
    _metrics(ev, plan, bars, decision_date, realised_parts, highs, lows, closes, benchmark, risk)
    return ev


def _metrics(
    ev: Evaluation,
    plan: PlanLevels,
    bars: pd.DataFrame,
    decision_date: date,
    parts: list[tuple[float, float]],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    bench: pd.Series | None,
    risk: float | None,
) -> None:
    m: dict[str, float | int | None] = {
        k: None
        for k in (
            "realized_return",
            "excess_return_vs_benchmark",
            "realized_r",
            "mfe",
            "mae",
            "max_drawdown",
            "days_to_entry",
            "days_to_stop",
            "days_to_tp1",
            "days_to_tp2",
            "holding_period",
        )
    }
    ev.metrics = m
    if ev.entry_date is None or ev.entry_price is None:
        return
    e = ev.entry_price
    m["days_to_entry"] = (ev.entry_date - decision_date).days
    m["mfe"] = (max(highs) - e) / e if highs else 0.0
    m["mae"] = (e - min(lows)) / e if lows else 0.0
    if closes:
        peak, dd = closes[0], 0.0
        for c in closes:
            peak = max(peak, c)
            dd = max(dd, (peak - c) / peak)
        m["max_drawdown"] = dd
    for key, dt in (
        ("days_to_stop", ev.stop_date),
        ("days_to_tp1", ev.tp1_date),
        ("days_to_tp2", ev.tp2_date),
    ):
        m[key] = (dt - decision_date).days if dt else None
    end = ev.exit_date or ev.last_bar
    m["holding_period"] = (end - ev.entry_date).days if end else None
    ev.details["return_basis"] = (
        "REALIZED" if ev.is_closed else "UNREALIZED (position still open at the last bar)"
    )
    if not ev.is_closed and closes:
        parts = [*parts, (1.0 - sum(f for f, _ in parts), closes[-1])]
    if parts:
        blended = sum(f * p for f, p in parts) / sum(f for f, _ in parts)
        m["realized_return"] = (blended - e) / e
        if risk and risk > 0:
            m["realized_r"] = (blended - e) / risk
    if (
        bench is not None
        and end is not None
        and ev.entry_date in bench.index
        and end in bench.index
        and m["realized_return"] is not None
    ):
        b0, b1 = float(bench.loc[ev.entry_date]), float(bench.loc[end])
        m["excess_return_vs_benchmark"] = float(m["realized_return"]) - (b1 / b0 - 1.0)
        ev.details["benchmark_return"] = b1 / b0 - 1.0
    ev.details["tp1_hit"] = ev.tp1_date is not None
    ev.details["dividends"] = "price return only: dividends are not included in the paper trade"
