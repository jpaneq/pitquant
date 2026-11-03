"""Append-only journal for forward pilot protocols, models, forecasts and assessments."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from pitquant.core.timeutils import utc_now
from pitquant.db.base import Base, UTCDateTime
from pitquant.db.models import ID, new_id


class ForwardPilotRecord(Base):
    __tablename__ = "forward_pilot_records"
    record_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    record_key: Mapped[str] = mapped_column(String(250), unique=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    market: Mapped[str] = mapped_column(String(10), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    payload_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
