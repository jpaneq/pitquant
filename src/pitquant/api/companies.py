"""Company factsheets (ADR-0067): SEC accounts + expensive/cheap indicator. Read-only."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from pitquant.api.analyzer import DB
from pitquant.core.timeutils import utc_now
from pitquant.db.models import SecurityProfile
from pitquant.forward.learning import US_UNIVERSE


def make_companies_router() -> APIRouter:
    router = APIRouter(prefix="/companies", tags=["companies"])

    @router.get("")
    def listing(db: DB) -> list[dict[str, Any]]:
        names = {
            p.current_ticker: p.display_name
            for p in db.scalars(
                select(SecurityProfile).where(SecurityProfile.current_ticker.in_(US_UNIVERSE))
            )
        }
        return [{"ticker": t, "name": names.get(t, t)} for t in sorted(US_UNIVERSE)]

    @router.get("/{ticker}")
    def sheet(ticker: str, db: DB) -> dict[str, Any]:
        from pitquant.analyzer.factsheet import factsheet

        try:
            return factsheet(db, ticker, utc_now(), US_UNIVERSE)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    return router
