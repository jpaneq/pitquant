"""Provider-neutral market data (ADR-0021).

Every external provider is normalized into these records BEFORE anything else sees it:

    Provider → raw archive → parser → normalized record → PIT validation → storage

The backtester and the total-return engine only ever read normalized records. Rules:

* RAW OHLCV is the base series. A vendor's adjusted close is kept ONLY for QA
  (``MarketBar.vendor_adj_close``); adjusted series are rebuilt from corporate actions.
* Every corporate action carries the dates the source states (announcement, ex, record,
  payment/effective) — missing dates stay ``None``, never inferred — plus ``available_at``,
  ``source``, ``source_hash`` and the provider's raw identifier.
* Complex Spanish events (rights issues, scrip dividends, OPAs, mergers, exchanges) must come
  from the OFFICIAL tier (BME/CNMV): a vendor record of those kinds for an ES security is
  QA-only (``requires_official_source``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pitquant.core.errors import DataQualityError
from pitquant.core.timeutils import require_aware


class CorporateActionKind(StrEnum):
    CASH_DIVIDEND = "CASH_DIVIDEND"
    SPECIAL_DIVIDEND = "SPECIAL_DIVIDEND"
    STOCK_DIVIDEND = "STOCK_DIVIDEND"
    SPLIT = "SPLIT"
    REVERSE_SPLIT = "REVERSE_SPLIT"
    RIGHTS_ISSUE = "RIGHTS_ISSUE"
    SCRIP_DIVIDEND = "SCRIP_DIVIDEND"
    SPINOFF = "SPINOFF"
    CASH_ACQUISITION = "CASH_ACQUISITION"
    STOCK_ACQUISITION = "STOCK_ACQUISITION"
    MERGER = "MERGER"
    DELISTING = "DELISTING"
    BANKRUPTCY = "BANKRUPTCY"
    TICKER_CHANGE = "TICKER_CHANGE"
    EXCHANGE_CHANGE = "EXCHANGE_CHANGE"
    LISTING = "LISTING"
    RETURN_OF_CAPITAL = "RETURN_OF_CAPITAL"
    ISIN_CHANGE = "ISIN_CHANGE"


class SourceTier(StrEnum):
    OFFICIAL = "OFFICIAL"  # issuer / exchange / regulator document (SEC, CNMV, BME)
    VENDOR = "VENDOR"  # Sharadar, EODHD, ...
    FIXTURE = "FIXTURE"  # tests only


# Spanish events whose economics need the official prospectus/notice (ADR-0021).
COMPLEX_ES_KINDS = frozenset(
    {
        CorporateActionKind.RIGHTS_ISSUE,
        CorporateActionKind.SCRIP_DIVIDEND,
        CorporateActionKind.CASH_ACQUISITION,
        CorporateActionKind.STOCK_ACQUISITION,
        CorporateActionKind.MERGER,
        CorporateActionKind.SPINOFF,
    }
)

# Minimum fields per kind (beyond the always-required provenance).
_REQUIRED: dict[CorporateActionKind, tuple[str, ...]] = {
    CorporateActionKind.CASH_DIVIDEND: ("ex_date", "cash_amount", "currency"),
    CorporateActionKind.SPECIAL_DIVIDEND: ("ex_date", "cash_amount", "currency"),
    CorporateActionKind.RETURN_OF_CAPITAL: ("ex_date", "cash_amount", "currency"),
    CorporateActionKind.STOCK_DIVIDEND: ("ex_date", "ratio"),
    CorporateActionKind.SPLIT: ("ex_date", "ratio"),
    CorporateActionKind.REVERSE_SPLIT: ("ex_date", "ratio"),
    CorporateActionKind.RIGHTS_ISSUE: ("ex_date",),
    CorporateActionKind.SCRIP_DIVIDEND: ("ex_date",),
    CorporateActionKind.SPINOFF: ("ex_date",),
    CorporateActionKind.CASH_ACQUISITION: ("effective_date", "cash_amount", "currency"),
    CorporateActionKind.STOCK_ACQUISITION: ("effective_date", "ratio"),
    CorporateActionKind.MERGER: ("effective_date",),
    CorporateActionKind.DELISTING: ("effective_date",),
    CorporateActionKind.BANKRUPTCY: ("effective_date",),
    CorporateActionKind.TICKER_CHANGE: ("effective_date",),
    CorporateActionKind.EXCHANGE_CHANGE: ("effective_date",),
    CorporateActionKind.LISTING: ("effective_date",),
    CorporateActionKind.ISIN_CHANGE: ("effective_date",),
}


@dataclass(frozen=True)
class Provenance:
    provider: str
    tier: SourceTier
    provider_raw_id: str  # the provider's own identifier of the record
    source_hash: str  # SHA-256 of the archived raw payload it was parsed from
    parser_version: str
    archive_id: str | None = None


@dataclass(frozen=True)
class MarketBar:
    """One RAW daily bar. ``available_at`` = the session close (or later if the provider's
    publication is later). ``vendor_adj_close`` is QA-only, never an input."""

    security_key: str
    session_date: date
    open: float | None
    high: float | None
    low: float | None
    close: float
    volume: float | None
    currency: str
    available_at: datetime
    provenance: Provenance
    vendor_adj_close: float | None = None
    vendor_last_updated: date | None = None
    # fields the vendor only publishes adjusted and that were de-adjusted (not observed raw)
    imputed_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_aware(self.available_at, "available_at")
        if not self.close > 0:
            raise DataQualityError(f"{self.security_key} {self.session_date}: close <= 0")
        if self.high is not None and self.low is not None and self.high < self.low:
            raise DataQualityError(f"{self.security_key} {self.session_date}: high < low")
        for name in ("open", "high", "low"):
            v = getattr(self, name)
            if v is not None and v <= 0:
                raise DataQualityError(f"{self.security_key} {self.session_date}: {name} <= 0")


@dataclass(frozen=True)
class CorporateAction:
    security_key: str
    kind: CorporateActionKind
    available_at: datetime
    provenance: Provenance
    announcement_date: date | None = None
    ex_date: date | None = None
    record_date: date | None = None
    payment_date: date | None = None
    effective_date: date | None = None
    ratio: float | None = None  # new shares per old share (2-for-1 -> 2.0; 1-for-10 -> 0.1)
    cash_amount: float | None = None  # per share, in ``currency``
    currency: str | None = None
    target_key: str | None = None  # acquirer / spun-off company / new security
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_aware(self.available_at, "available_at")
        missing = [f for f in _REQUIRED.get(self.kind, ()) if getattr(self, f) is None]
        if missing:
            raise DataQualityError(f"{self.kind} {self.security_key}: missing {missing}")
        if self.ratio is not None and self.ratio <= 0:
            raise DataQualityError(f"{self.kind} {self.security_key}: ratio must be > 0")
        if self.kind is CorporateActionKind.SPLIT and self.ratio is not None and self.ratio <= 1:
            raise DataQualityError(f"SPLIT {self.security_key}: ratio {self.ratio} <= 1")
        if (
            self.kind is CorporateActionKind.REVERSE_SPLIT
            and self.ratio is not None
            and self.ratio >= 1
        ):
            raise DataQualityError(f"REVERSE_SPLIT {self.security_key}: ratio {self.ratio} >= 1")
        if self.cash_amount is not None and self.cash_amount < 0:
            raise DataQualityError(f"{self.kind} {self.security_key}: negative cash amount")

    @property
    def anchor_date(self) -> date | None:
        """The date the action changes the price series (ex-date, else effective date)."""
        return self.ex_date or self.effective_date

    def requires_official_source(self, market: str) -> bool:
        return (
            market == "ES"
            and self.kind in COMPLEX_ES_KINDS
            and self.provenance.tier is not SourceTier.OFFICIAL
        )


@dataclass(frozen=True)
class ListingEvent:
    security_key: str
    listed_on: date
    exchange: str | None
    available_at: datetime
    provenance: Provenance


@dataclass(frozen=True)
class TickerEvent:
    security_key: str
    old_ticker: str
    new_ticker: str
    effective_date: date
    available_at: datetime
    provenance: Provenance


@dataclass(frozen=True)
class DelistingEvent:
    security_key: str
    last_trading_date: date
    reason: str  # ACQUIRED | MERGED | BANKRUPTCY | REGULATORY | VOLUNTARY | OTHER
    available_at: datetime
    provenance: Provenance
    acquirer_key: str | None = None


@dataclass(frozen=True)
class SecurityListing:
    """A provider's security master row (identity evidence, never identity by itself)."""

    security_key: str  # provider permanent key (e.g. Sharadar permaticker)
    ticker: str
    name: str
    exchange: str | None
    is_delisted: bool
    first_price_date: date | None
    last_price_date: date | None
    currency: str | None
    identifiers: dict[str, str]  # e.g. {"CUSIP": "...", "ISIN": "..."}
    provenance: Provenance
    category: str | None = None


@dataclass
class NormalizedBatch:
    bars: list[MarketBar] = field(default_factory=list)
    actions: list[CorporateAction] = field(default_factory=list)
    listings: list[ListingEvent] = field(default_factory=list)
    tickers: list[TickerEvent] = field(default_factory=list)
    delistings: list[DelistingEvent] = field(default_factory=list)
    securities: list[SecurityListing] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
