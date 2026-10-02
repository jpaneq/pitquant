"""Normalized market records → PIT validation → storage (ADR-0021).

    Provider → raw archive → parser → normalized (``market.normalized``) → HERE → tables

* identity first: a record whose provider key is not mapped to one of OUR proven
  security_ids is rejected (never stored under a guessed security);
* PIT validation: ``available_at`` must be aware, not in the future of the ingestion, and
  not before the event it describes (a bar is not known before its session close; an
  action not before its announcement date);
* RAW bars → ``prices``; the vendor's adjusted close → ``provider_adjusted_prices`` (QA);
* corporate actions → ``corporate_action_events`` (append-only, idempotent); complex
  Spanish actions from a vendor are refused as canonical (``requires_official_source``)
  and logged as data-quality issues for the official BME/CNMV layer.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.core.timeutils import require_aware, utc_now
from pitquant.db.models import (
    CorporateActionEvent,
    CorporateActionIngestion,
    DataQualityIssue,
    DataSource,
    Price,
    ProviderAdjustedPrice,
)
from pitquant.market.normalized import CorporateAction, MarketBar, NormalizedBatch


@dataclass
class StoreReport:
    bars_inserted: int = 0
    bars_existing: int = 0
    adjusted_qa_rows: int = 0
    actions_inserted: int = 0
    actions_existing: int = 0
    rejected: list[str] = field(default_factory=list)
    requires_official: list[str] = field(default_factory=list)


def _source_id(session: Session, name: str) -> int:
    src = session.scalars(select(DataSource).where(DataSource.name == name)).first()
    if src is None:
        src = DataSource(name=name, provider_type="market_data", is_point_in_time=False)
        session.add(src)
        session.flush()
    return src.source_id


def validate_bar(b: MarketBar, now: datetime) -> str | None:
    if b.available_at > now:
        return f"{b.security_key} {b.session_date}: available_at in the future"
    if b.available_at.date() < b.session_date:
        return f"{b.security_key} {b.session_date}: available before its session"
    return None


def validate_action(a: CorporateAction, now: datetime) -> str | None:
    if a.available_at > now:
        return f"{a.kind} {a.security_key}: available_at in the future"
    if a.announcement_date is not None and a.available_at.date() < a.announcement_date:
        return f"{a.kind} {a.security_key}: available before its announcement date"
    return None


def store_batch(
    session: Session,
    batch: NormalizedBatch,
    *,
    key_to_security: Mapping[str, str],
    market: str,
    now: datetime | None = None,
) -> StoreReport:
    now = require_aware(now) if now is not None else utc_now()
    rep = StoreReport()
    for b in batch.bars:
        sid = key_to_security.get(b.security_key)
        if sid is None:
            rep.rejected.append(f"{b.security_key}: identity not resolved")
            continue
        if (why := validate_bar(b, now)) is not None:
            rep.rejected.append(why)
            continue
        src = _source_id(session, b.provenance.provider)
        if session.get(Price, (sid, b.session_date, src)) is not None:
            rep.bars_existing += 1
        else:
            session.add(
                Price(
                    security_id=sid,
                    session_date=b.session_date,
                    source_id=src,
                    open=b.open,
                    high=b.high,
                    low=b.low,
                    close=b.close,
                    volume=b.volume,
                    currency=b.currency,
                    bar_close_at=b.available_at,
                )
            )
            rep.bars_inserted += 1
        if b.vendor_adj_close is not None and (
            session.get(ProviderAdjustedPrice, (sid, b.session_date, b.provenance.provider)) is None
        ):
            session.add(
                ProviderAdjustedPrice(
                    security_id=sid,
                    session_date=b.session_date,
                    provider=b.provenance.provider,
                    adj_close=b.vendor_adj_close,
                    vendor_last_updated=b.vendor_last_updated,
                    source_hash=b.provenance.source_hash,
                )
            )
            rep.adjusted_qa_rows += 1
    for a in batch.actions:
        sid = key_to_security.get(a.security_key)
        if sid is None:
            rep.rejected.append(f"{a.kind} {a.security_key}: identity not resolved")
            continue
        if (why := validate_action(a, now)) is not None:
            rep.rejected.append(why)
            continue
        if a.requires_official_source(market):
            rep.requires_official.append(f"{a.kind} {a.security_key} {a.anchor_date}")
            session.add(
                DataQualityIssue(
                    entity="corporate_action_events",
                    security_id=sid,
                    check_name="requires_official_source",
                    severity="medium",
                    details={
                        "kind": a.kind.value,
                        "provider": a.provenance.provider,
                        "date": str(a.anchor_date),
                        "detail": "complex ES action from a vendor: QA only, needs BME/CNMV",
                    },
                )
            )
            continue
        exists = session.scalars(
            select(CorporateActionEvent).where(
                CorporateActionEvent.provider == a.provenance.provider,
                CorporateActionEvent.provider_event_id == a.provenance.provider_raw_id,
                CorporateActionEvent.source_hash == a.provenance.source_hash,
            )
        ).first()
        if exists is not None:
            rep.actions_existing += 1
            continue
        target = key_to_security.get(a.target_key or "")
        session.add(
            CorporateActionEvent(
                security_id=sid,
                event_type=a.kind.value,
                announcement_date=a.announcement_date,
                ex_date=a.ex_date,
                record_date=a.record_date,
                payment_date=a.payment_date,
                effective_date=a.effective_date,
                available_at=a.available_at,
                ratio=a.ratio,
                cash_amount=a.cash_amount,
                currency=a.currency,
                target_security_id=target,
                details={**a.details, "target_key": a.target_key},
                provider=a.provenance.provider,
                source_tier=a.provenance.tier.value,
                provider_event_id=a.provenance.provider_raw_id,
                source_hash=a.provenance.source_hash,
                archive_id=a.provenance.archive_id,
                parser_version=a.provenance.parser_version,
            )
        )
        rep.actions_inserted += 1
    session.flush()
    return rep


def record_ca_ingestion(
    session: Session,
    *,
    security_id: str,
    provider: str,
    period_start: date,
    period_end: date,
    completed: bool,
    events_found: int,
    source_hash: str | None = None,
    detail: str | None = None,
) -> None:
    """Trace of ONE corporate-action query for ONE security and period (ADR-0022): the only
    thing from which coverage may be claimed."""
    session.add(
        CorporateActionIngestion(
            security_id=security_id,
            provider=provider,
            period_start=period_start,
            period_end=period_end,
            status="COMPLETED" if completed else "FAILED",
            events_found=events_found,
            source_hash=source_hash,
            detail=detail,
        )
    )
    session.flush()
