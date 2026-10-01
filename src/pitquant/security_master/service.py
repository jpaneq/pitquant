"""Security Master: permanent internal identifiers and dated identifier history (ADR-0002)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from pitquant.core.errors import (
    AmbiguousIdentifierError,
    OverlappingIntervalError,
    UnknownSecurityError,
)
from pitquant.core.intervals import overlaps as _overlaps
from pitquant.db.models import IdentifierHistory, Security, TickerHistory


@dataclass(frozen=True)
class SecurityView:
    """What the caller may know about a security AS OF a date.

    Delisting/successor information is withheld when it lies in the future relative to
    ``as_of`` (knowing a company will be acquired is look-ahead).
    """

    security_id: str
    name: str
    exchange: str
    currency: str
    ticker: str
    as_of: date
    listing_start: date | None
    delisted: bool
    delisting_reason: str | None
    is_synthetic: bool


class SecurityMaster:
    def __init__(self, session: Session) -> None:
        self.s = session

    # ── registration ──────────────────────────────────────────────────────────
    def register(
        self,
        *,
        name: str,
        exchange: str,
        currency: str,
        country: str | None = None,
        listing_start: date | None = None,
        is_synthetic: bool = False,
        security_id: str | None = None,
    ) -> Security:
        sec = Security(
            name=name,
            exchange=exchange,
            currency=currency,
            country=country,
            listing_start=listing_start,
            is_synthetic=is_synthetic,
        )
        if security_id:
            sec.security_id = security_id
        self.s.add(sec)
        self.s.flush()
        return sec

    def add_ticker(
        self,
        security_id: str,
        ticker: str,
        exchange: str,
        valid_from: date,
        valid_to: date | None = None,
    ) -> TickerHistory:
        ticker = ticker.upper().strip()
        # The same (ticker, exchange) may be reused by different securities, but never
        # with overlapping validity — otherwise resolution would be ambiguous.
        existing = self.s.scalars(
            select(TickerHistory).where(
                TickerHistory.ticker == ticker, TickerHistory.exchange == exchange
            )
        ).all()
        for row in existing:
            if _overlaps(row.valid_from, row.valid_to, valid_from, valid_to):
                raise OverlappingIntervalError(
                    f"{ticker}@{exchange} already assigned to {row.security_id} "
                    f"[{row.valid_from}, {row.valid_to}) overlapping [{valid_from}, {valid_to})"
                )
        # A security has at most one ticker per exchange at a time.
        own = self.s.scalars(
            select(TickerHistory).where(
                TickerHistory.security_id == security_id, TickerHistory.exchange == exchange
            )
        ).all()
        for row in own:
            if _overlaps(row.valid_from, row.valid_to, valid_from, valid_to):
                raise OverlappingIntervalError(
                    f"security {security_id} already has ticker {row.ticker} on {exchange} "
                    f"during [{row.valid_from}, {row.valid_to})"
                )
        th = TickerHistory(
            security_id=security_id,
            ticker=ticker,
            exchange=exchange,
            valid_from=valid_from,
            valid_to=valid_to,
        )
        self.s.add(th)
        self.s.flush()
        return th

    def change_ticker(
        self, security_id: str, exchange: str, new_ticker: str, effective: date
    ) -> TickerHistory:
        """Close the open ticker interval at ``effective`` and open a new one."""
        current = self.s.scalars(
            select(TickerHistory).where(
                TickerHistory.security_id == security_id,
                TickerHistory.exchange == exchange,
                TickerHistory.valid_to.is_(None),
            )
        ).one()
        if effective <= current.valid_from:
            raise OverlappingIntervalError("ticker change must be after the current start")
        current.valid_to = effective
        self.s.flush()
        return self.add_ticker(security_id, new_ticker, exchange, effective)

    def add_identifier(
        self,
        security_id: str,
        id_type: str,
        value: str,
        valid_from: date,
        valid_to: date | None = None,
    ) -> IdentifierHistory:
        id_type = id_type.upper()
        if id_type not in {"ISIN", "CUSIP", "FIGI", "CIK"}:
            raise ValueError(f"unsupported identifier type {id_type}")
        clash = self.s.scalars(
            select(IdentifierHistory).where(
                IdentifierHistory.id_type == id_type, IdentifierHistory.value == value
            )
        ).all()
        for row in clash:
            if row.security_id != security_id and _overlaps(
                row.valid_from, row.valid_to, valid_from, valid_to
            ):
                raise OverlappingIntervalError(f"{id_type} {value} already in use")
        ih = IdentifierHistory(
            security_id=security_id,
            id_type=id_type,
            value=value,
            valid_from=valid_from,
            valid_to=valid_to,
        )
        self.s.add(ih)
        self.s.flush()
        return ih

    def mark_delisted(
        self,
        security_id: str,
        last_session: date,
        reason: str,
        *,
        acquirer_security_id: str | None = None,
        successor_security_id: str | None = None,
    ) -> None:
        """Record a delisting. The security is NEVER deleted (survivorship bias)."""
        sec = self.s.get_one(Security, security_id)
        sec.listing_end = last_session
        sec.delisted = True
        sec.delisting_reason = reason
        sec.acquirer_security_id = acquirer_security_id
        sec.successor_security_id = successor_security_id
        for th in sec.tickers:
            if th.valid_to is None or th.valid_to > last_session:
                th.valid_to = date.fromordinal(last_session.toordinal() + 1)
        self.s.flush()

    # ── resolution ────────────────────────────────────────────────────────────
    def resolve(self, ticker: str, exchange: str, as_of: date) -> str:
        """Return the security_id that carried ``ticker`` on ``exchange`` at ``as_of``."""
        rows = self.s.scalars(
            select(TickerHistory.security_id).where(
                TickerHistory.ticker == ticker.upper().strip(),
                TickerHistory.exchange == exchange,
                TickerHistory.valid_from <= as_of,
                or_(TickerHistory.valid_to.is_(None), TickerHistory.valid_to > as_of),
            )
        ).all()
        if not rows:
            raise UnknownSecurityError(f"no security had ticker {ticker}@{exchange} on {as_of}")
        if len(set(rows)) > 1:
            raise AmbiguousIdentifierError(f"{ticker}@{exchange} ambiguous on {as_of}: {rows}")
        return rows[0]

    def resolve_identifier(self, id_type: str, value: str, as_of: date) -> str:
        rows = self.s.scalars(
            select(IdentifierHistory.security_id).where(
                and_(
                    IdentifierHistory.id_type == id_type.upper(),
                    IdentifierHistory.value == value,
                    IdentifierHistory.valid_from <= as_of,
                    or_(IdentifierHistory.valid_to.is_(None), IdentifierHistory.valid_to > as_of),
                )
            )
        ).all()
        if not rows:
            raise UnknownSecurityError(f"no security had {id_type}={value} on {as_of}")
        if len(set(rows)) > 1:
            raise AmbiguousIdentifierError(f"{id_type}={value} ambiguous on {as_of}")
        return rows[0]

    def ticker_as_of(self, security_id: str, as_of: date) -> str | None:
        row = self.s.scalars(
            select(TickerHistory.ticker).where(
                TickerHistory.security_id == security_id,
                TickerHistory.valid_from <= as_of,
                or_(TickerHistory.valid_to.is_(None), TickerHistory.valid_to > as_of),
            )
        ).first()
        return row

    def view(self, security_id: str, as_of: date) -> SecurityView:
        sec = self.s.get(Security, security_id)
        if sec is None:
            raise UnknownSecurityError(security_id)
        ticker = self.ticker_as_of(security_id, as_of)
        if ticker is None:
            raise UnknownSecurityError(f"{security_id} not listed on {as_of}")
        delisted_known = bool(sec.delisted and sec.listing_end and sec.listing_end < as_of)
        return SecurityView(
            security_id=sec.security_id,
            name=sec.name,
            exchange=sec.exchange,
            currency=sec.currency,
            ticker=ticker,
            as_of=as_of,
            listing_start=sec.listing_start,
            delisted=delisted_known,
            delisting_reason=sec.delisting_reason if delisted_known else None,
            is_synthetic=sec.is_synthetic,
        )
