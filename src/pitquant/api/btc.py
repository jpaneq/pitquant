"""Bitcoin Analyzer/Labs HTTP API; all writes stay in BTC or existing Simulation Lab tables."""

from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import AwareDatetime, BaseModel
from sqlalchemy import select

from pitquant.api.app import DB
from pitquant.api.simulations import row
from pitquant.btc.contracts import BTC_CAUSES, Cohort, target_time
from pitquant.btc.evaluation import analysis, evaluate_due
from pitquant.btc.experimental import forecast, latest_models
from pitquant.btc.features import feature_payload
from pitquant.btc.market import chart_bars, live_market
from pitquant.btc.models import BTCFeatureSnapshot, BTCPredictionSnapshot, BTCResearchRecord
from pitquant.btc.quote import LiveQuote
from pitquant.btc.research import freeze, guard_holdout, historical_test, readiness, reveal
from pitquant.btc.simulation import create, postmortem, prediction_tracking, trade_plan, update
from pitquant.core.timeutils import utc_now
from pitquant.db.models import (
    ResearchHypothesis,
    Simulation,
    SimulationOutcome,
    SimulationPostMortem,
)
from pitquant.simulation.service import replay_simulation


class AsOf(BaseModel):
    decision_at: AwareDatetime
    cohort: Cohort = Cohort.FORWARD_PAPER
    knowledge_at: AwareDatetime | None = None


class Simulate(BaseModel):
    snapshot_id: str
    notional: float = 1000
    horizon_days: int = 30
    use_live_reference: bool = False


class Update(BaseModel):
    as_of: AwareDatetime


class Postmortem(BaseModel):
    primary_cause: str
    classified_by: str
    notes: str = ""


class Hypothesis(BaseModel):
    statement: str
    created_by: str
    evidence: dict[str, Any]


class HistoricalTest(BaseModel):
    start: AwareDatetime
    end: AwareDatetime
    horizon: int
    feature_version: str = "btc-core-v0"
    model_version: str = "btc-core-baseline-v0"
    strategy_version: str = "btc-plan-v0"


def _market(db: Any) -> dict[str, Any]:
    if os.environ.get("PITQUANT_E2E_FIXTURE") == "1":
        from pitquant.btc.fixtures import synthetic_binance_fetch

        now = utc_now()
        return live_market(db, synthetic_binance_fetch(now), now, data_mode="SYNTHETIC_TEST_DATA")
    return live_market(db)


def make_btc_router() -> APIRouter:
    router = APIRouter(prefix="/btc", tags=["bitcoin"])
    live_quote = LiveQuote()

    @router.get("/quote")
    def quote(symbol: str = "BTCUSDT") -> dict[str, Any]:
        if os.environ.get("PITQUANT_E2E_FIXTURE") == "1":
            return {"status": "DISABLED", "reason": "SYNTHETIC_FIXTURE_NO_EXTERNAL_DATA"}
        try:
            return live_quote.get(symbol)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(
                503, "BTC_LIVE_QUOTE_UNAVAILABLE", headers={"Retry-After": "5"}
            ) from exc

    @router.get("/market/live")
    def market_live(db: DB) -> dict[str, Any]:
        """LIVE display and last closed MODEL bar, strictly separate."""
        return _market(db)

    @router.get("/market/bars")
    def market_bars(db: DB, range: str = "1Y") -> dict[str, Any]:
        try:
            return chart_bars(db, range, utc_now())
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.get("/quote/history")
    def quote_history(symbol: str = "BTCUSDT", range: str = "LIVE") -> dict[str, Any]:
        if os.environ.get("PITQUANT_E2E_FIXTURE") == "1":
            return {"status": "DISABLED", "points": []}
        try:
            return live_quote.history(symbol, range)
        except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
            raise HTTPException(503, "BTC_INTRADAY_HISTORY_UNAVAILABLE") from exc

    @router.get("/trade-plan")
    def live_trade_plan(db: DB) -> dict[str, Any]:
        """Rule-based BTC trade plan from the latest CLOSED daily bar (no freeze needed). NOT validated; not a forecast."""  # noqa: E501
        from types import SimpleNamespace

        from pitquant.btc.contracts import STRATEGY_VERSION
        from pitquant.positions.service import PositionError, btc_latest_payload

        try:
            payload = btc_latest_payload(db, utc_now())
        except PositionError as exc:
            raise HTTPException(409, str(exc)) from exc
        plan = trade_plan(SimpleNamespace(payload=payload, strategy_version=STRATEGY_VERSION))  # type: ignore[arg-type]
        return {
            "as_of_bar": payload["decision_at"],
            "plan": plan,
            "label": "RULE_BASED · NOT BACKTEST VALIDATED",
            "price_basis": "closed 1D UTC bar",
            "price_features": payload["price_features"].get("price"),
        }

    @router.get("/evaluation")
    def evaluation(db: DB, cohort: Cohort = Cohort.FORWARD_PAPER) -> dict[str, Any]:
        """Follow-up of frozen predictions: pending (with maturity date), evaluated, and per-horizon skill against history."""  # noqa: E501
        return analysis(db, utc_now(), cohort)

    @router.post("/evaluation/run")
    def evaluation_run(db: DB, cohort: Cohort = Cohort.FORWARD_PAPER) -> dict[str, Any]:
        result = evaluate_due(db, utc_now(), cohort)
        db.commit()
        return result

    @router.post("/experimental/forecast")
    def experimental_forecast(db: DB) -> dict[str, Any]:
        try:
            snap = forecast(db)
            db.commit()
            return snapshot_view(db, snap)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.get("/experimental/history")
    def experimental_history(db: DB, horizon: int = 30) -> dict[str, Any]:
        model = latest_models(db).get(horizon)
        if model is None:
            return {"status": "BLOCKED_BY_DATA", "predictions": []}
        return {k: v for k, v in model.payload.items() if k not in ("reg", "cls", "features")}

    @router.get("/status")
    def status(db: DB, cohort: Cohort = Cohort.FORWARD_PAPER) -> dict[str, Any]:
        collection = db.scalars(
            select(BTCResearchRecord)
            .where(BTCResearchRecord.kind == "COLLECTION")
            .order_by(BTCResearchRecord.created_at.desc())
        ).first()
        result = readiness(db, cohort)
        db.commit()
        return {
            "asset_type": "BTC",
            "frequency": "1D UTC",
            "decision_close": "00:00 UTC",
            "prediction_status": "NOT_YET_VALIDATED",
            "auto_trade": "NO_AUTO_PREDICTION_TRADE",
            "data": collection.payload if collection else None,
            "readiness": result,
            "strategies": {
                "TRADE_PLAN_ONLY": "NOT_YET_BACKTEST_VALIDATED",
                "BUY_AND_HOLD": "BENCHMARK",
                "PREDICTION_ONLY": "DISABLED",
                "HYBRID": "DISABLED",
            },
            "bitcoin_core": "NOT_CONFIGURED",
            "macro": "OPTIONAL_UNAVAILABLE",
        }

    @router.get("/analyzer")
    def analyzer(
        db: DB, decision_at: AwareDatetime, cohort: Cohort = Cohort.FORWARD_PAPER
    ) -> dict[str, Any]:
        try:
            guard_holdout(db, decision_at, cohort)
            payload = feature_payload(db, decision_at, cohort)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return payload

    @router.post("/freeze")
    def freeze_prediction(body: AsOf, db: DB) -> dict[str, Any]:
        try:
            snap = freeze(db, body.decision_at, body.cohort, body.knowledge_at)
            db.commit()
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return snapshot_view(db, snap)

    @router.get("/snapshots")
    def snapshots(db: DB, cohort: Cohort = Cohort.FORWARD_PAPER) -> list[dict[str, Any]]:
        rows = db.scalars(
            select(BTCFeatureSnapshot)
            .where(BTCFeatureSnapshot.cohort == cohort)
            .order_by(BTCFeatureSnapshot.decision_at.desc())
            .limit(100)
        )
        return [snapshot_view(db, snap) for snap in rows]

    @router.post("/predictions/{prediction_id}/reveal")
    def reveal_outcome(prediction_id: str, body: Update, db: DB) -> dict[str, Any]:
        try:
            result = reveal(db, prediction_id, body.as_of)
            db.commit()
        except ValueError as exc:
            if str(exc) == "LABEL_NOT_MATURE":
                pred = db.get(BTCPredictionSnapshot, prediction_id)
                snap = db.get(BTCFeatureSnapshot, pred.snapshot_id) if pred else None
                matures = target_time(snap.decision_at, pred.horizon) if pred and snap else None
                raise HTTPException(
                    409,
                    {
                        "code": "LABEL_NOT_MATURE",
                        "matures_at": matures.isoformat() if matures else None,
                        "message": f"La predicción aún no ha madurado: se podrá evaluar el {matures:%Y-%m-%d %H:%M} UTC. El seguimiento automático la comprobará entonces.",  # noqa: E501
                    },
                ) from exc
            raise HTTPException(409, str(exc)) from exc
        return row(result)

    @router.post("/historical-tests")
    def run_historical_test(body: HistoricalTest, db: DB) -> dict[str, Any]:
        try:
            result = historical_test(
                db,
                body.start,
                body.end,
                body.horizon,
                body.feature_version,
                body.model_version,
                body.strategy_version,
            )
            db.commit()
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return result

    @router.get("/research")
    def research(db: DB, cohort: Cohort = Cohort.FORWARD_PAPER) -> dict[str, Any]:
        records = list(
            db.scalars(
                select(BTCResearchRecord)
                .where(
                    BTCResearchRecord.cohort == cohort, BTCResearchRecord.kind != "CATALOG_SNAPSHOT"
                )
                .order_by(BTCResearchRecord.created_at.desc())
                .limit(100)
            )
        )
        return {
            "cohort": cohort,
            "records": [row(r) for r in records],
            "calibration": [],
            "warning": "NO_VALIDATED_MODEL_PREDICTIONS",
            "causes": BTC_CAUSES,
        }

    @router.post("/hypotheses")
    def hypothesis(body: Hypothesis, db: DB) -> dict[str, Any]:
        if not body.statement.strip() or not body.created_by.strip():
            raise HTTPException(422, "statement and created_by required")
        h = ResearchHypothesis(
            statement=body.statement,
            created_by=body.created_by,
            evidence={"asset_type": "BTC", **body.evidence},
            source="BTC_RESEARCH",
        )
        db.add(h)
        db.commit()
        return row(h)

    @router.post("/simulations")
    def simulate(body: Simulate, db: DB) -> dict[str, Any]:
        snap = db.get(BTCFeatureSnapshot, body.snapshot_id)
        if snap is None:
            raise HTTPException(404, "snapshot not found")
        try:
            reference = None
            if body.use_live_reference:
                m = _market(db)
                # server-side only: the client never supplies the reference price
                reference = {
                    "price": m["quote"]["price"],
                    "retrieved_at": m["quote"]["retrieved_at"],
                    "source": m["quote"]["source"],
                    "freshness": m["quote"]["status"],
                    "usage": "VISUAL_T0_REFERENCE_ONLY",
                }
            sim = create(
                db, snap, notional=body.notional, days=body.horizon_days, market_reference=reference
            )
            db.commit()
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return row(sim)

    @router.get("/simulations")
    def simulations(db: DB, cohort: Cohort = Cohort.FORWARD_PAPER) -> list[dict[str, Any]]:
        return [
            row(s)
            for s in db.scalars(select(Simulation).where(Simulation.asset_type == "BTC"))
            if (s.source_provenance or {}).get("cohort") == cohort
        ]

    @router.post("/simulations/{simulation_id}/update")
    def update_sim(simulation_id: str, body: Update, db: DB) -> dict[str, Any]:
        try:
            result = update(db, simulation_id, body.as_of)
            db.commit()
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return result

    @router.get("/simulations/{simulation_id}")
    def simulation_detail(simulation_id: str, db: DB) -> dict[str, Any]:
        sim = db.get(Simulation, simulation_id)
        if not sim or sim.asset_type != "BTC":
            raise HTTPException(404, "BTC simulation not found")
        return {
            "simulation": row(sim),
            "prediction_tracking": prediction_tracking(db, sim),
            "replay": asdict(replay_simulation(db, simulation_id)),
            "outcomes": [
                row(o)
                for o in db.scalars(
                    select(SimulationOutcome).where(
                        SimulationOutcome.simulation_id == simulation_id
                    )
                )
            ],
            "postmortems": [
                row(p)
                for p in db.scalars(
                    select(SimulationPostMortem).where(
                        SimulationPostMortem.simulation_id == simulation_id
                    )
                )
            ],
        }

    @router.post("/simulations/{simulation_id}/postmortem")
    def classify(simulation_id: str, body: Postmortem, db: DB) -> dict[str, Any]:
        try:
            result = postmortem(
                db, simulation_id, body.primary_cause, body.classified_by, body.notes
            )
            db.commit()
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return row(result)

    return router


def snapshot_view(db: Any, snapshot: BTCFeatureSnapshot) -> dict[str, Any]:
    return {
        **row(snapshot),
        "trade_plan": trade_plan(snapshot),
        "predictions": [
            row(p)
            for p in db.scalars(
                select(BTCPredictionSnapshot).where(
                    BTCPredictionSnapshot.snapshot_id == snapshot.snapshot_id
                )
            )
        ],
    }
