"""Read forward evidence; manually refresh forecasts/reviews without any fit or order."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from pitquant.api.analyzer import DB
from pitquant.config.settings import Settings
from pitquant.core.errors import PITQuantError
from pitquant.data.archive import ArchiveStore
from pitquant.forward import funds
from pitquant.forward.service import run_cycle, status
from pitquant.forward.simulation import create


class FundBody(BaseModel):
    isin: str = Field(min_length=12, max_length=12)
    symbol: str = Field(max_length=40)
    name: str = Field(max_length=200)
    currency: str | None = None


class FundRemoveBody(BaseModel):
    isin: str = Field(min_length=12, max_length=12)


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

    @router.get("/funds/search")
    def fund_search(isin: str) -> list[dict[str, Any]]:
        try:
            return funds.search(isin)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.post("/funds")
    def fund_add(body: FundBody, db: DB) -> dict[str, Any]:
        """Add a fund, download its NAVs and issue today's forecast right away."""
        try:
            funds.add(db, body.isin, body.symbol, body.name, body.currency)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        ingest = funds.ingest(db, ArchiveStore(Path(cfg.archive.root)), only=[body.isin.upper()])
        return {"ingest": ingest, "cycle": funds.cycle(db)}

    @router.post("/funds/remove")
    def fund_remove(body: FundRemoveBody, db: DB) -> dict[str, Any]:
        funds.remove(db, body.isin)
        return {"removed": body.isin.upper(), "history_kept": True}

    @router.post("/simulate")
    def manual(body: SimulationBody, db: DB) -> dict[str, Any]:
        try:
            return create(db, cfg, body.prediction_id, body.notional)
        except (ValueError, PITQuantError) as exc:
            db.rollback()
            raise HTTPException(409, str(exc)) from exc

    return router
