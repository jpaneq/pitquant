"""Frozen BTC V0 algorithm and research contracts, canonical daily close at 00:00 UTC."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from pitquant.core.timeutils import require_aware

FEATURE_VERSION = "btc-core-v0"
DATA_VERSION = "btc-data-v0"
STRATEGY_VERSION = "btc-plan-v0"
ENGINE_VERSION = "btc-v0"
HORIZONS = (7, 30, 90, 180, 365)
QUANTILES = (0.1, 0.25, 0.5, 0.75, 0.9)
BTC_CAUSES = (
    "FUNDING_EXTREME",
    "OI_EXPANSION",
    "OI_FLUSH",
    "BASIS_COMPRESSION",
    "LIQUIDATION_EVENT",
    "VOLATILITY_EXPANSION",
    "NETWORK_CHANGE",
    "REGIME_CHANGE",
)


class Availability(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_ENOUGH_HISTORY = "NOT_ENOUGH_HISTORY"
    SOURCE_RETENTION_LIMIT = "SOURCE_RETENTION_LIMIT"


class Cohort(StrEnum):
    HISTORICAL_OOS = "HISTORICAL_OOS"
    FORWARD_PAPER = "FORWARD_PAPER"
    SYNTHETIC = "SYNTHETIC"


def decision_time(at: datetime) -> datetime:
    require_aware(at, "decision_at")
    at = at.astimezone(UTC)
    if at.hour or at.minute or at.second or at.microsecond:
        raise ValueError("BTC decisions must be at 00:00:00 UTC (the preceding 1D bar closes)")
    return at


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, allow_nan=False).encode()
    ).hexdigest()


@dataclass(frozen=True)
class ResearchConfig:
    train_days: int = 1095
    validation_days: int = 180
    embargo_days: int = 7
    decision_step_days: int = 1
    holdout_start: str = "2025-10-01"
    holdout_end: str = "2026-09-30"
    feature_version: str = FEATURE_VERSION
    model_version: str = "btc-core-baseline-v0"
    strategy_version: str = STRATEGY_VERSION
    commission_bps: float = 0.0
    slippage_bps: float = 0.0
    funding_cost: float = 0.0

    def __post_init__(self) -> None:
        if min(self.train_days, self.validation_days, self.decision_step_days) <= 0:
            raise ValueError("research windows must be positive")
        if min(self.embargo_days, self.commission_bps, self.slippage_bps, self.funding_cost) < 0:
            raise ValueError("embargo and costs must be nonnegative")
        start, end = (
            datetime.fromisoformat(self.holdout_start),
            datetime.fromisoformat(self.holdout_end),
        )
        if start > end:
            raise ValueError("holdout start must precede end")

    @property
    def config_hash(self) -> str:
        return digest(asdict(self))


def prediction_contract(horizon: int) -> dict[str, Any]:
    if horizon not in HORIZONS:
        raise ValueError("unsupported BTC horizon")
    return {
        "horizon": f"{horizon}D",
        "status": "NOT_YET_VALIDATED",
        "expected_return": None,
        "p_up": None,
        "q10": None,
        "q25": None,
        "q50": None,
        "q75": None,
        "q90": None,
        "uncertainty": None,
        "model_version": None,
        "regression_target": "future_log_return_H",
        "classification_target": "UP_H",
        "target_kind": "RAW_BTC_RETURN",
        "benchmark": "BTC_BUY_AND_HOLD",
    }


def target_time(at: datetime, horizon: int) -> datetime:
    if horizon not in HORIZONS:
        raise ValueError("unsupported BTC horizon")
    return decision_time(at) + timedelta(days=horizon)


@dataclass(frozen=True)
class BTCMacroSnapshot:
    status: str = "UNAVAILABLE"
    reason: str = "OPTIONAL_NOT_CONFIGURED"


class BitcoinCoreNetworkProvider:
    status = "NOT_CONFIGURED"
