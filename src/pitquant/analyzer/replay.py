# ruff: noqa: E501
"""Retrospective signal replay + forward paper markers for the Analyzer chart (ADR-0040).

* RETROSPECTIVE replay: at sampled past sessions T the Trade Plan V0 is rebuilt with ONLY bars known at T (``AnalyzerService.trade_plan(sid, T)``), the BASE setup is picked exactly like
  a real simulation (``simulation.service._pitquant_plan``) and the plan is played on the bars AFTER T with the registered, frozen simulation engine. Nothing is written to the database:
  these are NOT simulations and never reach Insights/evidence. They are labelled ``RETROSPECTIVE_NOT_PIT`` (prices were downloaded after the fact) and
  ``RULE_BASED_NOT_BACKTEST_VALIDATED``.
* The sealed holdout is never touched: a decision inside it, or whose paper-trade window reaches it, is skipped and counted (``holdout_skipped``), never plotted.
* FORWARD markers come from real paper simulations of the security (manual or AUTO_PAPER), never from the replay.
* Policy: ONE trade at a time (a decision is skipped while a previous plan is pending or open); exits PARTIAL_FRACTIONS 50 % at TP1 / 50 % at TP2; no costs (``COSTS_NOT_MODELED``).
"""

from __future__ import annotations

from datetime import date, datetime
from statistics import mean, median
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.analyzer.market import load_market
from pitquant.analyzer.service import AnalyzerService, clear_cache
from pitquant.config.settings import Settings
from pitquant.core.timeutils import utc_now
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.db.models import Simulation
from pitquant.simulation import registry
from pitquant.simulation import service as sim
from pitquant.simulation.engine import PlanLevels

REPLAY_VERSION = "signal-replay-1"
MAX_DECISIONS = 400
MIN_CLOSED = 10
EXIT_KIND = {"target 1": "TP", "target 2": "TP", "target 3": "TP"}


def exit_kind(reason: str) -> str:
    r = reason.lower()
    if r.startswith("target"):
        return "TP"
    if "stop" in r:
        return "STOP"
    if "invalid" in r:
        return "INVALIDATION"
    if "expir" in r or "horizon" in r:
        return "EXPIRY"
    return "OTHER"


def split_factor(notes: list[dict[str, Any]]) -> float:
    """Cumulative split ratio after the decision: decision-date units / chart (today, split-adjusted) units."""
    f = 1.0
    for n in notes:
        f *= float(n["ratio"])
    return f


def _trade(d: date, plan: dict[str, Any], ev: Any, notes: list[dict[str, Any]]) -> dict[str, Any]:
    fac = split_factor(notes)
    m = ev.metrics
    t: dict[str, Any] = {
        "decision_date": str(d), "setup_type": plan.get("setup_type"), "profile": plan.get("profile"), "entry_zone": [plan["entry_zone_low"], plan["entry_zone_high"]], "stop": plan["stop_loss"], "target_1": plan.get("target_1"), "target_2": plan.get("target_2"),
        "state": ev.state.value, "entry_date": str(ev.entry_date) if ev.entry_date else None, "entry_price": ev.entry_price, "exit_date": str(ev.exit_date) if ev.exit_date else None,
        "exits": [{**x, "kind": exit_kind(str(x.get("reason", ""))), "price_chart": x["price"] / fac} for x in ev.exits], "realized_return": m.get("realized_return"), "realized_r": m.get("realized_r"),
        "mae_pct": m.get("mae_pct"), "mfe_pct": m.get("mfe_pct"), "bars_to_entry": ev.bars_to_entry, "split_factor": fac, "closed": ev.is_closed, "price_units": "DECISION_DATE_UNITS",
    }  # fmt: skip
    if ev.entry_price:
        t["entry_price_chart"] = ev.entry_price / fac
    return t


def markers_of(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for t in trades:
        if t["entry_date"]:
            out.append(
                {
                    "time": t["entry_date"],
                    "kind": "ENTRY",
                    "origin": "RETROSPECTIVE",
                    "price": t.get("entry_price_chart"),
                    "text": f"{t['setup_type']} entry",
                }
            )
        for x in t["exits"]:
            out.append(
                {
                    "time": x["date"],
                    "kind": f"EXIT_{x['kind']}",
                    "origin": "RETROSPECTIVE",
                    "price": x["price_chart"],
                    "text": f"{x['reason']} · {x['fraction']:.0%}",
                }
            )
    return sorted(out, key=lambda m: m["time"])  # fmt: skip


def summarize(
    trades: list[dict[str, Any]],
    n_decisions: int,
    counts: dict[str, int],
    buy_hold: float | None,
    span: tuple[str, str] | None,
) -> dict[str, Any]:
    filled = [t for t in trades if t["entry_date"]]
    closed = [t for t in filled if t["closed"] and t["realized_return"] is not None]
    s: dict[str, Any] = {"n_decisions": n_decisions, "n_filled": len(filled), "n_closed": len(closed), "n_not_filled": sum(1 for t in trades if not t["entry_date"]), **counts, "buy_and_hold_return_same_span": buy_hold, "span": span}  # fmt: skip
    flags = [
        "RETROSPECTIVE_NOT_PIT",
        "RULE_BASED_NOT_BACKTEST_VALIDATED",
        "COSTS_NOT_MODELED",
        "ONE_TRADE_AT_A_TIME",
    ]
    if len(closed) < MIN_CLOSED:
        flags.append("INSUFFICIENT_SAMPLE")  # no rate is quoted from fewer than 10 closed trades
    else:
        rets = [t["realized_return"] for t in closed]
        s |= {"hit_rate": sum(1 for r in rets if r > 0) / len(rets), "mean_return": mean(rets), "median_return": median(rets), "mean_r": mean(t["realized_r"] for t in closed if t["realized_r"] is not None) if any(t["realized_r"] is not None for t in closed) else None}  # fmt: skip
    s["flags"] = flags
    return s


_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}


def cached_replay(
    session: Session, settings: Settings, security_id: str, start: date, end: date, **kw: Any
) -> dict[str, Any]:
    """Memoised per (security, window, parameters, last completed bar): a new bar changes the key, so results are never stale."""
    now = utc_now()
    last = load_market(session, security_id, now).last_session
    key = (security_id, start, end, tuple(sorted(kw.items())), last)
    if key not in _CACHE:
        if len(_CACHE) >= 32:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = retrospective_replay(
            session, settings, security_id, start, end, now=now, **kw
        )
    return _CACHE[key]


def retrospective_replay(
    session: Session, settings: Settings, security_id: str, start: date, end: date, *, step_sessions: int = 5, horizon_sessions: int = 20, profile: str = "BASE", now: datetime | None = None
) -> dict[str, Any]:  # fmt: skip
    now = now or utc_now()
    ho = settings.validation.final_holdout
    cal = get_calendar("XNYS")
    svc = AnalyzerService(session, settings)
    md = load_market(session, security_id, now)
    base: dict[str, Any] = {"version": REPLAY_VERSION, "label": "RETROSPECTIVE · RULE_BASED · NOT BACKTEST VALIDATED", "params": {"start": str(start), "end": str(end), "step_sessions": step_sessions, "horizon_sessions": horizon_sessions, "profile": profile, "exit_policy": "PARTIAL_FRACTIONS 50/50 at TP1/TP2", "engine": registry.CURRENT_SIMULATION_ENGINE_VERSION}, "writes_to_database": False}  # fmt: skip
    if md.series.n_bars == 0:
        return {**base, "status": "NO_DATA", "trades": [], "markers": [], "summary": None}
    idx = list(md.bars.index)
    in_range = [d for d in idx if start <= d <= end]
    decisions = in_range[::step_sessions]
    if len(decisions) > MAX_DECISIONS:
        raise ValueError(
            f"TOO_MANY_DECISIONS: {len(decisions)} > {MAX_DECISIONS}; widen step_sessions or narrow the range"
        )
    pos = {d: i for i, d in enumerate(idx)}
    trades: list[dict[str, Any]] = []
    counts = {"holdout_skipped": 0, "no_plan": 0, "invalid_plan": 0, "skipped_in_position": 0}
    busy_until: date | None = None
    for d in decisions:
        if busy_until is not None and d <= busy_until:
            counts["skipped_in_position"] += 1
            continue
        exp = idx[min(pos[d] + horizon_sessions, len(idx) - 1)]
        if ho.start <= d <= ho.end or (d < ho.start <= exp):
            counts["holdout_skipped"] += 1
            continue
        plan = sim._pitquant_plan(
            svc.trade_plan(security_id, cal.session_close(d)), profile
        )  # only bars known at the close of d
        if plan is None:
            counts["no_plan"] += 1
            continue
        bars, notes = sim.restated_bars(md, d, now)
        bars = bars[
            bars.index <= exp
        ]  # the trade cannot outlive its horizon; bars past it are never shown to the engine
        lo, hi = float(plan["entry_zone_low"]), float(plan["entry_zone_high"])
        levels = PlanLevels("LIMIT" if lo == hi else "ENTRY_ZONE", lo, hi, float(plan["stop_loss"]), float(plan["target_1"]), plan.get("target_2"), plan.get("invalidation_level"), exp, None, "PARTIAL_FRACTIONS", (0.5, 0.5, 0.0))  # fmt: skip
        try:
            ev = registry.current_engine().evaluate(levels, bars, d)
        except ValueError:
            counts["invalid_plan"] += 1
            continue
        t = _trade(d, plan, ev, notes)
        trades.append(t)
        busy_until = ev.exit_date if ev.entry_date and ev.is_closed and ev.exit_date else exp
    clear_cache()  # the per-date engine caches hold full market frames: do not keep hundreds of them
    ents = [t["entry_date"] for t in trades if t["entry_date"]]
    span = (
        (min(ents), max([t["exit_date"] or t["entry_date"] for t in trades if t["entry_date"]]))
        if ents
        else None
    )
    bh = None
    if span:
        c = md.series.split_adjusted["close"]
        w = c[(c.index >= date.fromisoformat(span[0])) & (c.index <= date.fromisoformat(span[1]))]
        bh = float(w.iloc[-1] / w.iloc[0] - 1.0) if len(w) >= 2 else None
    return {
        **base,
        "status": "OK",
        "trades": trades,
        "markers": markers_of(trades),
        "summary": summarize(trades, len(decisions), counts, bh, span),
    }


def forward_markers(
    session: Session, security_id: str, now: datetime | None = None
) -> list[dict[str, Any]]:
    """Real paper trades of this security (manual or AUTO_PAPER; never synthetic). Plan = decision date; entry/exit from the stored outcome."""
    now = now or utc_now()
    md = load_market(session, security_id, now)
    out: list[dict[str, Any]] = []
    for row in session.scalars(
        select(Simulation)
        .where(Simulation.security_id == security_id, Simulation.is_synthetic.is_(False))
        .order_by(Simulation.decision_at)
    ):
        o = sim.latest_outcome(session, row.simulation_id)
        _, notes = sim.restated_bars(md, row.decision_at.date(), now)
        fac = split_factor(notes)
        base = {"origin": row.mode, "simulation_id": row.simulation_id}
        out.append(
            {
                **base,
                "time": str(row.decision_at.date()),
                "kind": "PLAN",
                "price": row.entry_zone_high / fac,
                "text": f"{row.mode} plan",
            }
        )
        if o and o.entry_date:
            out.append(
                {
                    **base,
                    "time": str(o.entry_date),
                    "kind": "ENTRY",
                    "price": (o.entry_price or 0) / fac,
                    "text": f"{row.mode} entry",
                }
            )
        if o and o.is_closed and o.exit_date and o.entry_date:
            out.append(
                {
                    **base,
                    "time": str(o.exit_date),
                    "kind": "EXIT",
                    "price": None,
                    "text": f"{o.state} · {o.realized_return:.2%}"
                    if o.realized_return is not None
                    else str(o.state),
                }
            )
    return out
