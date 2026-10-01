"""Typed configuration loaded from YAML, with environment overrides for secrets/URLs.

The full resolved configuration is hashed (``config_hash``) and stored with every
prediction so that results are traceable to the exact settings that produced them.
"""

from __future__ import annotations

import os
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from pitquant.core.hashing import content_hash
from pitquant.core.types import ExecutionMode, Horizon, ValidationMode

DEFAULT_CONFIG_PATH = Path(__file__).with_name("default.yaml")


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DatabaseConfig(_Frozen):
    url: str
    parquet_root: str


class MarketConfig(_Frozen):
    timezone: str
    currency: str
    benchmark_tr: str


class UniverseConfig(_Frozen):
    code: str
    calendar: str
    expected_size: tuple[int, int]
    canonical_source: str


class ArchiveConfig(_Frozen):
    root: str


class SecConfig(_Frozen):
    user_agent: str
    max_requests_per_second: float = Field(gt=0, le=10)
    coverage_start: date
    availability_policy: Literal["conservative_session", "accepted_plus_lag"]
    lag_minutes: int = Field(ge=0)
    forms: list[str]


class FundamentalsConfig(_Frozen):
    sec: SecConfig


class PITConfig(_Frozen):
    default_publication_lag_minutes: int = Field(ge=0)
    label_data_lag_minutes: int = Field(ge=0)


class ExecutionConfig(_Frozen):
    mode: ExecutionMode
    delay_sessions: int = Field(ge=0)


class BacktestConfig(_Frozen):
    rebalance_frequency: Literal["monthly", "weekly", "quarterly"]
    snapshot_rule: Literal["first_session"]
    overlapping: bool


class HoldoutConfig(_Frozen):
    start: date
    end: date

    @model_validator(mode="after")
    def _ordered(self) -> HoldoutConfig:
        if self.end <= self.start:
            raise ValueError("final_holdout.end must be after start")
        return self


class ValidationConfig(_Frozen):
    mode: ValidationMode
    train_min_months: int = Field(gt=0)
    validation_months: int = Field(ge=0)
    test_months: int = Field(gt=0)
    step_months: int = Field(gt=0)
    embargo_months: int | None = Field(default=None, ge=0)
    final_holdout: HoldoutConfig


class BlockWeights(_Frozen):
    fundamental: float = Field(ge=0)
    technical: float = Field(ge=0)
    market_regime: float = Field(ge=0)

    @model_validator(mode="after")
    def _sum_to_one(self) -> BlockWeights:
        total = self.fundamental + self.technical + self.market_regime
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"block weights must sum to 1, got {total}")
        return self


class Thresholds(_Frozen):
    p_buy: float = Field(gt=0, lt=1)
    p_sell: float = Field(gt=0, lt=1)
    min_confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _ordered(self) -> Thresholds:
        if self.p_sell >= self.p_buy:
            raise ValueError("p_sell must be strictly below p_buy (HOLD band required)")
        return self


class ScoringConfig(_Frozen):
    version: str
    weights: dict[Horizon, BlockWeights]
    thresholds: Thresholds
    winsorize: tuple[float, float]


class DataReadinessConfig(_Frozen):
    # Filled ONLY by the D-05 ADR once a provider passes the contract suite
    # (tests/contracts/). Until then market data / corporate actions can never be READY.
    accepted_market_data_sources: dict[str, list[str]] = Field(default_factory=dict)
    accepted_corporate_action_sources: list[str] = Field(default_factory=list)
    min_universe_coverage: float = Field(default=0.95, gt=0, le=1)


class ReportingConfig(_Frozen):
    base_currency: str
    excess_return_currency: Literal["local", "base"]


class Settings(_Frozen):
    version: str
    database: DatabaseConfig
    markets: dict[str, MarketConfig]
    universes: list[UniverseConfig]
    archive: ArchiveConfig
    fundamentals: FundamentalsConfig
    pit: PITConfig
    horizons: list[Horizon]
    execution: ExecutionConfig
    backtest: BacktestConfig
    validation: ValidationConfig
    scoring: ScoringConfig
    reporting: ReportingConfig
    data_readiness: DataReadinessConfig = Field(default_factory=DataReadinessConfig)
    seed: int

    @model_validator(mode="after")
    def _universes_have_calendars(self) -> Settings:
        for u in self.universes:
            if u.calendar not in self.markets:
                raise ValueError(f"universe {u.code} references unknown market {u.calendar}")
        return self

    def universe(self, code: str) -> UniverseConfig:
        for u in self.universes:
            if u.code == code:
                return u
        raise KeyError(code)

    @property
    def config_hash(self) -> str:
        return content_hash(self.model_dump(mode="json"))


def load_settings(path: Path | str | None = None) -> Settings:
    raw = yaml.safe_load(Path(path or DEFAULT_CONFIG_PATH).read_text(encoding="utf-8"))
    db_url = os.environ.get("PITQUANT_DATABASE_URL")
    if db_url:
        raw["database"]["url"] = db_url
    ua = os.environ.get("PITQUANT_SEC_USER_AGENT")
    if ua:
        raw["fundamentals"]["sec"]["user_agent"] = ua
    return Settings.model_validate(raw)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings(os.environ.get("PITQUANT_CONFIG"))
