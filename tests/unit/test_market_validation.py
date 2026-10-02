# ruff: noqa: E501
"""Alpha Vantage TIME_SERIES_DAILY adapter, series validation and provider comparison.
Payloads are SYNTHETIC fixtures in the vendor's documented layout (SYN, not real quotes)."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from pitquant.core.errors import DataQualityError
from pitquant.market.credentials import SourceStatus
from pitquant.market.normalized import MarketBar, Provenance, SourceTier
from pitquant.market.providers.alphavantage_daily import (
    AlphaVantageDailyProvider,
    parse_daily,
)
from pitquant.market.validation import compare_bars, validate_series

PROV = Provenance("SYN", SourceTier.FIXTURE, "x", "0" * 64, "syn-1")


def _payload(
    rows: dict[str, tuple[float, float, float, float, int]], tz: str = "US/Eastern"
) -> bytes:
    return json.dumps(
        {
            "Meta Data": {
                "2. Symbol": "SYN",
                "3. Last Refreshed": max(rows),
                "4. Output Size": "Compact",
                "5. Time Zone": tz,
            },
            "Time Series (Daily)": {
                d: {
                    "1. open": str(o),
                    "2. high": str(h),
                    "3. low": str(lo),
                    "4. close": str(c),
                    "5. volume": str(v),
                }
                for d, (o, h, lo, c, v) in rows.items()
            },
        }
    ).encode()


ROWS = {
    "2024-03-04": (10.0, 11.0, 9.5, 10.5, 1000),
    "2024-03-05": (10.5, 11.5, 10.0, 11.0, 1200),
    "2024-03-06": (11.0, 11.2, 10.8, 10.9, 900),
    "2024-03-09": (10.9, 11.0, 10.8, 10.9, 10),  # a Saturday
}


def _bars(payload: bytes) -> list[MarketBar]:
    return AlphaVantageDailyProvider().normalize("SYN", payload).bars


def test_parse_and_normalize_keeps_non_sessions_out_with_warning() -> None:
    batch = AlphaVantageDailyProvider().normalize("SYN", _payload(ROWS))
    assert [b.session_date for b in batch.bars] == [
        date(2024, 3, 4),
        date(2024, 3, 5),
        date(2024, 3, 6),
    ]
    assert any("2024-03-09" in w and "non_session" in w for w in batch.warnings)
    b = batch.bars[0]
    assert (b.open, b.close, b.volume, b.currency) == (10.0, 10.5, 1000.0, "USD")
    assert b.available_at.tzinfo is not None and b.vendor_adj_close is None
    assert (
        b.provenance.source_hash
        == AlphaVantageDailyProvider()
        .normalize("SYN", _payload(ROWS))
        .bars[0]
        .provenance.source_hash
    )


@pytest.mark.parametrize("key", ["Error Message", "Note", "Information"])
def test_error_payloads_are_refused_not_parsed_as_empty(key: str) -> None:
    with pytest.raises(DataQualityError, match=key):
        parse_daily(json.dumps({key: "premium endpoint"}).encode())


def test_wrong_timezone_and_malformed_rows_refused() -> None:
    with pytest.raises(DataQualityError, match="time zone"):
        _bars(_payload(ROWS, tz="UTC"))
    bad = json.loads(_payload(ROWS))
    del bad["Time Series (Daily)"]["2024-03-04"]["4. close"]
    with pytest.raises(DataQualityError, match="malformed"):
        parse_daily(json.dumps(bad).encode())


def test_no_key_means_blocked_and_url_never_leaks_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PITQUANT_ALPHAVANTAGE_API_KEY", raising=False)
    av = AlphaVantageDailyProvider(fetch=lambda u: _payload(ROWS))
    assert av.status() is SourceStatus.SOURCE_NOT_CONFIGURED
    with pytest.raises(Exception, match="SOURCE_NOT_CONFIGURED"):
        av.download("AAPL")
    monkeypatch.setenv("PITQUANT_ALPHAVANTAGE_API_KEY", "SECRETKEY123")
    body, redacted = av.download("AAPL", "compact")
    assert "SECRETKEY123" not in redacted and "function=TIME_SERIES_DAILY" in redacted
    assert "ADJUSTED" not in redacted and "outputsize=compact" in redacted
    assert body == _payload(ROWS)


def test_never_requests_adjusted_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PITQUANT_ALPHAVANTAGE_API_KEY", "k")
    assert "TIME_SERIES_DAILY_ADJUSTED" not in AlphaVantageDailyProvider().url("AAPL")


# ───────────────────────────── series validation ──────────────────────────────────────
def _bar(d: date, close: float = 10.0, **kw: float | None) -> MarketBar:
    return MarketBar(
        "S",
        d,
        kw.get("open", close),
        kw.get("high", close),
        kw.get("low", close),
        close,
        kw.get("volume", 5.0),
        "USD",
        datetime(d.year, d.month, d.day, 21, tzinfo=UTC),
        PROV,
    )  # type: ignore[arg-type]


def test_validate_series_reports_gaps_duplicates_order_and_non_sessions() -> None:
    bars = [_bar(date(2024, 3, 4)), _bar(date(2024, 3, 6)), _bar(date(2024, 3, 6)), _bar(date(2024, 3, 5)),
            _bar(date(2024, 3, 9)), _bar(date(2024, 3, 11))]  # fmt: skip
    r = validate_series(bars, "XNYS")
    assert r.duplicates == [date(2024, 3, 6)] and r.out_of_order == 1
    assert r.non_session == [date(2024, 3, 9)] and not r.clean
    assert r.missing_sessions == [date(2024, 3, 7), date(2024, 3, 8)]
    assert r.gap_runs == [(date(2024, 3, 7), date(2024, 3, 8), 2)]


def test_validate_series_impossible_values_and_pre_calendar() -> None:
    r = validate_series([_bar(date(2024, 3, 4), close=10.0, high=9.0, low=8.0)], "XNYS")
    assert r.impossible and "outside" in r.impossible[0]
    old = validate_series([_bar(date(1980, 12, 12)), _bar(date(2024, 3, 4))], "XNYS")
    assert old.pre_calendar == 1 and old.first_date == date(1980, 12, 12)  # reported, not crashed
    assert old.missing_sessions  # gap measured only from the calendar's first session


def test_clean_series_has_no_gaps() -> None:
    r = validate_series(
        _bars(_payload({k: v for k, v in ROWS.items() if k != "2024-03-09"})), "XNYS"
    )
    assert r.clean and r.n_missing == 0 and r.n_bars == 3


# ───────────────────────────── provider disagreement ──────────────────────────────────
def test_compare_bars_statistics_and_no_autocorrection() -> None:
    a = [
        _bar(date(2024, 3, 4), 10.0),
        _bar(date(2024, 3, 5), 10.0),
        _bar(date(2024, 3, 6), 10.0),
        _bar(date(2024, 3, 7), 10.0),
    ]
    b = [replace(a[0]), replace(a[1], close=10.02, high=10.02, low=10.0), replace(a[2], close=12.0, high=12.0, low=10.0),
         _bar(date(2024, 3, 8), 10.0)]  # fmt: skip
    snapshot = list(a)
    st = compare_bars(a, b)
    assert (st.exact_matches, st.small_differences, st.large_differences) == (1, 1, 1)
    assert st.missing_dates_source_b == [date(2024, 3, 7)]  # in A only
    assert st.missing_dates_source_a == [date(2024, 3, 8)]  # in B only
    assert st.large_examples and "2024-03-06" in st.large_examples[0]
    assert a == snapshot  # never modifies a source
