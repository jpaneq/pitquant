# ruff: noqa: E501
"""Paper-trade state machine and outcome metrics (ADR-0034, ADR-0036). PURE: a plan and DAILY bars in, events/timeline and metrics out.

PAPER TRADE, NO REAL MONEY. Long only in V0. With daily bars the order of events INSIDE a bar is unknowable: when an entry and a stop/target (or a
stop and a target that would close part of the position) can both happen in the same bar and the order cannot be determined, the state is
``AMBIGUOUS_INTRABAR``; the favourable reading is never chosen and the possible readings are kept in ``details['ambiguity']``. Gaps are resolved
at the open. Bars must start strictly AFTER the decision session (nothing at or before T0 is traded).

Exit policy (``PlanLevels.exit_policy``): ``TRACK_TARGETS_ONLY`` (touching a target is recorded, the position stays complete), ``PARTIAL_FRACTIONS``
(explicit ``exit_fractions`` per target, sum <= 1) and ``LEGACY_HALF_AT_TP1`` (the V0 behaviour of simulations created before ADR-0036: half at
target 1 when a second target exists). Every step is also emitted as an EVENT (``Evaluation.events``): the event log is the source of truth
that ``fold_events`` replays without any market data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any

import pandas as pd

SIM_ENGINE_VERSION = "sim-engine-2"
OBSERVATION_HORIZONS = (1, 5, 20, 60)  # sessions after the decision (T+1, T+5, T+20, T+60)
EPS = 1e-12


class SimState(StrEnum):
    CREATED = "CREATED"
    WAITING_ENTRY = "WAITING_ENTRY"
    ENTERED = "ENTERED"
    PARTIAL_TP = "PARTIAL_TP"
    TP1 = "TP1"
    TP2 = "TP2"
    TP3 = "TP3"
    STOPPED = "STOPPED"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"
    CLOSED_MANUAL = "CLOSED_MANUAL"
    AMBIGUOUS_INTRABAR = "AMBIGUOUS_INTRABAR"
    CANCELLED = "CANCELLED"


CLOSED = {
    SimState.TP1,
    SimState.TP2,
    SimState.TP3,
    SimState.STOPPED,
    SimState.INVALIDATED,
    SimState.EXPIRED,
    SimState.CLOSED_MANUAL,
    SimState.AMBIGUOUS_INTRABAR,
    SimState.CANCELLED,
}
EXIT_POLICIES = ("TRACK_TARGETS_ONLY", "PARTIAL_FRACTIONS", "LEGACY_HALF_AT_TP1")
ENTRY_TYPES = ("LIMIT", "ENTRY_ZONE", "STOP_BUY", "MARKET", "MARKET_REFERENCE")


@dataclass(frozen=True)
class PlanLevels:
    entry_type: str  # LIMIT (one price) | ENTRY_ZONE | STOP_BUY | MARKET (next open) | MARKET_REFERENCE (the price stored at creation)
    entry_low: float
    entry_high: float
    stop: float
    target_1: float
    target_2: float | None = None
    invalidation: float | None = None
    expiration: date | None = None  # last session on which the simulation is alive
    target_3: float | None = None
    exit_policy: str = "LEGACY_HALF_AT_TP1"
    exit_fractions: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def validate(self) -> None:
        if self.entry_type not in ENTRY_TYPES:
            raise ValueError(f"entry_type must be one of {ENTRY_TYPES}")
        if not (0 < self.stop < self.entry_low <= self.entry_high < self.target_1):
            raise ValueError(
                "levels must satisfy 0 < stop < entry_low <= entry_high < target_1 (long only)"
            )
        if self.entry_type == "MARKET_REFERENCE" and self.entry_low != self.entry_high:
            raise ValueError("MARKET_REFERENCE needs ONE reference price (entry_low == entry_high)")
        if self.target_2 is not None and self.target_2 <= self.target_1:
            raise ValueError("target_2 must be above target_1")
        if self.target_3 is not None and (self.target_2 is None or self.target_3 <= self.target_2):
            raise ValueError("target_3 needs a target_2 and must be above it")
        if self.invalidation is not None and self.invalidation <= 0:
            raise ValueError("invalidation must be positive")
        if self.exit_policy not in EXIT_POLICIES:
            raise ValueError(f"exit_policy must be one of {EXIT_POLICIES}")
        fr = self.exit_fractions
        if any(f < 0 or f > 1 for f in fr) or sum(fr) > 1 + EPS:
            raise ValueError("exit fractions must be in [0, 1] and sum to at most 1")
        for f, t in zip(fr, (self.target_1, self.target_2, self.target_3), strict=True):
            if f > 0 and t is None:
                raise ValueError("an exit fraction needs its target")
        if self.exit_policy != "PARTIAL_FRACTIONS" and any(fr):
            raise ValueError("exit_fractions only apply to PARTIAL_FRACTIONS")

    def targets(self) -> list[tuple[int, float]]:
        return [
            (n, t)
            for n, t in ((1, self.target_1), (2, self.target_2), (3, self.target_3))
            if t is not None
        ]

    def fractions(self) -> dict[int, float]:
        if self.exit_policy == "TRACK_TARGETS_ONLY":
            return {n: 0.0 for n, _ in self.targets()}
        if self.exit_policy == "LEGACY_HALF_AT_TP1":
            return {1: 0.5, 2: 0.5} if self.target_2 is not None else {1: 1.0}
        return {n: f for n, f in zip((1, 2, 3), self.exit_fractions, strict=True)}

    def initial_risk(self, entry: float) -> float:
        return entry - self.stop


@dataclass
class Evaluation:
    state: SimState
    timeline: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    entry_date: date | None = None
    entry_price: float | None = None
    entry_method: str | None = None
    exit_date: date | None = None
    tp1_date: date | None = None
    tp2_date: date | None = None
    tp3_date: date | None = None
    stop_date: date | None = None
    last_bar: date | None = None
    exits: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, float | int | None] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_closed(self) -> bool:
        return self.state in CLOSED


def _t(ev: Evaluation, d: date, state: SimState, note: str) -> None:
    ev.timeline.append({"date": str(d), "state": state.value, "note": note})


def _e(ev: Evaluation, typ: str, d: date, **payload: Any) -> None:
    ev.events.append({"type": typ, "date": str(d), "payload": payload})


def entry_fill(plan: PlanLevels, o: float, h: float, lo: float) -> tuple[float, str] | None:
    """Fill price and method of the entry on a daily bar (LONG), or None. Never uses the close."""
    if plan.entry_type == "MARKET":
        return o, "MARKET_NEXT_OPEN"
    if plan.entry_type == "STOP_BUY":
        if h >= plan.entry_high:
            return (
                (o, "STOP_BUY_GAP") if o >= plan.entry_high else (plan.entry_high, "STOP_BUY_LEVEL")
            )
        return None
    if lo > plan.entry_high:  # price never reached the limit / the top of the zone
        return None
    single = plan.entry_low == plan.entry_high
    if o <= plan.entry_high:
        if single:
            return o, "EXPLICIT_LIMIT" if o == plan.entry_high else "FAVORABLE_GAP"
        if o >= plan.entry_low:
            return o, "OPEN_WITHIN_ZONE"
        return o, "FAVORABLE_GAP"
    return plan.entry_high, ("EXPLICIT_LIMIT" if single else "FIRST_ZONE_TOUCH")


def evaluate(
    plan: PlanLevels,
    bars: pd.DataFrame,
    decision_date: date,
    *,
    benchmark: pd.Series | None = None,
    manual_close: tuple[date, float] | None = None,
    reference_price: float | None = None,
    cancel_on: date | None = None,
) -> Evaluation:
    """``bars``: daily OHLC indexed by session date (the caller passes only completed bars known at the evaluation instant)."""
    plan.validate()
    if len(bars) and bars.index[0] <= decision_date:
        raise ValueError(
            "bars must start strictly after the decision date (no data of T0 or earlier is traded)"
        )
    ev = Evaluation(SimState.CREATED)
    _t(ev, decision_date, SimState.CREATED, "paper trade created (no real money)")
    _e(ev, "SIMULATION_CREATED", decision_date, state_after="CREATED")
    ev.state = SimState.WAITING_ENTRY
    _t(ev, decision_date, SimState.WAITING_ENTRY, "waiting for the entry")
    fr = plan.fractions()
    targets = plan.targets()
    touched: set[int] = set()
    remaining = 1.0
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    risk: float | None = None
    last_close: float | None = None
    n_bar = 0

    def fill_entry(d: date, price: float, method: str) -> None:
        nonlocal risk
        ev.entry_date, ev.entry_price, ev.entry_method = d, price, method
        risk = price - plan.stop
        ev.state = SimState.ENTERED
        _e(ev, "ENTRY_TRIGGERED", d, level=price)
        _e(
            ev,
            "ENTRY_FILLED",
            d,
            price=price,
            fill_method=method,
            initial_risk_per_unit=risk,
            state_after="ENTERED",
        )
        _t(ev, d, SimState.ENTERED, f"entered at {price:.2f} ({method})")

    def exit_remaining(
        d: date, price: float, method: str, state: SimState, reason: str, ev_type: str
    ) -> None:
        nonlocal remaining
        ev.exits.append(
            {
                "date": str(d),
                "fraction": remaining,
                "price": price,
                "method": method,
                "reason": reason,
            }
        )
        _e(ev, ev_type, d, price=price, fill_method=method, reason=reason, state_after=state.value)
        _e(
            ev,
            "EXIT_FILLED",
            d,
            fraction=remaining,
            price=price,
            fill_method=method,
            reason=reason,
            remaining=0.0,
            state_after=state.value,
        )
        remaining = 0.0
        ev.state = state
        _t(ev, d, state, reason)

    def touch(n: int, t: float, d: date, o: float) -> None:
        nonlocal remaining
        touched.add(n)
        setattr(ev, f"tp{n}_date", d)
        gap = o >= t
        method = "TARGET_GAP" if gap else "TARGET_LIMIT"
        px = max(o, t)
        _e(ev, f"TP{n}_TOUCHED", d, target=t, fill_method=method, exit_fraction=fr.get(n, 0.0))
        f = min(fr.get(n, 0.0), remaining)
        if f > EPS:
            remaining -= f
            ev.exits.append(
                {
                    "date": str(d),
                    "fraction": f,
                    "price": px,
                    "method": method,
                    "reason": f"target {n}",
                }
            )
            full = remaining <= EPS
            st = SimState(f"TP{n}") if full else SimState.PARTIAL_TP
            _e(
                ev,
                "PARTIAL_EXIT",
                d,
                target_n=n,
                fraction=f,
                price=px,
                fill_method=method,
                remaining=max(remaining, 0.0),
                state_after=st.value,
            )
            ev.state = st
            _t(ev, d, st, f"target {n} {t:.2f} hit: {f * 100:.0f}% closed at {px:.2f} ({method})")
        else:
            _t(
                ev,
                d,
                ev.state,
                f"target {n} {t:.2f} touched (position unchanged: {plan.exit_policy})",
            )

    def scenarios(
        o: float, hit_targets: list[tuple[int, float]], base_r: float
    ) -> list[dict[str, Any]]:
        assert risk is not None and ev.entry_price is not None
        e = ev.entry_price
        stop_first = base_r + remaining * (plan.stop - e) / risk
        r_t = base_r
        rem = remaining
        for n, t in hit_targets:
            f = min(fr.get(n, 0.0), rem)
            r_t += f * (max(o, t) - e) / risk
            rem -= f
        target_first = r_t + rem * (plan.stop - e) / risk
        return [
            {
                "order": "STOP_FIRST",
                "state": "STOPPED",
                "exit_price": plan.stop,
                "realized_r": stop_first,
            },
            {
                "order": "TARGET_FIRST",
                "state": "STOPPED" if rem > EPS else f"TP{hit_targets[-1][0]}",
                "targets": [n for n, _ in hit_targets],
                "realized_r": target_first,
            },
        ]

    def realized_so_far() -> float:
        assert risk is not None and ev.entry_price is not None
        return float(sum(x["fraction"] * (x["price"] - ev.entry_price) / risk for x in ev.exits))

    def process_bar(d: date, o: float, h: float, lo: float, c: float) -> bool:
        """Post-entry evaluation of ONE bar. Returns True when the trade is closed (or ambiguous)."""
        assert risk is not None and ev.entry_price is not None
        # 1. the open decides gaps (the open precedes everything else in the bar)
        if o <= plan.stop:
            ev.stop_date = d
            _e(ev, "STOP_GAP", d, open=o, stop=plan.stop)
            exit_remaining(
                d,
                o,
                "STOP_GAP",
                SimState.STOPPED,
                "gap down through the stop: filled at the open",
                "STOP_TRIGGERED",
            )
            return True
        for n, t in targets:
            if n not in touched and o >= t:
                touch(n, t, d, o)
        if remaining <= EPS:
            return True
        # 2. inside the bar
        pending = [(n, t) for n, t in targets if n not in touched]
        hit_stop = lo <= plan.stop
        hit_t = [(n, t) for n, t in pending if h >= t]
        exiting = [(n, t) for n, t in hit_t if fr.get(n, 0.0) > EPS]
        if hit_stop and exiting:
            ev.state = SimState.AMBIGUOUS_INTRABAR
            ev.details["ambiguity"] = {
                "date": str(d),
                "kind": "STOP_AND_TARGET_SAME_BAR",
                "scenarios": scenarios(o, hit_t, realized_so_far()),
            }
            _e(
                ev,
                "AMBIGUOUS_INTRABAR",
                d,
                kind="STOP_AND_TARGET_SAME_BAR",
                scenarios=ev.details["ambiguity"]["scenarios"],
                state_after="AMBIGUOUS_INTRABAR",
            )
            _t(
                ev,
                d,
                SimState.AMBIGUOUS_INTRABAR,
                "stop and a target inside the same daily bar: order unknowable",
            )
            return True
        if hit_stop:
            for (
                n,
                t,
            ) in hit_t:  # touches without an exit: their order against the stop is unknown, the outcome (the stop) is not
                touch(n, t, d, o)
            ev.stop_date = d
            if hit_t:
                ev.details["touch_order_unknown"] = {
                    "date": str(d),
                    "targets": [n for n, _ in hit_t],
                }
            exit_remaining(
                d,
                plan.stop,
                "STOP_LEVEL",
                SimState.STOPPED,
                f"stop {plan.stop:.2f} hit",
                "STOP_TRIGGERED",
            )
            return True
        for n, t in hit_t:
            touch(n, t, d, o)
        if remaining <= EPS:
            return True
        if plan.invalidation is not None and c < plan.invalidation:
            exit_remaining(
                d,
                c,
                "INVALIDATION_CLOSE",
                SimState.INVALIDATED,
                f"close {c:.2f} below the invalidation level {plan.invalidation:.2f}",
                "INVALIDATED",
            )
            return True
        return False

    if plan.entry_type == "MARKET_REFERENCE":
        ref = reference_price if reference_price is not None else plan.entry_high
        fill_entry(decision_date, ref, "MARKET_REFERENCE")
        last_close = ref

    for d, b in bars.iterrows():
        o, h, lo, c = float(b["open"]), float(b["high"]), float(b["low"]), float(b["close"])
        if manual_close and d > manual_close[0] and ev.entry_date is not None:
            break
        if cancel_on and d > cancel_on and ev.entry_date is None:
            break  # the cancellation is recorded after the loop
        n_bar += 1
        ev.last_bar = d
        bench_close = (
            float(benchmark.loc[d]) if benchmark is not None and d in benchmark.index else None
        )
        counted: tuple[float, float]
        if ev.entry_date is None:
            if plan.expiration and d > plan.expiration:
                ev.state = SimState.EXPIRED
                _e(ev, "EXPIRED", d, reason="expired before the entry", state_after="EXPIRED")
                _t(ev, d, SimState.EXPIRED, "expired before the entry")
                break
            if plan.invalidation is not None and c < plan.invalidation:
                ev.state = SimState.INVALIDATED
                note = f"close {c:.2f} below the invalidation level {plan.invalidation:.2f} before the entry"
                _e(ev, "INVALIDATED", d, reason=note, state_after="INVALIDATED")
                _t(ev, d, SimState.INVALIDATED, note)
                break
            f = entry_fill(plan, o, h, lo)
            if f is None:
                _e(
                    ev,
                    "BAR_PROCESSED",
                    d,
                    open=o,
                    high=h,
                    low=lo,
                    close=c,
                    bench_close=bench_close,
                    counts_for_excursion=False,
                )
                _observe(ev, n_bar, d, c, None, bench_close, benchmark)
                continue
            fill, method = f
            at_open = fill == o
            fill_entry(d, fill, method)
            risk = fill - plan.stop
            if risk <= 0:
                ev.stop_date = d
                exit_remaining(
                    d,
                    fill,
                    "FILLED_AT_OR_BELOW_STOP",
                    SimState.STOPPED,
                    "filled at or below the stop",
                    "STOP_TRIGGERED",
                )
                _e(
                    ev,
                    "BAR_PROCESSED",
                    d,
                    open=o,
                    high=h,
                    low=lo,
                    close=c,
                    bench_close=bench_close,
                    counts_for_excursion=False,
                )
                break
            if not at_open and (lo <= plan.stop or any(h >= t for _, t in targets)):
                # an intrabar entry with a stop/target also inside the bar: the order is unknowable with daily data
                reach = [n for n, t in targets if h >= t]
                ev.state = SimState.AMBIGUOUS_INTRABAR
                sc = (
                    [
                        {
                            "order": "ENTRY_THEN_STOP",
                            "state": "STOPPED",
                            "exit_price": plan.stop,
                            "realized_r": (plan.stop - fill) / risk,
                        }
                    ]
                    if lo <= plan.stop
                    else []
                )
                sc += [
                    {
                        "order": f"ENTRY_THEN_TARGET_{n}",
                        "target": t,
                        "realized_r": (t - fill) / risk,
                    }
                    for n, t in targets
                    if h >= t
                ]
                ev.details["ambiguity"] = {
                    "date": str(d),
                    "kind": "ENTRY_AND_EXIT_SAME_BAR",
                    "stop_reached": lo <= plan.stop,
                    "targets_reached": reach,
                    "scenarios": sc,
                }
                _e(
                    ev,
                    "AMBIGUOUS_INTRABAR",
                    d,
                    kind="ENTRY_AND_EXIT_SAME_BAR",
                    scenarios=sc,
                    state_after="AMBIGUOUS_INTRABAR",
                )
                _t(
                    ev,
                    d,
                    SimState.AMBIGUOUS_INTRABAR,
                    "entry and stop/target inside the same daily bar: order unknowable with daily data",
                )
                _e(
                    ev,
                    "BAR_PROCESSED",
                    d,
                    open=o,
                    high=h,
                    low=lo,
                    close=c,
                    bench_close=bench_close,
                    counts_for_excursion=False,
                )
                break
            counted = (max(fill, h), min(fill, lo)) if at_open else (max(fill, c), min(fill, c))
            highs, lows, closes = [counted[0]], [counted[1]], [c]
            if at_open:
                _e(
                    ev,
                    "BAR_PROCESSED",
                    d,
                    open=o,
                    high=h,
                    low=lo,
                    close=c,
                    bench_close=bench_close,
                    counts_for_excursion=True,
                    exc_high=counted[0],
                    exc_low=counted[1],
                )
                closed = process_bar(d, o, h, lo, c)
                last_close = c
                _observe(ev, n_bar, d, c, ev.entry_price, bench_close, benchmark)
                if closed:
                    break
            else:
                _e(
                    ev,
                    "BAR_PROCESSED",
                    d,
                    open=o,
                    high=h,
                    low=lo,
                    close=c,
                    bench_close=bench_close,
                    counts_for_excursion=True,
                    exc_high=counted[0],
                    exc_low=counted[1],
                )
                last_close = c
                _observe(ev, n_bar, d, c, ev.entry_price, bench_close, benchmark)
            continue
        # after the entry (the entry bar was handled above)
        if plan.expiration and d > plan.expiration:
            px = last_close if last_close is not None else (ev.entry_price or c)
            ev.details["mark_to_market_return_at_expiration"] = (px - (ev.entry_price or px)) / (
                ev.entry_price or px
            )
            exit_remaining(
                d,
                px,
                "EXPIRY_LAST_CLOSE",
                SimState.EXPIRED,
                "horizon reached: closed at the last close inside the horizon",
                "EXPIRED",
            )
            break
        highs.append(h)
        lows.append(lo)
        closes.append(c)
        _e(
            ev,
            "BAR_PROCESSED",
            d,
            open=o,
            high=h,
            low=lo,
            close=c,
            bench_close=bench_close,
            counts_for_excursion=True,
            exc_high=h,
            exc_low=lo,
        )
        closed = process_bar(d, o, h, lo, c)
        last_close = c
        _observe(ev, n_bar, d, c, ev.entry_price, bench_close, benchmark)
        if closed:
            break
    if cancel_on and ev.entry_date is None and not ev.is_closed:
        ev.state = SimState.CANCELLED
        _e(ev, "CANCELLED", cancel_on, reason="cancelled before the entry", state_after="CANCELLED")
        _t(ev, cancel_on, SimState.CANCELLED, "cancelled by the user before the entry")
    if manual_close and ev.entry_date is not None and not ev.is_closed:
        md, mp = manual_close
        ev.exit_date = md
        rest = remaining
        _e(ev, "MANUAL_CLOSE", md, price=mp, fraction=rest, state_after="CLOSED_MANUAL")
        ev.exits.append(
            {
                "date": str(md),
                "fraction": rest,
                "price": mp,
                "method": "MANUAL",
                "reason": "closed manually",
            }
        )
        _e(
            ev,
            "EXIT_FILLED",
            md,
            fraction=rest,
            price=mp,
            fill_method="MANUAL",
            reason="closed manually",
            remaining=0.0,
            state_after="CLOSED_MANUAL",
        )
        remaining = 0.0
        ev.state = SimState.CLOSED_MANUAL
        _t(ev, md, SimState.CLOSED_MANUAL, f"closed manually at {mp:.2f}")
    if ev.is_closed and ev.exit_date is None:
        ev.exit_date = ev.last_bar
    ev.details["position_remaining"] = remaining if ev.entry_date is not None else None
    _metrics(
        ev, plan, decision_date, highs, lows, closes, benchmark, risk, remaining, last_close, n_bar
    )
    return ev


def _observe(
    ev: Evaluation,
    n: int,
    d: date,
    close: float,
    entry: float | None,
    bench_close: float | None,
    bench: pd.Series | None,
) -> None:
    if n not in OBSERVATION_HORIZONS:
        return
    ret = (close / entry - 1.0) if entry else None
    b_ret = None
    if (
        bench is not None
        and bench_close is not None
        and ev.entry_date is not None
        and ev.entry_date in bench.index
    ):
        b_ret = bench_close / float(bench.loc[ev.entry_date]) - 1.0
    _e(
        ev,
        "OBSERVATION_RECORDED",
        d,
        horizon=f"T+{n}",
        close=close,
        return_since_entry=ret,
        benchmark_return_since_entry=b_ret,
        state=ev.state.value,
    )


def _metrics(
    ev: Evaluation,
    plan: PlanLevels,
    decision_date: date,
    highs: list[float],
    lows: list[float],
    closes: list[float],
    bench: pd.Series | None,
    risk: float | None,
    remaining: float,
    last_close: float | None,
    n_bar: int,
) -> None:
    keys = (
        "realized_return", "excess_return_vs_benchmark", "realized_r", "mfe", "mae", "max_drawdown", "days_to_entry", "days_to_stop", "days_to_tp1", "days_to_tp2",
        "days_to_tp3", "holding_period", "mfe_pct", "mae_pct", "mfe_r", "mae_r", "initial_risk_per_unit", "mark_to_market_return", "days_waiting_entry",
    )  # fmt: skip
    m: dict[str, float | int | None] = {k: None for k in keys}
    ev.metrics = m
    if ev.entry_date is None or ev.entry_price is None:
        m["days_waiting_entry"] = ((ev.last_bar or decision_date) - decision_date).days
        return
    e = ev.entry_price
    m["days_to_entry"] = m["days_waiting_entry"] = (ev.entry_date - decision_date).days
    mx, mn = (max(highs), min(lows)) if highs else (e, e)
    m["mfe"] = (mx - e) / e  # legacy key: favourable excursion as a fraction of the entry
    m["mae"] = (e - mn) / e  # legacy key: POSITIVE adverse excursion
    m["mfe_pct"] = mx / e - 1.0
    m["mae_pct"] = mn / e - 1.0  # NEGATIVE (spec): min(low since entry) / entry - 1
    if risk and risk > 0:
        m["initial_risk_per_unit"] = risk
        m["mfe_r"] = (mx - e) / risk
        m["mae_r"] = (
            mn - e
        ) / risk  # negative; the denominator is the INITIAL risk and never changes
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
        ("days_to_tp3", ev.tp3_date),
    ):
        m[key] = (dt - decision_date).days if dt else None
    end = ev.exit_date or ev.last_bar
    m["holding_period"] = (end - ev.entry_date).days if end else None
    ev.details["return_basis"] = (
        "REALIZED" if ev.is_closed else "UNREALIZED (position still open at the last bar)"
    )
    ev.details["bars_in_trade"] = len(closes)
    ev.details["bars_to_entry"] = None
    parts = [(x["fraction"], x["price"]) for x in ev.exits]
    if not ev.is_closed and last_close is not None and remaining > EPS:
        parts.append((remaining, last_close))
    if parts:
        blended = sum(f * p for f, p in parts) / sum(f for f, _ in parts)
        m["realized_return"] = (blended - e) / e
        m["mark_to_market_return"] = m["realized_return"] if not ev.is_closed else None
        if risk and risk > 0:
            m["realized_r"] = sum(f * (p - e) / risk for f, p in parts) / sum(f for f, _ in parts)
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
    ev.details["targets_touched"] = [
        n for n, d in ((1, ev.tp1_date), (2, ev.tp2_date), (3, ev.tp3_date)) if d
    ]
    ev.details["exit_policy"] = plan.exit_policy
    ev.details["fills"] = {"entry": {"price": e, "method": ev.entry_method}, "exits": ev.exits}
    ev.details["dividends"] = "price return only: dividends are not included in the paper trade"
    ev.details["costs"] = {
        "commission": 0.0,
        "slippage": "only the explicit gap fills",
        "fees": 0.0,
    }


def fold_events(events: list[dict[str, Any]], plan: PlanLevels) -> dict[str, Any]:
    """Rebuild the state and the metrics from the EVENT LOG ONLY (no market data, no engine call). An independent implementation of the fold,
    used by ``simulation-replay`` to check the persisted outcome."""
    state, entry, entry_date, method = "CREATED", None, None, None
    exits: list[tuple[float, float]] = []
    exit_date: str | None = None
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    last_close: float | None = None
    last_bar: str | None = None
    remaining = 1.0
    bench_entry = bench_last = None
    for e in events:
        t, p, d = e["type"], e["payload"], e["date"]
        if "state_after" in p:
            state = p["state_after"]
        if t == "SIMULATION_CREATED":
            state = "WAITING_ENTRY"
        elif t == "ENTRY_FILLED":
            entry, entry_date, method = p["price"], d, p["fill_method"]
        elif t == "PARTIAL_EXIT":
            exits.append((p["fraction"], p["price"]))
            remaining = p["remaining"]
        elif t == "EXIT_FILLED":
            exits.append((p["fraction"], p["price"]))
            remaining = p["remaining"]
            exit_date = d
        elif t == "BAR_PROCESSED":
            last_bar = d
            last_close = p["close"]
            if p.get("bench_close") is not None:
                bench_last = p["bench_close"]
                if entry_date == d and bench_entry is None:
                    bench_entry = p["bench_close"]
            if p.get("counts_for_excursion") and entry is not None:
                highs.append(p["exc_high"])
                lows.append(p["exc_low"])
                closes.append(p["close"])
        elif t in ("AMBIGUOUS_INTRABAR", "EXPIRED", "INVALIDATED"):
            exit_date = exit_date or d
        elif t == "MANUAL_CLOSE":
            exit_date = d
    closed = state in {s.value for s in CLOSED}
    out: dict[str, Any] = {
        "state": state,
        "is_closed": closed,
        "entry_price": entry,
        "entry_date": entry_date,
        "entry_method": method,
        "position_remaining": remaining if entry is not None else None,
    }
    out["exit_date"] = exit_date if closed else None
    if closed and out["exit_date"] is None:
        out["exit_date"] = last_bar
    if entry is None:
        return out
    risk = entry - plan.stop
    parts = list(exits)
    if not closed and last_close is not None and remaining > EPS:
        parts.append((remaining, last_close))
    if parts:
        tot = sum(f for f, _ in parts)
        blended = sum(f * p for f, p in parts) / tot
        out["realized_return"] = (blended - entry) / entry
        out["realized_r"] = (
            sum(f * (p - entry) / risk for f, p in parts) / tot if risk > 0 else None
        )
    mx, mn = (max(highs), min(lows)) if highs else (entry, entry)
    out["mfe"], out["mae"] = (mx - entry) / entry, (entry - mn) / entry
    out["mfe_pct"], out["mae_pct"] = mx / entry - 1.0, mn / entry - 1.0
    if risk > 0:
        out["mfe_r"], out["mae_r"] = (mx - entry) / risk, (mn - entry) / risk
    if closes:
        peak, dd = closes[0], 0.0
        for c in closes:
            peak = max(peak, c)
            dd = max(dd, (peak - c) / peak)
        out["max_drawdown"] = dd
    if (
        bench_entry
        and bench_last
        and out.get("realized_return") is not None
        and out["exit_date"] is not None
    ):
        out["_bench_hint"] = bench_last / bench_entry - 1.0
    return out
