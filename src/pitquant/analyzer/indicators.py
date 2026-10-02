# ruff: noqa: E501
"""Series-level technical indicators (pure pandas). Conventions are fixed per ``TECHNICAL_ENGINE_VERSION``.

Everything here works on SPLIT-ADJUSTED OHLCV (never dividend-adjusted) except the total-return based
measures, which receive the internal TR index. EMA uses ``ewm(adjust=False)`` seeded with the first value;
RSI/ATR/ADX use Wilder smoothing seeded with the simple mean of the first ``n`` values.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(x: pd.Series, n: int) -> pd.Series:
    return x.rolling(n, min_periods=n).mean()


def ema(x: pd.Series, n: int) -> pd.Series:
    out = x.ewm(span=n, adjust=False).mean()
    out.iloc[: n - 1] = np.nan  # not enough history to call it an n-day EMA
    return out


def wilder(x: pd.Series, n: int) -> pd.Series:
    """Wilder smoothing; the first value (at position n-1 of the first valid run) is the mean of n values."""
    v = x.to_numpy(dtype=float)
    out = np.full(len(v), np.nan)
    valid = np.flatnonzero(~np.isnan(v))
    if len(valid) < n:
        return pd.Series(out, index=x.index)
    start = valid[0] + n - 1
    out[start] = v[valid[0] : valid[0] + n].mean()
    for i in range(start + 1, len(v)):
        out[i] = (out[i - 1] * (n - 1) + v[i]) / n
    return pd.Series(out, index=x.index)


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up, dn = d.clip(lower=0.0), (-d).clip(lower=0.0)
    au, ad = (
        wilder(up.iloc[1:], n).reindex(close.index),
        wilder(dn.iloc[1:], n).reindex(close.index),
    )
    rs = au / ad
    out = 100.0 - 100.0 / (1.0 + rs)
    out[(ad == 0) & au.notna()] = 100.0
    return out


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False, ignore_na=True).mean()
    sig[line.isna()] = np.nan
    first = line.first_valid_index()
    if first is not None:  # the signal EMA needs ``signal`` MACD values before it is meaningful
        pos = line.index.get_loc(first)
        sig.iloc[: pos + signal - 1] = np.nan
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def true_range(h: pd.Series, lo: pd.Series, c: pd.Series) -> pd.Series:
    pc = c.shift(1)
    return pd.concat([h - lo, (h - pc).abs(), (lo - pc).abs()], axis=1).max(axis=1)


def atr(h: pd.Series, lo: pd.Series, c: pd.Series, n: int = 14) -> pd.Series:
    tr = true_range(h, lo, c)
    tr.iloc[0] = np.nan  # no previous close on the first bar
    return wilder(tr, n)


def adx(h: pd.Series, lo: pd.Series, c: pd.Series, n: int = 14) -> pd.DataFrame:
    """Wilder ADX with +DI / -DI. Direction is NOT implied by ADX: it only measures trend strength."""
    up, dn = h.diff(), -lo.diff()
    plus_dm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=h.index)
    minus_dm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=h.index)
    tr = true_range(h, lo, c)
    for s in (plus_dm, minus_dm, tr):
        s.iloc[0] = np.nan
    atr_n = wilder(tr, n)
    pdi = 100.0 * wilder(plus_dm, n) / atr_n
    mdi = 100.0 * wilder(minus_dm, n) / atr_n
    dx = 100.0 * (pdi - mdi).abs() / (pdi + mdi)
    return pd.DataFrame({"adx": wilder(dx, n), "plus_di": pdi, "minus_di": mdi})


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    mid = sma(close, n)
    sd = close.rolling(n, min_periods=n).std(ddof=0)  # population std, the charting convention
    return pd.DataFrame({"upper": mid + k * sd, "mid": mid, "lower": mid - k * sd})


def downside_vol(returns: pd.Series, n: int = 63) -> float | None:
    """sqrt(mean(min(r, 0)^2)) * sqrt(252) over the last n daily returns (target 0)."""
    if len(returns) < n:
        return None
    r = returns.iloc[-n:]
    return float(np.sqrt((np.minimum(r, 0.0) ** 2).mean()) * np.sqrt(252))
