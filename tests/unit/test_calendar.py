"""Real calendars, time zones, DST and execution timing (§9–10)."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from pitquant.core.errors import CalendarRangeError, NaiveDatetimeError
from pitquant.data.calendars.market_calendar import get_calendar
from tests.conftest import MAD, ny, utc

pytestmark = pytest.mark.pit


def test_market_calendar_holidays() -> None:
    nyse, bme = get_calendar("XNYS"), get_calendar("XMAD")
    assert not nyse.is_session(date(2020, 7, 3))  # Independence Day observed
    assert not nyse.is_session(date(2020, 4, 10))  # Good Friday
    assert not bme.is_session(date(2020, 4, 10))  # Good Friday (BME)
    assert not bme.is_session(date(2020, 12, 25))
    assert bme.is_session(date(2020, 10, 12))  # Spanish national holiday, but BME trades
    assert not nyse.is_session(date(2020, 6, 13))  # Saturday


def test_early_closes() -> None:
    assert get_calendar("XNYS").session_close(date(2020, 11, 27)) == utc(2020, 11, 27, 18, 0)
    assert get_calendar("XMAD").session_close(date(2020, 12, 24)) == utc(2020, 12, 24, 13, 0)


def test_timezone_and_dst() -> None:
    nyse = get_calendar("XNYS")
    # 16:00 New York is 21:00 UTC in winter and 20:00 UTC in summer.
    assert nyse.session_close(date(2020, 1, 15)) == utc(2020, 1, 15, 21, 0)
    assert nyse.session_close(date(2020, 7, 15)) == utc(2020, 7, 15, 20, 0)
    # US/EU DST mismatch week (US switched 2020-03-08, EU 2020-03-29).
    assert nyse.session_open(date(2020, 3, 16)) == utc(2020, 3, 16, 13, 30)
    assert get_calendar("XMAD").session_open(date(2020, 3, 16)) == utc(2020, 3, 16, 8, 0)


def test_naive_datetime_rejected() -> None:
    with pytest.raises(NaiveDatetimeError):
        get_calendar("XNYS").next_session_open(datetime(2020, 6, 15, 16, 0))


def test_next_session_execution() -> None:
    nyse = get_calendar("XNYS")
    # Signal after Friday close -> Monday open.
    assert nyse.next_session_open(ny(2020, 6, 12, 16, 0)) == utc(2020, 6, 15, 13, 30)
    # After Thursday 2-Jul close: Friday 3-Jul is a holiday -> Monday open.
    assert nyse.next_session_open(ny(2020, 7, 2, 16, 0)) == utc(2020, 7, 6, 13, 30)
    # Exactly at the open is NOT allowed (strictly after).
    assert nyse.next_session_open(ny(2020, 6, 15, 9, 30)) == utc(2020, 6, 16, 13, 30)
    t = nyse.execution_time(ny(2020, 6, 12, 16, 0), "next_close")
    assert t == utc(2020, 6, 15, 20, 0)
    with pytest.raises(NotImplementedError):
        nyse.execution_time(ny(2020, 6, 12, 16, 0), "next_vwap")


def test_last_closed_session_excludes_unfinished_bar() -> None:
    nyse = get_calendar("XNYS")
    assert nyse.last_closed_session(ny(2020, 6, 15, 15, 59)) == date(2020, 6, 12)
    assert nyse.last_closed_session(ny(2020, 6, 15, 16, 0)) == date(2020, 6, 15)


def test_horizon_uses_calendar_months_and_rolls_to_session() -> None:
    nyse = get_calendar("XNYS")
    # 2020-06-15 + 6 months = 2020-12-15 (a Tuesday session); NOT +180 days (2020-12-12, Saturday).
    assert nyse.horizon_end(ny(2020, 6, 15, 9, 30), 6) == date(2020, 12, 15)
    # 2019-07-04 + 12 months lands on 2020-07-04 (Sat) -> next session Monday 2020-07-06.
    assert nyse.horizon_end(ny(2019, 7, 5, 9, 30), 12) == date(2020, 7, 6)
    assert get_calendar("XMAD").horizon_end(datetime(2020, 6, 25, 9, 0, tzinfo=MAD), 6) == date(
        2020, 12, 28
    )


def test_date_only_publication_is_conservative() -> None:
    nyse = get_calendar("XNYS")
    assert nyse.available_after_publication(date(2020, 11, 5), 60) == utc(2020, 11, 5, 22, 0)
    # weekend filing -> Monday close + lag
    assert nyse.available_after_publication(date(2020, 11, 7), 0) == utc(2020, 11, 9, 21, 0)


def test_out_of_range_dates_fail() -> None:
    with pytest.raises(CalendarRangeError):
        get_calendar("XNYS").is_session(date(1980, 1, 2))
