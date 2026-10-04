"""Daily routine records: daily picks and weekly evaluations (ADR-0042). Append-only."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from pitquant.core.timeutils import utc_now
from pitquant.db.base import Base, UTCDateTime
from pitquant.db.models import ID, new_id

MARKETS = ("IBEX", "SP500", "MSCI_WORLD", "BTC")
PICK_STATUSES = ("ANALYZED", "NO_DATA")
EVAL_STATES = ("IN_PROGRESS", "TARGET_HIT", "STOP_HIT", "AMBIGUOUS_STOP", "EXPIRED")


class DailyPick(Base):
    __tablename__ = "daily_picks"
    pick_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    run_date: Mapped[date] = mapped_column(Date, index=True)
    market: Mapped[str] = mapped_column(String(12))
    ticker: Mapped[str | None] = mapped_column(String(20))
    security_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(10))
    params_version: Mapped[str] = mapped_column(String(30))
    params: Mapped[dict[str, Any]] = mapped_column(JSON)
    price: Mapped[float | None] = mapped_column(Float)
    price_freshness: Mapped[str | None] = mapped_column(String(20))
    decisions: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    unavailable: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
    __table_args__ = (
        UniqueConstraint("run_date", "market", name="uq_daily_pick_day_market"),
        CheckConstraint("market IN ('IBEX','SP500','MSCI_WORLD','BTC')", name="market_values"),
        CheckConstraint("status IN ('ANALYZED','NO_DATA')", name="status_values"),
    )


class DailyEvaluation(Base):
    __tablename__ = "daily_evaluations"
    evaluation_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    position_id: Mapped[str] = mapped_column(ForeignKey("paper_positions.position_id"), index=True)
    week_key: Mapped[str] = mapped_column(String(12))  # ISO week 'YYYY-Www' or 'FINAL'
    evaluated_at: Mapped[datetime] = mapped_column(UTCDateTime)
    state: Mapped[str] = mapped_column(String(16))
    price: Mapped[float] = mapped_column(Float)
    return_pct: Mapped[float] = mapped_column(Float)
    target_progress: Mapped[float | None] = mapped_column(Float)
    max_favorable: Mapped[float | None] = mapped_column(Float)
    max_adverse: Mapped[float | None] = mapped_column(Float)
    outcome_date: Mapped[date | None] = mapped_column(Date)
    bars_used: Mapped[int] = mapped_column(Integer)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
    __table_args__ = (
        UniqueConstraint("position_id", "week_key", name="uq_daily_eval_position_week"),
        CheckConstraint(
            "state IN ('IN_PROGRESS','TARGET_HIT','STOP_HIT','AMBIGUOUS_STOP','EXPIRED')",
            name="state_values",
        ),
    )
