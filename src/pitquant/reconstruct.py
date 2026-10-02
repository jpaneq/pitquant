"""``pitquant reconstruct-security``: what could an investor know about ONE security at T?

Only reads through ``PITContext`` (prices closed at T, actions known at T, facts available at
T). No feature, score or return is computed here: it is a reconstruction of the information
set, with provenance for every piece, so that an auditor can replay it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from pitquant.core.errors import PITQuantError
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.data.point_in_time.context import PITContext
from pitquant.db.models import (
    DataQualityIssue,
    DataSource,
    FundamentalFact,
    IdentifierHistory,
    Issuer,
    Price,
    SecFiling,
    Security,
    TickerHistory,
)


class UnknownSecurityRef(PITQuantError):
    pass


def resolve_security(session: Session, ref: str) -> Security:
    """``security_id`` | dated ticker (any period) | ``CIK:<cik>`` (SEC-registered)."""
    sec = session.get(Security, ref)
    if sec is not None:
        return sec
    if ref.upper().startswith("CIK:"):
        cik = ref[4:].zfill(10)
        found = session.scalars(select(Security).where(Security.name.like(f"CIK {cik}%"))).all()
    else:
        ids = session.scalars(
            select(TickerHistory.security_id).where(TickerHistory.ticker == ref.upper())
        ).all()
        found = [s for s in (session.get(Security, i) for i in set(ids)) if s is not None]
    if len(found) != 1:
        raise UnknownSecurityRef(
            f"{ref!r}: {len(found)} matches (US tickers have no dated source yet: use CIK:<cik>)"
        )
    return found[0]


@dataclass
class Reconstruction:
    security_id: str
    name: str
    exchange: str
    currency: str
    as_of: str
    ticker: str | None
    issuer: str | None
    identifiers: list[str] = field(default_factory=list)
    bars: dict[str, Any] = field(default_factory=dict)
    fundamentals: dict[str, Any] = field(default_factory=dict)
    corporate_actions: list[dict[str, Any]] = field(default_factory=list)
    unresolved_dividends: list[dict[str, Any]] = field(default_factory=list)
    benchmark: str = "none ingested"
    notes: list[str] = field(default_factory=list)


def reconstruct(session: Session, ref: str, on: date) -> Reconstruction:
    sec = resolve_security(session, ref)
    cal = get_calendar(sec.exchange)
    day = cal.session_on_or_before(on)
    ctx = PITContext(session, cal.session_close(day))  # information set at that session's close
    issuer = session.get(Issuer, sec.issuer_id) if sec.issuer_id else None
    tick = session.scalars(
        select(TickerHistory.ticker).where(
            TickerHistory.security_id == sec.security_id,
            TickerHistory.valid_from <= on,
            or_(TickerHistory.valid_to.is_(None), TickerHistory.valid_to > on),
        )
    ).first()
    r = Reconstruction(
        sec.security_id, sec.name, sec.exchange, sec.currency, ctx.as_of.isoformat(), tick,
        issuer.name if issuer else None,
    )  # fmt: skip
    r.identifiers = [
        f"{i.id_type}={i.value} [{i.valid_from}..{i.valid_to or ''}]"
        for i in session.scalars(
            select(IdentifierHistory).where(
                IdentifierHistory.security_id == sec.security_id,
                IdentifierHistory.valid_from <= on,
            )
        )
    ]
    if tick is None:
        r.notes.append("no dated ticker for this security: ticker intentionally left empty")
    bars = ctx.raw_bars(sec.security_id)
    if bars.empty:
        r.bars = {"n": 0}
        r.notes.append("PRICE_DATA: no raw bar closed at T")
    else:
        srcs = session.execute(
            select(DataSource.name, func.count())
            .select_from(Price)
            .join(DataSource, DataSource.source_id == Price.source_id)
            .where(Price.security_id == sec.security_id, Price.bar_close_at <= ctx.as_of)
            .group_by(DataSource.name)
        ).all()
        r.bars = {
            "n": len(bars),
            "first": str(bars.index[0]),
            "last": str(bars.index[-1]),
            "last_close": float(bars["close"].iloc[-1]),
            "sources": {n: c for n, c in srcs},
        }
    subj = [FundamentalFact.security_id == sec.security_id]
    if sec.issuer_id:
        subj.append(FundamentalFact.issuer_id == sec.issuer_id)
    nfacts = session.scalar(
        select(func.count()).select_from(FundamentalFact).where(
            or_(*subj), FundamentalFact.available_at <= ctx.as_of
        )
    )  # fmt: skip
    filings = session.scalars(
        select(SecFiling.accession_number).where(
            SecFiling.security_id == sec.security_id, SecFiling.available_at <= ctx.as_of
        )
    ).all()
    r.fundamentals = {"facts_available": nfacts or 0, "sec_filings_available": len(filings)}
    for a in sorted(ctx.market_actions(sec.security_id), key=lambda x: x.anchor_date or on):
        r.corporate_actions.append(
            {
                "kind": a.kind.value,
                "ex_date": str(a.ex_date) if a.ex_date else None,
                "effective_date": str(a.effective_date) if a.effective_date else None,
                "announcement_date": str(a.announcement_date) if a.announcement_date else None,
                "record_date": str(a.record_date) if a.record_date else None,
                "payment_date": str(a.payment_date) if a.payment_date else None,
                "ratio": a.ratio,
                "cash_amount": a.cash_amount,
                "currency": a.currency,
                "provider": a.provenance.provider,
                "tier": a.provenance.tier.value,
                "source_hash": a.provenance.source_hash,
                "archive_id": a.provenance.archive_id,
                "known_at": a.available_at.isoformat(),
            }
        )
    for i in session.scalars(
        select(DataQualityIssue).where(
            DataQualityIssue.security_id == sec.security_id,
            DataQualityIssue.check_name == "ca_unresolved_ex_date",
            DataQualityIssue.resolved_at.is_(None),
        )
    ):
        if date.fromisoformat(i.details["window_to"]) <= on:
            r.unresolved_dividends.append(i.details.get("row", i.details))
    if r.unresolved_dividends:
        r.notes.append(
            f"{len(r.unresolved_dividends)} dividend(s) up to T have NO published ex-date: "
            "total return across them is undefined"
        )
    return r


def to_text(r: Reconstruction) -> str:
    out = [
        f"{r.name}  [{r.security_id}]  {r.exchange}/{r.currency}  ticker={r.ticker}",
        f"  as_of (information set): {r.as_of}   issuer: {r.issuer}",
        f"  identifiers: {r.identifiers or 'none dated'}",
        f"  raw OHLCV closed at T: {r.bars}",
        f"  fundamentals available at T: {r.fundamentals}",
        f"  corporate actions known at T: {len(r.corporate_actions)}",
    ]
    for a in r.corporate_actions[-8:]:
        amount = a["cash_amount"] if a["cash_amount"] is not None else f"x{a['ratio']}"
        out.append(
            f"    {a['kind']:<17} anchor={a['ex_date'] or a['effective_date']} {amount} "
            f"{a['currency'] or ''} [{a['tier']} {a['provider']} sha={a['source_hash'][:12]}]"
        )
    out.append(f"  unresolved dividends (no ex-date) up to T: {len(r.unresolved_dividends)}")
    out.append(f"  benchmark: {r.benchmark}")
    out += [f"  NOTE: {n}" for n in r.notes]
    return "\n".join(out)
