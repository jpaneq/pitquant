# ruff: noqa: E501
"""Yahoo chart adapter (free, keyless, unofficial): RAW restoration, completed sessions only, honest failures. Canned SYNTHETIC responses: no network."""

import json
from datetime import UTC, date, datetime

import pytest

from pitquant.core.errors import DataQualityError
from pitquant.market.normalized import CorporateActionKind
from pitquant.market.providers.yahoo import YahooChartMarketDataProvider

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)


def ts(y: int, m: int, d: int, hour: int = 14, minute: int = 30) -> int:
    return int(datetime(y, m, d, hour, minute, tzinfo=UTC).timestamp())


def body(rows, splits=None, divs=None, symbol="TST", currency="USD", gmt=-14400):
    q = {k: [r[i] for r in rows] for i, k in enumerate(("open", "high", "low", "close", "volume"))}
    return json.dumps(
        {
            "chart": {
                "result": [
                    {
                        "meta": {"symbol": symbol, "currency": currency, "gmtoffset": gmt},
                        "timestamp": [r[5] for r in rows],
                        "indicators": {
                            "quote": [q],
                            "adjclose": [{"adjclose": [r[3] for r in rows]}],
                        },
                        "events": {
                            "splits": {str(i): s for i, s in enumerate(splits or [])},
                            "dividends": {str(i): d for i, d in enumerate(divs or [])},
                        },
                    }
                ],
                "error": None,
            }
        }
    ).encode()


def row(day, price, vol=1000):
    return (price, price + 1, price - 1, price, vol, ts(2020, 8, day))


def test_prices_are_restored_to_RAW_with_the_splits_that_come_after() -> None:
    # adjusted history: 25.0 before a 4:1 split on 2020-08-31, 130 after
    rows = [row(27, 25.0), row(28, 25.0), row(31, 130.0)]
    split = {"date": ts(2020, 8, 31), "numerator": 4.0, "denominator": 1.0, "splitRatio": "4:1"}
    out = YahooChartMarketDataProvider().normalize("S", "TST", body(rows, [split]), NOW)
    closes = {b.session_date: b.close for b in out.bars}
    assert closes[date(2020, 8, 28)] == pytest.approx(100.0) and closes[
        date(2020, 8, 31)
    ] == pytest.approx(130.0)  # raw pre-split price = adjusted × 4
    pre = next(b for b in out.bars if b.session_date == date(2020, 8, 28))
    assert (
        pre.volume is None and "close" in pre.imputed_fields
    )  # volume before a split is withheld, not guessed
    post = next(b for b in out.bars if b.session_date == date(2020, 8, 31))
    assert post.volume == 1000 and post.imputed_fields == ()
    sp = [a for a in out.actions if a.kind is CorporateActionKind.SPLIT]
    assert len(sp) == 1 and sp[0].ratio == 4.0 and sp[0].ex_date == date(2020, 8, 31)


def test_dividend_amounts_are_restored_to_the_actual_payout() -> None:
    rows = [row(27, 25.0), row(31, 130.0)]
    split = {"date": ts(2020, 8, 31), "numerator": 4.0, "denominator": 1.0}
    div = {"date": ts(2020, 8, 27), "amount": 0.20}  # Yahoo: split-adjusted
    out = YahooChartMarketDataProvider().normalize("S", "TST", body(rows, [split], [div]), NOW)
    d = next(a for a in out.actions if a.kind is CorporateActionKind.CASH_DIVIDEND)
    assert (
        d.cash_amount == pytest.approx(0.80)
        and d.currency == "USD"
        and d.provenance.provider.startswith("YAHOO_CHART")
        and d.provenance.tier.value == "VENDOR"
    )


def test_a_session_that_has_not_closed_is_never_stored() -> None:
    # 2020-08-31 14:30 UTC is mid-session in New York: "now" is that same afternoon
    rows = [row(28, 100.0), row(31, 101.0)]
    out = YahooChartMarketDataProvider().normalize(
        "S", "TST", body(rows), datetime(2020, 8, 31, 15, 0, tzinfo=UTC)
    )
    assert [b.session_date for b in out.bars] == [date(2020, 8, 28)] and any(
        "not closed" in w for w in out.warnings
    )


def test_incomplete_rows_and_weekends_are_skipped_with_a_warning() -> None:
    rows = [(None, None, None, None, None, ts(2020, 8, 27)), row(29, 100.0)]  # 08-29 is a Saturday
    out = YahooChartMarketDataProvider().normalize("S", "TST", body(rows), NOW)
    assert out.bars == [] and any("non_session" in w for w in out.warnings)


def test_madrid_symbols_use_their_own_calendar_and_currency() -> None:
    rows = [(10.0, 11.0, 9.0, 10.5, 500, int(datetime(2026, 9, 30, 7, 0, tzinfo=UTC).timestamp()))]
    out = YahooChartMarketDataProvider().normalize(
        "S", "SAN.MC", body(rows, symbol="SAN.MC", currency="EUR", gmt=7200), NOW
    )
    assert (
        len(out.bars) == 1
        and out.bars[0].currency == "EUR"
        and out.bars[0].session_date == date(2026, 9, 30)
    )
    assert out.bars[0].available_at.hour in (15, 16)  # 17:30 Madrid close in UTC


def test_unsupported_exchanges_and_error_bodies_fail_loudly() -> None:
    with pytest.raises(DataQualityError, match="no calendar mapping"):
        YahooChartMarketDataProvider().normalize("S", "ASML.AS", body([row(28, 1.0)]), NOW)
    err = json.dumps(
        {
            "chart": {
                "result": None,
                "error": {
                    "code": "Not Found",
                    "description": "No data found, symbol may be delisted",
                },
            }
        }
    ).encode()
    with pytest.raises(DataQualityError, match="unusable"):
        YahooChartMarketDataProvider().normalize("S", "TST", err, NOW)


def test_url_asks_for_daily_bars_with_events_and_needs_no_key() -> None:
    p = YahooChartMarketDataProvider()
    u = p.url("SAN.MC", date(2024, 1, 1), date(2024, 2, 1))
    assert (
        "SAN.MC" in u
        and "interval=1d" in u
        and "events=div%2Csplit" in u
        and "period1=" in u
        and "key" not in u.lower()
        and "token" not in u.lower()
        and p.status().value
    )
