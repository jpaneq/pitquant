# ruff: noqa: E501
"""Strategy runs (ADR-0039): decisions, AUTO_PAPER wiring into the Simulation Lab, SYNTHETIC / HISTORICAL / FORWARD_PAPER runners.

* ONE decision step (``process_decision``) serves every run kind: PIT inputs at ``decision_at`` ⇒ ``evaluate_strategy`` ⇒ an immutable ``StrategyDecision`` ⇒ (ENTER) a
  paper trade through the Simulation Lab or (EXIT) a manual close of that trade. The Simulation engine, event store, observations and replay are REUSED, never duplicated.
* Exits: stop / target / invalidation / horizon are the simulation engine's; prediction deterioration and risk regime are strategy decisions that close the trade at the
  session close known at ``decision_at``. ``exit_reason`` is always stored.
* SYNTHETIC runs exist only in fixture/test mode (``PITQUANT_E2E_FIXTURE=1``): their simulations are ``is_synthetic`` and never count as evidence.
* HISTORICAL runs need every data gate open (evaluated ONCE per run); otherwise the run is recorded BLOCKED and nothing is executed.
* FORWARD_PAPER runs freeze the strategy version; ``activated_at`` is server time, a tick never looks before it and nothing can be back-dated.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.analyzer.service import AnalyzerService
from pitquant.config.settings import Settings
from pitquant.core.errors import HoldoutAccessError
from pitquant.core.hashing import content_hash
from pitquant.core.timeutils import utc_now
from pitquant.db.models import Simulation, SimulationOutcome
from pitquant.db.models_lab import (
    PredictionSnapshot,
    StrategyDecision,
    StrategyDefinition,
    StrategyRun,
    StrategyRunEvent,
    StrategySimulationLink,
)
from pitquant.prediction.models import evaluate_training_gates
from pitquant.research.registry import commit_sha
from pitquant.simulation import registry
from pitquant.simulation import service as sim
from pitquant.strategy.engine import DecisionResult, evaluate_strategy
from pitquant.strategy.spec import PREDICTION_FAMILIES, StrategyError, StrategySpec, spec_of

CLOCK = utc_now  # patched in tests; the API and CLI never accept a client-supplied «now» for forward runs
STATE_TO_EXIT_REASON = {
    "STOPPED": "STOP",
    "TP1": "TARGET",
    "TP2": "TARGET",
    "TP3": "TARGET",
    "INVALIDATED": "THESIS_INVALIDATION",
    "EXPIRED": "HORIZON_EXPIRY",
}


def synthetic_runs_allowed() -> bool:
    return (
        os.environ.get("PITQUANT_E2E_FIXTURE") == "1"
        or os.environ.get("PITQUANT_ALLOW_SYNTHETIC_RUNS") == "1"
    )


def _event(
    session: Session,
    run: StrategyRun,
    typ: str,
    at: datetime,
    payload: dict[str, Any] | None = None,
) -> None:
    session.add(
        StrategyRunEvent(run_id=run.run_id, event_type=typ, occurred_at=at, payload=payload or {})
    )
    session.flush()


def run_status(session: Session, run: StrategyRun) -> str:
    last = session.scalars(
        select(StrategyRunEvent)
        .where(StrategyRunEvent.run_id == run.run_id)
        .order_by(StrategyRunEvent.occurred_at.desc(), StrategyRunEvent.created_at.desc())
    ).first()
    return {
        "BLOCKED": "BLOCKED",
        "ACTIVATED": "ACTIVE",
        "TICK": "ACTIVE",
        "COMPLETED": "COMPLETED",
        "STOPPED": "STOPPED",
    }.get(last.event_type if last else "", "CREATED")


def create_run(
    session: Session,
    settings: Settings,
    strategy: StrategyDefinition,
    kind: str,
    universe: Sequence[str],
    *,
    params: dict[str, Any] | None = None,
    readiness: dict[str, bool] | None = None,
) -> StrategyRun:
    """Create ONE run of an exact strategy version. FORWARD_PAPER activates it now (server time); HISTORICAL checks the data gates once and is BLOCKED when closed."""
    if not universe:
        raise StrategyError("a run needs at least one security")
    if kind not in ("SYNTHETIC", "HISTORICAL", "FORWARD_PAPER"):
        raise StrategyError("run_kind must be SYNTHETIC, HISTORICAL or FORWARD_PAPER")
    if kind == "SYNTHETIC" and not synthetic_runs_allowed():
        raise StrategyError(
            "SYNTHETIC runs exist only in fixture/test mode (PITQUANT_E2E_FIXTURE=1): they must never touch real evidence"
        )
    if kind == "FORWARD_PAPER" and strategy.family in PREDICTION_FAMILIES:
        raise StrategyError(
            f"{strategy.family} is DISABLED_NOT_VALIDATED: a forward paper run needs a validated Prediction Engine"
        )
    now = CLOCK()
    blocked: list[str] = []
    gates: dict[str, bool] = {}
    if kind == "HISTORICAL":
        g = evaluate_training_gates(
            session, settings, readiness
        )  # evaluated ONCE per run (it rebuilds the anchor graph)
        gates, blocked = dict(g.flags), list(g.reasons)
    run = StrategyRun(
        run_kind=kind, strategy_row_id=strategy.strategy_row_id, strategy_id=strategy.strategy_id, strategy_version=strategy.strategy_version, universe=list(universe),
        activated_at=now if kind == "FORWARD_PAPER" else None, dataset_version=None, model_id=(strategy.prediction_model_requirement or {}).get("model_id"), model_version=None,
        simulation_engine_version=registry.CURRENT_SIMULATION_ENGINE_VERSION, commit_sha=commit_sha(), readiness=gates, blocked_reasons=blocked, params=params or {}, is_synthetic=kind == "SYNTHETIC",
    )  # fmt: skip
    session.add(run)
    session.flush()
    _event(
        session,
        run,
        "CREATED",
        now,
        {"kind": kind, "strategy": f"{strategy.strategy_id} v{strategy.strategy_version}"},
    )
    if blocked:
        _event(session, run, "BLOCKED", now, {"reasons": blocked})
    elif kind == "FORWARD_PAPER":
        _event(
            session,
            run,
            "ACTIVATED",
            now,
            {
                "activated_at": now.isoformat(),
                "note": "the strategy version is frozen from this instant; only data after it counts",
            },
        )
    return run


# ───────────────────────────────────────────── helpers
def period_key(at: datetime, frequency: str) -> str:
    d = at.date()
    if frequency == "MONTHLY":
        return f"{d.year}-{d.month:02d}"
    if frequency == "WEEKLY":
        iso = d.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    return d.isoformat()


def _positions(
    session: Session, run: StrategyRun, security_id: str
) -> list[tuple[StrategyDecision, Simulation]]:
    """ENTRY-linked paper trades of this run in ``security_id`` that no EXIT decision has closed yet."""
    out = []
    for link, dec in session.execute(
        select(StrategySimulationLink, StrategyDecision)
        .join(StrategyDecision, StrategyDecision.decision_id == StrategySimulationLink.decision_id)
        .where(
            StrategyDecision.run_id == run.run_id,
            StrategyDecision.security_id == security_id,
            StrategySimulationLink.role == "ENTRY",
        )
    ):
        closed = session.scalars(
            select(StrategySimulationLink).where(
                StrategySimulationLink.simulation_id == link.simulation_id,
                StrategySimulationLink.role == "EXIT",
            )
        ).first()
        if closed is None:
            out.append((dec, session.get_one(Simulation, link.simulation_id)))
    return out


def _all_positions_open(session: Session, run: StrategyRun) -> int:
    return sum(len(_positions(session, run, s)) for s in run.universe)


def exit_reason_for(session: Session, simulation_id: str) -> str | None:
    """Why a paper trade ended: the strategy decision that closed it, else the simulation engine's state mapped to the contract (STOP, TARGET, THESIS_INVALIDATION, HORIZON_EXPIRY)."""
    link = session.scalars(
        select(StrategySimulationLink).where(
            StrategySimulationLink.simulation_id == simulation_id,
            StrategySimulationLink.role == "EXIT",
        )
    ).first()
    if link is not None:
        dec = session.get_one(StrategyDecision, link.decision_id)
        if dec.exit_reason:
            return dec.exit_reason
    out = sim.latest_outcome(session, simulation_id)
    return STATE_TO_EXIT_REASON.get(out.state) if out is not None and out.is_closed else None


def lookup_prediction(
    session: Session,
    security_id: str,
    horizon: int | None,
    as_of: datetime,
    *,
    exact: bool,
    not_before: datetime | None = None,
) -> PredictionSnapshot | None:
    """The prediction usable at ``as_of``: generated by then (``generated_at <= as_of``) and about a decision not later than it. ``exact``: the snapshot of THAT decision_at."""
    if horizon is None:
        return None
    q = select(PredictionSnapshot).where(
        PredictionSnapshot.security_id == security_id,
        PredictionSnapshot.horizon_months == horizon,
        PredictionSnapshot.generated_at <= as_of,
    )
    q = (
        q.where(PredictionSnapshot.decision_at == as_of)
        if exact
        else q.where(PredictionSnapshot.decision_at <= as_of)
    )
    if not_before is not None:
        q = q.where(PredictionSnapshot.decision_at >= not_before)
    return session.scalars(
        q.order_by(PredictionSnapshot.decision_at.desc(), PredictionSnapshot.created_at.desc())
    ).first()


def _has_prediction(p: PredictionSnapshot | None) -> bool:
    return p is not None and (p.p_outperform is not None or p.expected_excess_return is not None)


def build_inputs(
    session: Session,
    settings: Settings,
    spec: StrategySpec,
    security_id: str,
    decision_at: datetime,
    prediction: PredictionSnapshot | None,
    entry_prediction: PredictionSnapshot | None,
    holding_sessions: int | None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """PIT rule inputs at ``decision_at`` (everything comes from the Analyzer / predictions AS OF that instant) and the trade-plan snapshot used."""
    svc = AnalyzerService(session, settings)
    plan = None
    if spec.family != "BUY_AND_HOLD":
        try:
            plan = sim._pitquant_plan(
                svc.trade_plan(security_id, decision_at),
                str(spec.trade_plan_rules.get("profile", "BASE")),
            )
        except Exception:
            plan = None
    dq = svc.data_quality(security_id, decision_at)
    label = ((dq.get("overall") or {}) if isinstance(dq.get("overall"), dict) else {}).get("label")
    tech = svc.technicals(security_id, decision_at)
    p_now = prediction.p_outperform if _has_prediction(prediction) and prediction else None
    e_now = (
        prediction.expected_excess_return if _has_prediction(prediction) and prediction else None
    )
    p0 = entry_prediction.p_outperform if entry_prediction else None
    e0 = entry_prediction.expected_excess_return if entry_prediction else None
    inputs: dict[str, Any] = {
        "prediction_snapshot_id": prediction.prediction_id if prediction else None, "prediction_status": prediction.prediction_status if prediction else None, "prediction_available": _has_prediction(prediction),
        "prediction_model_version": prediction.model_version if prediction else None, "p_outperform": p_now, "expected_excess_return": e_now,
        "prediction_drop_from_entry": (p0 - p_now) if p0 is not None and p_now is not None else None, "expected_return_drop_from_entry": (e0 - e_now) if e0 is not None and e_now is not None else None,
        "trade_plan_available": plan is not None, "trade_plan_risk_reward_1": plan.get("risk_reward_1") if plan else None, "data_quality_ok": label in ("High", "Medium"), "data_quality_label": label,
        "risk_regime_ok": True, "volatility_63d": (tech.get("risk") or {}).get("vol63"), "holding_sessions": holding_sessions,
    }  # fmt: skip
    return inputs, plan


def _decision_exists(session: Session, run: StrategyRun, security_id: str, key: str) -> bool:
    for (ri,) in session.execute(
        select(StrategyDecision.rule_inputs).where(
            StrategyDecision.run_id == run.run_id, StrategyDecision.security_id == security_id
        )
    ):
        if ri.get("decision_key") == key:
            return True
    return False


def _record(
    session: Session,
    run: StrategyRun,
    security_id: str,
    decision_at: datetime,
    res: DecisionResult,
    prediction: PredictionSnapshot | None,
    plan: dict[str, Any] | None,
) -> StrategyDecision:
    d = StrategyDecision(
        run_id=run.run_id, strategy_id=run.strategy_id, strategy_version=run.strategy_version, security_id=security_id, decision_at=decision_at, prediction_snapshot_id=prediction.prediction_id if prediction else None,
        trade_plan_snapshot=plan, trade_plan_hash=content_hash(plan) if plan else None, rule_inputs=res.rule_inputs, rules_evaluated=res.rules_evaluated, rules_passed=res.rules_passed, rules_failed=res.rules_failed,
        decision=res.decision, exit_reason=res.exit_reason, is_synthetic=run.is_synthetic,
    )  # fmt: skip
    session.add(d)
    session.flush()
    return d


def _link(session: Session, decision: StrategyDecision, simulation_id: str, role: str) -> None:
    session.add(
        StrategySimulationLink(
            decision_id=decision.decision_id, simulation_id=simulation_id, role=role
        )
    )
    session.flush()


def _open_simulation(
    session: Session,
    settings: Settings,
    run: StrategyRun,
    spec: StrategySpec,
    security_id: str,
    decision_at: datetime,
) -> Simulation:
    auth = sim.AutoPaperAuthority(spec.strategy_id, run.strategy_version, spec.family, run.run_kind)
    s = spec.position_sizing
    kw: dict[str, Any] = {
        "mode": "AUTO_PAPER",
        "authority": auth,
        "at": decision_at,
        "capital": float(s.get("capital", 100_000.0)),
        "risk_pct": float(s.get("risk_pct", 1.0)),
        "horizon_sessions": int(spec.risk_rules.get("max_holding_sessions", 20)),
    }
    if spec.family in ("TRADE_PLAN_ONLY", "HYBRID"):
        return sim.create_simulation(session, settings, security_id, plan_origin="PITQUANT", **kw)
    px = float(AnalyzerService(session, settings).quote(security_id, decision_at)["price"])
    plan = sim.PlanInput(
        entry_type="MARKET_REFERENCE",
        stop_loss=px * (1.0 - float(spec.risk_rules.get("catastrophic_stop_pct", 0.25))),
        target_1=px * (1.0 + float(spec.risk_rules.get("target_pct", 2.0))),
        exit_policy="TRACK_TARGETS_ONLY",
    )  # a catastrophic stop (UNVALIDATED) + far target keep the paper trade valid; exits are the prediction and the horizon
    return sim.create_simulation(
        session, settings, security_id, plan_origin="USER_DEFINED", plan=plan, **kw
    )


def _close_by_strategy(
    session: Session, settings: Settings, simulation_id: str, decision_at: datetime, reason: str
) -> None:
    sim.update_simulation(session, settings, simulation_id, decision_at)
    out = sim.latest_outcome(session, simulation_id)
    if out is None or out.is_closed:
        return
    if out.entry_date is None:
        sim.cancel_simulation(
            session, settings, simulation_id, at=decision_at, reason=f"STRATEGY_EXIT:{reason}"
        )
    else:
        row = session.get_one(Simulation, simulation_id)
        bars, _ = sim._bars_after(session, row, decision_at)
        px = float(bars["close"].iloc[-1]) if len(bars) else float(out.entry_price or 0.0)
        sim.close_manual(
            session,
            settings,
            simulation_id,
            at=decision_at,
            price=px,
            reason=f"STRATEGY_EXIT:{reason}",
        )
    sim.update_simulation(session, settings, simulation_id, decision_at)


def process_decision(
    session: Session,
    settings: Settings,
    run: StrategyRun,
    security_id: str,
    decision_at: datetime,
    *,
    prediction_exact: bool = True,
    not_before: datetime | None = None,
) -> StrategyDecision | None:
    """ONE rule evaluation for (run, security, decision_at). Returns None when this period was already decided (idempotent)."""
    strategy = session.get_one(StrategyDefinition, run.strategy_row_id)
    spec = spec_of(strategy)
    ho = settings.validation.final_holdout
    if ho.start <= decision_at.date() <= ho.end:
        raise HoldoutAccessError("a strategy decision cannot be taken inside the sealed holdout")
    if run.activated_at is not None and decision_at < run.activated_at:
        raise StrategyError("a forward run never decides before its activation")
    key = period_key(decision_at, spec.rebalance_frequency)
    if _decision_exists(session, run, security_id, key):
        return None
    allow_synth = run.run_kind == "SYNTHETIC"
    positions = _positions(session, run, security_id)
    # a position the simulation engine already closed (stop / target / invalidation / horizon): record it ONCE as an EXIT decision with its reason
    for _entry_dec, sm in positions:
        sim.update_simulation(session, settings, sm.simulation_id, decision_at)
        out = sim.latest_outcome(session, sm.simulation_id)
        if out is not None and out.is_closed:
            reason = STATE_TO_EXIT_REASON.get(out.state, "UNRESOLVED")
            res = DecisionResult(
                "EXIT",
                reason,
                {
                    "decision_key": key,
                    "position_closed_by": "SIMULATION_ENGINE",
                    "simulation_state": out.state,
                },
                [
                    {
                        "id": "SIMULATION_ENGINE",
                        "kind": "ENGINE",
                        "metric": "simulation_state",
                        "op": "==",
                        "value": out.state,
                        "observed": out.state,
                        "passed": True,
                        "label": "STRUCTURAL",
                        "exit_reason": reason,
                    }
                ],
                ["SIMULATION_ENGINE"],
                [],
            )
            d = _record(session, run, security_id, decision_at, res, None, None)
            _link(session, d, sm.simulation_id, "EXIT")
            return d
    open_pos = [
        (e, sm)
        for e, sm in positions
        if (lo := sim.latest_outcome(session, sm.simulation_id)) is None or not lo.is_closed
    ]
    entry_pred = (
        session.get(PredictionSnapshot, open_pos[0][0].prediction_snapshot_id)
        if open_pos and open_pos[0][0].prediction_snapshot_id
        else None
    )
    pred = lookup_prediction(
        session,
        security_id,
        spec.prediction_horizon_months,
        decision_at,
        exact=prediction_exact,
        not_before=not_before,
    )
    holding = None
    if open_pos:
        from pitquant.data.calendars.market_calendar import get_calendar

        holding = (
            len(
                get_calendar("XNYS").sessions(open_pos[0][0].decision_at.date(), decision_at.date())
            )
            - 1
        )
    inputs, plan = build_inputs(
        session, settings, spec, security_id, decision_at, pred, entry_pred, holding
    )
    inputs["decision_key"] = key
    inputs["strategy_family"] = spec.family
    inputs["costs"] = spec.costs
    res = evaluate_strategy(
        spec,
        inputs,
        in_position=bool(open_pos),
        allow_synthetic=allow_synth,
        positions_open=_all_positions_open(session, run),
    )
    new_sim: Simulation | None = None
    if res.decision == "ENTER" and spec.family != "BUY_AND_HOLD":
        try:
            with session.begin_nested():
                new_sim = _open_simulation(session, settings, run, spec, security_id, decision_at)
        except (sim.SimulationError, sim.PriceDataRequired) as e:
            res.decision = "NO_ACTION"
            res.rules_failed.append("SIMULATION_CREATE_FAILED")
            res.rules_evaluated.append(
                {
                    "id": "SIMULATION_CREATE_FAILED",
                    "kind": "GATE",
                    "metric": "simulation",
                    "op": "==",
                    "value": "OK",
                    "observed": str(e)[:200],
                    "passed": False,
                    "label": "STRUCTURAL",
                    "exit_reason": None,
                }
            )
    d = _record(session, run, security_id, decision_at, res, pred, plan)
    if new_sim is not None:
        _link(session, d, new_sim.simulation_id, "ENTRY")
        sim.update_simulation(session, settings, new_sim.simulation_id, decision_at)
    if res.decision == "EXIT" and open_pos:
        _close_by_strategy(
            session,
            settings,
            open_pos[0][1].simulation_id,
            decision_at,
            res.exit_reason or "PREDICTION_DETERIORATION",
        )
        _link(session, d, open_pos[0][1].simulation_id, "EXIT")
    return d


# ───────────────────────────────────────────── runners
def run_synthetic(
    session: Session, settings: Settings, run: StrategyRun, decision_dates: Sequence[datetime]
) -> list[StrategyDecision]:
    """Replay a fixed list of decision instants over the run's universe (fixture data). Each instant uses ONLY data and predictions known at it."""
    if run.run_kind != "SYNTHETIC":
        raise StrategyError("run_synthetic needs a SYNTHETIC run")
    return _run_dates(session, settings, run, decision_dates)


def run_historical(
    session: Session, settings: Settings, run: StrategyRun, decision_dates: Sequence[datetime]
) -> list[StrategyDecision]:
    """HISTORICAL: executes only when the data gates were open at creation (``blocked_reasons`` empty); a BLOCKED run executes nothing."""
    if run.run_kind != "HISTORICAL":
        raise StrategyError("run_historical needs a HISTORICAL run")
    if run.blocked_reasons:
        return []
    return _run_dates(session, settings, run, decision_dates)


def _run_dates(
    session: Session, settings: Settings, run: StrategyRun, decision_dates: Sequence[datetime]
) -> list[StrategyDecision]:
    out: list[StrategyDecision] = []
    for at in sorted(decision_dates):
        for sid in run.universe:
            d = process_decision(session, settings, run, sid, at)
            if d is not None:
                out.append(d)
    _event(
        session,
        run,
        "COMPLETED",
        CLOCK(),
        {"decisions": len(out), "dates": len(list(decision_dates))},
    )
    return out


def forward_tick(
    session: Session, settings: Settings, run: StrategyRun, as_of: datetime | None = None
) -> list[StrategyDecision]:
    """One forward step at the SERVER's now (``as_of`` exists for tests only). Rejects any instant before activation: nothing is back-dated."""
    if run.run_kind != "FORWARD_PAPER" or run.activated_at is None:
        raise StrategyError("forward_tick needs an activated FORWARD_PAPER run")
    if run_status(session, run) != "ACTIVE":
        raise StrategyError("the run is not ACTIVE")
    now = as_of or CLOCK()
    if now < run.activated_at:
        raise StrategyError("a forward tick cannot look before the activation instant")
    out = []
    for sid in run.universe:
        d = process_decision(
            session, settings, run, sid, now, prediction_exact=False, not_before=run.activated_at
        )
        if d is not None:
            out.append(d)
    _event(session, run, "TICK", now, {"decisions": len(out)})
    return out


def stop_run(session: Session, run: StrategyRun) -> None:
    _event(session, run, "STOPPED", CLOCK(), {})


def outcome_of(session: Session, simulation_id: str) -> SimulationOutcome | None:
    return sim.latest_outcome(session, simulation_id)
