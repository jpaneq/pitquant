"""Daily routine API (ADR-0042): run today's step and download the plain-text report."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from pitquant.api.analyzer import DB
from pitquant.config.settings import Settings
from pitquant.positions.routine import PARAMS, PARAMS_VERSION, evaluate_positions, run_daily
from pitquant.positions.routine_report import build_report


def make_routine_router(cfg: Settings) -> APIRouter:
    r = APIRouter(prefix="/routine", tags=["routine"])

    @r.post("/run")
    def run(db: DB) -> dict[str, Any]:
        ran = run_daily(db, cfg)
        evaluated = evaluate_positions(db, cfg)
        db.commit()
        return {"run": ran, "evaluation": evaluated, "params_version": PARAMS_VERSION}

    @r.get("/report", response_class=PlainTextResponse)
    def report(db: DB, days: int = 14) -> str:
        return build_report(db, cfg, days=max(1, min(days, 365)))

    @r.get("/params")
    def params() -> dict[str, Any]:
        return {"version": PARAMS_VERSION, "params": PARAMS}

    return r
