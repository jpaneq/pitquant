# ruff: noqa: E501
"""BTC live market display (Binance Spot, no API key). Three strictly separate concepts:

* LIVE MARKET DISPLAY: ``/ticker/price`` + ``/ticker/24hr``; stamped with ``retrieved_at`` (``timestamp_kind=RETRIEVED_AT``: the endpoint has no trade timestamp and none is invented).
* DAILY MODEL DATA: the last 1D UTC kline whose ``closeTime <= request_now``. The open candle is NEVER a model bar; it is exposed apart as ``INCOMPLETE``.
* SYNTHETIC TEST DATA: only when ``PITQUANT_E2E_FIXTURE=1``. Never a fallback of the normal application.

Nothing here feeds FeatureSnapshot, PredictionSnapshot, replay or any T0 daily decision.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.btc.contracts import Cohort
from pitquant.btc.models import BTCDatum, BTCResearchRecord
from pitquant.core.timeutils import utc_now

BASES = ("https://data-api.binance.vision", "https://api.binance.com")
SYMBOL = "BTCUSDT"
LIVE_SECONDS, RECENT_SECONDS = 10, 60
Fetch = Callable[[str, str, dict[str, Any]], Any]
# stale thresholds for archived series (hours): the cadence of each source plus slack; nothing is back-filled
STALE_AFTER = {"funding_rate": 24, "open_interest": 6, "basis": 6}
NETWORK_STALE_AFTER = 72
NETWORK_METRICS = (
    "active_addresses",
    "transaction_count",
    "fees",
    "hash_rate",
    "supply",
    "market_cap",
    "MVRV",
)


def http_fetch(base: str, path: str, params: dict[str, Any]) -> Any:
    from urllib.parse import urlencode

    req = urllib.request.Request(
        f"{base}{path}?{urlencode(params)}",
        headers={"User-Agent": "PITQuant/BTC-V0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=4) as r:
        return json.loads(r.read())


def fetch_with_fallback(fetch: Fetch, path: str, params: dict[str, Any]) -> tuple[Any, str]:
    last: Exception | None = None
    for base in BASES:
        try:
            return fetch(base, path, params), base
        except Exception as exc:  # network, HTTP or parse failure: try the next official base
            last = exc
    raise ConnectionError(f"BINANCE_UNREACHABLE: {last}")


def ms(value: int) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000, UTC)


def freshness(retrieved_at: datetime | None, now: datetime) -> str:
    """Based on the quote's ``retrieved_at`` only. STALE is never hidden."""
    if retrieved_at is None:
        return "UNAVAILABLE"
    age = (now - retrieved_at).total_seconds()
    return "LIVE" if age <= LIVE_SECONDS else "RECENT" if age <= RECENT_SECONDS else "STALE"


def parse_bar(k: list[Any]) -> dict[str, Any]:
    return {
        "open_time": ms(k[0]).isoformat(), "close_time": ms(k[6]).isoformat(), "open": float(k[1]), "high": float(k[2]), "low": float(k[3]), "close": float(k[4]),
        "volume": float(k[5]), "number_of_trades": int(k[8]),
    }  # fmt: skip


def split_klines(
    klines: list[list[Any]], now: datetime
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """(last CLOSED bar, forming bar). Closed = ``closeTime <= now``; the open candle is never returned as a model bar."""
    closed = [k for k in klines if ms(k[6]) <= now]
    forming = [k for k in klines if ms(k[6]) > now >= ms(k[0])]
    return (
        parse_bar(max(closed, key=lambda k: k[6])) if closed else None,
        parse_bar(forming[-1]) if forming else None,
    )


def parse_24h(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "change": float(raw["priceChange"]), "change_pct": float(raw["priceChangePercent"]), "high": float(raw["highPrice"]), "low": float(raw["lowPrice"]),
        "volume_btc": float(raw["volume"]), "volume_usdt": float(raw["quoteVolume"]), "open_time": ms(raw["openTime"]).isoformat(), "close_time": ms(raw["closeTime"]).isoformat(),
        "window": "24H_ROLLING_NOT_UTC_DAILY_BAR",
    }  # fmt: skip


def archived_last(session: Session) -> tuple[dict[str, Any], datetime] | None:
    row = session.scalars(
        select(BTCDatum)
        .where(
            BTCDatum.source == "BINANCE_SPOT",
            BTCDatum.metric == "spot",
            BTCDatum.cohort == Cohort.FORWARD_PAPER,
        )
        .order_by(BTCDatum.exchange_timestamp.desc(), BTCDatum.retrieved_at.desc())
        .limit(1)
    ).first()
    if row is None:
        return None
    p = row.payload
    bar = {"open_time": (row.exchange_timestamp - timedelta(days=1)).isoformat(), "close_time": (row.exchange_timestamp - timedelta(milliseconds=1)).isoformat(), "open": p["open"], "high": p["high"], "low": p["low"], "close": p["close"], "volume": p["volume"], "number_of_trades": None}  # fmt: skip
    return bar, row.retrieved_at


def latest_series(
    session: Session, source: str, metric: str, now: datetime, stale_hours: float
) -> dict[str, Any]:
    row = session.scalars(
        select(BTCDatum)
        .where(
            BTCDatum.source == source,
            BTCDatum.metric == metric,
            BTCDatum.cohort == Cohort.FORWARD_PAPER,
        )
        .order_by(BTCDatum.exchange_timestamp.desc(), BTCDatum.retrieved_at.desc())
        .limit(1)
    ).first()
    if row is None:
        return {
            "metric": metric,
            "status": "UNAVAILABLE",
            "value": None,
            "as_of": None,
            "available_at": None,
            "first_knowledge_at": None,
            "retrieved_at": None,
            "source": source,
        }
    first = session.scalars(
        select(BTCDatum.available_at)
        .where(
            BTCDatum.source == source,
            BTCDatum.metric == metric,
            BTCDatum.exchange_timestamp == row.exchange_timestamp,
            BTCDatum.cohort == Cohort.FORWARD_PAPER,
        )
        .order_by(BTCDatum.available_at)
        .limit(1)
    ).first()
    stale = now - row.exchange_timestamp > timedelta(hours=stale_hours)
    p = row.payload
    return {
        "metric": metric, "status": "STALE" if stale else "AVAILABLE", "value": p.get("value"), "as_of": row.exchange_timestamp.isoformat(), "available_at": row.available_at.isoformat(),
        "first_knowledge_at": first.isoformat() if first else None, "retrieved_at": row.retrieved_at.isoformat(), "source": source, "stale_after_hours": stale_hours,
        **({"basis_rate": p["basisRate"]} if "basisRate" in p else {}),
    }  # fmt: skip


def archived_context(session: Session, now: datetime) -> dict[str, Any]:
    """Latest REAL archived values; never back-filled, never fabricated. Failed Coin Metrics series stay visible as UNAVAILABLE with the recorded reason."""
    rec = session.scalars(
        select(BTCResearchRecord)
        .where(BTCResearchRecord.kind == "COLLECTION")
        .order_by(BTCResearchRecord.created_at.desc())
        .limit(1)
    ).first()
    sources = (rec.payload.get("sources") if rec else None) or {}
    network = []
    for m in NETWORK_METRICS:
        item = latest_series(session, "COIN_METRICS", m, now, NETWORK_STALE_AFTER)
        if item["status"] == "UNAVAILABLE":
            item["reason"] = (sources.get(m) or {}).get("reason") or "NOT_ARCHIVED"
        network.append(item)
    return {
        "funding": latest_series(session, "BINANCE_FUNDING", "funding_rate", now, STALE_AFTER["funding_rate"]),
        "open_interest": latest_series(session, "BINANCE_DERIVATIVES", "open_interest", now, STALE_AFTER["open_interest"]),
        "basis": latest_series(session, "BINANCE_DERIVATIVES", "basis", now, STALE_AFTER["basis"]),
        "network": network,
    }  # fmt: skip


def live_market(
    session: Session,
    fetch: Fetch = http_fetch,
    now: datetime | None = None,
    *,
    data_mode: str = "REAL",
) -> dict[str, Any]:
    """The /btc/market/live payload. Order: Binance REST → latest archived REAL observation (STALE) → UNAVAILABLE. Never a synthetic fallback."""
    now = now or utc_now()
    base_out: dict[str, Any] = {
        "asset": "BTC",
        "pair": SYMBOL,
        "model_frequency": "1D_UTC",
        "data_mode": data_mode,
        "model_bar_note": "Predictions use closed daily bars, not the live quote.",
    }
    if data_mode == "SYNTHETIC_TEST_DATA":
        base_out["warning"] = "SYNTHETIC TEST DATA"
    context = archived_context(session, now)
    try:
        price_raw, base = fetch_with_fallback(fetch, "/api/v3/ticker/price", {"symbol": SYMBOL})
        retrieved = utc_now() if data_mode == "REAL" else now
        if price_raw["symbol"] != SYMBOL:
            raise ValueError("unexpected symbol")
        price = float(price_raw["price"])
        h24_raw, _ = fetch_with_fallback(fetch, "/api/v3/ticker/24hr", {"symbol": SYMBOL})
        klines, _ = fetch_with_fallback(
            fetch,
            "/api/v3/klines",
            {"symbol": SYMBOL, "interval": "1d", "timeZone": "0", "limit": 3},
        )
        closed, forming = split_klines(klines, now)
        if price <= 0:
            raise ValueError("non-positive price")
        return {
            **base_out,
            "quote": {"price": price, "retrieved_at": retrieved.isoformat(), "timestamp_kind": "RETRIEVED_AT", "source": "BINANCE_SPOT", "status": freshness(retrieved, now), "currency": "USDT"},
            "rolling_24h": parse_24h(h24_raw), "last_closed_daily_bar": closed, "forming_daily_bar": {**forming, "status": "INCOMPLETE", "usage": "DISPLAY_ONLY_NOT_MODEL_INPUT"} if forming else None,
            "retrieved_at": retrieved.isoformat(), "provenance": {"base_url": base, "endpoints": ["/api/v3/ticker/price", "/api/v3/ticker/24hr", "/api/v3/klines"], "usage": "DISPLAY_ONLY_NOT_PIT"}, **context,
        }  # fmt: skip
    except Exception as exc:
        reason = str(exc)[:200]
    arch = archived_last(session)
    if arch is None:
        return {
            **base_out, "quote": {"price": None, "retrieved_at": None, "timestamp_kind": "RETRIEVED_AT", "source": "BINANCE_SPOT", "status": "UNAVAILABLE", "currency": "USDT"},
            "rolling_24h": None, "last_closed_daily_bar": None, "forming_daily_bar": None, "retrieved_at": None, "reason": f"REAL DATA UNAVAILABLE: {reason}", "provenance": {"fallback": "NONE"}, **context,
        }  # fmt: skip
    bar, at = arch
    return {
        **base_out,
        "quote": {"price": bar["close"], "retrieved_at": at.isoformat(), "timestamp_kind": "RETRIEVED_AT", "source": "BINANCE_SPOT_ARCHIVE", "status": "STALE", "currency": "USDT", "note": "last archived daily close, not a live price"},
        "rolling_24h": None, "last_closed_daily_bar": bar, "forming_daily_bar": None, "retrieved_at": at.isoformat(), "reason": f"LIVE UNAVAILABLE, ARCHIVE SHOWN: {reason}",
        "provenance": {"fallback": "LATEST_ARCHIVED_REAL_BINANCE_OBSERVATION", "usage": "DISPLAY_ONLY_NOT_PIT"}, **context,
    }  # fmt: skip


def chart_bars(session: Session, range_: str, now: datetime) -> dict[str, Any]:
    """Real archived daily bars only. No bar is fabricated; a missing day is flagged with ``gap_before`` so the UI shows the gap."""
    days = {"1M": 31, "3M": 92, "6M": 183, "1Y": 366, "3Y": 1096, "MAX": None}
    if range_ not in days:
        raise ValueError("range must be one of " + ", ".join(days))
    q = (
        select(BTCDatum)
        .where(
            BTCDatum.source == "BINANCE_SPOT",
            BTCDatum.metric == "spot",
            BTCDatum.cohort == Cohort.FORWARD_PAPER,
        )
        .order_by(BTCDatum.exchange_timestamp, BTCDatum.retrieved_at)
    )
    span = days[range_]
    if span is not None:
        q = q.where(BTCDatum.exchange_timestamp >= now - timedelta(days=span))
    latest = {r.exchange_timestamp: r for r in session.scalars(q)}  # last revision per bar
    bars, prev = [], None
    for ts in sorted(latest):
        p = latest[ts].payload
        bars.append({"open_time": (ts - timedelta(days=1)).isoformat(), "close_time": (ts - timedelta(milliseconds=1)).isoformat(), **{k: p[k] for k in ("open", "high", "low", "close", "volume")}, "gap_before": prev is not None and ts - prev > timedelta(days=1)})  # fmt: skip
        prev = ts
    return {
        "range": range_,
        "interval": "1d",
        "bars": bars,
        "source": "BINANCE_SPOT_ARCHIVE",
        "note": "closed 1D UTC bars; missing days are gaps, never interpolated",
    }
