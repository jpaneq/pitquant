"""Filing availability policies (D-01 requirement 8 and 10).

``available_at`` is distinct from ``period_end`` AND from the filing date: it is the first
instant a signal may use the filing.

* ``conservative_session`` (default): a filing accepted during a session becomes usable at
  ``accepted_at + lag`` only if that is still before the session close; otherwise — and
  for anything accepted after the close, on weekends or holidays — it becomes usable at the
  next session open. A signal computed at the close of the acceptance day never sees an
  after-close filing.
* ``accepted_plus_lag``: ``accepted_at + lag`` (for intraday research only).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from pitquant.core.timeutils import require_aware
from pitquant.data.calendars.market_calendar import MarketCalendar


def filing_available_at(
    cal: MarketCalendar, accepted_at: datetime, policy: str, lag_minutes: int
) -> datetime:
    accepted_at = require_aware(accepted_at, "accepted_at")
    candidate = accepted_at + timedelta(minutes=lag_minutes)
    if policy == "accepted_plus_lag":
        return candidate
    if policy != "conservative_session":
        raise ValueError(f"unknown availability policy {policy}")
    local_day = pd.Timestamp(accepted_at).tz_convert(cal.tz).date()
    if cal.is_session(local_day):
        close = cal.session_close(local_day)
        if candidate < close:
            return candidate  # pre-market or intraday, usable the same session
        return cal.next_session_open(close)
    return cal.next_session_open(accepted_at)
