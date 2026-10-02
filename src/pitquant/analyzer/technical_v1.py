# ruff: noqa: E501
"""TechnicalEngine V1: one implementation for the Analyzer and for research (``decision_at`` mandatory)."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

import pandas as pd

from pitquant.analyzer import indicators as I
from pitquant.analyzer.market import MarketData
from pitquant.analyzer.sr_v1 import SR_VERSION, compute_zones
from pitquant.features.v0 import technical as T

TECHNICAL_ENGINE_VERSION = "technical-v1.0"
TREND_THRESHOLDS_VERSION = "trend-rules-v0.1"


def _f(x: Any) -> float | None:
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) or math.isinf(v) else v


def _last(s: pd.Series) -> float | None:
    return _f(s.iloc[-1]) if len(s) else None


def _slope(ma: pd.Series, n: int) -> float | None:
    """MA(t) / MA(t-n) - 1 (normalised change of the average over n sessions)."""
    s = ma.dropna()
    if len(s) <= n:
        return None
    return _f(s.iloc[-1] / s.iloc[-1 - n] - 1.0)


def classify_trend(m: dict[str, float | None]) -> dict[str, Any]:
    """Deterministic, explainable trend state (NOT a return forecast). Five evidence items, +1/-1 each."""
    items = [
        ("close_above_sma20", m["close"], m["sma20"], "close > SMA20"),
        ("close_above_sma50", m["close"], m["sma50"], "close > SMA50"),
        ("close_above_sma200", m["close"], m["sma200"], "close > SMA200"),
        ("sma50_above_sma200", m["sma50"], m["sma200"], "SMA50 > SMA200"),
    ]
    ev: list[dict[str, Any]] = []
    score, k = 0, 0
    for code, a, b, txt in items:
        if a is None or b is None:
            ev.append({"code": code, "text": txt, "available": False})
            continue
        k += 1
        pos = a > b
        score += 1 if pos else -1
        ev.append(
            {
                "code": code,
                "text": txt if pos else txt.replace(">", "<="),
                "positive": bool(pos),
                "available": True,
                "metric": round(a / b - 1.0, 5),
            }
        )
    sl = m.get("sma200_slope_20")
    if sl is None:
        ev.append({"code": "sma200_rising", "text": "SMA200 rising", "available": False})
    else:
        k += 1
        pos = sl > 0
        score += 1 if pos else -1
        ev.append(
            {
                "code": "sma200_rising",
                "text": "SMA200 rising" if pos else "SMA200 not rising",
                "positive": bool(pos),
                "available": True,
                "metric": round(sl, 5),
            }
        )
    if k < 4:
        state = "INSUFFICIENT_HISTORY"
    elif score >= 4:
        state = "STRONG_UPTREND"
    elif score >= 2:
        state = "UPTREND"
    elif score >= -1:
        state = "NEUTRAL"
    elif score >= -3:
        state = "DOWNTREND"
    else:
        state = "STRONG_DOWNTREND"
    return {
        "state": state,
        "score": score,
        "items_available": k,
        "evidence": ev,
        "rules_version": TREND_THRESHOLDS_VERSION,
    }


# (lookback, minimum observations, input series): split-adjusted OHLCV, never dividend-adjusted
_META: dict[str, tuple[int, int, str]] = {
    "sma20": (20, 20, "close"),
    "sma50": (50, 50, "close"),
    "sma200": (200, 200, "close"),
    "ema20": (20, 20, "close"),
    "ema50": (50, 50, "close"),
    "rsi14": (14, 15, "close"),
    "macd": (26, 35, "close"),
    "macd_signal": (26, 35, "close"),
    "macd_hist": (26, 35, "close"),
    "atr14": (14, 15, "high, low, close"),
    "adx14": (14, 28, "high, low, close"),
    "bollinger_mid": (20, 20, "close"),
    "bollinger_upper": (20, 20, "close"),
    "bollinger_lower": (20, 20, "close"),
}


def indicator_meta(n_bars: int, last_session: str) -> dict[str, dict[str, Any]]:
    """Per-indicator audit metadata: how much history it needs and whether it had enough."""
    return {
        k: {
            "lookback": lb,
            "required_observations": need,
            "available_observations": n_bars,
            "sufficient": n_bars >= need,
            "input_series": inp,
            "adjustment": "SPLIT_ADJUSTED_ONLY (no dividend adjustment)",
            "last_timestamp": last_session,
        }
        for k, (lb, need, inp) in _META.items()
    }


def compute_technicals(
    md: MarketData, bench: MarketData | None = None, bench_ticker: str | None = None
) -> dict[str, Any]:
    ps = md.series
    out: dict[str, Any] = {
        "as_of": md.decision_at.isoformat(),
        "engine_version": TECHNICAL_ENGINE_VERSION,
        "support_resistance_version": SR_VERSION,
        "warnings": [],
    }
    if ps.n_bars == 0:
        out.update(status="NO_DATA", warnings=["no completed price bars known at decision_at"])
        return out
    adj = ps.split_adjusted
    c, h, lo, v = adj["close"], adj["high"], adj["low"], adj["volume"]
    out["last_session"] = str(ps.last_session)
    out["n_bars"] = ps.n_bars
    close = _last(c)
    sma20, sma50, sma200 = I.sma(c, 20), I.sma(c, 50), I.sma(c, 200)
    ema20, ema50 = I.ema(c, 20), I.ema(c, 50)
    mac = I.macd(c)
    atr14 = I.atr(h, lo, c, 14)
    adxd = I.adx(h, lo, c, 14)
    boll = I.bollinger(c)
    a14 = _last(atr14)
    ind = {
        "sma20": _last(sma20),
        "sma50": _last(sma50),
        "sma200": _last(sma200),
        "ema20": _last(ema20),
        "ema50": _last(ema50),
        "rsi14": _last(I.rsi(c, 14)),
        "macd": _last(mac["macd"]),
        "macd_signal": _last(mac["signal"]),
        "macd_hist": _last(mac["hist"]),
        "atr14": a14,
        "atr14_pct": None if a14 is None or not close else a14 / close,
        "adx14": _last(adxd["adx"]),
        "plus_di14": _last(adxd["plus_di"]),
        "minus_di14": _last(adxd["minus_di"]),
        "bollinger_upper": _last(boll["upper"]),
        "bollinger_mid": _last(boll["mid"]),
        "bollinger_lower": _last(boll["lower"]),
        "close_vs_sma20": None if not ind_ok(close, _last(sma20)) else close / _last(sma20) - 1.0,  # type: ignore[operator]
        "close_vs_sma50": None if not ind_ok(close, _last(sma50)) else close / _last(sma50) - 1.0,  # type: ignore[operator]
        "close_vs_sma200": None
        if not ind_ok(close, _last(sma200))
        else close / _last(sma200) - 1.0,  # type: ignore[operator]
        "sma50_vs_sma200": None
        if not ind_ok(_last(sma50), _last(sma200))
        else _last(sma50) / _last(sma200) - 1.0,  # type: ignore[operator]
        "sma200_slope_20": _slope(sma200, 20),
        "ema20_slope_10": _slope(ema20, 10),
    }
    bb_u, bb_l = ind["bollinger_upper"], ind["bollinger_lower"]
    ind["bollinger_position"] = (
        None
        if bb_u is None or bb_l is None or bb_u == bb_l or close is None
        else (close - bb_l) / (bb_u - bb_l)
    )
    out["indicator_meta"] = indicator_meta(ps.n_bars, str(ps.last_session))
    out["indicators"] = ind
    out["trend"] = classify_trend(
        {
            "close": close,
            "sma20": ind["sma20"],
            "sma50": ind["sma50"],
            "sma200": ind["sma200"],
            "sma200_slope_20": ind["sma200_slope_20"],
        }
    )
    g, lvl = ps.tr_gross, ps.tr_level
    out["momentum"] = {f"ret{n}": _f(T.tr_return(g, n)) for n in (21, 63, 126, 252)} | {
        "mom_12_1": _f(T.mom_12_1(lvl)),
        "mom_1m": _f(T.tr_return(g, 21)),
        "mom_3m": _f(T.tr_return(g, 63)),
        "mom_6m": _f(T.tr_return(g, 126)),
        "mom_12m": _f(T.tr_return(g, 252)),
    }
    hi52 = _f(c.iloc[-252:].max()) if len(c) >= 252 else None
    out["momentum"]["distance_52w_high"] = (
        None if hi52 is None or close is None else close / hi52 - 1.0
    )
    rs: dict[str, float | None] = {}
    if bench is not None and bench.series.n_bars > 0:
        for n in (21, 63, 126, 252):
            rs[f"{n}"] = _f(T.relative_return(g, bench.series.tr_gross, n))
        out["relative_strength"] = {**rs, "benchmark": bench_ticker, "benchmark_type": "ETF_PROXY"}
        beta = _f(T.beta(g, bench.series.tr_gross))
    else:
        out["relative_strength"] = {
            "21": None,
            "63": None,
            "126": None,
            "252": None,
            "benchmark": None,
            "benchmark_type": "ETF_PROXY",
            "reason": "benchmark prices unavailable",
        }
        beta = None
        out["warnings"].append(
            "relative strength / beta unavailable: no benchmark proxy with prices"
        )
    out["risk"] = {
        "vol20": _f(T.annualized_vol(g, 20)),
        "vol63": _f(T.annualized_vol(g, 63)),
        "vol252": _f(T.annualized_vol(g, 252)),
        "downside_vol63": _f(I.downside_vol(g - 1.0, 63)),
        "max_drawdown252": _f(T.max_drawdown(lvl, 252)),
        "beta252": beta,
        "atr14_pct": ind["atr14_pct"],
    }
    rawv = md.bars["volume"].astype(float)
    avg20 = _f(v.iloc[-20:].mean()) if len(v) >= 20 else None
    out["volume"] = {
        "avg20": avg20,
        "ratio20": _f(T.volume_ratio(v, 20)),
        "zscore20": _f(T.volume_zscore(v, 20)),
        "dollar_volume": _f(float(md.bars["close"].iloc[-1]) * float(rawv.iloc[-1])),
    }
    out["overextension"] = {
        "distance_from_sma20_atr": None
        if not (a14 and ind["sma20"] and close)
        else (close - ind["sma20"]) / a14,
        "distance_from_sma50_atr": None
        if not (a14 and ind["sma50"] and close)
        else (close - ind["sma50"]) / a14,
        "distance_from_sma200_pct": ind["close_vs_sma200"],
    }
    out["support_resistance"] = compute_zones(adj, a14, close)
    out["last_close_split_adjusted"] = close
    for name, need in (("sma200", 200), ("rsi14", 15), ("adx14", 28)):
        if ps.n_bars < need:
            out["warnings"].append(f"{name}: insufficient history ({ps.n_bars} < {need} bars)")
    if ps.split_adjusted.index.size and md.actions:
        out["corporate_actions_applied"] = [
            {
                "kind": a.kind.value,
                "date": str(a.anchor_date),
                "ratio": a.ratio,
                "cash": a.cash_amount,
                "tier": a.provenance.tier.value,
            }
            for a in md.actions
            if a.anchor_date and a.anchor_date >= ps.split_adjusted.index[0]
        ][-12:]
    out["status"] = "OK"
    return out


def ind_ok(a: float | None, b: float | None) -> bool:
    return a is not None and b is not None and b != 0


RANGES = {"1M": 21, "3M": 63, "6M": 126, "1Y": 252, "3Y": 756, "5Y": 1260}


def chart_payload(
    md: MarketData, range_: str = "1Y", decision_at: datetime | None = None
) -> dict[str, Any]:
    """Candles + volume + overlays + indicator panes, computed on the FULL history and then sliced, so
    averages are correct at the left edge of any range. Prices are SPLIT-ADJUSTED (candles consistent over
    time); dividends are NOT applied."""
    ps = md.series
    if ps.n_bars == 0:
        return {
            "status": "NO_DATA",
            "as_of": (decision_at or md.decision_at).isoformat(),
            "candles": [],
        }
    adj = ps.split_adjusted
    c, h, lo = adj["close"], adj["high"], adj["low"]
    ma = {
        "sma20": I.sma(c, 20),
        "sma50": I.sma(c, 50),
        "sma200": I.sma(c, 200),
        "ema20": I.ema(c, 20),
        "ema50": I.ema(c, 50),
    }
    boll = I.bollinger(c)
    mac = I.macd(c)
    rsi14 = I.rsi(c, 14)
    n = len(adj) if range_ == "MAX" else RANGES.get(range_) if range_ != "YTD" else None
    if range_ == "YTD":
        last = adj.index[-1]
        n = int((adj.index >= last.replace(month=1, day=1)).sum()) if last else len(adj)
    n = min(n or len(adj), len(adj))
    sl = slice(len(adj) - n, len(adj))

    def ser(s: pd.Series) -> list[dict[str, Any]]:
        t = s.iloc[sl]
        return [{"time": str(i), "value": round(float(x), 6)} for i, x in t.items() if pd.notna(x)]

    candles = [
        {
            "time": str(i),
            "open": round(float(r.open), 6),
            "high": round(float(r.high), 6),
            "low": round(float(r.low), 6),
            "close": round(float(r.close), 6),
            "volume": float(r.volume),
        }
        for i, r in adj.iloc[sl].iterrows()
    ]
    return {
        "status": "OK",
        "as_of": (decision_at or md.decision_at).isoformat(),
        "engine_version": TECHNICAL_ENGINE_VERSION,
        "range": range_,
        "n_bars": len(candles),
        "price_basis": "SPLIT_ADJUSTED_NOT_DIVIDEND_ADJUSTED",
        "currency": "USD",
        "sources": md.sources,
        "candles": candles,
        "overlays": {k: ser(v) for k, v in ma.items()}
        | {
            "bollinger_upper": ser(boll["upper"]),
            "bollinger_mid": ser(boll["mid"]),
            "bollinger_lower": ser(boll["lower"]),
        },
        "panes": {
            "rsi14": ser(rsi14),
            "macd": ser(mac["macd"]),
            "macd_signal": ser(mac["signal"]),
            "macd_hist": ser(mac["hist"]),
            "atr14": ser(I.atr(h, lo, c, 14)),
        },
        "corporate_actions": [
            {
                "kind": a.kind.value,
                "date": str(a.anchor_date),
                "ratio": a.ratio,
                "cash": a.cash_amount,
            }
            for a in md.actions
            if a.anchor_date and a.anchor_date >= adj.index[sl.start]
        ],
    }
