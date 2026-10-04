"""BTC 24/7 orchestration of the existing append-only Simulation Lab, engine and replay."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.btc.contracts import BTC_CAUSES, ENGINE_VERSION, Cohort
from pitquant.btc.features import known_data
from pitquant.btc.models import BTCFeatureSnapshot, BTCPredictionSnapshot, BTCResearchRecord
from pitquant.core.timeutils import utc_now
from pitquant.db.models import (
    Security,
    Simulation,
    SimulationEvent,
    SimulationObservation,
    SimulationPostMortem,
)
from pitquant.simulation import registry
from pitquant.simulation.engine import Evaluation, PlanLevels
from pitquant.simulation.service import (
    POSTMORTEM_CAUSES,
    _as_dict,
    _materialise,
    _norm,
    latest_outcome,
    plan_of,
    snapshot_hash,
    stored_events,
    verify_snapshot,
)


class BTCSimulationEngine:
    """Same conservative bar semantics as the frozen pure engine; no equity calendar/CA pipeline."""

    version = ENGINE_VERSION
    event_schema_version = 1
    event_labels = (ENGINE_VERSION,)

    def evaluate(
        self,
        plan: PlanLevels,
        bars: pd.DataFrame,
        decision_date: date,
        *,
        benchmark: pd.Series | None = None,
        manual_close: tuple[date, float] | None = None,
        reference_price: float | None = None,
        cancel_on: date | None = None,
    ) -> Evaluation:
        # Price discontinuities are observed moves, never an assumed market closure.
        ev = registry.SimulationEngineV1().evaluate(
            plan,
            bars,
            decision_date,
            benchmark=None,
            manual_close=manual_close,
            reference_price=reference_price,
            cancel_on=cancel_on,
        )
        if benchmark is not None and reference_price:
            for event in ev.events:
                if event["type"] == "BAR_PROCESSED":
                    day = date.fromisoformat(event["date"])
                    event["payload"]["btc_benchmark_t0_price"] = reference_price
                    event["payload"]["btc_benchmark_close"] = float(benchmark.loc[day])
            end = ev.exit_date or ev.last_bar
            if end in benchmark.index and ev.metrics.get("realized_return") is not None:
                buy_hold = float(benchmark.loc[end]) / reference_price - 1
                ev.metrics["excess_return_vs_benchmark"] = (
                    float(ev.metrics["realized_return"] or 0) - buy_hold
                )
                ev.details["benchmark_return"] = buy_hold
                ev.details["benchmark_window"] = "T0_TO_LAST_EXECUTION_BAR_CLOSE"
        return ev

    def fold_events(self, events: list[dict[str, Any]], plan: PlanLevels) -> dict[str, Any]:
        folded = registry.SimulationEngineV1().fold_events(events, plan)
        processed = [
            e["payload"]
            for e in events
            if e["type"] == "BAR_PROCESSED" and e["payload"].get("btc_benchmark_t0_price")
        ]
        if processed:
            last = processed[-1]
            folded["_bench_hint"] = last["btc_benchmark_close"] / last["btc_benchmark_t0_price"] - 1
        return folded


registry.SIMULATION_ENGINES.setdefault(ENGINE_VERSION, BTCSimulationEngine())


def trade_plan(snapshot: BTCFeatureSnapshot) -> dict[str, Any]:
    f = snapshot.payload
    px, atr = f["price_features"].get("price"), f["volatility_features"].get("ATR14")
    if not f["spot_ready"] or not px or not atr or px - 2 * atr <= 0:
        return {"status": "BLOCKED_BY_DATA", "reason": "CURRENT_PRICE_AND_ATR14_REQUIRED"}
    return {
        "status": "NOT_YET_BACKTEST_VALIDATED",
        "kind": "RULE_BASED",
        "side": "LONG",
        "entry_type": "MARKET",
        "entry_zone_low": px,
        "entry_zone_high": px,
        "stop_loss": px - 2 * atr,
        "invalidation_level": px - 2 * atr,
        "target_1": px + 2 * atr,
        "target_2": px + 4 * atr,
        "exit_policy": "PARTIAL_FRACTIONS",
        "exit_fractions": [0.5, 0.5, 0],
        "risk_reward": {"tp1": 1, "tp2": 2},
        "rule": "ATR14_STOP_2X_TARGET_2X_4X",
        "support": px - 2 * atr,
        "resistance": px + 2 * atr,
        "sr_kind": "PIT_CONFIRMED_PIVOTS_WITH_ATR_FALLBACK",
        "support_resistance": f["support_resistance"],
        "prediction_used": False,
        "strategy_version": snapshot.strategy_version,
    }


def create(
    session: Session,
    snapshot: BTCFeatureSnapshot,
    *,
    notional: float = 1000,
    days: int = 30,
    commission_bps: float = 0,
    slippage_bps: float = 0,
    funding_cost: float = 0,
    market_reference: dict[str, Any] | None = None,
) -> Simulation:
    if notional <= 0 or days <= 0 or min(commission_bps, slippage_bps, funding_cost) < 0:
        raise ValueError("positive notional/days and nonnegative costs required")
    prediction = session.scalar(
        select(BTCPredictionSnapshot).where(
            BTCPredictionSnapshot.snapshot_id == snapshot.snapshot_id,
            BTCPredictionSnapshot.horizon == days,
        )
    )
    if prediction is None:
        raise ValueError("FROZEN_HORIZON_PREDICTION_REQUIRED")
    p = trade_plan(snapshot)
    if p["status"] == "BLOCKED_BY_DATA":
        raise ValueError(p["reason"])
    security = session.get(Security, "btc-spot")
    if security is None:
        security = Security(
            security_id="btc-spot", name="Bitcoin BTCUSDT", exchange="XCRY", currency="USDT"
        )
        session.add(security)
        session.flush()
    knowledge_at = datetime.fromisoformat(snapshot.payload["knowledge_at"])
    effective = (
        max(knowledge_at, utc_now()) if snapshot.cohort == Cohort.FORWARD_PAPER else knowledge_at
    )
    midnight = effective.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    execution_start = midnight if effective == midnight else midnight + timedelta(days=1)
    quantity = notional / p["entry_zone_high"]  # fractional BTC, no integer shares
    sim = Simulation(
        security_id=security.security_id,
        asset_type="BTC",
        mode="MANUAL_SIMULATION",
        decision_at=snapshot.decision_at,
        created_at=utc_now(),
        analyzer_version="btc-analyzer-v0",
        feature_version=snapshot.feature_version,
        model_version=prediction.payload.get("model_version"),
        model_id=None,
        rules_version=snapshot.strategy_version,
        prediction_status=prediction.payload["status"],
        simulation_engine_version=ENGINE_VERSION,
        price_snapshot=snapshot.payload["price_features"],
        fundamental_snapshot={},
        valuation_snapshot={},
        technical_snapshot=snapshot.payload,
        support_resistance_snapshot={"support": p["support"], "resistance": p["resistance"]},
        trade_plan_snapshot=p,
        market_regime_snapshot=snapshot.payload["regime"],
        data_quality={
            "cohort": snapshot.cohort,
            "availability": snapshot.payload["availability"],
            **({"market_reference_quote": market_reference} if market_reference else {}),
        },
        funding_snapshot=snapshot.payload["derivatives_features"],
        open_interest_snapshot=snapshot.payload["derivatives_features"],
        basis_snapshot=snapshot.payload["derivatives_features"],
        onchain_snapshot=snapshot.payload["network_features"],
        plan_origin="PITQUANT",
        original_pitquant_plan=p,
        final_simulated_plan=p,
        side="LONG",
        entry_type=p["entry_type"],
        entry_zone_low=p["entry_zone_low"],
        entry_zone_high=p["entry_zone_high"],
        stop_loss=p["stop_loss"],
        invalidation_level=p["invalidation_level"],
        target_1=p["target_1"],
        target_2=p["target_2"],
        risk_reward_expected=1,
        position_size_simulated=quantity,
        capital_at_risk=quantity * (p["entry_zone_high"] - p["stop_loss"]),
        time_horizon_sessions=days,
        expiration_at=snapshot.decision_at + timedelta(days=days),
        source_provenance={
            "btc_snapshot_id": snapshot.snapshot_id,
            "prediction_at_creation": {
                "prediction_id": prediction.prediction_id,
                "prediction_hash": prediction.prediction_hash,
                "horizon_days": prediction.horizon,
                "decision_at": snapshot.decision_at.isoformat(),
                "target_at": (snapshot.decision_at + timedelta(days=days)).isoformat(),
                "payload": prediction.payload,
                "plan": p,
            },
            "execution_not_before": execution_start.isoformat(),
            "cohort": snapshot.cohort,
            "snapshot_hash": snapshot.snapshot_hash,
            "versions": {
                "data_version": snapshot.data_version,
                "feature_version": snapshot.feature_version,
                "model_version": prediction.payload.get("model_version"),
                "strategy_version": snapshot.strategy_version,
                "simulation_engine_version": ENGINE_VERSION,
                "commit_sha": snapshot.commit_sha,
            },
            "costs": {
                "commission_bps": commission_bps,
                "slippage_bps": slippage_bps,
                "funding_cost": funding_cost,
            },
            "warning": "COSTS_NOT_MODELED"
            if not any((commission_bps, slippage_bps, funding_cost))
            else None,
            "benchmark": "BTC_BUY_AND_HOLD",
            "cash_return": 0,
        },
    )
    sim.snapshot_hash = snapshot_hash(sim)
    session.add(sim)
    session.flush()
    session.add(
        SimulationEvent(
            simulation_id=sim.simulation_id,
            sequence_number=0,
            event_type="SIMULATION_CREATED",
            occurred_at=sim.decision_at.date(),
            payload_json={"state_after": "CREATED"},
            engine_version=ENGINE_VERSION,
            event_schema_version=1,
        )
    )
    session.flush()
    return sim


def update(session: Session, simulation_id: str, as_of: datetime) -> dict[str, Any]:
    sim = session.get_one(Simulation, simulation_id)
    if sim.asset_type != "BTC" or not verify_snapshot(sim):
        raise ValueError("BTC_SNAPSHOT_REQUIRED")
    cohort = (sim.source_provenance or {})["cohort"]
    if cohort == Cohort.FORWARD_PAPER and as_of > utc_now():
        raise ValueError("FUTURE_FORWARD_EVALUATION")
    if as_of < sim.decision_at:
        raise ValueError("cannot evaluate before T0")
    data = [r for r in known_data(session, as_of, cohort) if r.metric == "spot"]
    # Day d OHLC executes AFTER the preceding close boundary; UTC bars include weekends.
    bars = pd.DataFrame(
        [r.payload for r in data],
        index=[(r.exchange_timestamp - timedelta(days=1)).date() for r in data],
    )
    if bars.empty:
        bars = pd.DataFrame(columns=["open", "high", "low", "close"])
    # T0 is the close of the previous day, so the new day's open is the first executable bar.
    decision_date = (
        datetime.fromisoformat((sim.source_provenance or {})["execution_not_before"])
        - timedelta(days=1)
    ).date()
    bars = bars.loc[bars.index > decision_date]
    bench = bars["close"].copy()
    ev = registry.resolve_engine(sim.simulation_engine_version).evaluate(
        plan_of(sim), bars, decision_date, benchmark=bench, reference_price=sim.entry_zone_high
    )
    old = stored_events(session, simulation_id)
    # Created event date follows the shared engine's decision-session convention.
    if ev.events:
        ev.events[0]["date"] = str(sim.decision_at.date())
    for row, event in zip(old, ev.events, strict=False):
        if _norm(_as_dict(row)) != _norm(event):
            raise ValueError(
                "EVENT_LOG_DIVERGENCE: corrected bars cannot overwrite forward history"
            )
    added = ev.events[len(old) :]
    for index, event in enumerate(added, len(old)):
        session.add(
            SimulationEvent(
                simulation_id=simulation_id,
                sequence_number=index,
                event_type=event["type"],
                occurred_at=date.fromisoformat(event["date"]),
                source_bar_timestamp=date.fromisoformat(event["date"]),
                payload_json=event["payload"],
                engine_version=sim.simulation_engine_version,
                event_schema_version=1,
            )
        )
    session.flush()
    outcome = latest_outcome(session, simulation_id)
    if added or outcome is None:
        outcome = _materialise(
            sim, ev, as_of, max(len(old), len(ev.events)), len(bars), sim.simulation_engine_version
        )
        costs = (sim.source_provenance or {})["costs"]
        raw = outcome.realized_return
        modeled_cost = (
            2 * (costs["commission_bps"] + costs["slippage_bps"]) / 10000 + costs["funding_cost"]
        )
        outcome.details = {
            **outcome.details,
            "cohort": cohort,
            "gross_return": raw,
            "net_return": None if raw is None else raw - modeled_cost,
            "benchmark": "BTC_BUY_AND_HOLD",
            "costs": costs,
            "warning": (sim.source_provenance or {}).get("warning"),
        }
        session.add(outcome)
        session.flush()
    for days in (1, 7, 30, 90):
        label = f"BTC_T+{days}D"
        boundary = sim.decision_at + timedelta(days=days)
        exists = session.scalar(
            select(SimulationObservation.observation_id).where(
                SimulationObservation.simulation_id == simulation_id,
                SimulationObservation.horizon_label == label,
            )
        )
        matching = [
            r
            for r in data
            if r.exchange_timestamp == boundary
            and r.available_at <= boundary + timedelta(minutes=15)
        ]
        if not exists and matching:
            session.add(
                SimulationObservation(
                    simulation_id=simulation_id,
                    observed_at=boundary,
                    kind="PERIODIC",
                    horizon_label=label,
                    source_bar_date=(boundary - timedelta(days=1)).date(),
                    observation_schema_version=1,
                    analyzer_version=sim.analyzer_version,
                    feature_version=sim.feature_version,
                    payload={
                        "cohort": cohort,
                        "close": matching[0].payload["close"],
                        "datum_id": matching[0].datum_id,
                        "raw_hash": matching[0].raw_hash,
                        "causality": "NO_AUTOMATIC_CLASSIFICATION",
                    },
                )
            )
    session.flush()
    pinned_prediction = (sim.source_provenance or {}).get("prediction_at_creation")
    if pinned_prediction and as_of >= datetime.fromisoformat(pinned_prediction["target_at"]):
        from pitquant.btc.research import reveal

        already = session.scalar(
            select(BTCResearchRecord.record_id).where(
                BTCResearchRecord.kind == "REVEAL_OUTCOME",
                BTCResearchRecord.prediction_id == pinned_prediction["prediction_id"],
            )
        )
        if already is None:
            try:
                reveal(session, pinned_prediction["prediction_id"], as_of)
            except ValueError as exc:
                if str(exc) != "EXACT_TARGET_PRICE_REQUIRED":
                    raise
                # A missing target keeps the assessment pending; never invent an outcome.
    return {
        "state": outcome.state,
        "is_closed": outcome.is_closed,
        "new_events": len(added),
        "outcome": outcome.details,
        "simulation_id": simulation_id,
    }


def postmortem(
    session: Session, simulation_id: str, cause: str, classified_by: str, notes: str = ""
) -> SimulationPostMortem:
    sim = session.get_one(Simulation, simulation_id)
    outcome = latest_outcome(session, simulation_id)
    if sim.asset_type != "BTC" or not outcome or not outcome.is_closed:
        raise ValueError("closed BTC simulation required")
    if cause not in (*POSTMORTEM_CAUSES, *BTC_CAUSES) or not classified_by.strip():
        raise ValueError("valid cause and explicit classified_by required")
    row = SimulationPostMortem(
        simulation_id=simulation_id,
        primary_cause=cause,
        secondary_causes=[],
        notes=notes,
        classified_by=classified_by,
        metrics={"facts": outcome.details, "causality": "EXPLICIT_USER_CLASSIFICATION"},
    )
    session.add(row)
    session.flush()
    return row


def strategy_test(
    session: Session, snapshots: list[BTCFeatureSnapshot], horizon: int
) -> dict[str, Any]:
    """Evaluate frozen rule plans through the existing event store, per independent decision.

    Daily long-horizon decisions overlap: these are trade/cohort metrics, not an investable
    portfolio equity curve. Cash during an unentered/closed trade earns zero.
    """
    existing = list(session.scalars(select(Simulation).where(Simulation.asset_type == "BTC")))
    trades: list[dict[str, Any]] = []
    for snap in snapshots:
        if trade_plan(snap)["status"] == "BLOCKED_BY_DATA":
            trades.append({"snapshot_id": snap.snapshot_id, "status": "BLOCKED_BY_DATA"})
            continue
        sim = next(
            (
                s
                for s in existing
                if (s.source_provenance or {}).get("btc_snapshot_id") == snap.snapshot_id
                and s.time_horizon_sessions == horizon
                and s.plan_origin == "PITQUANT"
            ),
            None,
        )
        if sim is None:
            sim = create(session, snap, days=horizon)
            existing.append(sim)
        result = update(session, sim.simulation_id, snap.decision_at + timedelta(days=horizon))
        outcome = latest_outcome(session, sim.simulation_id)
        assert outcome is not None
        target = snap.decision_at + timedelta(days=horizon)
        target_rows = [
            r
            for r in known_data(session, target, snap.cohort)
            if r.metric == "spot" and r.exchange_timestamp == target
        ]
        if len(target_rows) != 1:
            raise ValueError("EXACT_STRATEGY_BENCHMARK_TARGET_REQUIRED")
        benchmark = target_rows[0].payload["close"] / snap.payload["price_features"]["price"] - 1
        trade_return = outcome.realized_return
        if outcome.is_closed and outcome.entry_date is None:
            trade_return = 0.0  # cash-only period; no fictional trade fill
        trades.append(
            {
                "snapshot_id": snap.snapshot_id,
                "simulation_id": sim.simulation_id,
                "status": result["state"],
                "return": trade_return,
                "excess_vs_buy_and_hold": None
                if trade_return is None
                else trade_return - benchmark,
                "drawdown": outcome.max_drawdown,
                "r": outcome.realized_r,
                "benchmark_return": benchmark,
                "benchmark_window": "T0_TO_HORIZON_INCLUDING_CASH_AFTER_EARLY_EXIT",
                "cash_return": 0,
            }
        )
    return {
        "family": "TRADE_PLAN_ONLY",
        "trades": trades,
        "returns": [t.get("return") for t in trades],
        "drawdown": [t.get("drawdown") for t in trades],
        "benchmark": "BTC_BUY_AND_HOLD",
        "evaluation_unit": "INDEPENDENT_OVERLAPPING_TRADES_NOT_PORTFOLIO",
        "cost_warning": "COSTS_NOT_MODELED",
        "superiority": "NOT_CLAIMED",
    }


def prediction_tracking(session: Session, sim: Simulation) -> dict[str, Any]:
    pinned = (sim.source_provenance or {}).get("prediction_at_creation")
    if not pinned:
        return {"status": "LEGACY_NO_PREDICTION_LINK"}
    actual = session.scalars(
        select(BTCResearchRecord)
        .where(
            BTCResearchRecord.prediction_id == pinned["prediction_id"],
            BTCResearchRecord.kind == "REVEAL_OUTCOME",
        )
        .order_by(BTCResearchRecord.created_at)
    ).first()
    outcome = latest_outcome(session, sim.simulation_id)
    plan_status = "PENDING"
    if outcome:
        if outcome.state == "AMBIGUOUS_INTRABAR":
            plan_status = "INDETERMINATE"
        elif outcome.state == "TP2":
            plan_status = "TARGETS_MET"
        elif outcome.state in ("TP1", "PARTIAL_TP"):
            plan_status = "PARTIALLY_MET"
        elif outcome.is_closed:
            plan_status = "CLOSED_WITHOUT_ALL_TARGETS"
    predicted = pinned["payload"].get("expected_return")
    validated = pinned["payload"].get("status") in ("VALIDATED", "EXPERIMENTAL_NOT_VALIDATED")
    return {
        "status": "ASSESSED"
        if actual and validated
        else "NO_VALIDATED_PREDICTION"
        if not validated
        else "WAITING_OUTCOME",
        "frozen": pinned,
        "actual": actual.payload.get("actual") if actual else None,
        "expected": predicted,
        "error": predicted - actual.payload["actual"] if actual and predicted is not None else None,
        "outcome_status": "MATURED" if actual else "WAITING_HORIZON_OR_DATA",
        "plan_status": plan_status,
        "tp1_met": bool(
            outcome
            and (outcome.details.get("tp1_hit") or 1 in outcome.details.get("targets_touched", []))
        ),
        "tp2_met": bool(
            outcome
            and (outcome.details.get("tp2_hit") or 2 in outcome.details.get("targets_touched", []))
        ),
        "outcome_record_id": actual.record_id if actual else None,
        "forecast_correct": ((pinned["payload"]["p_up"] >= 0.5) == bool(actual.payload["UP_H"]))
        if actual and validated and pinned["payload"].get("p_up") is not None
        else None,
        "validation_status": pinned["payload"].get("status"),
    }
