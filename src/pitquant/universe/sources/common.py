"""Shared helpers for index-history sources: register the securities an event stream
refers to, and archive the raw source documents."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from pitquant.db.models import DataSource, ProviderKey, TickerHistory
from pitquant.security_master.service import SecurityMaster
from pitquant.universe.events import EventSource


@dataclass
class RegistrationReport:
    created: int = 0
    reused: int = 0
    warnings: list[str] = field(default_factory=list)


def ensure_index_source(session: Session, name: str, *, synthetic: bool = False) -> int:
    src = session.scalars(select(DataSource).where(DataSource.name == name)).first()
    if src is None:
        src = DataSource(
            name=name, provider_type="index_history", is_synthetic=synthetic, is_point_in_time=True
        )
        session.add(src)
        session.flush()
    return src.source_id


def register_event_securities(
    session: Session, src: EventSource, *, exchange: str, currency: str, country: str
) -> tuple[dict[str, str], RegistrationReport]:
    """Map every ``security_key`` in the stream to a permanent security_id.

    New keys create a security whose ticker history starts at its first event. Ticker
    changes are applied by ``apply_ticker_changes`` (same security_id, new ticker row).
    If a ticker is still open for ANOTHER security that is not referenced at that date,
    its interval is closed and a warning is recorded (to be confirmed with D-05 data).
    """
    rep = RegistrationReport()
    source_id = ensure_index_source(session, src.membership_source)
    keys = {
        r.provider_key: r.security_id
        for r in session.scalars(select(ProviderKey).where(ProviderKey.source_id == source_id))
    }
    sm = SecurityMaster(session)
    first_seen: dict[str, tuple[date, str]] = {}
    for e in sorted(src.events, key=lambda x: x.effective_date):
        if e.security_key and e.security_key not in first_seen and e.ticker:
            first_seen[e.security_key] = (e.effective_date, e.ticker)
    for key, (d0, ticker) in sorted(first_seen.items(), key=lambda kv: kv[1][0]):
        if key in keys:
            rep.reused += 1
            continue
        clash = session.scalars(
            select(TickerHistory).where(
                TickerHistory.ticker == ticker.upper(),
                TickerHistory.exchange == exchange,
                TickerHistory.valid_from <= d0,
                or_(TickerHistory.valid_to.is_(None), TickerHistory.valid_to > d0),
            )
        ).first()
        if clash is not None:
            clash.valid_to = d0
            rep.warnings.append(
                f"ticker {ticker} reassigned on {d0}: closed for {clash.security_id} "
                "(verify with D-05)"
            )
            session.flush()
        sec = sm.register(
            name=f"{ticker} ({src.membership_source})",
            exchange=exchange,
            currency=currency,
            country=country,
        )
        sm.add_ticker(sec.security_id, ticker, exchange, d0)
        if key.startswith("ISIN:"):
            sm.add_identifier(sec.security_id, "ISIN", key.removeprefix("ISIN:"), d0)
        session.add(ProviderKey(source_id=source_id, provider_key=key, security_id=sec.security_id))
        keys[key] = sec.security_id
        rep.created += 1
    session.flush()
    return keys, rep
