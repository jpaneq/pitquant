"""Ephemeral display-only quote; never a feature, label or simulation price input."""

from __future__ import annotations

import json
import math
import time
import urllib.request
from datetime import UTC, datetime
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

    def get(self) -> dict[str, Any]:
        with self._lock:
            if self._cached is not None and time.monotonic() < self._expires:
                return dict(self._cached)
            url = SPOT + "/api/v3/ticker/24hr?symbol=BTCUSDT"
            request = urllib.request.Request(url, headers={"User-Agent": "PITQuant/BTC-V0"})
            with urllib.request.urlopen(request, timeout=4) as response:
                raw = json.loads(response.read())
            now = utc_now()
            market_at = datetime.fromtimestamp(int(raw["closeTime"]) / 1000, UTC)
            if raw["symbol"] != "BTCUSDT" or not -5 <= (now - market_at).total_seconds() <= 30:
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
                "symbol": "BTCUSDT",
                "currency": "USDT",
                "source": "BINANCE_SPOT",
                "market_at": market_at.isoformat(),
                "retrieved_at": now.isoformat(),
                "refresh_seconds": 5,
                "usage": "DISPLAY_ONLY_NOT_PIT",
                **values,
            }
            self._expires = time.monotonic() + 5
            return dict(self._cached)

    def history(self) -> dict[str, Any]:
        """Recent closed minute bars for display only; no database writes."""
        with self._lock:
            if self._history is not None and time.monotonic() < self._history_expires:
                return dict(self._history)
            request = urllib.request.Request(
                SPOT + "/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=1000",
                headers={"User-Agent": "PITQuant/BTC-V0"},
            )
            with urllib.request.urlopen(request, timeout=4) as response:
                raw = json.loads(response.read())
            now = utc_now()
            points = []
            for bar in raw:
                closed_at = int(bar[6]) / 1000
                price = float(bar[4])
                if not math.isfinite(price) or price <= 0:
                    raise ValueError("INVALID_BTC_INTRADAY_PRICE")
                if closed_at <= now.timestamp():
                    points.append({"time": int(bar[0]) // 1000 + 60, "value": price})
            if not points or now.timestamp() - points[-1]["time"] > 180:
                raise ValueError("STALE_BTC_INTRADAY_HISTORY")
            if any(a["time"] >= b["time"] for a, b in pairwise(points)):
                raise ValueError("INVALID_BTC_INTRADAY_ORDER")
            self._history = {
                "status": "AVAILABLE",
                "interval": "1m",
                "points": points,
                "retrieved_at": now.isoformat(),
                "usage": "DISPLAY_ONLY_NOT_PIT",
            }
            self._history_expires = time.monotonic() + 60
            return dict(self._history)
