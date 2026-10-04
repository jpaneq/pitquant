"""Daily routine API (ADR-0042): run today's step and download the plain-text report."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from pitquant.api.analyzer import DB
from pitquant.config.settings import Settings
from pitquant.positions.routine import (
    PARAMS,
    PARAMS_VERSION,
    evaluate_positions,
    evaluate_virtual,
    run_daily,
)
from pitquant.positions.routine_report import build_report


def make_routine_router(cfg: Settings) -> APIRouter:
    r = APIRouter(prefix="/routine", tags=["routine"])

    @r.post("/run")
    def run(db: DB, force: bool = False) -> dict[str, Any]:
        """Only markets OPEN now are analysed unless force=true (manual button)."""
        ran = run_daily(db, cfg, respect_hours=not force)
        evaluated = {**evaluate_positions(db, cfg), **evaluate_virtual(db, cfg)}
        db.commit()
        return {"run": ran, "evaluation": evaluated, "params_version": PARAMS_VERSION}

    @r.get("/report", response_class=PlainTextResponse)
    def report(db: DB, days: int = 14) -> str:
        return build_report(db, cfg, days=max(1, min(days, 365)))

    @r.get("/backtest-report", response_class=PlainTextResponse)
    def backtest_report() -> str:
        """Latest backtest report written by ``backtest-run`` (run from the command line)."""
        from pathlib import Path

        files = sorted(Path("data/reports").glob("backtest_rutina_*.txt"))
        return (
            files[-1].read_text(encoding="utf-8")
            if files
            else "Todavía no hay backtest: ejecuta  python -m pitquant.cli backtest-run\n"
        )

    @r.get("/params")
    def params() -> dict[str, Any]:
        return {"version": PARAMS_VERSION, "params": PARAMS}

    return r
