"""SQLAlchemy models for every table in the data model (docs/DATA_MODEL.md is generated
from this module by ``scripts/gen_data_model_doc.py``).

Conventions
-----------
* ``*_at`` columns are instants (UTCDateTime, aware). ``*_date`` columns are calendar dates.
* Validity intervals are half-open ``[valid_from, valid_to)``; ``valid_to IS NULL`` = open.
* ``available_at``: earliest instant an outside investor could know the record.
* ``ingested_at``: when *this system* stored it (needed for forward-test audits).
* Tables listed in ``IMMUTABLE_TABLES`` are append-only (ORM guard + PostgreSQL trigger).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import false as sa_false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pitquant.core.timeutils import utc_now
from pitquant.db.base import Base, UTCDateTime


def new_id() -> str:
    return str(uuid.uuid4())


ID = String(36)


# ───────────────────────────── provenance ─────────────────────────────


class DataSource(Base):
    __tablename__ = "data_sources"

    source_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    provider_type: Mapped[str] = mapped_column(String(50))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    is_point_in_time: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text)


class RawRecord(Base):
    """Verbatim provider payload: the root of data lineage."""

    __tablename__ = "raw_records"

    raw_record_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.source_id"))
    original_identifier: Mapped[str] = mapped_column(String(200))
    retrieved_at: Mapped[datetime] = mapped_column(UTCDateTime)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    payload_hash: Mapped[str] = mapped_column(String(64))

    __table_args__ = (
        UniqueConstraint("source_id", "original_identifier", "payload_hash"),  # idempotency
    )


class RawSourceArchive(Base):
    """Verbatim copy of every important external document (filings, index histories, avisos).

    Content is stored content-addressed (SHA-256) by ``pitquant.data.archive``; this row
    records one RETRIEVAL. The same bytes fetched twice produce two rows and one file.
    We never depend on an external URL still existing or still serving the same bytes.
    """

    __tablename__ = "raw_source_archive"

    archive_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(100))
    source_identifier: Mapped[str] = mapped_column(String(1000))  # URL or document id
    retrieved_at: Mapped[datetime] = mapped_column(UTCDateTime)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime)  # publication/acceptance
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_uri: Mapped[str] = mapped_column(String(500))
    parser_version: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)


class DataQualityIssue(Base):
    __tablename__ = "data_quality_issues"

    issue_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    entity: Mapped[str] = mapped_column(String(50))
    security_id: Mapped[str | None] = mapped_column(ForeignKey("securities.security_id"))
    check_name: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(20))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    detected_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    raw_record_id: Mapped[str | None] = mapped_column(ForeignKey("raw_records.raw_record_id"))


# ───────────────────────────── security master ─────────────────────────────


class Issuer(Base):
    __tablename__ = "issuers"

    issuer_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(300))
    country: Mapped[str | None] = mapped_column(String(2))


class Security(Base):
    __tablename__ = "securities"

    security_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    issuer_id: Mapped[str | None] = mapped_column(ForeignKey("issuers.issuer_id"))
    name: Mapped[str] = mapped_column(String(300))
    exchange: Mapped[str] = mapped_column(String(10))  # MIC calendar code: XNYS, XMAD
    currency: Mapped[str] = mapped_column(String(3))
    country: Mapped[str | None] = mapped_column(String(2))
    listing_start: Mapped[date | None] = mapped_column(Date)
    listing_end: Mapped[date | None] = mapped_column(Date)
    delisted: Mapped[bool] = mapped_column(Boolean, default=False)
    delisting_reason: Mapped[str | None] = mapped_column(String(30))
    acquirer_security_id: Mapped[str | None] = mapped_column(ForeignKey("securities.security_id"))
    successor_security_id: Mapped[str | None] = mapped_column(ForeignKey("securities.security_id"))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)

    tickers: Mapped[list[TickerHistory]] = relationship(back_populates="security")

    __table_args__ = (
        CheckConstraint(
            "listing_end IS NULL OR listing_start IS NULL OR listing_end >= listing_start",
            name="listing_order",
        ),
    )


class TickerHistory(Base):
    __tablename__ = "ticker_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.security_id"), index=True)
    ticker: Mapped[str] = mapped_column(String(20))
    exchange: Mapped[str] = mapped_column(String(10))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.source_id"))

    security: Mapped[Security] = relationship(back_populates="tickers")

    __table_args__ = (
        Index("ix_ticker_lookup", "ticker", "exchange", "valid_from"),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="interval"),
    )


class ProviderKey(Base):
    """Maps a provider's own security key to our permanent security_id (idempotent ingestion)."""

    __tablename__ = "provider_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.source_id"))
    provider_key: Mapped[str] = mapped_column(String(100))
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.security_id"))

    __table_args__ = (UniqueConstraint("source_id", "provider_key"),)


class IdentifierHistory(Base):
    __tablename__ = "identifier_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.security_id"), index=True)
    id_type: Mapped[str] = mapped_column(String(10))  # ISIN | CUSIP | FIGI
    value: Mapped[str] = mapped_column(String(20))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)

    __table_args__ = (
        Index("ix_identifier_lookup", "id_type", "value", "valid_from"),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="interval"),
    )


class SectorClassification(Base):
    __tablename__ = "sector_classification"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.security_id"), index=True)
    scheme: Mapped[str] = mapped_column(String(20), default="GICS")
    sector: Mapped[str] = mapped_column(String(100))
    industry_group: Mapped[str | None] = mapped_column(String(100))
    industry: Mapped[str | None] = mapped_column(String(100))
    sub_industry: Mapped[str | None] = mapped_column(String(100))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    available_at: Mapped[datetime] = mapped_column(UTCDateTime)


# ───────────────────────────── universe ─────────────────────────────


class IndexEvent(Base):
    """Immutable index event stream: the ONLY source from which membership is derived.

    event_type: INDEX_ADD | INDEX_DELETE | TICKER_CHANGE | ORDINARY_REVIEW |
    EXTRAORDINARY_REVIEW | INITIAL_SNAPSHOT. Review events are parents of the adds/deletes
    they caused (``parent_event_id``). A TICKER_CHANGE never changes membership.
    """

    __tablename__ = "index_events"

    event_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    index_code: Mapped[str] = mapped_column(String(20))
    event_type: Mapped[str] = mapped_column(String(30))
    parent_event_id: Mapped[str | None] = mapped_column(ForeignKey("index_events.event_id"))
    security_id: Mapped[str | None] = mapped_column(ForeignKey("securities.security_id"))
    ticker: Mapped[str | None] = mapped_column(String(20))  # symbol as written in the source
    new_ticker: Mapped[str | None] = mapped_column(String(20))  # TICKER_CHANGE only
    identifier: Mapped[str | None] = mapped_column(
        String(20)
    )  # ISIN/CUSIP when the source gives it
    effective_date: Mapped[date] = mapped_column(Date)  # first session the change applies
    announced_at: Mapped[datetime | None] = mapped_column(UTCDateTime)  # NOT the effective date
    reason: Mapped[str | None] = mapped_column(String(300))
    membership_source: Mapped[str] = mapped_column(String(100))
    source_event_id: Mapped[str] = mapped_column(String(200))
    source_confidence: Mapped[str] = mapped_column(String(40))
    raw_source_hash: Mapped[str] = mapped_column(String(64))
    archive_id: Mapped[str | None] = mapped_column(ForeignKey("raw_source_archive.archive_id"))
    # RESOLVED: the source pins WHICH security (ISIN/CUSIP/permanent id). IDENTITY_UNRESOLVED:
    # membership is known but the security is not (e.g. ticker only) — never backtestable.
    identity_status: Mapped[str] = mapped_column(
        String(30), default="RESOLVED", server_default="RESOLVED"
    )
    ingested_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)

    __table_args__ = (
        UniqueConstraint("membership_source", "source_event_id", "raw_source_hash"),
        Index("ix_index_events_seq", "index_code", "membership_source", "effective_date"),
        CheckConstraint(
            "event_type IN ('INDEX_ADD','INDEX_DELETE','TICKER_CHANGE','ORDINARY_REVIEW',"
            "'EXTRAORDINARY_REVIEW','INITIAL_SNAPSHOT')",
            name="event_type_values",
        ),
        CheckConstraint(
            "identity_status IN ('RESOLVED','IDENTITY_UNRESOLVED')", name="identity_status_values"
        ),
    )


class MembershipBuild(Base):
    """One reconstruction of an index's membership from a fixed set of events.

    Builds are never edited. A provider correction produces a NEW build; old snapshots stay
    reproducible by pinning ``build_id`` in their data_version.
    """

    __tablename__ = "membership_builds"

    build_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    index_code: Mapped[str] = mapped_column(String(20))
    membership_source: Mapped[str] = mapped_column(String(100))
    source_confidence: Mapped[str] = mapped_column(String(40))
    raw_source_hash: Mapped[str] = mapped_column(String(64))
    events_hash: Mapped[str] = mapped_column(String(64))
    n_events: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))  # ok | failed
    # True only for a CANONICAL source with every interval's identity resolved. Provisional,
    # synthetic or identity-incomplete builds can never feed holdout evaluation/promotion.
    eligible_for_final_model_validation: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=sa_false()
    )
    report: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    built_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)


class IndexMembership(Base):
    """Derived intervals ``[effective_from, effective_to)`` belonging to one build."""

    __tablename__ = "index_membership"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    build_id: Mapped[str] = mapped_column(ForeignKey("membership_builds.build_id"))
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.security_id"))
    index_code: Mapped[str] = mapped_column(String(20))
    ticker_at_inclusion: Mapped[str | None] = mapped_column(String(20))
    effective_from: Mapped[date] = mapped_column(Date)  # inclusive
    effective_to: Mapped[date | None] = mapped_column(Date)  # exclusive
    inclusion_reason: Mapped[str | None] = mapped_column(String(300))
    exclusion_reason: Mapped[str | None] = mapped_column(String(300))
    announced_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    membership_source: Mapped[str] = mapped_column(String(100))
    source_event_id: Mapped[str] = mapped_column(ForeignKey("index_events.event_id"))
    exclusion_event_id: Mapped[str | None] = mapped_column(ForeignKey("index_events.event_id"))
    source_confidence: Mapped[str] = mapped_column(String(40))
    raw_source_hash: Mapped[str] = mapped_column(String(64))
    identity_status: Mapped[str] = mapped_column(
        String(30), default="RESOLVED", server_default="RESOLVED"
    )

    __table_args__ = (
        Index("ix_membership_asof", "build_id", "index_code", "effective_from", "effective_to"),
        CheckConstraint("effective_to IS NULL OR effective_to > effective_from", name="interval"),
        CheckConstraint(
            "identity_status IN ('RESOLVED','IDENTITY_UNRESOLVED')", name="identity_status_values"
        ),
    )


# ───────────────────────────── market data ─────────────────────────────


class Price(Base):
    """RAW (unadjusted) daily bars. Adjusted series are derived as-of (ADR-0004).

    Bulk history lives in Parquet; this table holds the same schema for recent data
    and for small deployments.
    """

    __tablename__ = "prices"

    security_id: Mapped[str] = mapped_column(ForeignKey("securities.security_id"), primary_key=True)
    session_date: Mapped[date] = mapped_column(Date, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.source_id"), primary_key=True)
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3))
    bar_close_at: Mapped[datetime] = mapped_column(UTCDateTime)  # = available_at of the bar
    ingested_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)

    __table_args__ = (
        CheckConstraint("close > 0", name="positive_close"),
        CheckConstraint("high IS NULL OR low IS NULL OR high >= low", name="high_ge_low"),
    )


class CorporateAction(Base):
    __tablename__ = "corporate_actions"

    action_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.security_id"), index=True)
    action_type: Mapped[str] = mapped_column(String(30))
    announced_at: Mapped[datetime] = mapped_column(UTCDateTime)
    ex_date: Mapped[date] = mapped_column(Date)
    effective_date: Mapped[date | None] = mapped_column(Date)
    ratio: Mapped[float | None] = mapped_column(Float)
    cash_amount: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str | None] = mapped_column(String(3))
    target_security_id: Mapped[str | None] = mapped_column(ForeignKey("securities.security_id"))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.source_id"))
    ingested_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)


class Dividend(Base):
    __tablename__ = "dividends"

    dividend_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.security_id"), index=True)
    dividend_type: Mapped[str] = mapped_column(String(30), default="regular")
    announced_at: Mapped[datetime] = mapped_column(UTCDateTime)
    ex_date: Mapped[date] = mapped_column(Date)
    pay_date: Mapped[date | None] = mapped_column(Date)
    gross_amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3))
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.source_id"))
    ingested_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)

    __table_args__ = (
        UniqueConstraint("security_id", "ex_date", "dividend_type", "source_id"),
        CheckConstraint("gross_amount >= 0", name="non_negative"),
    )


class Benchmark(Base):
    __tablename__ = "benchmarks"

    benchmark_code: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20))  # market | sector | industry
    return_type: Mapped[str] = mapped_column(String(10), default="TR")
    currency: Mapped[str] = mapped_column(String(3))
    index_code: Mapped[str | None] = mapped_column(String(20))
    sector: Mapped[str | None] = mapped_column(String(100))

    __table_args__ = (CheckConstraint("return_type IN ('TR','NTR')", name="total_return_only"),)


class BenchmarkLevel(Base):
    __tablename__ = "benchmark_levels"

    benchmark_code: Mapped[str] = mapped_column(
        ForeignKey("benchmarks.benchmark_code"), primary_key=True
    )
    session_date: Mapped[date] = mapped_column(Date, primary_key=True)
    level: Mapped[float] = mapped_column(Float)
    available_at: Mapped[datetime] = mapped_column(UTCDateTime)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.source_id"))


# ───────────────────────────── fundamentals / estimates / macro ─────────────────────────────


class FinancialStatement(Base):
    __tablename__ = "financial_statements"

    statement_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.security_id"), index=True)
    statement_type: Mapped[str] = mapped_column(String(20))  # IS | BS | CF | full_filing
    fiscal_period: Mapped[str] = mapped_column(String(10))  # 2020Q3, 2020FY
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    published_at: Mapped[datetime] = mapped_column(UTCDateTime)
    available_at: Mapped[datetime] = mapped_column(UTCDateTime)
    revision_id: Mapped[int] = mapped_column(Integer, default=0)
    filing_ref: Mapped[str | None] = mapped_column(String(100))  # accession number, CNMV nº
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.source_id"))
    raw_record_id: Mapped[str | None] = mapped_column(ForeignKey("raw_records.raw_record_id"))
    ingested_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)

    __table_args__ = (
        CheckConstraint("available_at >= published_at", name="available_after_publication"),
    )


class SecFiling(Base):
    """One EDGAR filing (accession). ``accepted_at`` comes from the filing HEADER
    (ACCEPTANCE-DATETIME, US/Eastern), never from companyfacts."""

    __tablename__ = "sec_filings"

    accession_number: Mapped[str] = mapped_column(String(25), primary_key=True)
    cik: Mapped[str] = mapped_column(String(10), index=True)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.security_id"))
    form: Mapped[str] = mapped_column(String(20))
    is_amendment: Mapped[bool] = mapped_column(Boolean)
    filed_date: Mapped[date] = mapped_column(Date)
    report_period: Mapped[date | None] = mapped_column(Date)
    accepted_at: Mapped[datetime] = mapped_column(UTCDateTime)
    submissions_acceptance_raw: Mapped[str | None] = mapped_column(String(40))  # cross-check only
    available_at: Mapped[datetime] = mapped_column(UTCDateTime)
    availability_policy: Mapped[str] = mapped_column(String(40))
    primary_document: Mapped[str | None] = mapped_column(String(300))
    header_archive_id: Mapped[str] = mapped_column(ForeignKey("raw_source_archive.archive_id"))
    xbrl_archive_id: Mapped[str | None] = mapped_column(ForeignKey("raw_source_archive.archive_id"))
    ingested_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)

    __table_args__ = (
        CheckConstraint("available_at >= accepted_at", name="available_after_acceptance"),
    )


class FundamentalFact(Base):
    """Append-only fact versions. Each row is ONE value as reported in ONE filing.

    The same economic fact (concept, period, unit) appears once per filing that reports it
    (original, amendments, later comparatives). ``facts_as_of`` picks the version that was
    actually available at ``as_of``; nothing is ever updated in place.
    """

    __tablename__ = "fundamental_facts"

    fact_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.security_id"))
    taxonomy: Mapped[str] = mapped_column(String(30), default="internal")  # us-gaap, dei, ifrs-full
    concept: Mapped[str] = mapped_column(String(200))
    fiscal_period: Mapped[str | None] = mapped_column(String(10))
    period_start: Mapped[date | None] = mapped_column(Date)  # None for instants
    period_end: Mapped[date] = mapped_column(Date)
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(30))
    currency: Mapped[str | None] = mapped_column(String(3))
    available_at: Mapped[datetime] = mapped_column(UTCDateTime)
    revision_id: Mapped[int] = mapped_column(Integer, default=0)
    # filing provenance (mandatory for SEC facts, enforced by the SEC ingestor)
    cik: Mapped[str | None] = mapped_column(String(10))
    accession_number: Mapped[str | None] = mapped_column(
        ForeignKey("sec_filings.accession_number"), index=True
    )
    form: Mapped[str | None] = mapped_column(String(20))
    filed_date: Mapped[date | None] = mapped_column(Date)
    accepted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    is_amendment: Mapped[bool] = mapped_column(Boolean, default=False)
    source_document: Mapped[str | None] = mapped_column(String(500))
    statement_id: Mapped[str | None] = mapped_column(
        ForeignKey("financial_statements.statement_id")
    )
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.source_id"))
    raw_record_id: Mapped[str | None] = mapped_column(ForeignKey("raw_records.raw_record_id"))
    ingested_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)

    __table_args__ = (
        Index("ix_fact_asof", "security_id", "concept", "period_end", "available_at"),
        UniqueConstraint(
            "security_id",
            "taxonomy",
            "concept",
            "unit",
            "period_start",
            "period_end",
            "fiscal_period",
            "revision_id",
            "accession_number",
            "source_id",
        ),
        CheckConstraint(
            "accepted_at IS NULL OR available_at >= accepted_at", name="available_after_acceptance"
        ),
    )


class AnalystEstimate(Base):
    __tablename__ = "analyst_estimates"

    estimate_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.security_id"))
    metric: Mapped[str] = mapped_column(String(30))  # eps | revenue
    target_period_end: Mapped[date] = mapped_column(Date)
    statistic: Mapped[str] = mapped_column(String(20))  # mean | median | n | up | down
    value: Mapped[float | None] = mapped_column(Float)
    available_at: Mapped[datetime] = mapped_column(UTCDateTime)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.source_id"))
    ingested_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)

    __table_args__ = (
        Index("ix_estimate_asof", "security_id", "metric", "target_period_end", "available_at"),
    )


class MacroData(Base):
    """Macro series stored by VINTAGE: each revision is a row with its own available_at."""

    __tablename__ = "macro_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_code: Mapped[str] = mapped_column(String(50))
    observation_date: Mapped[date] = mapped_column(Date)
    value: Mapped[float | None] = mapped_column(Float)
    available_at: Mapped[datetime] = mapped_column(UTCDateTime)  # = macro_available_at
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.source_id"))
    ingested_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)

    __table_args__ = (
        Index("ix_macro_asof", "series_code", "observation_date", "available_at"),
        UniqueConstraint("series_code", "observation_date", "available_at"),
    )


# ───────────────────────────── features / models / predictions ─────────────────────────────


class FeatureSnapshotRow(Base):
    __tablename__ = "feature_snapshots"

    snapshot_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.security_id"))
    as_of: Mapped[datetime] = mapped_column(UTCDateTime)
    feature_version: Mapped[str] = mapped_column(String(50))
    data_version: Mapped[str] = mapped_column(String(50))
    code_version: Mapped[str] = mapped_column(String(64))
    features: Mapped[dict[str, Any]] = mapped_column(JSON)
    availability: Mapped[dict[str, Any]] = mapped_column(JSON)  # name -> available_at, source_ref
    missing_mask: Mapped[dict[str, Any]] = mapped_column(JSON)
    imputed_mask: Mapped[dict[str, Any]] = mapped_column(JSON)
    dq_warnings: Mapped[list[Any]] = mapped_column(JSON)
    max_available_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    content_hash: Mapped[str] = mapped_column(String(64))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)

    __table_args__ = (
        Index("ix_snapshot_lookup", "security_id", "as_of", "feature_version", "data_version"),
        CheckConstraint(
            "max_available_at IS NULL OR max_available_at <= as_of", name="no_lookahead"
        ),
    )


class ModelRow(Base):
    __tablename__ = "models"

    model_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    horizon: Mapped[str] = mapped_column(String(5))
    kind: Mapped[str] = mapped_column(String(20))  # baseline | ml
    role: Mapped[str] = mapped_column(
        String(20), default="challenger"
    )  # champion|challenger|retired
    description: Mapped[str | None] = mapped_column(Text)


class ModelVersion(Base):
    __tablename__ = "model_versions"

    model_version: Mapped[str] = mapped_column(String(80), primary_key=True)
    model_id: Mapped[str] = mapped_column(ForeignKey("models.model_id"))
    scoring_version: Mapped[str] = mapped_column(String(50))
    feature_version: Mapped[str] = mapped_column(String(50))
    code_version: Mapped[str] = mapped_column(String(64))
    config_hash: Mapped[str] = mapped_column(String(64))
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    artifact_uri: Mapped[str | None] = mapped_column(String(500))
    trained_until: Mapped[datetime | None] = mapped_column(UTCDateTime)  # train_cutoff
    seed: Mapped[int] = mapped_column(Integer)
    frozen: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)


class Prediction(Base):
    __tablename__ = "predictions"

    prediction_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("feature_snapshots.snapshot_id"))
    snapshot_hash: Mapped[str] = mapped_column(String(64))
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.security_id"))
    as_of: Mapped[datetime] = mapped_column(UTCDateTime)  # = signal_timestamp
    execution_at: Mapped[datetime] = mapped_column(UTCDateTime)
    horizon: Mapped[str] = mapped_column(String(5))
    model_version: Mapped[str] = mapped_column(ForeignKey("model_versions.model_version"))
    signal: Mapped[str] = mapped_column(String(4))
    probability: Mapped[float | None] = mapped_column(Float)
    expected_excess_return: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    scores: Mapped[dict[str, Any]] = mapped_column(JSON)
    explanation: Mapped[dict[str, Any]] = mapped_column(JSON)
    data_version: Mapped[str] = mapped_column(String(50))
    feature_version: Mapped[str] = mapped_column(String(50))
    scoring_version: Mapped[str] = mapped_column(String(50))
    config_hash: Mapped[str] = mapped_column(String(64))
    code_version: Mapped[str] = mapped_column(String(64))
    seed: Mapped[int] = mapped_column(Integer)
    supersedes_id: Mapped[str | None] = mapped_column(ForeignKey("predictions.prediction_id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)

    __table_args__ = (
        Index("ix_prediction_lookup", "security_id", "as_of", "horizon", "model_version"),
        CheckConstraint("signal IN ('BUY','HOLD','SELL')", name="signal_values"),
        CheckConstraint("execution_at > as_of", name="execution_after_signal"),
        CheckConstraint(
            "probability IS NULL OR (probability >= 0 AND probability <= 1)", name="prob_range"
        ),
    )


class LivePrediction(Base):
    """Forward paper-test registry. Rows are created at signal time and never edited."""

    __tablename__ = "live_predictions"

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    prediction_id: Mapped[str] = mapped_column(ForeignKey("predictions.prediction_id"), unique=True)
    registered_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
    evaluation_due_at: Mapped[datetime] = mapped_column(UTCDateTime)

    __table_args__ = (CheckConstraint("evaluation_due_at > registered_at", name="due_in_future"),)


# ───────────────────────────── backtests / outcomes / research ─────────────────────────────


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    run_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    model_version: Mapped[str] = mapped_column(ForeignKey("model_versions.model_version"))
    config: Mapped[dict[str, Any]] = mapped_column(JSON)
    config_hash: Mapped[str] = mapped_column(String(64))
    universe_codes: Mapped[list[str]] = mapped_column(JSON)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    frequency: Mapped[str] = mapped_column(String(20))
    overlapping: Mapped[bool] = mapped_column(Boolean)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    touches_holdout: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="created")
    report: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class BacktestObservation(Base):
    __tablename__ = "backtest_observations"

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("backtest_runs.run_id"), index=True)
    prediction_id: Mapped[str] = mapped_column(ForeignKey("predictions.prediction_id"))
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.security_id"))
    as_of: Mapped[datetime] = mapped_column(UTCDateTime)
    horizon: Mapped[str] = mapped_column(String(5))
    t_exec: Mapped[datetime] = mapped_column(UTCDateTime)
    label_end: Mapped[datetime] = mapped_column(UTCDateTime)
    label_available_at: Mapped[datetime] = mapped_column(UTCDateTime)

    __table_args__ = (
        CheckConstraint("t_exec > as_of", name="exec_after_signal"),
        CheckConstraint("label_end > t_exec", name="label_after_exec"),
        CheckConstraint("label_available_at >= label_end", name="label_available_after_end"),
    )


class RealizedReturn(Base):
    __tablename__ = "realized_returns"

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    prediction_id: Mapped[str] = mapped_column(ForeignKey("predictions.prediction_id"))
    horizon: Mapped[str] = mapped_column(String(5))
    t_exec: Mapped[datetime] = mapped_column(UTCDateTime)
    label_end: Mapped[datetime] = mapped_column(UTCDateTime)
    label_available_at: Mapped[datetime] = mapped_column(UTCDateTime)
    stock_total_return: Mapped[float] = mapped_column(Float)
    market_total_return: Mapped[float] = mapped_column(Float)
    sector_total_return: Mapped[float | None] = mapped_column(Float)
    market_excess_return: Mapped[float] = mapped_column(Float)
    sector_excess_return: Mapped[float | None] = mapped_column(Float)
    absolute_return: Mapped[float] = mapped_column(Float)
    volatility: Mapped[float | None] = mapped_column(Float)
    downside_volatility: Mapped[float | None] = mapped_column(Float)
    max_drawdown: Mapped[float | None] = mapped_column(Float)
    max_adverse_excursion: Mapped[float | None] = mapped_column(Float)
    max_favorable_excursion: Mapped[float | None] = mapped_column(Float)
    delisted_during_horizon: Mapped[bool] = mapped_column(Boolean, default=False)
    return_currency: Mapped[str] = mapped_column(String(3))
    computed_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)

    __table_args__ = (UniqueConstraint("prediction_id", "horizon"),)


class Experiment(Base):
    __tablename__ = "experiments"

    experiment_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    hypothesis: Mapped[str] = mapped_column(Text)
    model_version: Mapped[str | None] = mapped_column(ForeignKey("model_versions.model_version"))
    baseline_model_version: Mapped[str | None] = mapped_column(String(80))
    n_variants: Mapped[int] = mapped_column(Integer, default=1)  # multiple-testing ledger
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)


class ErrorAnalysis(Base):
    __tablename__ = "error_analysis"

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    prediction_id: Mapped[str] = mapped_column(ForeignKey("predictions.prediction_id"))
    category: Mapped[str] = mapped_column(String(40))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    hypothesis: Mapped[str | None] = mapped_column(Text)  # hypotheses only; never edits a model
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)


class HoldoutAccessLog(Base):
    __tablename__ = "holdout_access_log"

    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    model_version: Mapped[str] = mapped_column(ForeignKey("model_versions.model_version"))
    reason: Mapped[str] = mapped_column(Text)
    requested_by: Mapped[str] = mapped_column(String(100))
    accessed_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)


class HoldoutEvaluation(Base):
    """SEALED holdout results. Written only by ``evaluate_candidate_on_holdout``; never read
    by analytics, the API or the dashboard during development (see validation.holdout)."""

    __tablename__ = "holdout_evaluations"

    evaluation_id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    access_id: Mapped[str] = mapped_column(ForeignKey("holdout_access_log.id"), unique=True)
    model_version: Mapped[str] = mapped_column(ForeignKey("model_versions.model_version"))
    holdout_start: Mapped[date] = mapped_column(Date)
    holdout_end: Mapped[date] = mapped_column(Date)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON)
    n_observations: Mapped[int] = mapped_column(Integer)
    metrics_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)


IMMUTABLE_TABLES: frozenset[str] = frozenset(
    {
        "raw_records",
        "feature_snapshots",
        "predictions",
        "live_predictions",
        "backtest_observations",
        "realized_returns",
        "holdout_access_log",
        "holdout_evaluations",
        "raw_source_archive",
        "sec_filings",
        "fundamental_facts",
        "index_events",
        "membership_builds",
        "index_membership",
    }
)
