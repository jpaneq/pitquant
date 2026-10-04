"""Ephemeral display-only quote; never a feature, label or simulation price input."""

from __future__ import annotations

import json
import math
import time
import urllib.request
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from threading import Lock
from typing import Any

from pitquant.btc.providers import SPOT
from pitquant.core.timeutils import utc_now


class LiveQuote:
    def __init__(self) -> None:
        self._lock = Lock()
        self._cached: dict[str, Any] | None = None
        self._expires = 0.0
        self._history: dict[str, Any] | None = None
        self._history_expires = 0.0
        self._quotes: dict[str, tuple[float, dict[str, Any]]] = {}
        self._histories: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}

    def get(self, symbol: str = "BTCUSDT") -> dict[str, Any]:
        if symbol not in {"BTCUSDT", "BTCEUR"}:
            raise ValueError("INVALID_BTC_PAIR")
        with self._lock:
            if symbol in self._quotes and time.monotonic() < self._quotes[symbol][0]:
                return dict(self._quotes[symbol][1])
            url = SPOT + f"/api/v3/ticker/24hr?symbol={symbol}"
            request = urllib.request.Request(url, headers={"User-Agent": "PITQuant/BTC-V0"})
            with urllib.request.urlopen(request, timeout=4) as response:
                raw = json.loads(response.read())
            now = utc_now()
            market_at = datetime.fromtimestamp(int(raw["closeTime"]) / 1000, UTC)
            if raw["symbol"] != symbol or not -5 <= (now - market_at).total_seconds() <= 30:
                raise ValueError("STALE_OR_INVALID_BTC_QUOTE")
            values = {
                "price": float(raw["lastPrice"]),
                "bid": float(raw["bidPrice"]),
                "ask": float(raw["askPrice"]),
                "change_24h_percent": float(raw["priceChangePercent"]),
            }
            if (
                not all(math.isfinite(v) for v in values.values())
                or min(values["price"], values["bid"], values["ask"]) <= 0
            ):
                raise ValueError("INVALID_BTC_QUOTE_VALUES")
            self._cached = {
                "status": "LIVE",
                "symbol": symbol,
                "currency": "EUR" if symbol == "BTCEUR" else "USDT",
                "source": "BINANCE_SPOT",
                "market_at": market_at.isoformat(),
                "retrieved_at": now.isoformat(),
                "refresh_seconds": 5,
                "usage": "DISPLAY_ONLY_NOT_PIT",
                **values,
            }
            self._expires = time.monotonic() + 5
            self._quotes[symbol] = (self._expires, self._cached)
            return dict(self._cached)

    def history(self, symbol: str = "BTCUSDT", chart_range: str = "LIVE") -> dict[str, Any]:
        """Display-only exchange prices, never feature or simulation inputs."""
        days = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365, "3Y": 1095, "MAX": 10000}
        if symbol not in {"BTCUSDT", "BTCEUR"} or chart_range not in {"LIVE", *days}:
            raise ValueError("INVALID_BTC_CHART_SELECTION")
        key = (symbol, chart_range)
        with self._lock:
            if key in self._histories and time.monotonic() < self._histories[key][0]:
                return dict(self._histories[key][1])
            now = utc_now()
            interval = "1m" if chart_range == "LIVE" else "1d"
            start = (
                None
                if chart_range == "LIVE"
                else int(
                    max(
                        datetime(2017, 8, 17, tzinfo=UTC), now - timedelta(days=days[chart_range])
                    ).timestamp()
                    * 1000
                )
            )
            points = []
            for _ in range(5):
                url = SPOT + f"/api/v3/klines?symbol={symbol}&interval={interval}&limit=1000"
                if start is not None:
                    url += f"&startTime={start}"
                request = urllib.request.Request(url, headers={"User-Agent": "PITQuant/BTC-V0"})
                with urllib.request.urlopen(request, timeout=4) as response:
                    raw = json.loads(response.read())
                for bar in raw:
                    closed_at = int(bar[6]) / 1000
                    price = float(bar[4])
                    if not math.isfinite(price) or price <= 0:
                        raise ValueError("INVALID_BTC_INTRADAY_PRICE")
                    if closed_at <= now.timestamp():
                        points.append({"time": int(bar[6]) // 1000 + 1, "value": price})
                if interval == "1m" or len(raw) < 1000:
                    break
                start = int(raw[-1][0]) + 86400000
            if not points or now.timestamp() - points[-1]["time"] > (
                180 if interval == "1m" else 172800
            ):
                raise ValueError("STALE_BTC_INTRADAY_HISTORY")
            if any(a["time"] >= b["time"] for a, b in pairwise(points)):
                raise ValueError("INVALID_BTC_INTRADAY_ORDER")
            result = {
                "status": "AVAILABLE",
                "symbol": symbol,
                "interval": interval,
                "points": points,
                "retrieved_at": now.isoformat(),
                "usage": "DISPLAY_ONLY_NOT_PIT",
            }
            self._histories[key] = (time.monotonic() + (60 if interval == "1m" else 3600), result)
            return dict(result)
