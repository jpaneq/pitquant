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

    New keys create a security whose ticker history is derived from the stream and BOUNDED
    to its membership periods (``membership_ticker_periods``): an index source only proves
    which code a security had while it was a member.
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
    first_seen: dict[str, tuple[date, str | None]] = {}
    for e in sorted(src.events, key=lambda x: (x.effective_date, x.ticker is None)):
        if e.security_key and e.security_key not in first_seen:
            first_seen[e.security_key] = (e.effective_date, e.ticker)
    observed = {k: (t, d) for k, t, d in src.ticker_observations}
    periods = membership_ticker_periods(src)
    for key, (d0, ticker) in sorted(first_seen.items(), key=lambda kv: (kv[1][0], kv[0])):
        if key in keys:
            rep.reused += 1
            continue
        spans = [sp for sp in periods.get(key, []) if sp[0]]
        if ticker is None and key in observed and not spans:
            ticker, d0_ticker = observed[key]
            spans = [(ticker, d0_ticker, None)]
        sec = sm.register(
            name=f"{ticker or key} ({src.membership_source})",
            exchange=exchange,
            currency=currency,
            country=country,
        )
        for tick, start, end in spans:
            _close_clashing_ticker(session, tick, exchange, start, rep)
            sm.add_ticker(sec.security_id, tick, exchange, start, end)
        if key.startswith("ISIN:"):
            sm.add_identifier(sec.security_id, "ISIN", key.removeprefix("ISIN:"), d0)
        session.add(ProviderKey(source_id=source_id, provider_key=key, security_id=sec.security_id))
        keys[key] = sec.security_id
        rep.created += 1
    session.flush()
    return keys, rep


def _close_clashing_ticker(
    session: Session, ticker: str, exchange: str, d0: date, rep: RegistrationReport
) -> None:
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
            f"ticker {ticker} reassigned on {d0}: closed for {clash.security_id} (verify with D-05)"
        )
        session.flush()


def membership_ticker_periods(src: EventSource) -> dict[str, list[tuple[str, date, date | None]]]:
    """(ticker, from, to) per security key while it was a member: opened by an inclusion,
    split by each TICKER_CHANGE, closed by the exclusion. Open-ended while still a member."""
    from pitquant.universe.events import EventType

    order = {
        EventType.INDEX_DELETE: 0,
        EventType.TICKER_CHANGE: 1,
        EventType.INITIAL_SNAPSHOT: 2,
        EventType.INDEX_ADD: 2,
    }
    out: dict[str, list[tuple[str, date, date | None]]] = {}
    open_: dict[str, tuple[str, date]] = {}
    evs = [e for e in src.events if e.security_key and e.event_type in order]
    for e in sorted(evs, key=lambda e: (e.effective_date, order[e.event_type])):
        k = e.security_key or ""
        if e.event_type in (EventType.INITIAL_SNAPSHOT, EventType.INDEX_ADD):
            if e.ticker:
                open_[k] = (e.ticker.upper(), e.effective_date)
        elif e.event_type is EventType.TICKER_CHANGE and k in open_:
            t, start = open_.pop(k)
            if start < e.effective_date:
                out.setdefault(k, []).append((t, start, e.effective_date))
            open_[k] = ((e.new_ticker or "").upper(), e.effective_date)
        elif e.event_type is EventType.INDEX_DELETE and k in open_:
            t, start = open_.pop(k)
            if start < e.effective_date:
                out.setdefault(k, []).append((t, start, e.effective_date))
    for k, (t, start) in open_.items():
        out.setdefault(k, []).append((t, start, None))
    return out
