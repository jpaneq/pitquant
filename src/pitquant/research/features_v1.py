# ruff: noqa: E501
"""Research feature set V1 (ADR-0048): CONTINUOUS, point-in-time technical, support and risk features. Raw values only: no imputation, no scaling, no thresholds.

* Built ONCE per security over its whole history from RAW bars + corporate actions (split-adjusted OHLCV for trend/volume/ATR, the total-return index for returns, volatility and drawdowns).
  Every rolling window is CAUSAL: the row of session ``t`` uses bars <= ``t`` only. ``tests`` prove the truncation property (the value at ``t`` from the full series equals the one from the series cut at ``t``)
  and cross-check against the frozen Feature Engine V0 where the definitions coincide.
* A decision at the OPEN of session D uses the row of the last bar before D (``available_at`` = that bar's close <= ``decision_at``).
* Missing is NULL with a reason (``NOT_ENOUGH_HISTORY``, ``PROVIDER_GAP`` for holes / withheld volume, ``UNAVAILABLE``): never 0. A window that spans a hole in the session calendar is missing.
* ``support_*``: the zone is detected with bars up to t-1 (``sr_v1``) and frozen; ``support_broken`` = close_t < frozen zone low; no zone = ``UNAVAILABLE`` (never "not broken").
* ``risk_alert_h{H}`` is the V0 BAJA call renamed (score <= -2 for horizon H) and is a RISK feature, not a sell signal; its components are stored separately. Nothing here changes the live rule.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

import numpy as np
import pandas as pd

from pitquant.analyzer import indicators as I
from pitquant.analyzer import sr_v1
from pitquant.core.errors import DataQualityError
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.features.v0.series import build_series
from pitquant.market.normalized import CorporateAction
from pitquant.positions import review as engine
from pitquant.positions import routine as rt

FEATURE_SET_VERSION = "research-features-v1"
TD = 252
T0 = datetime(
    2000, 1, 1, tzinfo=UTC
)  # fixed review instant: the alert is a pure function of the features

PRICE_FEATURES: tuple[tuple[str, int], ...] = (  # (name, sessions of history needed incl. the current bar)
    ("ret_1m", 22), ("ret_3m", 64), ("ret_6m", 127), ("ret_12m", 253), ("momentum_12_1", 253),
    ("distance_sma20", 20), ("distance_sma50", 50), ("distance_sma200", 200),
    ("sma20_slope", 40), ("sma50_slope", 70), ("sma200_slope", 220),
    ("ema20_distance", 20), ("ema50_distance", 50),
    ("sma20_vs_sma50", 50), ("sma50_vs_sma200", 200),
    ("distance_52w_high", 252), ("distance_26w_high", 126), ("drawdown_from_52w_high", 252), ("drawdown_from_26w_high", 126),
    ("realized_vol_20", 21), ("realized_vol_63", 64), ("realized_vol_126", 127),
    ("atr14_pct", 15), ("atr14_normalized", 266),
    ("return_skew_63", 64), ("return_kurtosis_63", 64), ("downside_vol_63", 64),
    ("volume_change_20", 40), ("volume_change_63", 126), ("volume_zscore_20", 20), ("volume_zscore_63", 63),
    ("rsi14", 15),
)  # fmt: skip
VOLUME_FEATURES = {"volume_change_20", "volume_change_63", "volume_zscore_20", "volume_zscore_63"}
SUPPORT_FEATURES = (
    "support_zone_low",
    "support_zone_high",
    "support_age_bars",
    "support_touches",
    "support_broken",
    "support_distance_pct",
    "support_distance_atr",
)
RISK_COMPONENTS = (
    "rc_below_sma200",
    "rc_momentum_negative",
    "rc_support_broken",
    "rc_elevated_volatility",
    "rc_drawdown_state",
)
RISK_ALERT = tuple(f"risk_alert_h{h}" for h in rt.HORIZONS)
ALL_NAMES = tuple(n for n, _ in PRICE_FEATURES) + SUPPORT_FEATURES + RISK_COMPONENTS + RISK_ALERT


@dataclass
class SeriesBundle:
    """Everything about one security's price history, computed once."""

    security_id: str
    ticker: str
    exchange: str
    adj: pd.DataFrame  # split-adjusted OHLCV, index = session date
    level: pd.Series  # total-return index (1.0 on the first bar); price index for an index symbol
    close_instants: np.ndarray  # UTC close instant of every bar (datetime64[ns]), sorted
    return_type: str = "TOTAL_RETURN"  # TOTAL_RETURN | PRICE_RETURN_FALLBACK | PRICE_INDEX
    warnings: list[str] = field(default_factory=list)
    gap_free: dict[int, pd.Series] = field(
        default_factory=dict
    )  # window -> bool per bar: the last ``w`` returns span consecutive sessions

    @property
    def index(self) -> pd.Index:
        return self.adj.index


def _drop_actions_without_bar(
    actions: list[CorporateAction], bar_days: set[date]
) -> tuple[list[CorporateAction], list[str]]:
    kept, dropped = [], []
    for a in actions:
        if (
            a.anchor_date is not None
            and a.anchor_date not in bar_days
            and a.anchor_date >= min(bar_days)
            and a.anchor_date <= max(bar_days)
        ):
            dropped.append(f"{a.kind.value} {a.anchor_date}")
        else:
            kept.append(a)
    return kept, dropped


def build_bundle(
    security_id: str,
    ticker: str,
    exchange: str,
    bars: pd.DataFrame,
    actions: list[CorporateAction],
    *,
    is_index: bool = False,
) -> SeriesBundle:
    """``bars``: RAW OHLCV indexed by session date. Never reads anything after the last bar."""
    cal = get_calendar(exchange)
    bars = bars.sort_index()
    last = bars.index[-1]
    far = datetime(2100, 1, 1, tzinfo=cal.session_close(last).tzinfo)
    warnings: list[str] = []
    rtype = "PRICE_INDEX" if is_index else "TOTAL_RETURN"
    try:
        ps = build_series(bars, [] if is_index else actions, far, date(2100, 1, 1), exchange)
    except DataQualityError:
        kept, dropped = _drop_actions_without_bar(actions, set(bars.index))
        warnings.append(f"actions on days without a bar were dropped: {dropped}")
        ps = build_series(bars, kept, far, date(2100, 1, 1), exchange)
    adj, level = ps.split_adjusted, ps.tr_level
    if is_index:  # a price index has no dividends: its "level" is the close
        level = bars["close"].astype(float) / float(bars["close"].iloc[0])
    instants = np.array(
        [cal.session_close(d).replace(tzinfo=None) for d in adj.index], dtype="datetime64[ns]"
    )
    # contiguity: window w is clean at bar i iff the calendar sessions between bar i-w and bar i number exactly w
    sessions = cal.sessions(adj.index[0], adj.index[-1])
    ordinal = pd.Series(range(len(sessions)), index=sessions)
    pos = ordinal.reindex(adj.index)
    gap = {w: ((pos - pos.shift(w)) == w) for w in (1, 21, 63, 126, 252)}
    return SeriesBundle(
        security_id, ticker, exchange, adj, level.reindex(adj.index), instants, rtype, warnings, gap
    )


def _skew_kurt(r: pd.Series, n: int) -> tuple[pd.Series, pd.Series]:
    roll = r.rolling(n, min_periods=n)
    return roll.skew(), roll.kurt()  # sample skewness, EXCESS kurtosis


def technical_panel(b: SeriesBundle) -> pd.DataFrame:
    """One row per bar with every price feature as known at that bar's close. NaN = missing (the reason is derived from the history length / the gap check)."""
    a, lvl = b.adj, b.level
    c, h, lo, v = (
        a["close"].astype(float),
        a["high"].astype(float),
        a["low"].astype(float),
        a["volume"].astype(float),
    )
    logret = np.log(lvl / lvl.shift(1))
    out = pd.DataFrame(index=a.index)
    for name, n in (("ret_1m", 21), ("ret_3m", 63), ("ret_6m", 126), ("ret_12m", 252)):
        out[name] = lvl / lvl.shift(n) - 1.0
    out["momentum_12_1"] = lvl.shift(21) / lvl.shift(252) - 1.0
    smas = {n: I.sma(c, n) for n in (20, 50, 200)}
    for n in (20, 50, 200):
        out[f"distance_sma{n}"] = c / smas[n] - 1.0
        out[f"sma{n}_slope"] = smas[n] / smas[n].shift(20) - 1.0
    for n in (20, 50):
        out[f"ema{n}_distance"] = c / I.ema(c, n) - 1.0
    out["sma20_vs_sma50"] = smas[20] / smas[50] - 1.0
    out["sma50_vs_sma200"] = smas[50] / smas[200] - 1.0
    out["distance_52w_high"] = c / c.rolling(252, min_periods=252).max() - 1.0
    out["distance_26w_high"] = c / c.rolling(126, min_periods=126).max() - 1.0
    out["drawdown_from_52w_high"] = lvl / lvl.rolling(252, min_periods=252).max() - 1.0
    out["drawdown_from_26w_high"] = lvl / lvl.rolling(126, min_periods=126).max() - 1.0
    for n in (20, 63, 126):
        out[f"realized_vol_{n}"] = logret.rolling(n, min_periods=n).std(ddof=1) * np.sqrt(TD)
    atr14 = I.atr(h, lo, c, 14)
    out["atr14_pct"] = atr14 / c
    out["atr14_normalized"] = atr14 / atr14.rolling(252, min_periods=252).mean()
    out["return_skew_63"], out["return_kurtosis_63"] = _skew_kurt(logret, 63)
    out["downside_vol_63"] = np.sqrt(
        (logret.clip(upper=0.0) ** 2).rolling(63, min_periods=63).mean()
    ) * np.sqrt(TD)
    for n in (20, 63):
        m = v.rolling(n, min_periods=n).mean()
        out[f"volume_change_{n}"] = m / m.shift(n) - 1.0
        out[f"volume_zscore_{n}"] = (v - m) / v.rolling(n, min_periods=n).std(ddof=1)
    out["rsi14"] = I.rsi(c, 14)
    out["_atr14"] = atr14
    out["_close"] = c
    out["_sma200_up"] = out["sma200_slope"] > 0
    out["_vol252"] = logret.rolling(252, min_periods=252).std(ddof=1) * np.sqrt(TD)
    # windows that span a hole in the session calendar are not valid: PROVIDER_GAP
    windows = {"ret_1m": 21, "ret_3m": 63, "ret_6m": 126, "ret_12m": 252, "momentum_12_1": 252, "realized_vol_20": 21, "realized_vol_63": 63, "realized_vol_126": 126, "drawdown_from_52w_high": 252,
               "drawdown_from_26w_high": 126, "return_skew_63": 63, "return_kurtosis_63": 63, "downside_vol_63": 63}  # fmt: skip
    for name, w in windows.items():
        out.loc[~b.gap_free[w].fillna(False).astype(bool), name] = np.nan
    return out


def missing_reason(
    name: str, row_pos: int, value: float | None, volume_withheld: bool
) -> str | None:
    if value is not None and not (isinstance(value, float) and np.isnan(value)):
        return None
    need = dict(PRICE_FEATURES)[name]
    if row_pos + 1 < need:
        return "NOT_ENOUGH_HISTORY"
    if name in VOLUME_FEATURES and volume_withheld:
        return "PROVIDER_GAP"
    return "PROVIDER_GAP"  # enough bars but the window has a hole or the input is absent


def frozen_support(panel: pd.DataFrame, adj: pd.DataFrame, pos: int) -> dict[str, Any] | None:
    """support_rule_v1 at bar ``pos``: zones from bars <= pos-1, ATR14 of pos-1, nearest zone below the close of pos-1."""
    if pos < 1:
        return None
    atr_prev = panel["_atr14"].iloc[pos - 1]
    if pd.isna(atr_prev):
        return None
    prev = adj.iloc[:pos]
    zones = sr_v1.compute_zones(prev, float(atr_prev), float(prev["close"].iloc[-1])).get(
        "supports", []
    )
    if not zones:
        return None
    z = max(zones, key=lambda x: float(str(x["upper"])))
    lt = pd.Timestamp(str(z["last_touch"])).date()
    age = pos - 1 - int(adj.index.get_loc(lt)) if lt in adj.index else None
    return {
        "low": float(str(z["lower"])),
        "high": float(str(z["upper"])),
        "touches": int(str(z["touches"])),
        "age_bars": age,
    }


def trend_state(panel: pd.DataFrame, pos: int) -> str | None:
    """Analyzer trend rules v0.1 (the same five facts and cut-offs as ``technical_v1``)."""
    r = panel.iloc[pos]
    parts = [
        r["distance_sma20"],
        r["distance_sma50"],
        r["distance_sma200"],
        r["sma50_vs_sma200"],
        r["sma200_slope"],
    ]
    got = [x for x in parts if not pd.isna(x)]
    if len(got) < 4:
        return None
    score = sum(1 if x > 0 else -1 for x in got)
    return (
        "STRONG_UPTREND"
        if score >= 4
        else "UPTREND"
        if score >= 2
        else "NEUTRAL"
        if score >= -1
        else "DOWNTREND"
        if score >= -3
        else "STRONG_DOWNTREND"
    )


def risk_features(
    panel: pd.DataFrame, pos: int, support: dict[str, Any] | None, price: float
) -> dict[str, float | None]:
    """RISK_ALERT per horizon (V0 BAJA renamed) + its components. Components are 0/1 or None (unavailable): never invented."""
    r = panel.iloc[pos]

    def flag(cond: bool | None) -> float | None:
        return None if cond is None else (1.0 if cond else 0.0)

    d200, ret6, dd52, v63, v252 = (
        r["distance_sma200"],
        r["ret_6m"],
        r["drawdown_from_52w_high"],
        r["realized_vol_63"],
        r["_vol252"],
    )
    broken = None if support is None else price < support["low"]
    out: dict[str, float | None] = {
        "rc_below_sma200": None if pd.isna(d200) else flag(d200 < 0),
        "rc_momentum_negative": None if pd.isna(ret6) else flag(ret6 < 0),
        "rc_support_broken": flag(broken),
        "rc_elevated_volatility": None
        if pd.isna(v63) or pd.isna(v252)
        else flag(v63 > 1.25 * v252),
        "rc_drawdown_state": None if pd.isna(dd52) else flag(dd52 <= -0.15),
    }
    ctx = engine.Context(
        price=price, atr14=None if pd.isna(r["_atr14"]) else float(r["_atr14"]), trend_state=trend_state(panel, pos), close_vs_sma200=None if pd.isna(d200) else float(d200), close_vs_sma50=None if pd.isna(r["distance_sma50"]) else float(r["distance_sma50"]),
        ret_6m=None if pd.isna(ret6) else float(ret6), rsi14=None if pd.isna(r["rsi14"]) else float(r["rsi14"]),
        support_lower=None if support is None else float(support["low"]), vol_annual=None if pd.isna(v63) else float(v63),
    )  # fmt: skip
    for h in rt.HORIZONS:
        rv = engine.review(engine.Position(price, 1.0, T0, h), ctx, T0)
        out[f"risk_alert_h{h}"] = (
            1.0
            if rv["recommendation"] == "SELL" and ctx.trend_state is not None
            else (None if ctx.trend_state is None and ctx.close_vs_sma200 is None else 0.0)
        )
    return out


def features_at(
    b: SeriesBundle, panel: pd.DataFrame, pos: int, *, with_support: bool = True
) -> dict[str, dict[str, Any]]:
    """Feature dict for the bar at ``pos``: name -> {value, available_at, source, missing_reason}. ``available_at`` = the bar's close."""
    avail = pd.Timestamp(b.close_instants[pos]).tz_localize("UTC").isoformat()
    row = panel.iloc[pos]
    withheld = bool(
        b.adj["volume"].iloc[max(0, pos - 63) : pos + 1].isna().any()
        or (b.adj["volume"].iloc[max(0, pos - 63) : pos + 1] == 0).all()
    )
    feats: dict[str, dict[str, Any]] = {}
    src = f"BARS+{b.return_type}"

    def put(name: str, value: Any, reason: str | None) -> None:
        v = (
            None
            if value is None or (isinstance(value, float) and np.isnan(value))
            else float(value)
        )
        feats[name] = {
            "value": v,
            "available_at": avail,
            "source": src,
            "missing_reason": None if v is not None else (reason or "UNAVAILABLE"),
        }

    for name, _ in PRICE_FEATURES:
        v = row[name]
        put(name, v, missing_reason(name, pos, None if pd.isna(v) else float(v), withheld))
    price = float(row["_close"])
    sup = frozen_support(panel, b.adj, pos) if with_support else None
    atr = row["_atr14"]
    if sup is None:
        reason = (
            "NOT_ENOUGH_HISTORY" if pos < 2 * sr_v1.WINDOW + 3 or pd.isna(atr) else "UNAVAILABLE"
        )
        for n in SUPPORT_FEATURES:
            put(n, None, reason)
    else:
        put("support_zone_low", sup["low"], None)
        put("support_zone_high", sup["high"], None)
        put(
            "support_age_bars",
            sup["age_bars"],
            None if sup["age_bars"] is not None else "UNAVAILABLE",
        )
        put("support_touches", sup["touches"], None)
        put("support_broken", 1.0 if price < sup["low"] else 0.0, None)
        put("support_distance_pct", price / sup["low"] - 1.0, None)
        put(
            "support_distance_atr",
            (price - sup["low"]) / float(atr) if not pd.isna(atr) and atr > 0 else None,
            "UNAVAILABLE",
        )
    for n, v in risk_features(panel, pos, sup, price).items():
        put(n, v, "UNAVAILABLE")
    return feats
