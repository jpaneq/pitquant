"""LOCAL/MANUAL: real Alpha Vantage free-tier call (AAPL, compact = last ~100 sessions).

Skipped ONLY when ``PITQUANT_ALPHAVANTAGE_API_KEY`` is absent. With a key every failure is a
failure (nothing is swallowed): ``PITQUANT_ALPHAVANTAGE_API_KEY=... pytest tests/real_api -q``.
"""

from __future__ import annotations

import os

import pytest

from pitquant.market.providers.alphavantage_daily import AlphaVantageDailyProvider
from pitquant.market.validation import validate_series

pytestmark = pytest.mark.skipif(
    not os.environ.get("PITQUANT_ALPHAVANTAGE_API_KEY"), reason="BLOCKED_BY_CREDENTIAL"
)


@pytest.mark.parametrize("symbol", ["AAPL", "MSFT"])
def test_real_compact_daily(symbol: str) -> None:
    av = AlphaVantageDailyProvider()
    body, redacted = av.download(symbol, "compact")
    assert os.environ["PITQUANT_ALPHAVANTAGE_API_KEY"] not in redacted
    batch = av.normalize(symbol, body)
    rep = validate_series(batch.bars, "XNYS")
    assert 90 <= rep.n_bars <= 110
    assert rep.clean and not rep.gap_runs
