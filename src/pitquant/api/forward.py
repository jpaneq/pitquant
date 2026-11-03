"""Read forward evidence; manually refresh forecasts/reviews without any fit or order."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from pitquant.api.analyzer import DB
from pitquant.config.settings import Settings
from pitquant.core.errors import PITQuantError
from pitquant.forward.service import run_cycle, status
from pitquant.forward.simulation import create


class SimulationBody(BaseModel):
    prediction_id: str
    notional: float = Field(default=1000, gt=0)


def make_forward_router(cfg: Settings) -> APIRouter:
    router = APIRouter(prefix="/forward-pilots", tags=["forward-pilots"])

    @router.get("")
    def overview(db: DB) -> dict[str, Any]:
        return status(db)

    @router.post("/review")
    def assess(db: DB) -> dict[str, Any]:
        return run_cycle(db, Path("data/forward-pilots-v1"), cfg=cfg)

    @router.post("/simulate")
    def manual(body: SimulationBody, db: DB) -> dict[str, Any]:
        try:
            return create(db, cfg, body.prediction_id, body.notional)
        except (ValueError, PITQuantError) as exc:
            db.rollback()
            raise HTTPException(409, str(exc)) from exc

    return router
