"""Simulated positions (paper): header, append-only event log, persisted reviews (ADR-0041)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, CheckConstraint, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from pitquant.core.timeutils import utc_now
from pitquant.db.base import Base, UTCDateTime
from pitquant.db.models import ID, new_id

POSITION_ASSETS = ("EQUITY", "BTC")
POSITION_EVENTS = ("OPEN", "ADD", "REDUCE", "CLOSE")
RECOMMENDATIONS = ("ADD", "HOLD", "SELL")


class PaperPosition(Base):
    """A simulated purchase with a horizon in months. Immutable: buys/sells are events."""

    __tablename__ = "paper_positions"
    position_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    asset_type: Mapped[str] = mapped_column(String(10), index=True)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.security_id"), index=True)
    horizon_months: Mapped[int] = mapped_column(Integer)
    target_return: Mapped[float | None] = mapped_column(Float)
    stop_price: Mapped[float | None] = mapped_column(Float)
    stop_rule: Mapped[str] = mapped_column(String(40))
    note: Mapped[str] = mapped_column(String(300), default="")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    opened_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
    __table_args__ = (
        CheckConstraint("asset_type IN ('EQUITY','BTC')", name="asset_values"),
        CheckConstraint("horizon_months BETWEEN 1 AND 60", name="horizon_range"),
    )


class PaperPositionEvent(Base):
    __tablename__ = "paper_position_events"
    event_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    position_id: Mapped[str] = mapped_column(ForeignKey("paper_positions.position_id"), index=True)
    event_type: Mapped[str] = mapped_column(String(10))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime)
    price: Mapped[float] = mapped_column(Float)
    quantity: Mapped[float] = mapped_column(Float)
    price_source: Mapped[str] = mapped_column(String(40))
    price_freshness: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
    __table_args__ = (
        CheckConstraint("event_type IN ('OPEN','ADD','REDUCE','CLOSE')", name="event_values"),
        CheckConstraint("price > 0 AND quantity > 0", name="positive_price_quantity"),
    )


class PositionReview(Base):
    """A review the user chose to keep (the live review is computed on demand and never stored)."""

    __tablename__ = "position_reviews"
    review_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    position_id: Mapped[str] = mapped_column(ForeignKey("paper_positions.position_id"), index=True)
    reviewed_at: Mapped[datetime] = mapped_column(UTCDateTime)
    engine_version: Mapped[str] = mapped_column(String(30))
    horizon_bucket: Mapped[str] = mapped_column(String(10))
    recommendation: Mapped[str] = mapped_column(String(6))
    score: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    avg_cost: Mapped[float] = mapped_column(Float)
    quantity: Mapped[float] = mapped_column(Float)
    pnl_pct: Mapped[float] = mapped_column(Float)
    rules: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON)
    context_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
    __table_args__ = (
        CheckConstraint("recommendation IN ('ADD','HOLD','SELL')", name="recommendation_values"),
    )
