"""Leak-free preprocessing (§63–67).

* Cross-sectional transforms (winsorize, percentile rank, sector z-score) use ONLY the rows
  of the same ``as_of`` date — no statistics from other dates, past or future.
* Learned transforms (scaler, imputer) are fitted on the training partition only and then
  applied unchanged to validation/test. They record a fingerprint of the fit rows so tests
  and audits can prove nothing else was used.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from pitquant.core.hashing import content_hash


def winsorize_cross_section(
    df: pd.DataFrame,
    cols: list[str],
    date_col: str = "as_of",
    lower: float = 0.01,
    upper: float = 0.99,
) -> pd.DataFrame:
    out = df.copy()
    g = out.groupby(date_col)[cols]
    lo = g.transform(lambda s: s.quantile(lower))
    hi = g.transform(lambda s: s.quantile(upper))
    out[cols] = out[cols].clip(lower=lo, upper=hi, axis=1)
    return out


def percentile_rank_cross_section(
    df: pd.DataFrame, cols: list[str], date_col: str = "as_of", group_col: str | None = None
) -> pd.DataFrame:
    """Percentile (0–1] within each date (and optionally each sector at that date)."""
    keys = [date_col] + ([group_col] if group_col else [])
    out = df.copy()
    out[[f"{c}_pct" for c in cols]] = out.groupby(keys)[cols].rank(pct=True).to_numpy()
    return out


def zscore_cross_section(
    df: pd.DataFrame, cols: list[str], date_col: str = "as_of", group_col: str | None = None
) -> pd.DataFrame:
    keys = [date_col] + ([group_col] if group_col else [])
    out = df.copy()
    g = out.groupby(keys)[cols]
    mu, sd = g.transform("mean"), g.transform("std").replace(0, np.nan)
    out[[f"{c}_z" for c in cols]] = ((out[cols] - mu) / sd).to_numpy()
    return out


def _fingerprint(index: pd.Index) -> str:
    return content_hash(sorted(str(i) for i in index))


@dataclass
class TrainOnlyStandardScaler:
    mean_: pd.Series | None = field(default=None, init=False)
    std_: pd.Series | None = field(default=None, init=False)
    fit_fingerprint: str | None = field(default=None, init=False)

    def fit(self, train: pd.DataFrame) -> TrainOnlyStandardScaler:
        self.mean_ = train.mean()
        self.std_ = train.std(ddof=0).replace(0, 1.0)
        self.fit_fingerprint = _fingerprint(train.index)
        return self

    def transform(self, x: pd.DataFrame) -> pd.DataFrame:
        if self.mean_ is None or self.std_ is None:
            raise RuntimeError("scaler not fitted")
        return (x - self.mean_) / self.std_


@dataclass
class TrainOnlyMedianImputer:
    """Median imputation fitted on train; returns the data plus an ``imputed`` mask (§67)."""

    medians_: pd.Series | None = field(default=None, init=False)
    fit_fingerprint: str | None = field(default=None, init=False)

    def fit(self, train: pd.DataFrame) -> TrainOnlyMedianImputer:
        self.medians_ = train.median()
        self.fit_fingerprint = _fingerprint(train.index)
        return self

    def transform(self, x: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        if self.medians_ is None:
            raise RuntimeError("imputer not fitted")
        mask = x.isna()
        return x.fillna(self.medians_), mask
