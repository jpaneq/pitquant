"""Idempotent ingestion pipeline (§77, §87–89).

Every function can be re-run for the same range without creating duplicates. Provider
payloads are stored verbatim in ``raw_records`` for lineage; failed data-quality checks
are logged in ``data_quality_issues`` and the offending row is NOT loaded (never patched).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.core.errors import ProviderContractError
from pitquant.core.hashing import canonical_json, content_hash
from pitquant.core.timeutils import utc_now
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.data.providers.base import (
    CorporateActionsProvider,
    FundamentalProvider,
    IndexMembershipProvider,
    PriceProvider,
    ProviderInfo,
    SecurityProvider,
)
from pitquant.data.validation.quality import check_bar, check_price_jump
from pitquant.db.models import (
    CorporateAction,
    DataQualityIssue,
    DataSource,
    Dividend,
    FundamentalFact,
    IndexMembership,
    Price,
    ProviderKey,
    RawRecord,
    Security,
)
from pitquant.security_master.service import SecurityMaster
from pitquant.universe.index_membership import IndexUniverse


@dataclass
class IngestReport:
    inserted: int = 0
    skipped_existing: int = 0
    rejected: int = 0
    issues: list[str] = field(default_factory=list)


def ensure_source(session: Session, info: ProviderInfo) -> int:
    src = session.scalars(select(DataSource).where(DataSource.name == info.name)).first()
    if src is None:
        src = DataSource(
            name=info.name,
            provider_type="composite",
            is_synthetic=info.is_synthetic,
            is_point_in_time=info.is_point_in_time,
        )
        session.add(src)
        session.flush()
    return src.source_id


def _key_map(session: Session, source_id: int) -> dict[str, str]:
    rows = session.scalars(select(ProviderKey).where(ProviderKey.source_id == source_id)).all()
    return {r.provider_key: r.security_id for r in rows}


def _raw(session: Session, source_id: int, ident: str, payload: dict[str, object]) -> str:
    h = content_hash(payload)
    existing = session.scalars(
        select(RawRecord).where(
            RawRecord.source_id == source_id,
            RawRecord.original_identifier == ident,
            RawRecord.payload_hash == h,
        )
    ).first()
    if existing:
        return existing.raw_record_id
    rr = RawRecord(
        source_id=source_id,
        original_identifier=ident,
        retrieved_at=utc_now(),
        payload=json.loads(canonical_json(payload)),
        payload_hash=h,
    )
    session.add(rr)
    session.flush()
    return rr.raw_record_id


def _issue(
    session: Session,
    entity: str,
    sid: str | None,
    check: str,
    sev: str,
    detail: str,
    raw_id: str | None = None,
) -> None:
    session.add(
        DataQualityIssue(
            entity=entity,
            security_id=sid,
            check_name=check,
            severity=sev,
            details={"detail": detail},
            raw_record_id=raw_id,
        )
    )


# ───────────────────────────── securities ─────────────────────────────


def ingest_securities(session: Session, provider: SecurityProvider) -> IngestReport:
    rep = IngestReport()
    sid_src = ensure_source(session, provider.info)
    keys = _key_map(session, sid_src)
    sm = SecurityMaster(session)
    records = provider.securities()
    for rec in records:
        if rec.provider_security_key in keys:
            rep.skipped_existing += 1
            continue
        _raw(session, sid_src, f"security:{rec.provider_security_key}", asdict(rec))
        sec = sm.register(
            name=rec.name,
            exchange=rec.exchange,
            currency=rec.currency,
            country=rec.country,
            listing_start=rec.listing_start,
            is_synthetic=provider.info.is_synthetic,
        )
        for t, f, to in rec.tickers:
            sm.add_ticker(sec.security_id, t, rec.exchange, f, to)
        for typ, val, f, to in rec.identifiers:
            sm.add_identifier(sec.security_id, typ, val, f, to)
        session.add(
            ProviderKey(
                source_id=sid_src,
                provider_key=rec.provider_security_key,
                security_id=sec.security_id,
            )
        )
        keys[rec.provider_security_key] = sec.security_id
        rep.inserted += 1
    # second pass: delistings and acquirer links (needs all ids)
    for rec in records:
        sec_obj = session.get(Security, keys[rec.provider_security_key])
        if rec.listing_end and sec_obj is not None and not sec_obj.delisted:
            sec_obj.listing_end = rec.listing_end
            sec_obj.delisted = True
            sec_obj.delisting_reason = rec.delisting_reason
            if rec.acquirer_key:
                sec_obj.acquirer_security_id = keys[rec.acquirer_key]
    session.flush()
    return rep


# ───────────────────────────── membership ─────────────────────────────


def ingest_memberships(
    session: Session, provider: IndexMembershipProvider, index_code: str
) -> IngestReport:
    if not provider.info.is_point_in_time:
        raise ProviderContractError(
            f"{provider.info.name} is not point-in-time: refusing to build historical universes "
            "from current constituents (survivorship bias)"
        )
    rep = IngestReport()
    src = ensure_source(session, provider.info)
    keys = _key_map(session, src)
    uni = IndexUniverse(session)
    for m in provider.memberships(index_code):
        sid = keys.get(m.provider_security_key)
        if sid is None:
            rep.rejected += 1
            rep.issues.append(f"unknown security {m.provider_security_key}")
            continue
        exists = session.scalars(
            select(IndexMembership).where(
                IndexMembership.security_id == sid,
                IndexMembership.index_code == m.index_code,
                IndexMembership.inclusion_date == m.inclusion_date,
            )
        ).first()
        if exists:
            rep.skipped_existing += 1
            continue
        uni.add_membership(
            security_id=sid,
            index_code=m.index_code,
            inclusion_date=m.inclusion_date,
            exclusion_date=m.exclusion_date,
            inclusion_reason=m.inclusion_reason,
            exclusion_reason=m.exclusion_reason,
            announced_at=m.announced_at,
            ticker_at_inclusion=m.ticker_at_inclusion,
            source_id=src,
        )
        rep.inserted += 1
    return rep


# ───────────────────────────── corporate actions ─────────────────────────────


def ingest_corporate_actions(
    session: Session, provider: CorporateActionsProvider, start: date, end: date
) -> IngestReport:
    rep = IngestReport()
    src = ensure_source(session, provider.info)
    keys = _key_map(session, src)
    for a in provider.actions(list(keys), start, end):
        sid = keys[a.provider_security_key]
        dup = session.scalars(
            select(CorporateAction).where(
                CorporateAction.security_id == sid,
                CorporateAction.action_type == a.action_type,
                CorporateAction.ex_date == a.ex_date,
                CorporateAction.source_id == src,
            )
        ).first()
        if dup:
            rep.skipped_existing += 1
            continue
        session.add(
            CorporateAction(
                security_id=sid,
                action_type=a.action_type,
                announced_at=a.announced_at,
                ex_date=a.ex_date,
                ratio=a.ratio,
                cash_amount=a.cash_amount,
                currency=a.currency,
                target_security_id=keys.get(a.target_key) if a.target_key else None,
                details=a.details,
                source_id=src,
            )
        )
        rep.inserted += 1
    for d in provider.dividends(list(keys), start, end):
        sid = keys[d.provider_security_key]
        dup_div = session.scalars(
            select(Dividend).where(
                Dividend.security_id == sid,
                Dividend.ex_date == d.ex_date,
                Dividend.dividend_type == d.dividend_type,
                Dividend.source_id == src,
            )
        ).first()
        if dup_div:
            rep.skipped_existing += 1
            continue
        session.add(
            Dividend(
                security_id=sid,
                dividend_type=d.dividend_type,
                announced_at=d.announced_at,
                ex_date=d.ex_date,
                pay_date=d.pay_date,
                gross_amount=d.gross_amount,
                currency=d.currency,
                source_id=src,
            )
        )
        rep.inserted += 1
    session.flush()
    return rep


# ───────────────────────────── prices ─────────────────────────────


def ingest_prices(
    session: Session,
    provider: PriceProvider,
    keys_subset: Sequence[str] | None,
    start: date,
    end: date,
) -> IngestReport:
    rep = IngestReport()
    src = ensure_source(session, provider.info)
    keys = _key_map(session, src)
    wanted = list(keys_subset) if keys_subset else list(keys)
    for k in wanted:
        sid = keys[k]
        sec = session.get_one(Security, sid)
        cal = get_calendar(sec.exchange)
        existing = set(
            session.scalars(
                select(Price.session_date).where(
                    Price.security_id == sid,
                    Price.source_id == src,
                    Price.session_date >= start,
                    Price.session_date <= end,
                )
            ).all()
        )
        split_days = set(
            session.scalars(
                select(CorporateAction.ex_date).where(
                    CorporateAction.security_id == sid, CorporateAction.action_type == "split"
                )
            ).all()
        )
        prev_close: float | None = None
        for bar in provider.bars([k], start, end):
            findings = check_bar(bar, expected_currency=sec.currency)
            if not cal.is_session(bar.session_date):
                _issue(session, "price", sid, "bar_on_non_session", "high", str(bar.session_date))
                rep.rejected += 1
                continue
            if prev_close is not None and bar.session_date not in split_days:
                jump = check_price_jump(prev_close, bar.close)
                if jump:
                    findings.append(jump)
            for f in findings:
                _issue(
                    session,
                    "price",
                    sid,
                    f.check,
                    f.severity.value,
                    f"{bar.session_date}: {f.detail}",
                )
            if any(f.blocking for f in findings):
                rep.rejected += 1
                continue
            prev_close = bar.close
            if bar.session_date in existing:
                rep.skipped_existing += 1
                continue
            session.add(
                Price(
                    security_id=sid,
                    session_date=bar.session_date,
                    source_id=src,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                    currency=bar.currency,
                    bar_close_at=cal.session_close(bar.session_date),
                )
            )
            rep.inserted += 1
    session.flush()
    return rep


# ───────────────────────────── fundamentals ─────────────────────────────


def ingest_fundamentals(
    session: Session,
    provider: FundamentalProvider,
    start: date,
    end: date,
    publication_lag_minutes: int,
) -> IngestReport:
    rep = IngestReport()
    src = ensure_source(session, provider.info)
    keys = _key_map(session, src)
    for f in provider.facts(list(keys), start, end):
        sid = keys[f.provider_security_key]
        sec = session.get_one(Security, sid)
        dup = session.scalars(
            select(FundamentalFact).where(
                FundamentalFact.security_id == sid,
                FundamentalFact.concept == f.concept,
                FundamentalFact.fiscal_period == f.fiscal_period,
                FundamentalFact.revision_id == f.revision_id,
                FundamentalFact.source_id == src,
            )
        ).first()
        if dup:
            rep.skipped_existing += 1
            continue
        available_at = get_calendar(sec.exchange).available_after_publication(
            f.published_at, publication_lag_minutes
        )
        raw_id = _raw(
            session,
            src,
            f"fact:{f.provider_security_key}:{f.concept}:{f.fiscal_period}:{f.revision_id}",
            asdict(f),
        )
        session.add(
            FundamentalFact(
                security_id=sid,
                concept=f.concept,
                fiscal_period=f.fiscal_period,
                period_start=f.period_start,
                period_end=f.period_end,
                value=f.value,
                unit=f.unit,
                currency=f.currency,
                available_at=available_at,
                revision_id=f.revision_id,
                source_id=src,
                raw_record_id=raw_id,
            )
        )
        rep.inserted += 1
    session.flush()
    return rep
