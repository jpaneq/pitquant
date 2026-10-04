# ruff: noqa: E501
"""RUN 3 research dataset tables (ADR-0048): continuous PIT feature snapshots, research targets and Filing Intelligence snapshots. Append-only."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
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

FILING_ANALYSIS_STATUSES = ("COMPLETE", "PARTIAL", "FAILED")


class ResearchFeatureSnapshot(Base):
    """One security at one decision instant: every continuous feature with its own ``available_at``, ``source`` and ``missing_reason`` (never 0), plus the cross-sectional ranks of the SAME-DATE cohort."""

    __tablename__ = "research_feature_snapshots"
    snapshot_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.security_id"), index=True)
    decision_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    decision_session: Mapped[date] = mapped_column(Date, index=True)
    exchange: Mapped[str] = mapped_column(String(8))
    feature_set_version: Mapped[str] = mapped_column(String(30))
    cohort_definition: Mapped[str] = mapped_column(String(60))
    cohort_size: Mapped[int] = mapped_column(Integer)
    features: Mapped[dict[str, Any]] = mapped_column(JSON)
    ranks: Mapped[dict[str, Any]] = mapped_column(JSON)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON)
    feature_hash: Mapped[str] = mapped_column(String(64))
    code_commit: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
    __table_args__ = (
        UniqueConstraint(
            "security_id", "decision_at", "feature_set_version", name="uq_research_feature_snapshot"
        ),
    )


class ResearchTarget(Base):
    """What happened after a decision, for one horizon. Entry = the last close KNOWN at ``decision_at``; exit = the close of the last session on or before ``decision_at + H months``. The benchmark uses the
    same instants (its own last close at or before each instant). ``label_available_at`` = exit close + lag: a target never trains a model before it."""

    __tablename__ = "research_targets"
    target_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.security_id"), index=True)
    decision_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    horizon_months: Mapped[int] = mapped_column(Integer)
    target_set_version: Mapped[str] = mapped_column(String(30))
    benchmark_id: Mapped[str | None] = mapped_column(ForeignKey("securities.security_id"))
    benchmark_ticker: Mapped[str | None] = mapped_column(String(20))
    benchmark_type: Mapped[str | None] = mapped_column(String(40))
    benchmark_source: Mapped[str | None] = mapped_column(String(60))
    entry_session: Mapped[date | None] = mapped_column(Date)
    exit_session: Mapped[date | None] = mapped_column(Date)
    label_available_at: Mapped[datetime] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(String(12))
    reason: Mapped[str | None] = mapped_column(String(200))
    security_total_return: Mapped[float | None] = mapped_column(Float)
    benchmark_total_return: Mapped[float | None] = mapped_column(Float)
    excess_total_return: Mapped[float | None] = mapped_column(Float)
    outperform: Mapped[bool | None] = mapped_column(Boolean)
    direction_up: Mapped[bool | None] = mapped_column(Boolean)
    max_drawdown: Mapped[float | None] = mapped_column(Float)
    drawdown_10: Mapped[bool | None] = mapped_column(Boolean)
    drawdown_15: Mapped[bool | None] = mapped_column(Boolean)
    drawdown_20: Mapped[bool | None] = mapped_column(Boolean)
    details: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
    __table_args__ = (
        UniqueConstraint(
            "security_id",
            "decision_at",
            "horizon_months",
            "target_set_version",
            name="uq_research_target",
        ),
        CheckConstraint("status IN ('OK','UNAVAILABLE')", name="status_values"),
    )


class FilingAnalysisSnapshot(Base):
    """Structured analysis of ONE filing by a versioned prompt/model (Filing Intelligence, design + contract only: no LLM is called in this build). A snapshot is knowable at T only if the filing's
    ``available_at`` AND this snapshot's own ``analysis_available_at`` are <= T; an analysis produced later than the filing is ``is_retrospective`` and never stands for what was known then."""

    __tablename__ = "filing_analysis_snapshots"
    analysis_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    accession_number: Mapped[str] = mapped_column(
        ForeignKey("sec_filings.accession_number"), index=True
    )
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.security_id"), index=True)
    issuer_id: Mapped[str | None] = mapped_column(ForeignKey("issuers.issuer_id"))
    form: Mapped[str] = mapped_column(String(20))
    period_end: Mapped[date | None] = mapped_column(Date)
    accepted_at: Mapped[datetime] = mapped_column(UTCDateTime)
    filing_available_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    document_hash: Mapped[str] = mapped_column(String(64))
    analysis_schema_version: Mapped[str] = mapped_column(String(30))
    prompt_version: Mapped[str] = mapped_column(String(30))
    model_provider: Mapped[str] = mapped_column(String(40))
    model_name: Mapped[str] = mapped_column(String(80))
    model_version: Mapped[str] = mapped_column(String(80))
    analysis: Mapped[dict[str, Any]] = mapped_column(JSON)
    analysis_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(10))
    confidence: Mapped[float | None] = mapped_column(Float)
    warnings: Mapped[list[str]] = mapped_column(JSON)
    analysis_available_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    is_retrospective: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
    __table_args__ = (
        UniqueConstraint(
            "accession_number",
            "analysis_schema_version",
            "prompt_version",
            "model_name",
            "model_version",
            "document_hash",
            name="uq_filing_analysis_version",
        ),
        CheckConstraint("status IN ('COMPLETE','PARTIAL','FAILED')", name="status_values"),
        CheckConstraint(
            "analysis_available_at >= filing_available_at OR is_retrospective",
            name="analysis_not_before_filing",
        ),
    )
