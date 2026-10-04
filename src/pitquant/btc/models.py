"""BTC data revisions and immutable snapshots. Simulation/research hypotheses reuse core tables."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from pitquant.core.timeutils import utc_now
from pitquant.db.base import Base, UTCDateTime
from pitquant.db.models import ID, new_id


class BTCDatum(Base):
    __tablename__ = "btc_data"
    datum_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    source: Mapped[str] = mapped_column(String(40), index=True)
    metric: Mapped[str] = mapped_column(String(60), index=True)
    cohort: Mapped[str] = mapped_column(String(20))
    exchange_timestamp: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    available_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    retrieved_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    raw_hash: Mapped[str] = mapped_column(String(64))
    archive_id: Mapped[str] = mapped_column(ForeignKey("raw_source_archive.archive_id"))
    value_hash: Mapped[str] = mapped_column(String(64))
    __table_args__ = (
        UniqueConstraint(
            "source",
            "metric",
            "cohort",
            "exchange_timestamp",
            "value_hash",
            "retrieved_at",
            name="uq_btc_data_version",
        ),
    )


class BTCFeatureSnapshot(Base):
    __tablename__ = "btc_feature_snapshots"
    snapshot_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    decision_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    cohort: Mapped[str] = mapped_column(String(20))
    feature_version: Mapped[str] = mapped_column(String(40))
    data_version: Mapped[str] = mapped_column(String(40))
    model_version: Mapped[str | None] = mapped_column(String(60))
    strategy_version: Mapped[str] = mapped_column(String(40))
    simulation_engine_version: Mapped[str] = mapped_column(String(20))
    commit_sha: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    snapshot_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)

    __table_args__ = (
        UniqueConstraint("decision_at", "cohort", "feature_version", name="uq_btc_frozen_decision"),
    )


class BTCPredictionSnapshot(Base):
    __tablename__ = "btc_prediction_snapshots"
    prediction_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("btc_feature_snapshots.snapshot_id"))
    horizon: Mapped[int]
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    prediction_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
    __table_args__ = (UniqueConstraint("snapshot_id", "horizon", name="uq_btc_prediction_horizon"),)


class BTCResearchRecord(Base):
    """Append-only configuration, blind reveals, baseline artifacts and forward activations."""

    __tablename__ = "btc_research_records"
    record_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    cohort: Mapped[str] = mapped_column(String(20))
    prediction_id: Mapped[str | None] = mapped_column(
        ForeignKey("btc_prediction_snapshots.prediction_id")
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    record_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
