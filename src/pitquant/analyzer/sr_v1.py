# ruff: noqa: E501
"""SupportResistanceEngineV1: ZONES, never magic lines (docs/TECHNICAL_ENGINE_V1.md).

* Pivot (swing) high at bar i: ``high[i] > max(high[i-5:i])`` and ``high[i] >= max(high[i+1:i+6])``
  (strict on the left, non-strict on the right: a flat top is confirmed by its FIRST bar and a later
  equal bar does not create a second pivot because the left test would fail). Swing low is symmetric.
* A pivot exists only once 5 later bars have been completed: with ``decision_at`` fixed, a pivot at
  bar i is visible iff i + 5 <= last completed bar. No look-ahead.
* Clustering: pivots of the same type are grouped while ``|level - cluster center| <= 0.75 * ATR14``
  (ATR at the decision, the current volatility context). Zone = [min, max] of its pivots, widened to
  at least ±0.1 ATR so a single touch is still a band.
* Strength (explainable, not optimised): 100 * (0.4*min(touches,5)/5 + 0.3*recency + 0.3*min(rejection_atr/3, 1)),
  recency = mean over touches of 0.5 ** (age_sessions / 126), rejection = mean move AWAY from the pivot
  over the next 5 bars in ATR units. Volume confirmation is reported (pivot volume / 20-bar mean), not scored.
* Output: at most 3 supports (zones whose center is below the last close) and 3 resistances, nearest first,
  only zones with >= 2 touches or a rejection >= 1 ATR.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

SR_VERSION = "sr-v1.0"
WINDOW = 5
CLUSTER_ATR = 0.75
LOOKBACK = 504


@dataclass
class Zone:
    kind: str  # SUPPORT | RESISTANCE
    lower: float
    upper: float
    midpoint: float
    touches: int
    first_touch: str
    last_touch: str
    strength: float
    distance_pct: float
    distance_atr: float
    reasons: list[str] = field(default_factory=list)
    volume_confirmation: float | None = None
    # V1 documented contract (additive): explicit band, method, recency and the raw strength
    zone_low: float = 0.0
    zone_high: float = 0.0
    method: str = "SWING_PIVOT_CLUSTER_ATR"
    recency: float = 0.0
    strength_raw: float = 0.0
    calculation_at: str = ""


def pivots(high: pd.Series, low: pd.Series, window: int = WINDOW) -> tuple[list[int], list[int]]:
    """Positions of CONFIRMED swing highs / lows (needs ``window`` completed bars after the pivot)."""
    h, lo = high.to_numpy(float), low.to_numpy(float)
    hi_idx: list[int] = []
    lo_idx: list[int] = []
    for i in range(window, len(h) - window):
        if h[i] > h[i - window : i].max() and h[i] >= h[i + 1 : i + 1 + window].max():
            hi_idx.append(i)
        if lo[i] < lo[i - window : i].min() and lo[i] <= lo[i + 1 : i + 1 + window].min():
            lo_idx.append(i)
    return hi_idx, lo_idx


def _cluster(levels: list[tuple[int, float]], tol: float) -> list[list[tuple[int, float]]]:
    out: list[list[tuple[int, float]]] = []
    for pos, lvl in sorted(levels, key=lambda t: t[1]):
        if out and abs(lvl - float(np.mean([x[1] for x in out[-1]]))) <= tol:
            out[-1].append((pos, lvl))
        else:
            out.append([(pos, lvl)])
    return out


def compute_zones(
    adj: pd.DataFrame, atr14: float | None, last_close: float | None = None
) -> dict[str, list[dict[str, object]]]:
    """``adj``: split-adjusted OHLCV (index = session date), completed bars only."""
    if atr14 is None or atr14 <= 0 or len(adj) < 2 * WINDOW + 2:
        return {"supports": [], "resistances": []}
    d = adj.iloc[-LOOKBACK:]
    close = float(d["close"].iloc[-1]) if last_close is None else last_close
    hi_idx, lo_idx = pivots(d["high"], d["low"])
    vol20 = d["volume"].rolling(20, min_periods=5).mean()
    n = len(d)
    zones: list[Zone] = []
    for kind, idxs, col in (("RESISTANCE", hi_idx, "high"), ("SUPPORT", lo_idx, "low")):
        pts = [(i, float(d[col].iloc[i])) for i in idxs]
        for cl in _cluster(pts, CLUSTER_ATR * atr14):
            levels = [lv for _, lv in cl]
            lower, upper = min(levels), max(levels)
            if upper - lower < 0.2 * atr14:
                mid = (upper + lower) / 2
                lower, upper = mid - 0.1 * atr14, mid + 0.1 * atr14
            positions = [p for p, _ in cl]
            rej = []
            for p in positions:
                nxt = d.iloc[p + 1 : p + 1 + WINDOW]
                move = (
                    (float(d[col].iloc[p]) - float(nxt["low"].min()))
                    if kind == "RESISTANCE"
                    else (float(nxt["high"].max()) - float(d[col].iloc[p]))
                )
                rej.append(max(move, 0.0) / atr14)
            rec = float(np.mean([0.5 ** ((n - 1 - p) / 126.0) for p in positions]))
            rejection = float(np.mean(rej))
            touches = len(cl)
            strength = 100.0 * (
                0.4 * min(touches, 5) / 5 + 0.3 * rec + 0.3 * min(rejection / 3.0, 1.0)
            )
            mid = (lower + upper) / 2
            if (kind == "SUPPORT" and mid >= close) or (kind == "RESISTANCE" and mid <= close):
                continue
            if touches < 2 and rejection < 1.0:
                continue
            vc = [
                float(d["volume"].iloc[p] / vol20.iloc[p])
                for p in positions
                if pd.notna(vol20.iloc[p]) and vol20.iloc[p] > 0
            ]
            zones.append(
                Zone(
                    kind,
                    lower,
                    upper,
                    mid,
                    touches,
                    str(d.index[min(positions)]),
                    str(d.index[max(positions)]),
                    round(strength, 1),
                    (mid / close - 1.0),
                    abs(mid - close) / atr14,
                    [
                        f"{touches} confirmed swing {'highs' if kind == 'RESISTANCE' else 'lows'}",
                        f"mean rejection {rejection:.2f} ATR",
                        f"recency weight {rec:.2f}",
                    ],
                    float(np.mean(vc)) if vc else None,
                    zone_low=lower,
                    zone_high=upper,
                    recency=round(rec, 4),
                    strength_raw=strength,
                    calculation_at=str(d.index[-1]),
                )
            )
    broken = _broken_resistances(d, hi_idx, atr14, close, vol20)
    sup = sorted((z for z in zones if z.kind == "SUPPORT"), key=lambda z: abs(z.distance_atr))[:3]
    res = sorted((z for z in zones if z.kind == "RESISTANCE"), key=lambda z: abs(z.distance_atr))[
        :3
    ]
    return {
        "supports": [asdict(z) for z in sup],
        "resistances": [asdict(z) for z in res],
        "broken_resistances": broken,
    }


def _broken_resistances(
    d: pd.DataFrame, hi_idx: list[int], atr14: float, close: float, vol20: pd.Series
) -> list[dict[str, object]]:
    """Former resistance zones that price has CLEARED with a completed close above ``upper + 0.25*ATR14``
    within the last 30 sessions (a confirmed breakout, never an intraday or incomplete candle)."""
    out: list[dict[str, object]] = []
    n = len(d)
    pts = [(i, float(d["high"].iloc[i])) for i in hi_idx]
    for cl in _cluster(pts, CLUSTER_ATR * atr14):
        levels = [lv for _, lv in cl]
        lower, upper = min(levels), max(levels)
        if upper - lower < 0.2 * atr14:
            mid = (upper + lower) / 2
            lower, upper = mid - 0.1 * atr14, mid + 0.1 * atr14
        trigger = upper + 0.25 * atr14
        recent = d["close"].iloc[-30:]
        if close <= trigger or not (recent <= upper).any():
            continue  # not cleared, or it was already above the zone for the whole window (no fresh breakout)
        if len(cl) < 2 and n - 1 - cl[0][0] > 252:
            continue
        first_above = recent[recent > trigger].index[0]
        out.append(
            {
                "lower": lower,
                "upper": upper,
                "midpoint": (lower + upper) / 2,
                "touches": len(cl),
                "trigger": trigger,
                "broke_on": str(first_above),
                "distance_atr": (close - upper) / atr14,
                "reasons": [
                    f"{len(cl)} confirmed swing highs",
                    f"completed close {close:.2f} > zone upper + 0.25 ATR = {trigger:.2f}",
                ],
            }
        )
    return sorted(out, key=lambda z: float(z["distance_atr"]))[:2]  # type: ignore[arg-type]
