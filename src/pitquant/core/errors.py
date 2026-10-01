"""Exception hierarchy. Every integrity violation fails loudly with a specific type."""

from __future__ import annotations


class PITQuantError(Exception):
    """Base class for all platform errors."""


class LookAheadError(PITQuantError):
    """Information with ``available_at > as_of`` reached a point-in-time computation."""


class NaiveDatetimeError(PITQuantError, ValueError):
    """A timezone-naive datetime was supplied where an aware one is mandatory."""


class UnknownSecurityError(PITQuantError, LookupError):
    """No security matches the identifier at the requested date."""


class AmbiguousIdentifierError(PITQuantError, LookupError):
    """More than one security matches the identifier at the requested date."""


class OverlappingIntervalError(PITQuantError, ValueError):
    """Two validity intervals that must be disjoint overlap."""


class ImmutableRecordError(PITQuantError):
    """An attempt was made to modify or delete an append-only record."""


class HoldoutAccessError(PITQuantError):
    """The final holdout period was touched without an authorised, logged unlock."""


class LabelLeakageError(PITQuantError):
    """A training observation's label was not yet known at the training cutoff."""


class CalendarRangeError(PITQuantError, ValueError):
    """A date lies outside the range covered by the market calendar."""


class DataQualityError(PITQuantError):
    """A blocking data-quality issue prevents a computation."""


class ProviderContractError(PITQuantError):
    """A data provider does not satisfy the contract required by a consumer."""
