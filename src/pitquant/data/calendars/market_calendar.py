"""Real exchange calendars and horizon arithmetic (ADR-0005, ADR-0008).

Wraps ``exchange_calendars`` behind a small interface. All returned instants are aware UTC.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import lru_cache

import exchange_calendars as xcals
import pandas as pd
from dateutil.relativedelta import relativedelta

from pitquant.core.errors import CalendarRangeError
from pitquant.core.timeutils import require_aware

CALENDAR_START = "1995-01-01"


def _ts(d: date) -> pd.Timestamp:
    return pd.Timestamp(d)


def _to_dt(t: pd.Timestamp) -> datetime:
    out: datetime = t.tz_convert("UTC").to_pydatetime()
    return out


class MarketCalendar:
    def __init__(self, code: str) -> None:
        self.code = code
        self._cal = xcals.get_calendar(code, start=CALENDAR_START)
        self.tz = str(self._cal.tz)
        self.first_session: date = self._cal.first_session.date()
        self.last_session: date = self._cal.last_session.date()

    # ── coverage ────────────────────────────────────────────────────────────
    def _check(self, d: date) -> None:
        if d < self.first_session or d > self.last_session:
            raise CalendarRangeError(
                f"{d} outside {self.code} calendar coverage "
                f"[{self.first_session}, {self.last_session}]"
            )

    # ── sessions ────────────────────────────────────────────────────────────
    def is_session(self, d: date) -> bool:
        self._check(d)
        return bool(self._cal.is_session(_ts(d)))

    def sessions(self, start: date, end: date) -> list[date]:
        self._check(start)
        self._check(end)
        return [s.date() for s in self._cal.sessions_in_range(_ts(start), _ts(end))]

    def session_on_or_after(self, d: date) -> date:
        self._check(d)
        return self._cal.date_to_session(_ts(d), direction="next").date()  # type: ignore[no-any-return]

    def session_on_or_before(self, d: date) -> date:
        self._check(d)
        return self._cal.date_to_session(_ts(d), direction="previous").date()  # type: ignore[no-any-return]

    def session_open(self, session: date) -> datetime:
        if not self.is_session(session):
            raise CalendarRangeError(f"{session} is not a {self.code} session")
        return _to_dt(self._cal.session_open(_ts(session)))

    def session_close(self, session: date) -> datetime:
        if not self.is_session(session):
            raise CalendarRangeError(f"{session} is not a {self.code} session")
        return _to_dt(self._cal.session_close(_ts(session)))

    def next_session(self, session: date) -> date:
        return self._cal.next_session(_ts(session)).date()  # type: ignore[no-any-return]

    # ── point-in-time helpers ───────────────────────────────────────────────
    def last_closed_session(self, as_of: datetime) -> date:
        """Latest session whose close is <= as_of: the last bar a model may use."""
        as_of = require_aware(as_of, "as_of")
        local_day = pd.Timestamp(as_of).tz_convert(self.tz).date()
        d = self.session_on_or_before(local_day)
        while self.session_close(d) > as_of:
            d = self._cal.previous_session(_ts(d)).date()
        return d

    def next_session_open(self, ts: datetime) -> datetime:
        """Open of the first session that opens STRICTLY after ``ts``."""
        ts = require_aware(ts, "ts")
        local_day = pd.Timestamp(ts).tz_convert(self.tz).date()
        d = self.session_on_or_after(local_day)
        while self.session_open(d) <= ts:
            d = self.next_session(d)
        return self.session_open(d)

    def execution_time(
        self, signal_at: datetime, mode: str = "next_open", delay: int = 0
    ) -> datetime:
        signal_at = require_aware(signal_at, "signal_at")
        open_ = self.next_session_open(signal_at)
        session = pd.Timestamp(open_).tz_convert(self.tz).date()
        for _ in range(delay):
            session = self.next_session(session)
        if mode == "next_open":
            return self.session_open(session)
        if mode == "next_close":
            return self.session_close(session)
        if mode == "next_vwap":
            raise NotImplementedError("next_vwap requires intraday data (not yet ingested)")
        raise ValueError(f"unknown execution mode {mode}")

    def horizon_end(self, start: datetime, months: int) -> date:
        """Session on/after (local start date + ``months`` calendar months). Never +N days."""
        start = require_aware(start, "start")
        local = pd.Timestamp(start).tz_convert(self.tz).date()
        return self.session_on_or_after(local + relativedelta(months=months))

    def available_after_publication(
        self, publication: date | datetime, lag_minutes: int
    ) -> datetime:
        """Conservative availability for a record published on ``publication``.

        * aware datetime → that instant + lag.
        * date only (``availability_precision = DATE_ONLY``) → see ``date_only_available_at``.
          ``lag_minutes`` does not apply: no hour is invented.
        """
        if isinstance(publication, datetime):
            return require_aware(publication, "publication") + timedelta(minutes=lag_minutes)
        return self.date_only_available_at(publication)

    def date_only_available_at(self, publication_date: date) -> datetime:
        """First session open STRICTLY after the END of ``publication_date`` in the market's
        local time (ADR-0018). A document dated D may have been published at 23:59 local,
        so it is never usable on D itself — not even after D's close."""
        end_of_day = pd.Timestamp(publication_date + timedelta(days=1)).tz_localize(self.tz)
        return self.next_session_open(_to_dt(end_of_day) - timedelta(microseconds=1))

    def first_sessions_of_months(self, start: date, end: date) -> list[date]:
        out: list[date] = []
        seen: set[tuple[int, int]] = set()
        for s in self.sessions(start, end):
            ym = (s.year, s.month)
            if ym not in seen:
                seen.add(ym)
                out.append(s)
        return out


@lru_cache(maxsize=8)
def get_calendar(code: str) -> MarketCalendar:
    return MarketCalendar(code)
