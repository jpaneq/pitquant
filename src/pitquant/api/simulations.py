# ruff: noqa: E501
"""Simulation Lab HTTP surface (ADR-0034). PAPER TRADE, NO REAL MONEY. Writes only simulation tables; never datasets, models or champions.
Holdout dates are refused (403); a security without price bars is refused (409 PRICE_DATA_REQUIRED); AUTO_PAPER stays disabled (409)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from pitquant.analyzer.search import search
from pitquant.analyzer.service import AnalyzerService
from pitquant.api.analyzer import DB
from pitquant.config.settings import Settings
from pitquant.core.errors import HoldoutAccessError
from pitquant.core.timeutils import utc_now
from pitquant.db.models import (
    Simulation,
    SimulationObservation,
    SimulationOutcome,
    SimulationPostMortem,
)
from pitquant.simulation import service as sim
from pitquant.simulation.engine import CLOSED, SimState

PAPER = "PAPER TRADE — NO REAL MONEY"


def row(r: Any) -> dict[str, Any]:
    return {
        c.key: (
            getattr(r, c.key).isoformat()
            if hasattr(getattr(r, c.key), "isoformat")
            else getattr(r, c.key)
        )
        for c in r.__table__.columns
    }


class PlanBody(BaseModel):
    entry_type: str = "LIMIT"
    entry_zone_low: float | None = None
    entry_zone_high: float | None = None
    stop_loss: float | None = None
    invalidation_level: float | None = None
    target_1: float | None = None
    target_2: float | None = None
    target_3_optional: float | None = None


class CreateBody(BaseModel):
    security: str
    plan_origin: str = "PITQUANT"
    plan: PlanBody | None = None
    as_of: str | None = None
    capital: float = 100_000.0
    risk_pct: float = 1.0
    horizon_sessions: int = 20
    mode: str = "MANUAL_SIMULATION"


class CloseBody(BaseModel):
    price: float
    reason: str = ""


class PostMortemBody(BaseModel):
    primary_cause: str
    secondary_causes: list[str] = []
    notes: str = ""
    classified_by: str


def make_simulation_router(cfg: Settings) -> APIRouter:
    r = APIRouter(prefix="/simulations", tags=["simulation-lab"])

    def when(s: str | None) -> datetime:
        if s is None:
            return utc_now()
        try:
            at = datetime.fromisoformat(s)
        except ValueError as e:
            raise HTTPException(422, f"invalid as_of {s!r}") from e
        if at.tzinfo is None:
            raise HTTPException(422, "as_of must include a UTC offset")
        return at

    def resolve(db: Any, ident: str) -> str:
        res: dict[str, Any] = search(db, ident, limit=5)
        hits = [h for h in res["results"] if h["match_type"] in ("EXACT", "IDENTIFIER")]
        if len(hits) != 1:
            raise HTTPException(404, f"no unique security matches {ident!r}")
        return str(hits[0]["security_id"])

    def wrap(fn: Any) -> Any:
        try:
            return fn()
        except HoldoutAccessError as e:
            raise HTTPException(403, str(e)) from e
        except sim.PriceDataRequired as e:
            raise HTTPException(409, str(e)) from e
        except sim.AutoPaperDisabled as e:
            raise HTTPException(409, str(e)) from e
        except sim.SimulationError as e:
            raise HTTPException(422, str(e)) from e

    def latest(db: Any, sid: str) -> dict[str, Any] | None:
        o = sim.latest_outcome(db, sid)
        return row(o) if o else None

    @r.get("/summary")
    def summary(db: DB) -> dict[str, Any]:
        s = sim.evidence_summary(db)
        sims = list(db.scalars(select(Simulation.simulation_id)))
        groups = {"OPEN": 0, "CLOSED": 0, "WAITING_ENTRY": 0, "STOPPED": 0, "TP1": 0, "TP2": 0}
        for sid in sims:
            o = sim.latest_outcome(db, sid)
            st = o.state if o else SimState.CREATED.value
            groups["CLOSED" if (o and o.is_closed) else "OPEN"] += 1
            if st in groups:
                groups[st] += 1
        return {"banner": PAPER, "groups": groups, "evidence": s.__dict__}

    @r.get("")
    def listing(db: DB) -> list[dict[str, Any]]:
        out = []
        for s in db.scalars(select(Simulation).order_by(Simulation.created_at.desc())):
            o = sim.latest_outcome(db, s.simulation_id)
            out.append({"simulation_id": s.simulation_id, "created_at": s.created_at.isoformat(), "security_id": s.security_id, "decision_at": s.decision_at.isoformat(), "plan_origin": s.plan_origin, "mode": s.mode, "state": o.state if o else "CREATED", "outcome": row(o) if o else None, "entry_zone": [s.entry_zone_low, s.entry_zone_high], "stop_loss": s.stop_loss, "target_1": s.target_1, "target_2": s.target_2, "banner": PAPER})  # fmt: skip
        return out

    @r.post("")
    def create(body: CreateBody, db: DB) -> dict[str, Any]:
        sid = resolve(db, body.security)
        at = when(body.as_of)
        plan = sim.PlanInput(**body.plan.model_dump()) if body.plan else None

        def go() -> dict[str, Any]:
            s = sim.create_simulation(
                db,
                cfg,
                sid,
                plan_origin=body.plan_origin,
                plan=plan,
                at=at,
                capital=body.capital,
                risk_pct=body.risk_pct,
                horizon_sessions=body.horizon_sessions,
                mode=body.mode,
            )
            db.commit()
            return {
                "simulation_id": s.simulation_id,
                "banner": PAPER,
                "prediction_status": s.prediction_status,
            }

        out: dict[str, Any] = wrap(go)
        return out

    @r.get("/{simulation_id}")
    def detail(simulation_id: str, db: DB) -> dict[str, Any]:
        s = db.get(Simulation, simulation_id)
        if s is None:
            raise HTTPException(404, "unknown simulation")
        now = utc_now()
        bars, _ = sim._bars_after(db, s, now)
        svc = AnalyzerService(db, cfg)
        try:
            analysis_now = svc.analysis(s.security_id, now)
        except Exception:
            analysis_now = {"status": "UNAVAILABLE"}
        return {
            "banner": PAPER, "simulation": row(s), "outcomes": [row(o) for o in db.scalars(select(SimulationOutcome).where(SimulationOutcome.simulation_id == simulation_id).order_by(SimulationOutcome.evaluated_at))],
            "observations": [row(o) for o in db.scalars(select(SimulationObservation).where(SimulationObservation.simulation_id == simulation_id).order_by(SimulationObservation.observed_at))],
            "postmortems": [row(p) for p in db.scalars(select(SimulationPostMortem).where(SimulationPostMortem.simulation_id == simulation_id))],
            "bars": [{"date": str(d), **{k: float(v) for k, v in b.items()}} for d, b in bars.iterrows()], "analysis_now": analysis_now,
        }  # fmt: skip

    @r.post("/{simulation_id}/evaluate")
    def evaluate_(simulation_id: str, db: DB) -> dict[str, Any]:
        if db.get(Simulation, simulation_id) is None:
            raise HTTPException(404, "unknown simulation")

        def go() -> dict[str, Any]:
            o = sim.evaluate_simulation(db, cfg, simulation_id)
            db.commit()
            return row(o)

        out: dict[str, Any] = wrap(go)
        return out

    @r.post("/{simulation_id}/snapshot")
    def snapshot(simulation_id: str, db: DB) -> dict[str, Any]:
        if db.get(Simulation, simulation_id) is None:
            raise HTTPException(404, "unknown simulation")

        def go() -> dict[str, Any]:
            o = sim.thesis_snapshot(db, cfg, simulation_id)
            db.commit()
            return {"observation_id": o.observation_id, "comparison": o.payload["comparison"]}

        out: dict[str, Any] = wrap(go)
        return out

    @r.post("/{simulation_id}/close")
    def close(simulation_id: str, body: CloseBody, db: DB) -> dict[str, Any]:
        if db.get(Simulation, simulation_id) is None:
            raise HTTPException(404, "unknown simulation")

        def go() -> dict[str, Any]:
            sim.close_manual(
                db, cfg, simulation_id, at=utc_now(), price=body.price, reason=body.reason
            )
            o = sim.evaluate_simulation(db, cfg, simulation_id)
            db.commit()
            return row(o)

        out: dict[str, Any] = wrap(go)
        return out

    @r.post("/{simulation_id}/postmortem")
    def postmortem(simulation_id: str, body: PostMortemBody, db: DB) -> dict[str, Any]:
        if db.get(Simulation, simulation_id) is None:
            raise HTTPException(404, "unknown simulation")

        def go() -> dict[str, Any]:
            p = sim.classify_postmortem(
                db,
                simulation_id,
                primary_cause=body.primary_cause,
                secondary_causes=body.secondary_causes,
                notes=body.notes,
                classified_by=body.classified_by,
            )
            db.commit()
            return row(p)

        out: dict[str, Any] = wrap(go)
        return out

    _ = CLOSED
    return r
