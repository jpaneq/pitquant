# ruff: noqa: E501
"""Visual trade viewer API: list of decisions/simulations and the chart payload of one of them (read-only)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from pitquant.api.analyzer import DB
from pitquant.config.settings import Settings
from pitquant.positions import trade_view as tv


def make_trades_router(cfg: Settings) -> APIRouter:
    r = APIRouter(prefix="/trades", tags=["trades"])

    @r.get("")
    def trades(db: DB, days: int = 120) -> list[dict[str, Any]]:
        return tv.list_trades(db, max(1, min(days, 730)))

    @r.get("/chart")
    def chart(db: DB, ref: str) -> dict[str, Any]:
        try:
            parts = ref.split("~")
            if parts[0] == "R" and len(parts) == 3:
                return tv.routine_chart(db, parts[1], int(parts[2]))
            if parts[0] == "S" and len(parts) == 2:
                return tv.simulation_chart(db, parts[1])
        except (KeyError, ValueError) as exc:
            raise HTTPException(404, str(exc)) from exc
        raise HTTPException(400, "ref must be R~<pick>~<horizon> or S~<simulation>")

    return r
