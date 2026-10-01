"""Domain enums and small value types shared across modules."""

from __future__ import annotations

from enum import StrEnum


class Signal(StrEnum):
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"  # = avoid / underweight vs benchmark. NOT a short position.


class Horizon(StrEnum):
    M6 = "6m"
    M12 = "12m"

    @property
    def months(self) -> int:
        return {"6m": 6, "12m": 12}[self.value]


class ExecutionMode(StrEnum):
    NEXT_OPEN = "next_open"
    NEXT_CLOSE = "next_close"
    NEXT_VWAP = "next_vwap"


class ValidationMode(StrEnum):
    EXPANDING = "expanding_walk_forward"
    ROLLING = "rolling_walk_forward"


class CorporateActionType(StrEnum):
    """Non-dividend corporate actions. Cash distributions live in the ``dividends`` table."""

    SPLIT = "split"  # ratio = new shares per old share (2-for-1 -> 2.0; reverse 1-for-10 -> 0.1)
    SPIN_OFF = "spin_off"
    RIGHTS_ISSUE = "rights_issue"
    MERGER = "merger"
    TENDER_OFFER = "tender_offer"
    DELISTING = "delisting"
    TICKER_CHANGE = "ticker_change"


class DividendType(StrEnum):
    REGULAR = "regular"
    SPECIAL = "special"
    RETURN_OF_CAPITAL = "return_of_capital"
    SCRIP = "scrip"  # e.g. Spanish "dividendo flexible"


class DelistingReason(StrEnum):
    ACQUIRED = "acquired"
    MERGED = "merged"
    BANKRUPTCY = "bankruptcy"
    REGULATORY = "regulatory"
    VOLUNTARY = "voluntary"
    OTHER = "other"


class DQSeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKING = "blocking"


SYNTHETIC_SOURCE = "SYNTHETIC"
