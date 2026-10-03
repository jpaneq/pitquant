# ruff: noqa: E501
"""Simulation Lab V0 service (ADR-0034): PAPER TRADING + forward validation. NO real money, NO broker, NO model change.

* ``create_simulation`` freezes the T0 snapshot (only what the Analyzer knew at ``decision_at``) in an immutable row.
* Outcomes, thesis snapshots, manual closes and post-mortems are SEPARATE append-only tables: the T0 row is never edited with future data.
* AUTO_PAPER exists as a contract and stays DISABLED while the Prediction Engine is NOT_YET_VALIDATED.
* Nothing here writes to datasets, model versions or champions; Research Lab only READS ``evidence_summary``.
"""

from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.analyzer.market import load_market
from pitquant.analyzer.service import AnalyzerService
from pitquant.analyzer.trade_plan_v0 import position_size
from pitquant.config.settings import Settings
from pitquant.core.errors import HoldoutAccessError, PITQuantError
from pitquant.core.timeutils import utc_now
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.db.models import (
    ResearchHypothesis,
    Simulation,
    SimulationObservation,
    SimulationOutcome,
    SimulationPostMortem,
)
from pitquant.market.ca_resolve import (
    collapse_equivalent,  # noqa: F401 — documents that actions are the resolved ones
)
from pitquant.simulation.engine import CLOSED, PlanLevels, evaluate

AUTO_PAPER_ENABLED = False
MIN_N_FOR_STATS = 10
POSTMORTEM_CAUSES = (
    "MODEL_DIRECTION_ERROR", "MODEL_MAGNITUDE_ERROR", "TIMING_ERROR", "ENTRY_ERROR", "STOP_TOO_TIGHT", "STOP_TOO_WIDE", "TARGET_TOO_AGGRESSIVE",
    "VALUATION_ERROR", "FUNDAMENTAL_DETERIORATION", "TECHNICAL_BREAKDOWN", "VOLATILITY_UNDERESTIMATED", "REGIME_CHANGE", "CORPORATE_ACTION",
    "DATA_QUALITY", "UNEXPECTED_EVENT", "NO_CLEAR_ERROR",
)  # fmt: skip


class PriceDataRequired(PITQuantError):
    """No completed price bars: a trade cannot be simulated (e.g. a FUNDAMENTAL_ONLY security)."""


class AutoPaperDisabled(PITQuantError):
    pass


class SimulationError(PITQuantError):
    pass


def _guard(at: datetime, settings: Settings) -> None:
    ho = settings.validation.final_holdout
    if ho.start <= at.date() <= ho.end:
        raise HoldoutAccessError(
            "a simulation cannot be created or evaluated inside the sealed holdout"
        )


def eligibility(
    session: Session, settings: Settings, sid: str, at: datetime | None = None
) -> dict[str, Any]:
    at = at or utc_now()
    n = load_market(session, sid, at).series.n_bars
    return {"enabled": n > 0, "reason": None if n > 0 else "PRICE_DATA_REQUIRED"}


@dataclass
class PlanInput:
    entry_type: str = "LIMIT"
    entry_zone_low: float | None = None
    entry_zone_high: float | None = None
    stop_loss: float | None = None
    invalidation_level: float | None = None
    target_1: float | None = None
    target_2: float | None = None
    target_3_optional: float | None = None


def _pitquant_plan(trade_plan: dict[str, Any], profile: str = "BASE") -> dict[str, Any] | None:
    setups = trade_plan.get("setups") or []
    pick = next((s for s in setups if s.get("profile") == profile), setups[0] if setups else None)
    if pick is None:
        return None
    return {
        "setup_type": pick.get("setup_type") or pick.get("type"), "profile": pick.get("profile"), "entry_type": "LIMIT",
        "entry_zone_low": pick["entry_zone"]["lower"], "entry_zone_high": pick["entry_zone"]["upper"], "stop_loss": pick["stop"],
        "invalidation_level": pick.get("invalidation_level"), "target_1": pick.get("target_1"), "target_2": pick.get("target_2"),
        "risk_reward_1": pick.get("risk_reward_1"), "risk_reward_2": pick.get("risk_reward_2"), "rules_version": pick.get("rules_version"),
    }  # fmt: skip


def create_simulation(
    session: Session,
    settings: Settings,
    security_id: str,
    *,
    plan_origin: str = "PITQUANT",
    plan: PlanInput | None = None,
    at: datetime | None = None,
    capital: float = 100_000.0,
    risk_pct: float = 1.0,
    horizon_sessions: int = 20,
    mode: str = "MANUAL_SIMULATION",
    asset_type: str = "EQUITY",
) -> Simulation:
    at = at or utc_now()
    _guard(at, settings)
    if mode == "AUTO_PAPER" and not AUTO_PAPER_ENABLED:
        raise AutoPaperDisabled(
            "AUTO_PAPER is DISABLED while the Prediction Engine is NOT_YET_VALIDATED"
        )
    if asset_type != "EQUITY":
        raise SimulationError(
            "only EQUITY simulations have an engine in V0 (BTC columns exist but no connector does)"
        )
    if plan_origin not in ("PITQUANT", "USER_MODIFIED", "USER_DEFINED"):
        raise SimulationError("plan_origin must be PITQUANT, USER_MODIFIED or USER_DEFINED")
    svc = AnalyzerService(session, settings)
    md = svc._md(security_id, at)
    if md.series.n_bars == 0:
        raise PriceDataRequired("PRICE_DATA_REQUIRED: no completed price bars for this security")
    tech, fund, val = (
        svc.technicals(security_id, at),
        svc.fundamentals(security_id, at),
        svc.valuation(security_id, at),
    )
    tplan, quote = svc.trade_plan(security_id, at), svc.quote(security_id, at)
    original = _pitquant_plan(tplan)
    base: dict[str, Any] = dict(original or {})
    if plan_origin in ("PITQUANT", "USER_MODIFIED") and original is None:
        raise SimulationError(
            "NO_PITQUANT_PLAN: the Analyzer offers no setup for this security at this date; define the levels yourself (USER_DEFINED)"
        )
    if plan_origin == "USER_DEFINED":
        base = {}
    if plan:
        for k, v in asdict(plan).items():
            if v is not None and (k != "entry_type" or plan_origin != "PITQUANT"):
                base[k] = v
    final = {
        k: base.get(k)
        for k in (
            "entry_type",
            "entry_zone_low",
            "entry_zone_high",
            "stop_loss",
            "invalidation_level",
            "target_1",
            "target_2",
            "target_3_optional",
        )
    }
    final["entry_type"] = str(final["entry_type"] or "LIMIT")
    levels = PlanLevels(
        str(final["entry_type"]),
        float(final["entry_zone_low"] or 0),
        float(final["entry_zone_high"] or 0),
        float(final["stop_loss"] or 0),
        float(final["target_1"] or 0),
        final["target_2"],
        final["invalidation_level"],
    )
    try:
        levels.validate()
    except ValueError as e:
        raise SimulationError(str(e)) from e
    sizing = position_size(capital, risk_pct, levels.entry_high, levels.stop)
    if sizing.get("status") != "OK":
        raise SimulationError(sizing.get("reason", "invalid position sizing inputs"))
    cal = get_calendar(md.exchange)
    last = md.series.last_session
    assert last is not None
    sessions = cal.sessions(last, cal.last_session)
    exp_session = sessions[min(horizon_sessions, len(sessions) - 1)]
    bench = svc._bench(at)
    risk_per = levels.entry_high - levels.stop
    sim = Simulation(
        mode=mode, security_id=security_id, asset_type=asset_type, decision_at=at, analyzer_version="analyzer-v0", feature_version=svc.versions()["feature_engine_version"], model_id=None, model_version=None,
        rules_version=svc.versions()["trade_plan_version"], prediction_status="NOT_YET_VALIDATED",
        price_snapshot=quote, fundamental_snapshot=fund, technical_snapshot=tech, valuation_snapshot=val, support_resistance_snapshot=tech.get("support_resistance") or {}, trade_plan_snapshot=tplan,
        market_regime_snapshot={"trend": tech.get("trend"), "risk": tech.get("risk"), "volume": tech.get("volume"), "overextension": tech.get("overextension")},
        data_quality=svc.data_quality(security_id, at), funding_snapshot=None, open_interest_snapshot=None, basis_snapshot=None, onchain_snapshot=None,
        plan_origin=plan_origin, original_pitquant_plan=original if plan_origin == "USER_MODIFIED" else (original if plan_origin == "PITQUANT" else None), final_simulated_plan=final, side="LONG", entry_type=final["entry_type"],
        entry_zone_low=levels.entry_low, entry_zone_high=levels.entry_high, entry_price_actual=None, stop_loss=levels.stop, invalidation_level=levels.invalidation, target_1=levels.target_1, target_2=levels.target_2,
        target_3_optional=final["target_3_optional"], risk_reward_expected=((levels.target_1 - levels.entry_high) / risk_per) if risk_per > 0 else None, position_size_simulated=float(sizing["shares"]),
        capital_at_risk=float(sizing["actual_risk"]), time_horizon_sessions=horizon_sessions, expiration_at=datetime(exp_session.year, exp_session.month, exp_session.day, 23, 59, tzinfo=UTC), benchmark_security_id=bench[0].security_id if bench[0] else None,
        created_at=max(utc_now(), at),
    )  # fmt: skip
    session.add(sim)
    session.flush()
    return sim


def _bars_after(
    session: Session, sim: Simulation, as_of: datetime
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    md = load_market(session, sim.security_id, as_of)
    bars = md.bars.loc[
        md.bars.index > sim.decision_at.date(), ["open", "high", "low", "close"]
    ].copy()
    notes: list[dict[str, Any]] = []
    for a in md.actions:
        kind = str(getattr(a.kind, "value", a.kind))
        ex = getattr(a, "ex_date", None)
        ratio = getattr(a, "ratio", None)
        if (
            kind in ("SPLIT", "REVERSE_SPLIT")
            and ex
            and ratio
            and sim.decision_at.date() < ex <= as_of.date()
        ):
            bars.loc[bars.index >= ex, ["open", "high", "low", "close"]] *= (
                ratio  # restate post-split prices in T0 units
            )
            notes.append({"corporate_action": kind, "ex_date": str(ex), "ratio": ratio})
    return bars, notes


def _manual_close(session: Session, sim: Simulation) -> tuple[date, float] | None:
    ob = session.scalars(
        select(SimulationObservation)
        .where(
            SimulationObservation.simulation_id == sim.simulation_id,
            SimulationObservation.kind == "MANUAL_CLOSE",
        )
        .order_by(SimulationObservation.observed_at)
    ).first()
    if ob is None:
        return None
    return date.fromisoformat(ob.payload["date"]), float(ob.payload["price"])


def evaluate_simulation(
    session: Session, settings: Settings, simulation_id: str, as_of: datetime | None = None
) -> SimulationOutcome:
    sim = session.get_one(Simulation, simulation_id)
    as_of = as_of or utc_now()
    _guard(as_of, settings)
    if as_of < sim.decision_at:
        raise SimulationError("cannot evaluate before the decision time")
    bars, notes = _bars_after(session, sim, as_of)
    bench = None
    if sim.benchmark_security_id:
        bmd = load_market(session, sim.benchmark_security_id, as_of)
        bench = bmd.bars["close"]
    levels = PlanLevels(
        sim.entry_type,
        sim.entry_zone_low,
        sim.entry_zone_high,
        sim.stop_loss,
        sim.target_1,
        sim.target_2,
        sim.invalidation_level,
        sim.expiration_at.date(),
    )
    ev = evaluate(
        levels,
        bars,
        sim.decision_at.date(),
        benchmark=bench,
        manual_close=_manual_close(session, sim),
    )
    if notes:
        ev.details["corporate_actions"] = notes
    m = ev.metrics
    out = SimulationOutcome(
        simulation_id=sim.simulation_id, evaluated_at=as_of, state=ev.state.value, is_closed=ev.state in CLOSED, entry_date=ev.entry_date, entry_price=ev.entry_price, exit_date=ev.exit_date,
        realized_return=m.get("realized_return"), excess_return_vs_benchmark=m.get("excess_return_vs_benchmark"), realized_r=m.get("realized_r"), mfe=m.get("mfe"), mae=m.get("mae"), max_drawdown=m.get("max_drawdown"),
        days_to_entry=m.get("days_to_entry"), days_to_stop=m.get("days_to_stop"), days_to_tp1=m.get("days_to_tp1"), days_to_tp2=m.get("days_to_tp2"), holding_period=m.get("holding_period"),
        prediction_direction_correct=None, trade_plan_execution_correct=None, timeline=ev.timeline, details={**ev.details, "bars_used": len(bars), "paper_trade": "NO REAL MONEY"},
    )  # fmt: skip
    session.add(out)
    session.flush()
    return out


def close_manual(
    session: Session,
    settings: Settings,
    simulation_id: str,
    *,
    at: datetime,
    price: float,
    reason: str = "",
) -> SimulationObservation:
    sim = session.get_one(Simulation, simulation_id)
    _guard(at, settings)
    if price <= 0 or at < sim.decision_at:
        raise SimulationError("invalid manual close")
    ob = SimulationObservation(
        simulation_id=simulation_id,
        observed_at=at,
        kind="MANUAL_CLOSE",
        payload={"date": str(at.date()), "price": price, "reason": reason},
    )
    session.add(ob)
    session.flush()
    return ob


def thesis_snapshot(
    session: Session, settings: Settings, simulation_id: str, at: datetime | None = None
) -> SimulationObservation:
    """A LATER analysis next to the T0 one. The T0 row is untouched; the comparison lists what changed."""
    sim = session.get_one(Simulation, simulation_id)
    at = at or utc_now()
    _guard(at, settings)
    if at < sim.decision_at:
        raise SimulationError("a thesis snapshot cannot precede the decision")
    svc = AnalyzerService(session, settings)
    tech, fund, val = (
        svc.technicals(sim.security_id, at),
        svc.fundamentals(sim.security_id, at),
        svc.valuation(sim.security_id, at),
    )
    t0_trend = (sim.technical_snapshot.get("trend") or {}).get("state")
    now_trend = (tech.get("trend") or {}).get("state")
    t0_vol = (sim.technical_snapshot.get("risk") or {}).get("vol_ann") or (
        sim.technical_snapshot.get("risk") or {}
    ).get("realized_vol_63d")
    now_vol = (tech.get("risk") or {}).get("vol_ann") or (tech.get("risk") or {}).get(
        "realized_vol_63d"
    )
    comparison = {
        "trend_break": bool(t0_trend and now_trend and t0_trend != now_trend), "trend": [t0_trend, now_trend], "volatility": [t0_vol, now_vol],
        "fundamental_status": [sim.fundamental_snapshot.get("status"), fund.get("status")], "valuation_status": [sim.valuation_snapshot.get("status"), val.get("status")],
        "regime_change": (sim.market_regime_snapshot.get("trend") or {}).get("state") != now_trend,
        "invalidated_level_breached": bool(sim.invalidation_level and (tech.get("last_close_split_adjusted") or 1e18) < sim.invalidation_level),
    }  # fmt: skip
    ob = SimulationObservation(
        simulation_id=simulation_id,
        observed_at=at,
        kind="THESIS_SNAPSHOT",
        payload={
            "technical": tech,
            "fundamental": fund,
            "valuation": val,
            "comparison": comparison,
        },
    )
    session.add(ob)
    session.flush()
    return ob


def latest_outcome(session: Session, simulation_id: str) -> SimulationOutcome | None:
    return session.scalars(
        select(SimulationOutcome)
        .where(SimulationOutcome.simulation_id == simulation_id)
        .order_by(SimulationOutcome.evaluated_at.desc(), SimulationOutcome.created_at.desc())
    ).first()


def classify_postmortem(
    session: Session,
    simulation_id: str,
    *,
    primary_cause: str,
    secondary_causes: list[str] | None = None,
    notes: str = "",
    classified_by: str,
) -> SimulationPostMortem:
    """Explicit and auditable (who classified it). Allowed only for a CLOSED simulation. No automatic verdict."""
    secondary = secondary_causes or []
    for c in (primary_cause, *secondary):
        if c not in POSTMORTEM_CAUSES:
            raise SimulationError(f"unknown post-mortem cause {c!r}")
    out = latest_outcome(session, simulation_id)
    if out is None or not out.is_closed:
        raise SimulationError("a post-mortem needs a CLOSED simulation (evaluate it first)")
    pm = SimulationPostMortem(
        simulation_id=simulation_id, primary_cause=primary_cause, secondary_causes=secondary, notes=notes or None, classified_by=classified_by,
        metrics={k: getattr(out, k) for k in ("state", "realized_return", "realized_r", "mfe", "mae", "max_drawdown", "holding_period")},
    )  # fmt: skip
    session.add(pm)
    session.flush()
    return pm


def propose_hypothesis(
    session: Session, *, statement: str, evidence: dict[str, Any], created_by: str
) -> ResearchHypothesis:
    """A ResearchHypothesis from simulation patterns. Never promotes a model: Challenger -> backtest -> walk-forward -> Champion comparison -> HUMAN promotion."""
    h = ResearchHypothesis(
        source="SIMULATION_PATTERN",
        statement=statement[:1000],
        evidence=evidence,
        status="PROPOSED",
        created_by=created_by,
    )
    session.add(h)
    session.flush()
    return h


@dataclass
class SimulationEvidenceSummary:
    """READ-ONLY interface for the Research Lab. No training ingestion, no dataset, no model or champion is touched."""

    n_simulations: int
    n_closed: int
    n_entered_closed: int
    by_state: dict[str, int]
    stats_available: bool
    hit_rate: float | None = None
    mean_r: float | None = None
    mean_return: float | None = None
    mean_excess_return: float | None = None
    mean_mae: float | None = None
    mean_mfe: float | None = None
    min_n: int = MIN_N_FOR_STATS
    note: str = "paper trades: forward evidence only; never a training label"


def evidence_summary(session: Session, min_n: int = MIN_N_FOR_STATS) -> SimulationEvidenceSummary:
    sims = list(session.scalars(select(Simulation.simulation_id)))
    latest = [o for o in (latest_outcome(session, s) for s in sims) if o is not None]
    by_state: dict[str, int] = {}
    for o in latest:
        by_state[o.state] = by_state.get(o.state, 0) + 1
    entered = [
        o
        for o in latest
        if o.is_closed and o.entry_date is not None and o.realized_return is not None
    ]
    s = SimulationEvidenceSummary(
        len(sims),
        sum(o.is_closed for o in latest),
        len(entered),
        by_state,
        len(entered) >= min_n,
        min_n=min_n,
    )
    if s.stats_available:

        def mean(xs: list[float]) -> float | None:
            return statistics.fmean(xs) if xs else None

        s.hit_rate = sum(1 for o in entered if (o.realized_return or 0) > 0) / len(entered)
        s.mean_r = mean([o.realized_r for o in entered if o.realized_r is not None])
        s.mean_return = mean([o.realized_return for o in entered if o.realized_return is not None])
        s.mean_excess_return = mean(
            [
                o.excess_return_vs_benchmark
                for o in entered
                if o.excess_return_vs_benchmark is not None
            ]
        )
        s.mean_mae = mean([o.mae for o in entered if o.mae is not None])
        s.mean_mfe = mean([o.mfe for o in entered if o.mfe is not None])
    return s
