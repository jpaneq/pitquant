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
