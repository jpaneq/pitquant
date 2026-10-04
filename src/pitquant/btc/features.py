"""Transparent feature families over immutable data versions available at the cutoff."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.btc.contracts import Availability, decision_time
from pitquant.btc.models import BTCDatum
from pitquant.btc.providers import NETWORK_CANDIDATES
from pitquant.core.timeutils import require_aware

DERIVATIVES = (
    "funding_rate_current",
    "funding_rate_mean_3d",
    "funding_rate_mean_7d",
    "funding_rate_zscore_30d",
    "open_interest",
    "oi_change_1d",
    "oi_change_7d",
    "oi_change_30d",
    "perp_premium",
    "basis",
    "annualized_basis",
    "taker_buy_sell_ratio",
    "long_short_ratio",
    "price_up_oi_up",
    "price_up_oi_down",
    "price_down_oi_up",
    "price_down_oi_down",
    "funding_positive_high",
    "funding_negative_high",
)


def known_data(
    session: Session, at: datetime, cohort: str, knowledge_at: datetime | None = None
) -> list[BTCDatum]:
    require_aware(at)
    cutoff = knowledge_at or at
    require_aware(cutoff)
    if not at <= cutoff <= at + timedelta(minutes=15):
        raise ValueError("knowledge cutoff must be within 15 minutes after the UTC decision close")
    rows = session.scalars(
        select(BTCDatum)
        .where(
            BTCDatum.cohort == cohort,
            BTCDatum.exchange_timestamp <= at,
            BTCDatum.available_at <= cutoff,
        )
        .order_by(BTCDatum.available_at, BTCDatum.datum_id)
    )
    versions = {}
    for row in rows:
        versions[(row.source, row.metric, row.exchange_timestamp)] = row
    return sorted(versions.values(), key=lambda row: row.exchange_timestamp)


def feature_payload(
    session: Session, at: datetime, cohort: str, knowledge_at: datetime | None = None
) -> dict[str, Any]:
    decision_time(at)
    rows = known_data(session, at, cohort, knowledge_at)
    spot = [r for r in rows if r.metric == "spot"]
    frame = pd.DataFrame([r.payload for r in spot], index=[r.exchange_timestamp for r in spot])
    result: dict[str, Any] = {
        family: {}
        for family in (
            "price_features",
            "momentum_features",
            "trend_features",
            "volatility_features",
            "volume_features",
            "derivatives_features",
            "network_features",
            "onchain_features",
            "macro_features",
        )
    }
    availability: dict[str, str] = {}
    reasons: dict[str, str] = {}

    def put(family: str, name: str, value: Any, reason: str = "NOT_ENOUGH_HISTORY") -> None:
        valid = value is not None and np.isfinite(float(value))
        result[family][name] = float(value) if valid else None
        availability[name] = Availability.AVAILABLE if valid else Availability.NOT_ENOUGH_HISTORY
        if valid:
            reasons.pop(name, None)
        else:
            reasons[name] = reason

    def window(n: int) -> pd.DataFrame | None:
        if len(frame) < n:
            return None
        f = frame.iloc[-n:]
        if n > 1 and any(
            (b - a).total_seconds() != 86400 for a, b in zip(f.index, f.index[1:], strict=False)
        ):
            return None
        return f

    close = frame["close"] if len(frame) else pd.Series(dtype=float)
    log = np.log(close).diff()
    put("price_features", "price", close.iloc[-1] if len(close) else None, "PRICE_DATA_REQUIRED")
    for n in (1, 3, 7, 14, 30, 90, 180, 365):
        w = window(n + 1)
        put(
            "momentum_features",
            f"log_return_{n}d",
            np.log(w.close.iloc[-1] / w.close.iloc[0]) if w is not None else None,
        )
    smas: dict[int, Any] = {}
    for n in (20, 50, 200):
        sample = window(n)
        smas[n] = sample.close.mean() if sample is not None else None
    for n, sma in smas.items():
        put("trend_features", f"distance_sma{n}", close.iloc[-1] / sma - 1 if sma else None)
    for a, b in ((20, 50), (50, 200)):
        put(
            "trend_features",
            f"sma{a}_vs_{b}",
            smas[a] / smas[b] - 1 if smas[a] and smas[b] else None,
        )
    for n in (20, 50):
        put(
            "trend_features",
            f"ema{n}",
            close.ewm(span=n, adjust=False).mean().iloc[-1] if window(n) is not None else None,
        )
    for n in (30, 90, 365):
        w = window(n)
        put(
            "price_features",
            f"distance_{n}d_high",
            close.iloc[-1] / w.high.max() - 1 if w is not None else None,
        )
        if n != 365:
            put(
                "price_features",
                f"drawdown_{n}d",
                (w.close / w.close.cummax() - 1).min() if w is not None else None,
            )
    put("price_features", "drawdown_from_ATH", None, "FULL_BTC_ATH_HISTORY_NOT_VERIFIED")
    put(
        "price_features",
        "drawdown_from_observed_high",
        close.iloc[-1] / frame.high.max() - 1 if len(frame) else None,
    )
    result["ath_scope"] = (
        "OBSERVED_HISTORY_ONLY"  # no claim that truncated archive contains the true ATH
    )
    for n in (7, 30, 90):
        put(
            "volatility_features",
            f"realized_vol_{n}d",
            log.iloc[-n:].std(ddof=1) * np.sqrt(365) if window(n + 1) is not None else None,
        )
    if window(15) is not None:
        tr = pd.concat(
            [
                frame.high - frame.low,
                (frame.high - close.shift()).abs(),
                (frame.low - close.shift()).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = tr.iloc[-14:].mean()
    else:
        atr = None
    put("volatility_features", "ATR14", atr)
    put(
        "volatility_features",
        "return_skew_30d",
        log.iloc[-30:].skew() if window(31) is not None else None,
    )
    put(
        "volatility_features",
        "return_kurtosis_30d",
        log.iloc[-30:].kurt() if window(31) is not None else None,
    )
    for n in (1, 7):
        w = window(n + 1)
        put(
            "volume_features",
            f"volume_change_{n}d",
            w.volume.iloc[-1] / w.volume.iloc[0] - 1
            if w is not None and w.volume.iloc[0]
            else None,
        )
    w = window(30)
    put(
        "volume_features",
        "volume_zscore_30d",
        (w.volume.iloc[-1] - w.volume.mean()) / w.volume.std(ddof=1)
        if w is not None and w.volume.std(ddof=1)
        else None,
    )
    series = {}
    for metric in (
        "funding_rate",
        "open_interest",
        "basis",
        "taker_buy_sell_ratio",
        "long_short_ratio",
        *NETWORK_CANDIDATES,
    ):
        metric_rows = [r for r in rows if r.metric == metric]
        series[metric] = pd.Series(
            [r.payload["value"] for r in metric_rows],
            index=[r.exchange_timestamp for r in metric_rows],
            dtype=float,
        )
    d = result["derivatives_features"]
    for name in DERIVATIVES:
        put("derivatives_features", name, None)
        if not len(series["funding_rate" if name.startswith("funding") else "open_interest"]):
            availability[name] = (
                Availability.SOURCE_RETENTION_LIMIT
                if name.startswith("oi_") or name == "open_interest"
                else Availability.UNAVAILABLE
            )
            reasons[name] = "NO_POINT_IN_TIME_ARCHIVE"
    for metric, name in (
        ("funding_rate", "funding_rate_current"),
        ("open_interest", "open_interest"),
        ("basis", "basis"),
        ("taker_buy_sell_ratio", "taker_buy_sell_ratio"),
        ("long_short_ratio", "long_short_ratio"),
    ):
        x = series[metric]
        if len(x) and (at - x.index[-1]).total_seconds() <= 86400:
            put("derivatives_features", name, x.iloc[-1])
    x = series["funding_rate"]
    for n in (3, 7, 30):
        z = x[x.index >= at - timedelta(days=n)]
        if len(z) and (z.index[-1] - z.index[0]).total_seconds() >= (n - 1) * 86400:
            name = f"funding_rate_mean_{n}d" if n != 30 else "funding_rate_zscore_30d"
            put(
                "derivatives_features",
                name,
                z.mean() if n != 30 else ((z.iloc[-1] - z.mean()) / z.std() if z.std() else None),
            )
    x = series["open_interest"]
    for n in (1, 7, 30):
        past = x[x.index <= at - timedelta(days=n)]
        if len(past) and d["open_interest"] is not None and past.iloc[-1]:
            put("derivatives_features", f"oi_change_{n}d", d["open_interest"] / past.iloc[-1] - 1)
    basis_rows = [r for r in rows if r.metric == "basis"]
    if basis_rows and at - basis_rows[-1].exchange_timestamp <= timedelta(days=1):
        put("derivatives_features", "perp_premium", basis_rows[-1].payload.get("basisRate"))
        put(
            "derivatives_features",
            "annualized_basis",
            basis_rows[-1].payload.get("annualizedBasisRate"),
        )
    p, oi, z = (
        result["momentum_features"].get("log_return_1d"),
        d.get("oi_change_1d"),
        d.get("funding_rate_zscore_30d"),
    )
    if p is not None and oi is not None:
        for name, condition in (
            ("price_up_oi_up", p > 0 and oi > 0),
            ("price_up_oi_down", p > 0 and oi < 0),
            ("price_down_oi_up", p < 0 and oi > 0),
            ("price_down_oi_down", p < 0 and oi < 0),
        ):
            put("derivatives_features", name, int(condition))
    if z is not None and d["funding_rate_current"] is not None:
        put(
            "derivatives_features",
            "funding_positive_high",
            int(z > 2 and d["funding_rate_current"] > 0),
        )
        put(
            "derivatives_features",
            "funding_negative_high",
            int(z < -2 and d["funding_rate_current"] < 0),
        )
    for metric in NETWORK_CANDIDATES:
        x = series[metric]
        put(
            "network_features",
            metric,
            x.iloc[-1] if len(x) and at - x.index[-1] <= timedelta(days=2) else None,
            "NOT_AVAILABLE_AT_CUTOFF",
        )
        if result["network_features"][metric] is None:
            availability[metric] = Availability.UNAVAILABLE
    from pitquant.analyzer.sr_v1 import compute_zones

    zones_frame = frame.copy()
    zones_frame.index = [x.date() for x in zones_frame.index]
    result["support_resistance"] = (
        compute_zones(zones_frame, atr) if len(frame) else {"supports": [], "resistances": []}
    )
    result["price_history"] = [
        {"time": r.exchange_timestamp.isoformat(), "close": r.payload["close"]} for r in spot[-90:]
    ]
    result.update(
        availability=availability,
        missing_reasons=reasons,
        decision_at=at.isoformat(),
        knowledge_at=(knowledge_at or at).isoformat(),
        last_spot_close=spot[-1].exchange_timestamp.isoformat() if spot else None,
        spot_ready=bool(spot and spot[-1].exchange_timestamp == at),
        provenance=[
            {
                "datum_id": r.datum_id,
                "source": r.source,
                "metric": r.metric,
                "exchange_timestamp": r.exchange_timestamp.isoformat(),
                "available_at": r.available_at.isoformat(),
                "raw_hash": r.raw_hash,
            }
            for r in rows
        ],
        regime={
            "trend": "UP"
            if smas[50] and smas[200] and smas[50] > smas[200]
            else "UNKNOWN_OR_NOT_UP",
            "rule": "SMA50_VS_SMA200",
            "prediction": False,
        },
    )
    return result
