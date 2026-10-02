"""Pure technical indicator math (no I/O). Conventions are fixed and versioned (FEATURE_VERSION)."""

from __future__ import annotations

import math

import pandas as pd

TRADING_DAYS = 252


def tr_return(gross: pd.Series, n: int) -> float | None:
    """Total return over the last ``n`` daily returns: product of gross factors - 1."""
    if len(gross) < n:
        return None
    return float(gross.iloc[-n:].prod() - 1.0)


def mom_12_1(level: pd.Series) -> float | None:
    """TR from ~T-252 to ~T-21 (skip the most recent month). ``level`` = TR index."""
    if len(level) < TRADING_DAYS + 1:
        return None
    return float(level.iloc[-22] / level.iloc[-(TRADING_DAYS + 1)] - 1.0)


def close_vs_sma(close: pd.Series, n: int) -> float | None:
    if len(close) < n:
        return None
    return float(close.iloc[-1] / close.iloc[-n:].mean() - 1.0)


def close_vs_ema(close: pd.Series, n: int) -> float | None:
    """EMA with alpha = 2/(n+1), seeded with the first value of the available history
    (``ewm(adjust=False)``). Requires at least ``n`` observations."""
    if len(close) < n:
        return None
    ema = close.ewm(span=n, adjust=False).mean()
    return float(close.iloc[-1] / ema.iloc[-1] - 1.0)


def annualized_vol(gross: pd.Series, n: int) -> float | None:
    """std (ddof=1) of daily LOG total returns over the last n sessions * sqrt(252)."""
    if len(gross) < n:
        return None
    r = gross.iloc[-n:].map(math.log)
    return float(r.std(ddof=1) * math.sqrt(TRADING_DAYS))


def max_drawdown(level: pd.Series, n: int = TRADING_DAYS) -> float | None:
    """Maximum drawdown (<= 0) of the TR index over the last n+1 points."""
    if len(level) < n + 1:
        return None
    w = level.iloc[-(n + 1) :]
    return float((w / w.cummax() - 1.0).min())


def _wilder(x: pd.Series, n: int) -> pd.Series:
    out = pd.Series(index=x.index, dtype=float)
    if len(x) < n:
        return out
    out.iloc[n - 1] = x.iloc[:n].mean()
    for i in range(n, len(x)):
        out.iloc[i] = (out.iloc[i - 1] * (n - 1) + x.iloc[i]) / n
    return out


def atr(adj: pd.DataFrame, n: int = 14) -> float | None:
    """Wilder ATR on split-adjusted OHLC (needs n+1 bars)."""
    if len(adj) < n + 1:
        return None
    pc = adj["close"].shift(1)
    tr = pd.concat(
        [adj["high"] - adj["low"], (adj["high"] - pc).abs(), (adj["low"] - pc).abs()], axis=1
    ).max(axis=1)
    a = _wilder(tr.iloc[1:], n)
    v = a.iloc[-1]
    return None if pd.isna(v) else float(v)


def rsi(close: pd.Series, n: int = 14) -> float | None:
    """Wilder RSI on split-adjusted closes (needs n+1 closes)."""
    if len(close) < n + 1:
        return None
    d = close.diff().iloc[1:]
    up, dn = d.clip(lower=0.0), (-d).clip(lower=0.0)
    au, ad = _wilder(up, n).iloc[-1], _wilder(dn, n).iloc[-1]
    if pd.isna(au) or pd.isna(ad):
        return None
    if ad == 0:
        return 100.0
    return float(100.0 - 100.0 / (1.0 + au / ad))


def volume_ratio(vol: pd.Series, n: int = 20) -> float | None:
    if len(vol) < n:
        return None
    m = vol.iloc[-n:].mean()
    return None if m == 0 else float(vol.iloc[-1] / m)


def volume_zscore(vol: pd.Series, n: int = 20) -> float | None:
    if len(vol) < n:
        return None
    w = vol.iloc[-n:]
    sd = w.std(ddof=1)
    return None if sd == 0 or pd.isna(sd) else float((w.iloc[-1] - w.mean()) / sd)


def beta(
    sec_gross: pd.Series, bench_gross: pd.Series, n: int = TRADING_DAYS, min_obs: int = 126
) -> float | None:
    """OLS beta of daily LOG returns on the benchmark's over the last ``n`` COMMON sessions."""
    j = pd.concat(
        [sec_gross.map(math.log), bench_gross.map(math.log)], axis=1, join="inner"
    ).dropna()
    j = j.iloc[-n:]
    if len(j) < min_obs:
        return None
    v = j.iloc[:, 1].var(ddof=1)
    return None if v == 0 or pd.isna(v) else float(j.iloc[:, 0].cov(j.iloc[:, 1]) / v)


def relative_return(sec_gross: pd.Series, bench_gross: pd.Series, n: int) -> float | None:
    """Security TR minus benchmark TR over the last n COMMON sessions."""
    j = pd.concat([sec_gross, bench_gross], axis=1, join="inner").dropna().iloc[-n:]
    if len(j) < n:
        return None
    return float(j.iloc[:, 0].prod() - j.iloc[:, 1].prod())
