"""Display-only minute data: exclude unclosed bars and reject stale history."""

import io
import json

import pytest

from pitquant.btc.fixtures import T0
from pitquant.btc.quote import LiveQuote


def test_closed_minute_display_cache_and_stale_rejection(monkeypatch):
    now_ms = int(T0.timestamp() * 1000)
    bars = [
        [now_ms - 60000, 0, 0, 0, "100", 0, now_ms - 1],
        [now_ms, 0, 0, 0, "999", 0, now_ms + 59999],
    ]
    calls = []
    clock = [0.0]

    def fetch(*args, **kwargs):
        calls.append(1)
        return io.BytesIO(json.dumps(bars).encode())

    monkeypatch.setattr("urllib.request.urlopen", fetch)
    monkeypatch.setattr("pitquant.btc.quote.utc_now", lambda: T0)
    monkeypatch.setattr("pitquant.btc.quote.time.monotonic", lambda: clock[0])
    provider = LiveQuote()
    result = provider.history()
    assert result["points"] == [{"time": now_ms // 1000, "value": 100}]
    assert result["usage"] == "DISPLAY_ONLY_NOT_PIT"
    assert provider.history() == result
    assert len(calls) == 1
    clock[0] = 61
    bars[:] = [[now_ms - 300000, 0, 0, 0, "100", 0, now_ms - 240001]]
    with pytest.raises(ValueError, match="STALE"):
        provider.history()


def test_pair_caches_are_separate_and_daily_history_pages(monkeypatch):
    now_ms = int(T0.timestamp() * 1000)
    urls = []

    def fetch(request, **kwargs):
        url = request.full_url
        urls.append(url)
        if "ticker" in url:
            symbol = "BTCEUR" if "BTCEUR" in url else "BTCUSDT"
            return io.BytesIO(
                json.dumps(
                    {
                        "symbol": symbol,
                        "closeTime": now_ms,
                        "lastPrice": "80" if symbol == "BTCEUR" else "100",
                        "bidPrice": "79",
                        "askPrice": "101",
                        "priceChangePercent": "1",
                    }
                ).encode()
            )
        if len([u for u in urls if "klines" in u]) == 1:
            bars = [
                [
                    now_ms - (1001 - i) * 86400000,
                    0,
                    0,
                    0,
                    "80",
                    0,
                    now_ms - (1000 - i) * 86400000 - 1,
                ]
                for i in range(1000)
            ]
        else:
            bars = [[now_ms - 86400000, 0, 0, 0, "81", 0, now_ms - 1]]
        return io.BytesIO(json.dumps(bars).encode())

    monkeypatch.setattr("urllib.request.urlopen", fetch)
    monkeypatch.setattr("pitquant.btc.quote.utc_now", lambda: T0)
    provider = LiveQuote()
    assert provider.get()["price"] == 100
    assert provider.get("BTCEUR")["price"] == 80
    assert provider.get()["currency"] == "USDT"
    result = provider.history("BTCEUR", "MAX")
    assert len(result["points"]) == 1001
    assert result["symbol"] == "BTCEUR"
    assert result["interval"] == "1d"
    assert "interval=1d" in urls[-1] and "startTime=" in urls[-1]
    with pytest.raises(ValueError, match="INVALID_BTC_PAIR"):
        provider.get("BAD")
