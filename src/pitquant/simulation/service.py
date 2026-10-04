# ruff: noqa: E501
"""Simulation Lab V0 service (ADR-0034): PAPER TRADING + forward validation. NO real money, NO broker, NO model change.

* ``create_simulation`` freezes the T0 snapshot (only what the Analyzer knew at ``decision_at``) in an immutable row.
* Outcomes, thesis snapshots, manual closes and post-mortems are SEPARATE append-only tables: the T0 row is never edited with future data.
* AUTO_PAPER exists as a contract and stays DISABLED while the Prediction Engine is NOT_YET_VALIDATED.
* Nothing here writes to datasets, model versions or champions; Research Lab only READS ``evidence_summary``.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from dataclasses import asdict, dataclass, field
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
    Security,
    SecurityProfile,
    Simulation,
    SimulationCounterfactual,
    SimulationEvent,
    SimulationObservation,
    SimulationOutcome,
    SimulationPostMortem,
)
from pitquant.market.ca_resolve import (
    collapse_equivalent,  # noqa: F401 — documents that actions are the resolved ones
)
from pitquant.simulation import registry
from pitquant.simulation.engine import (
    CLOSED,
    Evaluation,
    PlanLevels,
    SimState,
)
from pitquant.simulation.observations import (
    ANALYZER_VERSION,
    record_observations,
    thesis_facts,
    trend_flip,
)

AUTO_PAPER_ENABLED = (
    False  # legacy global switch: kept False; AUTO_PAPER needs an ``AutoPaperAuthority`` (ADR-0039)
)


@dataclass(frozen=True)
class AutoPaperAuthority:
    """Why an AUTO_PAPER trade may exist: a strategy decision of an allowed kind. Nothing else opens one."""

    strategy_id: str
    strategy_version: int
    family: str
    run_kind: str
    decision_id: str | None = None

    def allowed(self) -> tuple[bool, str]:
        if self.run_kind == "SYNTHETIC":
            return True, "SYNTHETIC run (fixture data, never evidence)"
        if self.family == "TRADE_PLAN_ONLY":
            return True, "TRADE_PLAN_ONLY needs no prediction"
        return (
            False,
            "AUTO_PAPER_PREDICTION = DISABLED_NOT_VALIDATED (the Prediction Engine is NOT_YET_VALIDATED)",
        )


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
    entry_price: float | None = None  # LIMIT / MARKET_REFERENCE: one price (zone low = zone high)
    exit_policy: str | None = None  # TRACK_TARGETS_ONLY (default) | PARTIAL_FRACTIONS
    exit_fractions: list[float] | None = None  # per target, sum <= 1 (PARTIAL_FRACTIONS)


HYPOTHESIS_STATES = ("UNTESTED", "TESTING", "SUPPORTED", "NOT_SUPPORTED")


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
    sizing_mode: str = "RISK_BASED",
    notional: float | None = None,
    authority: AutoPaperAuthority | None = None,
) -> Simulation:
    at = at or utc_now()
    _guard(at, settings)
    if mode == "AUTO_PAPER":
        # AUTO_PAPER is gated by AUTHORITY, not by a global flag: only a TRADE_PLAN_ONLY strategy decision (no model needed) or a SYNTHETIC run may open one;
        # prediction-based real runs stay AUTO_PAPER_PREDICTION = DISABLED_NOT_VALIDATED. A bare mode="AUTO_PAPER" is always refused.
        ok, why = authority.allowed() if authority is not None else (False, "no strategy authority")
        if not ok:
            raise AutoPaperDisabled(f"AUTO_PAPER is DISABLED_NOT_VALIDATED: {why}")
    if asset_type != "EQUITY":
        raise SimulationError(
            "only EQUITY simulations have an engine in V0 (BTC columns exist but no connector does)"
        )
    if plan_origin not in ("PITQUANT", "USER_MODIFIED", "USER_DEFINED"):
        raise SimulationError("plan_origin must be PITQUANT, USER_MODIFIED or USER_DEFINED")
    engine = registry.current_engine()  # the engine this NEW simulation is bound to for ever
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
    final: dict[str, Any] = {
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
    if final["entry_type"] == "ENTRY_ZONE" and not (
        final["entry_zone_low"] and final["entry_zone_high"]
    ):
        raise SimulationError("ENTRY_ZONE needs entry_zone_low and entry_zone_high")
    px_now = float(quote.get("price") or 0.0)
    one_price = base.get("entry_price")
    if final["entry_type"] == "MARKET_REFERENCE":
        # the price shown/stored at creation (never replaced later by a revised close)
        one_price = one_price or px_now
    if one_price:
        final["entry_zone_low"] = final["entry_zone_high"] = float(one_price)
    final["exit_policy"] = str(base.get("exit_policy") or "TRACK_TARGETS_ONLY")
    final["exit_fractions"] = [float(x) for x in (base.get("exit_fractions") or [0.0, 0.0, 0.0])][
        :3
    ]
    final["exit_fractions"] += [0.0] * (3 - len(final["exit_fractions"]))
    levels = PlanLevels(
        str(final["entry_type"]),
        float(final["entry_zone_low"] or 0),
        float(final["entry_zone_high"] or 0),
        float(final["stop_loss"] or 0),
        float(final["target_1"] or 0),
        final["target_2"],
        final["invalidation_level"],
        None,
        final["target_3_optional"],
        final["exit_policy"],
        (final["exit_fractions"][0], final["exit_fractions"][1], final["exit_fractions"][2]),
    )
    try:
        levels.validate()
    except ValueError as e:
        raise SimulationError(str(e)) from e
    sizing: dict[str, Any]
    if sizing_mode == "FIXED_NOTIONAL":
        if not notional or notional <= 0:
            raise SimulationError("FIXED_NOTIONAL needs a positive notional")
        shares = math.floor(notional / levels.entry_high)
        if shares < 1:
            raise SimulationError("the notional does not buy one share")
        sizing = {
            "status": "OK",
            "shares": shares,
            "actual_risk": shares * (levels.entry_high - levels.stop),
            "notional": shares * levels.entry_high,
        }
    elif sizing_mode == "RISK_BASED":
        sizing = position_size(capital, risk_pct, levels.entry_high, levels.stop)
    else:
        raise SimulationError("sizing_mode must be FIXED_NOTIONAL or RISK_BASED")
    if sizing.get("status") != "OK":
        raise SimulationError(sizing.get("reason", "invalid position sizing inputs"))
    final["sizing"] = {
        "mode": sizing_mode,
        "capital": capital,
        "risk_pct": risk_pct,
        "notional": sizing.get("notional"),
        "shares": sizing["shares"],
    }
    rr_ref = levels.entry_high - levels.stop
    final["risk_reward"] = {f"tp{n}": (t - levels.entry_high) / rr_ref for n, t in levels.targets()}
    final["stop_distance_pct"] = rr_ref / levels.entry_high
    cal = get_calendar(md.exchange)
    last = md.series.last_session
    assert last is not None
    sessions = cal.sessions(last, cal.last_session)
    exp_session = sessions[min(horizon_sessions, len(sessions) - 1)]
    bench = svc._bench(at)
    risk_per = levels.entry_high - levels.stop
    sim = Simulation(
        mode=mode, security_id=security_id, asset_type=asset_type, decision_at=at, analyzer_version=ANALYZER_VERSION, feature_version=svc.versions()["feature_engine_version"], model_id=None, model_version=None,
        rules_version=svc.versions()["trade_plan_version"], prediction_status="NOT_YET_VALIDATED",
        simulation_engine_version=engine.version,
        price_snapshot=quote, fundamental_snapshot=fund, technical_snapshot=tech, valuation_snapshot=val, support_resistance_snapshot=tech.get("support_resistance") or {}, trade_plan_snapshot=tplan,
        market_regime_snapshot={"trend": tech.get("trend"), "risk": tech.get("risk"), "volume": tech.get("volume"), "overextension": tech.get("overextension")},
        data_quality=svc.data_quality(security_id, at), funding_snapshot=None, open_interest_snapshot=None, basis_snapshot=None, onchain_snapshot=None,
        plan_origin=plan_origin, original_pitquant_plan=original if plan_origin == "USER_MODIFIED" else (original if plan_origin == "PITQUANT" else None), final_simulated_plan=final, side="LONG", entry_type=final["entry_type"],
        entry_zone_low=levels.entry_low, entry_zone_high=levels.entry_high, entry_price_actual=None, stop_loss=levels.stop, invalidation_level=levels.invalidation, target_1=levels.target_1, target_2=levels.target_2,
        target_3_optional=final["target_3_optional"], risk_reward_expected=((levels.target_1 - levels.entry_high) / risk_per) if risk_per > 0 else None, position_size_simulated=float(sizing["shares"]),
        capital_at_risk=float(sizing["actual_risk"]), time_horizon_sessions=horizon_sessions, expiration_at=datetime(exp_session.year, exp_session.month, exp_session.day, 23, 59, tzinfo=UTC), benchmark_security_id=bench[0].security_id if bench[0] else None,
        created_at=max(utc_now(), at), is_synthetic=bool(authority is not None and authority.run_kind == "SYNTHETIC"),
    )  # fmt: skip
    ver = svc.versions()
    sim.snapshot_hash = snapshot_hash(sim)
    sim.source_provenance = {
        "price": {"source": quote.get("source"), "kind": quote.get("kind"), "session": quote.get("session"), "timestamp": quote.get("timestamp")},
        "fundamental": {"latest_period": fund.get("latest_period"), "latest_filing_available_at": fund.get("latest_filing_available_at"), "engine_version": fund.get("engine_version"), "tag_map_version": fund.get("tag_map_version")},
        "valuation_engine": val.get("engine_version"),
        "providers": (sim.data_quality or {}).get("providers"),
        "analyzer_version": sim.analyzer_version,
        "feature_version": sim.feature_version,
        "trade_plan_rules_version": sim.rules_version,
        "prediction": {"model_id": None, "model_version": None, "status": "NOT_YET_VALIDATED"},
        "benchmark": {"security_id": sim.benchmark_security_id, "kind": "SPY_TOTAL_RETURN_PROXY" if sim.benchmark_security_id else None},
        "event_engine_version": engine.version,
        "simulation_engine_version": engine.version,
        "versions": ver,
    }  # fmt: skip
    session.add(sim)
    session.flush()
    session.add(
        SimulationEvent(
            simulation_id=sim.simulation_id,
            sequence_number=0,
            event_type="SIMULATION_CREATED",
            occurred_at=at.date(),
            source_bar_timestamp=None,
            payload_json={"state_after": "CREATED"},
            engine_version=engine.version,
            event_schema_version=engine.event_schema_version,
        )
    )
    session.flush()
    return sim


T0_FIELDS = (
    "security_id", "decision_at", "analyzer_version", "feature_version", "rules_version", "prediction_status", "price_snapshot", "fundamental_snapshot", "technical_snapshot",
    "valuation_snapshot", "support_resistance_snapshot", "trade_plan_snapshot", "market_regime_snapshot", "data_quality", "plan_origin", "original_pitquant_plan",
    "final_simulated_plan", "side", "entry_type", "entry_zone_low", "entry_zone_high", "stop_loss", "invalidation_level", "target_1", "target_2", "target_3_optional",
    "position_size_simulated", "capital_at_risk", "time_horizon_sessions", "expiration_at", "benchmark_security_id",
)  # fmt: skip


def snapshot_hash(sim: Simulation) -> str:
    """SHA-256 of the frozen T0 content (canonical JSON). ``verify_snapshot`` recomputes it: any edit of the row shows."""
    body = {k: getattr(sim, k) for k in T0_FIELDS}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def verify_snapshot(sim: Simulation) -> bool:
    return sim.snapshot_hash is None or sim.snapshot_hash == snapshot_hash(sim)


def restated_bars(
    md: Any, decision_date: date, as_of: datetime
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Completed bars after ``decision_date`` known in ``md``, with post-split prices restated into decision-date units (the units of the plan levels).
    Shared by simulations and by the Analyzer's retrospective signal replay."""
    bars = md.bars.loc[md.bars.index > decision_date, ["open", "high", "low", "close"]].copy()
    notes: list[dict[str, Any]] = []
    for a in md.actions:
        kind = str(getattr(a.kind, "value", a.kind))
        ex = getattr(
            a, "anchor_date", None
        )  # ex-date, else the first split-adjusted day (Apple IR gives no ex-date)
        ratio = getattr(a, "ratio", None)
        if (
            kind in ("SPLIT", "REVERSE_SPLIT")
            and ex
            and ratio
            and decision_date < ex <= as_of.date()
        ):
            bars.loc[bars.index >= ex, ["open", "high", "low", "close"]] *= (
                ratio  # restate post-split prices in T0 units
            )
            notes.append({"corporate_action": kind, "ex_date": str(ex), "ratio": ratio})
    return bars, notes


def _bars_after(
    session: Session, sim: Simulation, as_of: datetime
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    return restated_bars(
        load_market(session, sim.security_id, as_of), sim.decision_at.date(), as_of
    )


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


def plan_of(sim: Simulation, which: str = "FINAL") -> PlanLevels:
    """The levels of the plan stored in the immutable T0 row. ``ORIGINAL`` = the original PITQuant plan of a USER_MODIFIED simulation. Rows created
    before ADR-0036 carry no exit policy: they keep the V0 behaviour (LEGACY_HALF_AT_TP1)."""
    fp = sim.final_simulated_plan or {}
    policy = str(fp.get("exit_policy") or "LEGACY_HALF_AT_TP1")
    fr = [float(x) for x in (fp.get("exit_fractions") or [0.0, 0.0, 0.0])]
    fr += [0.0] * (3 - len(fr))
    exp = sim.expiration_at.date()
    if which == "ORIGINAL":
        o = sim.original_pitquant_plan or {}
        return PlanLevels(
            "LIMIT" if o.get("entry_zone_low") == o.get("entry_zone_high") else "ENTRY_ZONE", float(o["entry_zone_low"]), float(o["entry_zone_high"]), float(o["stop_loss"]), float(o["target_1"]),
            o.get("target_2"), o.get("invalidation_level"), exp, None, "TRACK_TARGETS_ONLY" if policy == "TRACK_TARGETS_ONLY" else policy, (fr[0], fr[1], fr[2]) if policy == "PARTIAL_FRACTIONS" else (0.0, 0.0, 0.0),
        )  # fmt: skip
    return PlanLevels(
        sim.entry_type,
        sim.entry_zone_low,
        sim.entry_zone_high,
        sim.stop_loss,
        sim.target_1,
        sim.target_2,
        sim.invalidation_level,
        exp,
        sim.target_3_optional,
        policy,
        (fr[0], fr[1], fr[2]),
    )


def _cancel_date(session: Session, sim: Simulation) -> date | None:
    ob = session.scalars(
        select(SimulationObservation)
        .where(
            SimulationObservation.simulation_id == sim.simulation_id,
            SimulationObservation.kind == "CANCEL",
        )
        .order_by(SimulationObservation.observed_at)
    ).first()
    return date.fromisoformat(ob.payload["date"]) if ob else None


BENCHMARK_KEYS = (
    "bench_close",
    "benchmark_return_since_entry",
)  # a benchmark bar may arrive AFTER the security's bar: not an integrity signal


def _norm(e: dict[str, Any]) -> str:
    payload = {k: v for k, v in e["payload"].items() if k not in BENCHMARK_KEYS}
    return json.dumps([e["type"], str(e["date"]), payload], sort_keys=True, default=str)


def stored_events(session: Session, simulation_id: str) -> list[SimulationEvent]:
    return list(
        session.scalars(
            select(SimulationEvent)
            .where(SimulationEvent.simulation_id == simulation_id)
            .order_by(SimulationEvent.sequence_number)
        )
    )


def _as_dict(r: SimulationEvent) -> dict[str, Any]:
    return {"type": r.event_type, "date": str(r.occurred_at), "payload": r.payload_json}


EXECUTION_OUTCOME = {
    "STOPPED": "STOP_HIT", "TP1": "TARGET_REACHED", "TP2": "TARGET_REACHED", "TP3": "TARGET_REACHED", "EXPIRED": "EXPIRED", "INVALIDATED": "INVALIDATED",
    "AMBIGUOUS_INTRABAR": "AMBIGUOUS_INTRABAR", "CLOSED_MANUAL": "CLOSED_MANUAL", "CANCELLED": "CANCELLED", "WAITING_ENTRY": "NOT_ENTERED",
}  # fmt: skip


def execution_outcome(ev: Evaluation) -> str:
    if ev.state.value in EXECUTION_OUTCOME:
        if ev.state is SimState.EXPIRED and ev.entry_date is None:
            return "NOT_ENTERED"
        return EXECUTION_OUTCOME[ev.state.value]
    return "OPEN_TARGETS_TOUCHED" if ev.details.get("targets_touched") else "OPEN"


@dataclass
class UpdateResult:
    simulation_id: str
    new_events: int
    outcome_created: bool
    state: str
    outcome: SimulationOutcome | None
    status: str = "OK"  # OK | DIVERGED | TAMPERED | ENGINE_VERSION_UNAVAILABLE | ERROR
    error: str | None = None
    bars_loaded: int = 0  # bars read from T0 (the update re-reads them: see ADR-0037 «performance»)
    bars_new: int = 0  # BAR_PROCESSED events appended by THIS update
    new_observations: int = 0
    observation_errors: list[str] = field(default_factory=list)


def _evaluate(
    session: Session, sim: Simulation, as_of: datetime
) -> tuple[Evaluation, int, list[dict[str, Any]]]:
    bars, notes = _bars_after(session, sim, as_of)
    bench = None
    if sim.benchmark_security_id:
        bench = load_market(session, sim.benchmark_security_id, as_of).bars["close"]
    ev = registry.resolve_engine(sim.simulation_engine_version).evaluate(
        plan_of(sim),
        bars,
        sim.decision_at.date(),
        benchmark=bench,
        manual_close=_manual_close(session, sim),
        cancel_on=_cancel_date(session, sim),
        reference_price=sim.entry_zone_high,
    )
    return ev, len(bars), notes


def update_simulation(
    session: Session, settings: Settings, simulation_id: str, as_of: datetime | None = None
) -> UpdateResult:
    """IDEMPOTENT event-log update. The engine is deterministic: re-running it over the completed bars known at ``as_of`` yields the SAME event
    prefix; only the events after the stored ones are appended (a second run with no new bars appends 0 events and no outcome). A stored event
    that the re-run does not reproduce raises ``EVENT_LOG_DIVERGENCE`` instead of rewriting history."""
    sim = session.get_one(Simulation, simulation_id)
    if sim.asset_type != "EQUITY":
        raise SimulationError("BTC_UPDATE_ROUTE_REQUIRED")
    engine = registry.resolve_engine(
        sim.simulation_engine_version
    )  # the PINNED engine; never the latest (ENGINE_VERSION_UNAVAILABLE fails closed)
    as_of = as_of or utc_now()
    _guard(as_of, settings)
    if as_of < sim.decision_at:
        raise SimulationError("cannot evaluate before the decision time")
    if not verify_snapshot(sim):
        raise SimulationError("SNAPSHOT_TAMPERED: the T0 row no longer matches its hash")
    ev, n_bars, notes = _evaluate(session, sim, as_of)
    if notes:
        ev.details["corporate_actions"] = notes
    old = stored_events(session, simulation_id)
    for i, row in enumerate(old[: len(ev.events)]):
        if _norm(_as_dict(row)) != _norm(ev.events[i]):
            raise SimulationError(
                f"EVENT_LOG_DIVERGENCE at sequence {i}: the stored event is not reproduced by the engine (corrected bars?)"
            )
    added = ev.events[len(old) :]
    for k, e in enumerate(added, start=len(old)):
        session.add(
            SimulationEvent(
                simulation_id=simulation_id,
                sequence_number=k,
                event_type=e["type"],
                occurred_at=date.fromisoformat(e["date"]),
                source_bar_timestamp=date.fromisoformat(e["date"])
                if e["type"] not in ("SIMULATION_CREATED", "MANUAL_CLOSE", "CANCELLED")
                else None,
                payload_json=e["payload"],
                engine_version=engine.version,
                event_schema_version=engine.event_schema_version,
            )
        )
    session.flush()
    latest = latest_outcome(session, simulation_id)
    bars_new = sum(1 for e in added if e["type"] == "BAR_PROCESSED")
    if (
        len(old) > len(ev.events)
    ):  # evaluated at an EARLIER instant than a previous update: nothing to add, no older state is materialised
        return UpdateResult(
            simulation_id,
            0,
            False,
            latest.state if latest else ev.state.value,
            latest,
            bars_loaded=n_bars,
        )
    created = False
    out = latest
    if added or latest is None:
        out = _materialise(sim, ev, as_of, len(old) + len(added), n_bars, engine.version)
        session.add(out)
        session.flush()
        created = True
    evaluate_counterfactual(session, sim, as_of)
    rec = record_observations(
        session, settings, sim, [_as_dict(r) for r in stored_events(session, simulation_id)], as_of
    )
    return UpdateResult(
        simulation_id, len(added), created, ev.state.value, out, bars_loaded=n_bars, bars_new=bars_new,
        new_observations=len(rec.created), observation_errors=rec.errors,
    )  # fmt: skip


def _materialise(
    sim: Simulation,
    ev: Evaluation,
    as_of: datetime,
    n_events: int,
    n_bars: int,
    engine_version: str,
) -> SimulationOutcome:
    m = ev.metrics
    extra = {
        k: m.get(k)
        for k in (
            "mfe_pct",
            "mae_pct",
            "mfe_r",
            "mae_r",
            "initial_risk_per_unit",
            "mark_to_market_return",
            "days_to_tp3",
            "days_waiting_entry",
        )
    }
    return SimulationOutcome(
        simulation_id=sim.simulation_id, evaluated_at=as_of, state=ev.state.value, is_closed=ev.state in CLOSED, entry_date=ev.entry_date, entry_price=ev.entry_price, exit_date=ev.exit_date,
        realized_return=m.get("realized_return"), excess_return_vs_benchmark=m.get("excess_return_vs_benchmark"), realized_r=m.get("realized_r"), mfe=m.get("mfe"), mae=m.get("mae"), max_drawdown=m.get("max_drawdown"),
        days_to_entry=m.get("days_to_entry"), days_to_stop=m.get("days_to_stop"), days_to_tp1=m.get("days_to_tp1"), days_to_tp2=m.get("days_to_tp2"), holding_period=m.get("holding_period"),
        prediction_direction_correct=None, trade_plan_execution_correct=None, timeline=ev.timeline,
        details={**ev.details, "metrics_extra": extra, "bars_used": n_bars, "paper_trade": "NO REAL MONEY"},
        prediction_outcome=None, execution_outcome=execution_outcome(ev), event_count=n_events, engine_version=engine_version, bars_to_entry=m.get("bars_to_entry"),
    )  # fmt: skip


def evaluate_simulation(
    session: Session, settings: Settings, simulation_id: str, as_of: datetime | None = None
) -> SimulationOutcome:
    """Compatibility entry point: update the event log and return the latest materialised outcome."""
    r = update_simulation(session, settings, simulation_id, as_of)
    assert r.outcome is not None
    return r.outcome


def update_active(
    session: Session,
    settings: Settings,
    as_of: datetime | None = None,
    simulation_id: str | None = None,
    *,
    commit: bool = False,
) -> list[UpdateResult]:
    """``pitquant simulation-update``: every simulation that is not closed (or one), in creation order. Each simulation runs in its OWN savepoint (and
    its own commit with ``commit=True``): one divergent, tampered or failing simulation is reported (``DIVERGED`` / ``TAMPERED`` / ``ERROR``) and never
    rolls back the events of the others."""
    ids = (
        [simulation_id]
        if simulation_id
        else list(
            session.scalars(
                select(Simulation.simulation_id)
                .where(Simulation.asset_type == "EQUITY")
                .order_by(Simulation.created_at)
            )
        )
    )
    out: list[UpdateResult] = []
    for sid in ids:
        lo = latest_outcome(session, sid)
        if simulation_id is None and lo is not None and lo.is_closed:
            continue
        try:
            with session.begin_nested():
                out.append(update_simulation(session, settings, sid, as_of))
            if commit:
                session.commit()
        except PITQuantError as e:
            msg = str(e)
            status = (
                "ENGINE_VERSION_UNAVAILABLE"
                if isinstance(e, registry.EngineVersionUnavailable)
                else "DIVERGED"
                if "EVENT_LOG_DIVERGENCE" in msg
                else "TAMPERED"
                if "SNAPSHOT_TAMPERED" in msg
                else "ERROR"
            )
            out.append(UpdateResult(sid, 0, False, lo.state if lo else "UNKNOWN", lo, status, msg))
    return out


@dataclass
class ReplayResult:
    simulation_id: str
    match: bool
    differences: list[str]
    folded: dict[str, Any]
    n_events: int
    engine_version: str = ""
    event_schema_versions: tuple[int, ...] = ()


def replay_simulation(session: Session, simulation_id: str) -> ReplayResult:
    """T0 row + event log ONLY (no market data): fold the events and compare with the persisted outcome."""
    sim = session.get_one(Simulation, simulation_id)
    rows = stored_events(session, simulation_id)
    diffs: list[str] = []
    if [r.sequence_number for r in rows] != list(range(len(rows))):
        diffs.append("event sequence has gaps or duplicates")
    if not verify_snapshot(sim):
        diffs.append("T0 snapshot hash mismatch")
    engine = registry.resolve_engine(sim.simulation_engine_version)
    for r in rows:
        if r.engine_version not in engine.event_labels:
            diffs.append(
                f"event #{r.sequence_number} was written by engine {r.engine_version!r}, the simulation is pinned to {sim.simulation_engine_version!r}"
            )
    folded = engine.fold_events([_as_dict(r) for r in rows], plan_of(sim))
    out = latest_outcome(session, simulation_id)
    if out is None:
        if len(rows) > 1:
            diffs.append("events beyond SIMULATION_CREATED but no materialised outcome")
        return ReplayResult(
            simulation_id,
            not diffs,
            diffs,
            folded,
            len(rows),
            engine.version,
            tuple(sorted({r.event_schema_version for r in rows})),
        )
    if out.event_count is not None and out.event_count != len(rows):
        diffs.append(
            f"outcome materialised from {out.event_count} events, the log holds {len(rows)}"
        )

    def cmp(name: str, a: Any, b: Any) -> None:
        if a is None and b is None:
            return
        if isinstance(a, int | float) and isinstance(b, int | float) and not isinstance(a, bool):
            if abs(float(a) - float(b)) > 1e-9:
                diffs.append(f"{name}: replay {a} != persisted {b}")
        elif str(a) != str(b):
            diffs.append(f"{name}: replay {a} != persisted {b}")

    extra = (out.details or {}).get("metrics_extra") or {}
    cmp("state", folded["state"], out.state)
    cmp("is_closed", folded["is_closed"], out.is_closed)
    cmp("entry_price", folded.get("entry_price"), out.entry_price)
    cmp("entry_date", folded.get("entry_date"), out.entry_date)
    cmp("exit_date", folded.get("exit_date"), out.exit_date)
    cmp(
        "position_remaining",
        folded.get("position_remaining"),
        (out.details or {}).get("position_remaining"),
    )
    for k in ("realized_return", "realized_r", "mfe", "mae", "max_drawdown"):
        cmp(k, folded.get(k), getattr(out, k))
    for k in ("mfe_pct", "mae_pct", "mfe_r", "mae_r"):
        cmp(k, folded.get(k), extra.get(k))
    hint = folded.get("_bench_hint")
    if (
        hint is not None
        and out.excess_return_vs_benchmark is not None
        and out.state != "CLOSED_MANUAL"
        and folded.get("realized_return") is not None
    ):
        cmp(
            "excess_return_vs_benchmark",
            folded["realized_return"] - hint,
            out.excess_return_vs_benchmark,
        )
    if out.bars_to_entry is not None:
        cmp("bars_to_entry", folded.get("bars_to_entry"), out.bars_to_entry)
    return ReplayResult(
        simulation_id,
        not diffs,
        diffs,
        folded,
        len(rows),
        engine.version,
        tuple(sorted({r.event_schema_version for r in rows})),
    )


def evaluate_counterfactual(
    session: Session, sim: Simulation, as_of: datetime
) -> SimulationCounterfactual | None:
    """COUNTERFACTUAL, never the real outcome: the ORIGINAL PITQuant plan of a USER_MODIFIED simulation over the SAME bars. Appended only when a
    new bar was processed; the real simulation is untouched."""
    if sim.plan_origin != "USER_MODIFIED" or not sim.original_pitquant_plan:
        return None
    try:
        plan = plan_of(sim, "ORIGINAL")
        plan.validate()
    except (KeyError, TypeError, ValueError):
        return None
    bars, _ = _bars_after(session, sim, as_of)
    bench = (
        load_market(session, sim.benchmark_security_id, as_of).bars["close"]
        if sim.benchmark_security_id
        else None
    )
    engine = registry.resolve_engine(
        sim.simulation_engine_version
    )  # SAME pinned engine as the real simulation: only the plan differs
    ev = engine.evaluate(
        plan,
        bars,
        sim.decision_at.date(),
        benchmark=bench,
        manual_close=None,
        cancel_on=_cancel_date(session, sim),
        reference_price=plan.entry_high,
    )
    last = session.scalars(
        select(SimulationCounterfactual)
        .where(SimulationCounterfactual.simulation_id == sim.simulation_id)
        .order_by(SimulationCounterfactual.created_at.desc())
    ).first()
    if last is not None and last.last_bar == ev.last_bar and last.state == ev.state.value:
        return last
    row = SimulationCounterfactual(
        simulation_id=sim.simulation_id, simulation_engine_version=engine.version, evaluated_at=as_of, last_bar=ev.last_bar, state=ev.state.value, plan={"entry_zone": [plan.entry_low, plan.entry_high], "stop": plan.stop, "target_1": plan.target_1, "target_2": plan.target_2, "exit_policy": plan.exit_policy},
        metrics={k: v for k, v in ev.metrics.items()}, details={"entry_price": ev.entry_price, "entry_method": ev.entry_method, "targets_touched": ev.details.get("targets_touched"), "execution_outcome": execution_outcome(ev), "label": "COUNTERFACTUAL — NOT THE REAL OUTCOME"}, timeline=ev.timeline,
    )  # fmt: skip
    session.add(row)
    session.flush()
    return row


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
    lo = latest_outcome(session, simulation_id)
    if lo is not None and (lo.is_closed or lo.entry_date is None):
        raise SimulationError(
            "a manual close needs an OPEN position (cancel a simulation that has not entered)"
        )
    ob = SimulationObservation(
        simulation_id=simulation_id,
        observed_at=at,
        kind="MANUAL_CLOSE",
        payload={"date": str(at.date()), "price": price, "reason": reason},
    )
    session.add(ob)
    session.flush()
    return ob


def cancel_simulation(
    session: Session, settings: Settings, simulation_id: str, *, at: datetime, reason: str = ""
) -> SimulationObservation:
    """CANCELLED: only a simulation that has NOT entered and is not closed. Appends an observation; the event log gets the CANCELLED event at the next update."""
    sim = session.get_one(Simulation, simulation_id)
    _guard(at, settings)
    if at < sim.decision_at:
        raise SimulationError("invalid cancellation time")
    lo = latest_outcome(session, simulation_id)
    if lo is not None and (lo.is_closed or lo.entry_date is not None):
        raise SimulationError(
            "only a simulation that has not entered and is not closed can be cancelled"
        )
    ob = SimulationObservation(
        simulation_id=simulation_id,
        observed_at=at,
        kind="CANCEL",
        payload={"date": str(at.date()), "reason": reason},
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


def latest_periodic(session: Session, simulation_id: str) -> SimulationObservation | None:
    return session.scalars(
        select(SimulationObservation)
        .where(
            SimulationObservation.simulation_id == simulation_id,
            SimulationObservation.kind == "PERIODIC",
        )
        .order_by(
            SimulationObservation.source_bar_date.desc(), SimulationObservation.created_at.desc()
        )
    ).first()


def thesis_evolution(session: Session, simulation_id: str) -> list[dict[str, Any]]:
    """For every recorded observation: its label/date/versions and the descriptive facts against T0. READ-ONLY: nothing is recomputed."""
    sim = session.get_one(Simulation, simulation_id)
    rows = session.scalars(
        select(SimulationObservation)
        .where(
            SimulationObservation.simulation_id == simulation_id,
            SimulationObservation.kind == "PERIODIC",
        )
        .order_by(SimulationObservation.source_bar_date)
    )
    return [
        {"observation_id": o.observation_id, "label": o.horizon_label, "bar_date": str(o.source_bar_date), "observed_at": o.observed_at.isoformat(), "observation_schema_version": o.observation_schema_version, "analyzer_version": o.analyzer_version, "feature_version": o.feature_version, "facts": thesis_facts(sim, o.payload, o.observation_id)}
        for o in rows
    ]  # fmt: skip


def postmortem_facts(
    session: Session, settings: Settings, simulation_id: str, as_of: datetime | None = None
) -> dict[str, Any]:
    """OBJECTIVE facts of a simulation (no verdict). A flag is a deterministic FACT with its definition; thresholds that are not validated are
    never turned into conclusions (``stop_distance_atr`` is stored, ``STOP_TOO_TIGHT`` is never inferred). Prediction and execution are kept apart:
    ``prediction_outcome`` stays NULL while the Prediction Engine is NOT_YET_VALIDATED, and a stop is an EXECUTION fact."""
    sim = session.get_one(Simulation, simulation_id)
    out = latest_outcome(session, simulation_id)
    if out is None:
        raise SimulationError("evaluate the simulation first")
    as_of = as_of or utc_now()
    ex = (out.details or {}).get("metrics_extra") or {}
    px0 = float((sim.price_snapshot or {}).get("price") or 0) or None
    atr_pct = ((sim.technical_snapshot or {}).get("risk") or {}).get("atr14_pct")
    entry = out.entry_price
    stop_dist = (entry - sim.stop_loss) if entry else (sim.entry_zone_high - sim.stop_loss)
    sup = ((sim.support_resistance_snapshot or {}).get("supports") or [{}])[0]
    facts: dict[str, Any] = {
        "prediction_outcome": None, "prediction_status": sim.prediction_status, "execution_outcome": out.execution_outcome, "state": out.state,
        "entry_quality": {"entry_method": (out.details or {}).get("fills", {}).get("entry", {}).get("method"), "entry_vs_t0_price": (entry / px0 - 1.0) if entry and px0 else None, "days_waiting_entry": ex.get("days_waiting_entry"), "nearest_support_distance_atr_t0": sup.get("distance_atr")},
        "stop_quality": {"stop_distance_pct": stop_dist / entry if entry else None, "stop_distance_atr": (stop_dist / (atr_pct * px0)) if atr_pct and px0 else None, "mae_r": ex.get("mae_r"), "stop_date": out.exit_date.isoformat() if out.state == "STOPPED" and out.exit_date else None},
        "target_quality": {"target_1_r": (sim.target_1 - entry) / stop_dist if entry and stop_dist > 0 else None, "mfe_r": ex.get("mfe_r"), "targets_touched": (out.details or {}).get("targets_touched")},
        "metrics": {k: getattr(out, k) for k in ("realized_return", "realized_r", "mfe", "mae", "max_drawdown", "holding_period", "excess_return_vs_benchmark")} | {"mfe_pct": ex.get("mfe_pct"), "mae_pct": ex.get("mae_pct")},
    }  # fmt: skip
    flags: list[dict[str, Any]] = []
    if out.state == "STOPPED" and out.exit_date:
        bars, _ = _bars_after(session, sim, as_of)
        later = bars.loc[bars.index > out.exit_date]
        if len(later) and float(later["high"].max()) >= sim.target_1:
            flags.append(
                {
                    "flag": "STOP_HIT_BEFORE_LATER_TP",
                    "definition": "stopped out, and a later bar (still inside the available data) reached target 1",
                }
            )
    if (ex.get("mfe_r") or 0) >= 1.0 and (out.realized_r or 0) <= 0 and out.entry_date:
        flags.append(
            {
                "flag": "HIGH_MFE_LOW_REALIZED",
                "definition": "favourable excursion reached at least 1R but the realised R is <= 0",
            }
        )
    if (
        out.entry_date
        and out.details.get("targets_touched") == []
        and out.is_closed
        and (ex.get("mfe_pct") is not None)
        and sim.target_1 > (out.entry_price or 0)
    ):
        mx = (out.entry_price or 0) * (1.0 + float(ex["mfe_pct"]))
        if mx < sim.target_1:
            flags.append(
                {
                    "flag": "TARGET_NEVER_APPROACHED",
                    "definition": "the highest price since entry never reached target 1",
                }
            )
    periodic = latest_periodic(session, simulation_id)
    if periodic is not None:
        # recorded HISTORICAL observation (as known on its bar date) vs T0: descriptive facts with their source observation id, no cause inferred
        names = {"trend_changed": "TREND_CHANGED", "support_broken": "SUPPORT_BROKEN", "resistance_broken": "RESISTANCE_BROKEN", "volatility_expanded": "VOLATILITY_EXPANDED",
                 "valuation_expanded": "VALUATION_EXPANDED", "valuation_compressed": "VALUATION_COMPRESSED", "fundamental_snapshot_changed": "FUNDAMENTAL_SNAPSHOT_CHANGED", "regime_changed": "REGIME_CHANGED"}  # fmt: skip
        for t in thesis_facts(sim, periodic.payload, periodic.observation_id):
            flag = names[t["fact"]]
            if flag == "TREND_CHANGED" and trend_flip(t["t0"], t["observed"]):
                flag = "TREND_REVERSED"  # an up<->down flip, not any change
            flags.append(
                {
                    "flag": flag,
                    "definition": t["definition"],
                    "t0": t["t0"],
                    "observed": t["observed"],
                    "source_observation_ids": [periodic.observation_id],
                    "observation_bar_date": str(periodic.source_bar_date),
                }
            )
    snaps = (
        []
        if periodic is not None
        else list(
            session.scalars(
                select(SimulationObservation)
                .where(
                    SimulationObservation.simulation_id == simulation_id,
                    SimulationObservation.kind == "THESIS_SNAPSHOT",
                )
                .order_by(SimulationObservation.observed_at)
            )
        )
    )
    if snaps:
        c = snaps[-1].payload.get("comparison") or {}
        if c.get("regime_change"):
            flags.append(
                {
                    "flag": "REGIME_CHANGED",
                    "definition": "the trend state of the last thesis snapshot differs from T0",
                }
            )
        if c.get("trend_break"):
            flags.append(
                {
                    "flag": "TREND_REVERSED",
                    "definition": "the trend state changed between T0 and the last thesis snapshot",
                }
            )
        fs = c.get("fundamental_status") or [None, None]
        if fs[0] != fs[1]:
            flags.append(
                {
                    "flag": "FUNDAMENTAL_STATUS_CHANGED",
                    "definition": "the fundamental engine status differs between T0 and the last thesis snapshot (not a judgement of deterioration)",
                }
            )
    facts["diagnostic_flags"] = flags
    facts["note"] = (
        "facts only: no cause is inferred; the cause is classified by a human (classify_postmortem)"
    )
    return facts


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
    pm.metrics = {
        **pm.metrics,
        "facts_at_classification": {
            "execution_outcome": out.execution_outcome,
            "prediction_outcome": out.prediction_outcome,
        },
    }
    session.add(pm)
    session.flush()
    return pm


def propose_hypothesis(
    session: Session,
    *,
    statement: str,
    evidence: dict[str, Any],
    created_by: str,
    simulation_id: str | None = None,
    status: str = "UNTESTED",
) -> ResearchHypothesis:
    """A ResearchHypothesis from simulation patterns, always UNTESTED at creation (TESTING / SUPPORTED / NOT_SUPPORTED belong to the Research Lab).
    Never promotes a model: Challenger -> backtest -> walk-forward -> Champion comparison -> HUMAN promotion."""
    if status not in HYPOTHESIS_STATES:
        raise SimulationError(f"hypothesis status must be one of {HYPOTHESIS_STATES}")
    if simulation_id is not None:
        session.get_one(Simulation, simulation_id)
        evidence = {**evidence, "simulation_id": simulation_id}
    h = ResearchHypothesis(
        source="SIMULATION_PATTERN",
        statement=statement[:1000],
        evidence=evidence,
        status=status,
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
    sims = list(
        session.scalars(
            select(Simulation.simulation_id).where(
                Simulation.asset_type == "EQUITY", Simulation.is_synthetic.is_(False)
            )
        )
    )  # synthetic trades are never evidence
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


# ───────────────────────────────────────────── Insights (descriptive only) and plan comparison
SEGMENTS = (
    "simulation_engine_version",
    "setup_type",
    "rules_version",
    "origin",
    "security",
    "sector",
    "trend_state",
    "valuation_state",
    "volatility_regime",
    "market_regime",
    "horizon",
)


def _segment_value(
    session: Session, sim: Simulation, by: str, vol_cuts: tuple[float, float] | None
) -> str:
    if by == "simulation_engine_version":
        return f"engine {sim.simulation_engine_version}"
    if by == "setup_type":
        return str((sim.original_pitquant_plan or {}).get("setup_type") or "USER_DEFINED")
    if by == "rules_version":
        return sim.rules_version
    if by == "origin":
        return sim.plan_origin
    if by == "security":
        sec = session.get(Security, sim.security_id)
        return sec.name if sec else sim.security_id
    if by == "sector":
        p = session.scalars(
            select(SecurityProfile)
            .where(SecurityProfile.security_id == sim.security_id)
            .order_by(SecurityProfile.ingested_at.desc())
        ).first()
        return (p.sector if p and p.sector else "UNKNOWN") or "UNKNOWN"
    if by == "trend_state":
        return str(((sim.technical_snapshot or {}).get("trend") or {}).get("state") or "UNKNOWN")
    if by == "valuation_state":
        return str((sim.valuation_snapshot or {}).get("status") or "UNKNOWN")
    if by == "volatility_regime":
        v = ((sim.technical_snapshot or {}).get("risk") or {}).get("vol63")
        if v is None or vol_cuts is None:
            return "UNKNOWN"
        return (
            "LOW" if v <= vol_cuts[0] else "HIGH" if v > vol_cuts[1] else "MID"
        )  # sample terciles: descriptive, not a validated regime
    if by == "market_regime":
        return str(
            ((sim.market_regime_snapshot or {}).get("trend") or {}).get("state") or "UNKNOWN"
        )
    if by == "horizon":
        return f"{sim.time_horizon_sessions} sessions"
    raise SimulationError(f"unknown segmentation {by!r}; use one of {SEGMENTS}")


def _stats(xs: list[float]) -> dict[str, float | None]:
    return {
        "mean": statistics.fmean(xs) if xs else None,
        "median": statistics.median(xs) if xs else None,
    }


def insights(
    session: Session, by: str = "setup_type", min_n: int = MIN_N_FOR_STATS
) -> dict[str, Any]:
    """DESCRIPTIVE segmentation of the simulations by T0 attributes. No recommendation, no model feedback; a segment with fewer than ``min_n`` entered
    trades shows its N and the flag INSUFFICIENT_SAMPLE instead of statistics."""
    if by not in SEGMENTS:
        raise SimulationError(f"unknown segmentation {by!r}; use one of {SEGMENTS}")
    sims = list(
        session.scalars(
            select(Simulation).where(
                Simulation.asset_type == "EQUITY", Simulation.is_synthetic.is_(False)
            )
        )
    )
    vols = sorted(
        v
        for v in (((x.technical_snapshot or {}).get("risk") or {}).get("vol63") for x in sims)
        if v is not None
    )
    cuts = (vols[len(vols) // 3], vols[2 * len(vols) // 3]) if len(vols) >= 3 else None
    engines: dict[str, int] = {}
    for x in sims:
        engines[x.simulation_engine_version] = engines.get(x.simulation_engine_version, 0) + 1
    groups: dict[str, list[tuple[Simulation, SimulationOutcome]]] = {}
    for x in sims:
        o = latest_outcome(session, x.simulation_id)
        if o is not None:
            groups.setdefault(_segment_value(session, x, by, cuts), []).append((x, o))
    rows = []
    for key, items in sorted(groups.items()):
        entered = [
            o for _, o in items if o.entry_date is not None and o.realized_return is not None
        ]
        n, ne = len(items), len(entered)
        row: dict[str, Any] = {
            "segment": key,
            "n": n,
            "n_entered": ne,
            "sample": "OK" if ne >= min_n else "INSUFFICIENT_SAMPLE",
        }
        if ne >= min_n:

            def ex(o: SimulationOutcome, k: str) -> float | None:
                v = ((o.details or {}).get("metrics_extra") or {}).get(k)
                return float(v) if v is not None else None

            row |= {
                "return": _stats(
                    [float(o.realized_return) for o in entered if o.realized_return is not None]
                ),
                "r": _stats([float(o.realized_r) for o in entered if o.realized_r is not None]),
                "mae_pct": _stats([v for o in entered if (v := ex(o, "mae_pct")) is not None]),
                "mfe_pct": _stats([v for o in entered if (v := ex(o, "mfe_pct")) is not None]),
                "stop_rate": sum(o.state == "STOPPED" for _, o in items) / n,
                "target_touch_rate": sum(
                    bool((o.details or {}).get("targets_touched")) for o in entered
                )
                / ne,
                "expiration_rate": sum(o.state == "EXPIRED" for _, o in items) / n,
                "ambiguous_rate": sum(o.state == "AMBIGUOUS_INTRABAR" for _, o in items) / n,
            }
        rows.append(row)
    return {
        "by": by,
        "segments": rows,
        "min_n": min_n,
        "note": "descriptive statistics of paper trades: no recommendation, never a training label",
        "available_segmentations": list(SEGMENTS),
        "engines": engines,
        "mixed_engines": len(engines) > 1 and by != "simulation_engine_version",
    }


def _plan_view(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    lo, hi, stop, t1, t2 = (
        plan.get("entry_zone_low"),
        plan.get("entry_zone_high"),
        plan.get("stop_loss"),
        plan.get("target_1"),
        plan.get("target_2"),
    )
    risk = (hi - stop) if hi is not None and stop is not None else None

    def r(t: float | None) -> float | None:
        return (
            ((t - hi) / risk) if (t is not None and hi is not None and risk and risk > 0) else None
        )

    return {
        "entry_zone": [lo, hi],
        "stop_loss": stop,
        "target_1": t1,
        "target_2": t2,
        "expected_r_tp1": r(t1),
        "expected_r_tp2": r(t2),
        "invalidation_level": plan.get("invalidation_level"),
    }


def compare_plans(session: Session, simulation_id: str) -> dict[str, Any]:
    """PITQuant ORIGINAL plan vs the USER plan (both frozen at T0) and, when bars exist, the COUNTERFACTUAL of the original plan next to the REAL outcome."""
    sim = session.get_one(Simulation, simulation_id)
    out = latest_outcome(session, simulation_id)
    cf = session.scalars(
        select(SimulationCounterfactual)
        .where(SimulationCounterfactual.simulation_id == simulation_id)
        .order_by(SimulationCounterfactual.created_at.desc())
    ).first()
    comp: dict[str, Any] = {
        "plan_origin": sim.plan_origin,
        "pitquant_original": _plan_view(sim.original_pitquant_plan),
        "user_plan": _plan_view(sim.final_simulated_plan),
        "counterfactual": None,
        "real": None,
    }
    if out is not None:
        ex = (out.details or {}).get("metrics_extra") or {}
        comp["real"] = {
            "state": out.state,
            "triggered": out.entry_date is not None,
            "entry_price": out.entry_price,
            "realized_r": out.realized_r,
            "mae_pct": ex.get("mae_pct"),
            "mfe_pct": ex.get("mfe_pct"),
            "targets_touched": (out.details or {}).get("targets_touched"),
            "label": "REAL SIMULATION",
        }
    if cf is not None:
        m = cf.metrics or {}
        comp["counterfactual"] = {
            "state": cf.state,
            "triggered": cf.details.get("entry_price") is not None,
            "entry_price": cf.details.get("entry_price"),
            "realized_r": m.get("realized_r"),
            "mae_pct": m.get("mae_pct"),
            "mfe_pct": m.get("mfe_pct"),
            "targets_touched": cf.details.get("targets_touched"),
            "last_bar": str(cf.last_bar),
            "label": "COUNTERFACTUAL — NOT THE REAL OUTCOME",
        }
    return comp


def explain_simulation(session: Session, simulation_id: str) -> dict[str, Any]:
    """Where every number of the simulation comes from (no new computation)."""
    sim = session.get_one(Simulation, simulation_id)
    out = latest_outcome(session, simulation_id)
    return {
        "simulation_id": simulation_id, "decision_at": sim.decision_at.isoformat(), "snapshot_hash": sim.snapshot_hash, "snapshot_verified": verify_snapshot(sim),
        "provenance": sim.source_provenance or {"note": "created before ADR-0036: provenance is reconstructed from the frozen snapshots only"},
        "versions": {"analyzer": sim.analyzer_version, "feature": sim.feature_version, "trade_plan_rules": sim.rules_version, "prediction_model": sim.model_version, "prediction_status": sim.prediction_status, "event_engine": out.engine_version if out else sim.simulation_engine_version, "simulation_engine": sim.simulation_engine_version, "event_schema": ", ".join(str(v) for v in sorted({e.event_schema_version for e in stored_events(session, simulation_id)})) or "1"},
        "plan_origin": sim.plan_origin, "exit_policy": (sim.final_simulated_plan or {}).get("exit_policy") or "LEGACY_HALF_AT_TP1", "events": len(stored_events(session, simulation_id)),
        "banner": "PAPER TRADING — NO REAL MONEY",
    }  # fmt: skip
