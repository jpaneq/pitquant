"""Abstract data-provider interfaces (§85, ADR-0012).

Index membership providers live in ``pitquant.universe.events`` (event streams, ADR-0013).

Core logic depends only on these contracts, never on a concrete vendor. Every record a
provider returns carries provenance and its own availability timestamp.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class ProviderInfo:
    name: str
    is_synthetic: bool
    is_point_in_time: bool  # publishes true availability timestamps / historical vintages
    capabilities: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class Provenance:
    provider: str
    original_identifier: str
    retrieved_at: datetime
    raw: dict[str, Any]


@dataclass(frozen=True)
class SecurityRecord:
    provider_security_key: str
    name: str
    exchange: str
    currency: str
    country: str | None
    listing_start: date | None
    listing_end: date | None
    delisting_reason: str | None
    tickers: Sequence[tuple[str, date, date | None]]  # (ticker, valid_from, valid_to)
    identifiers: Sequence[tuple[str, str, date, date | None]]  # (type, value, from, to)
    acquirer_key: str | None = None
    provenance: Provenance | None = None


@dataclass(frozen=True)
class PriceBar:
    provider_security_key: str
    session_date: date
    open: float | None
    high: float | None
    low: float | None
    close: float
    volume: float | None
    currency: str
    provenance: Provenance | None = None


@dataclass(frozen=True)
class CorporateActionRecord:
    provider_security_key: str
    action_type: str
    announced_at: datetime
    ex_date: date
    ratio: float | None = None
    cash_amount: float | None = None
    currency: str | None = None
    target_key: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    provenance: Provenance | None = None


@dataclass(frozen=True)
class DividendRecord:
    provider_security_key: str
    announced_at: datetime
    ex_date: date
    pay_date: date | None
    gross_amount: float
    currency: str
    dividend_type: str = "regular"
    provenance: Provenance | None = None


@dataclass(frozen=True)
class FactRecord:
    provider_security_key: str
    concept: str
    fiscal_period: str
    period_start: date | None
    period_end: date
    value: float | None
    unit: str
    currency: str | None
    published_at: datetime | date  # date-only => next open after the end of that date
    revision_id: int = 0
    filing_ref: str | None = None
    provenance: Provenance | None = None


@dataclass(frozen=True)
class MacroRecord:
    series_code: str
    observation_date: date
    value: float | None
    available_at: datetime  # vintage timestamp
    provenance: Provenance | None = None


@dataclass(frozen=True)
class EstimateRecord:
    provider_security_key: str
    metric: str
    target_period_end: date
    statistic: str
    value: float | None
    available_at: datetime
    provenance: Provenance | None = None


class _Provider(ABC):
    @property
    @abstractmethod
    def info(self) -> ProviderInfo: ...


class SecurityProvider(_Provider):
    @abstractmethod
    def securities(self) -> Sequence[SecurityRecord]: ...


class PriceProvider(_Provider):
    @abstractmethod
    def bars(self, keys: Sequence[str], start: date, end: date) -> Sequence[PriceBar]: ...


class CorporateActionsProvider(_Provider):
    @abstractmethod
    def actions(
        self, keys: Sequence[str], start: date, end: date
    ) -> Sequence[CorporateActionRecord]: ...

    @abstractmethod
    def dividends(
        self, keys: Sequence[str], start: date, end: date
    ) -> Sequence[DividendRecord]: ...


class FundamentalProvider(_Provider):
    @abstractmethod
    def facts(self, keys: Sequence[str], start: date, end: date) -> Sequence[FactRecord]: ...


class MacroProvider(_Provider):
    @abstractmethod
    def vintages(self, series_code: str, start: date, end: date) -> Sequence[MacroRecord]: ...


class AnalystEstimatesProvider(_Provider):
    @abstractmethod
    def estimates(
        self, keys: Sequence[str], start: date, end: date
    ) -> Sequence[EstimateRecord]: ...
