# ruff: noqa: E501
"""Simulated positions API (ADR-0041): buy, add, reduce, close and the rule-based review (add / hold / sell) for equities and BTC. Paper only."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from pitquant.api.analyzer import DB
from pitquant.config.settings import Settings
from pitquant.db.models_positions import PaperPosition, PositionReview
from pitquant.positions import service as svc
from pitquant.strategy.daily import resolve_universe
from pitquant.strategy.spec import StrategyError


class OpenBody(BaseModel):
    asset_type: str
    security: str | None = None
    horizon_months: int
    quantity: float | None = None
    notional: float | None = None
    price: float | None = None
    target_return: float | None = None
    stop_price: float | None = None
    note: str = ""


class EventBody(BaseModel):
    type: str
    quantity: float | None = None
    price: float | None = None


def make_positions_router(cfg: Settings) -> APIRouter:
    r = APIRouter(prefix="/positions", tags=["positions"])

    def sid_of(db: Any, ident: str | None, asset: str) -> str | None:
        if asset == "BTC" or not ident:
            return None
        try:
            ids = resolve_universe(db, [ident])
        except StrategyError as exc:
            raise HTTPException(404, str(exc)) from exc
        return ids[0]

    @r.post("")
    def open_(body: OpenBody, db: DB) -> dict[str, Any]:
        try:
            pos = svc.open_position(
                db, cfg, asset_type=body.asset_type, security_id=sid_of(db, body.security, body.asset_type), horizon_months=body.horizon_months, quantity=body.quantity, notional=body.notional,
                price=body.price, target_return=body.target_return, stop_price=body.stop_price, note=body.note,
            )  # fmt: skip
            db.commit()
        except svc.PositionError as exc:
            raise HTTPException(422, str(exc)) from exc
        return svc.live_review(db, cfg, pos)

    @r.get("")
    def list_(
        db: DB,
        asset_type: str | None = None,
        security: str | None = None,
        include_closed: bool = False,
    ) -> list[dict[str, Any]]:
        sid = (
            svc.btc_security(db)
            if asset_type == "BTC"
            else sid_of(db, security, asset_type or "EQUITY")
        )
        return svc.list_positions(db, cfg, asset_type, sid, include_closed)

    @r.post("/{position_id}/events")
    def event(position_id: str, body: EventBody, db: DB) -> dict[str, Any]:
        pos = db.get(PaperPosition, position_id)
        if pos is None:
            raise HTTPException(404, "position not found")
        try:
            svc.add_event(db, cfg, position_id, body.type, quantity=body.quantity, price=body.price)
            db.commit()
        except svc.PositionError as exc:
            raise HTTPException(422, str(exc)) from exc
        return svc.live_review(db, cfg, pos)

    @r.post("/{position_id}/review")
    def keep_review(position_id: str, db: DB) -> dict[str, Any]:
        if db.get(PaperPosition, position_id) is None:
            raise HTTPException(404, "position not found")
        try:
            row = svc.save_review(db, cfg, position_id)
            db.commit()
        except svc.PositionError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {
            "review_id": row.review_id,
            "recommendation": row.recommendation,
            "score": row.score,
            "reviewed_at": row.reviewed_at.isoformat(),
        }

    @r.get("/{position_id}/reviews")
    def reviews(position_id: str, db: DB) -> list[dict[str, Any]]:
        rows = db.scalars(
            select(PositionReview)
            .where(PositionReview.position_id == position_id)
            .order_by(PositionReview.reviewed_at.desc())
        )
        return [
            {
                "review_id": x.review_id,
                "reviewed_at": x.reviewed_at.isoformat(),
                "recommendation": x.recommendation,
                "score": x.score,
                "price": x.price,
                "pnl_pct": x.pnl_pct,
                "horizon_bucket": x.horizon_bucket,
                "engine_version": x.engine_version,
            }
            for x in rows
        ]

    return r
