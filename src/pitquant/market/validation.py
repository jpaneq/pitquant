"""Series validation and cross-source comparison for RAW daily bars (ADR-0023).

Nothing here repairs or drops data silently: every anomaly is COUNTED and listed, and a series
that violates an invariant is reported, not "corrected" with another source.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

from pitquant.data.calendars.market_calendar import MarketCalendar, get_calendar
from pitquant.market.normalized import MarketBar


def calendar_status(cal: MarketCalendar, d: date) -> str:
    """ok | pre_calendar | post_calendar | non_session."""
    if d < cal.first_session:
        return "pre_calendar"
    if d > cal.last_session:
        return "post_calendar"
    return "ok" if cal.is_session(d) else "non_session"


@dataclass
class SeriesReport:
    exchange: str
    n_bars: int
    first_date: date | None
    last_date: date | None
    duplicates: list[date] = field(default_factory=list)
    out_of_order: int = 0
    pre_calendar: int = 0  # before the calendar's first supported session (not stored)
    non_session: list[date] = field(default_factory=list)
    missing_sessions: list[date] = field(default_factory=list)  # sessions inside the range
    gap_runs: list[tuple[date, date, int]] = field(default_factory=list)  # (from, to, n)
    impossible: list[str] = field(default_factory=list)
    zero_volume: int = 0

    @property
    def n_missing(self) -> int:
        return len(self.missing_sessions)

    @property
    def clean(self) -> bool:
        return not (self.duplicates or self.out_of_order or self.non_session or self.impossible)


def validate_series(bars: Sequence[MarketBar], exchange: str) -> SeriesReport:
    cal = get_calendar(exchange)
    dates = [b.session_date for b in bars]
    rep = SeriesReport(exchange, len(bars), min(dates, default=None), max(dates, default=None))
    seen: set[date] = set()
    for i, b in enumerate(bars):
        d = b.session_date
        if d in seen:
            rep.duplicates.append(d)
        seen.add(d)
        if i and d < bars[i - 1].session_date:
            rep.out_of_order += 1
        st = calendar_status(cal, d)
        if st == "pre_calendar":
            rep.pre_calendar += 1
        elif st != "ok":
            rep.non_session.append(d)
        for name in ("open", "high", "low", "close"):
            v = getattr(b, name)
            if v is not None and (not math.isfinite(v) or v <= 0):
                rep.impossible.append(f"{d} {name}={v}")
        if b.volume is not None and (not math.isfinite(b.volume) or b.volume < 0):
            rep.impossible.append(f"{d} volume={b.volume}")
        hi, lo = b.high, b.low
        if hi is not None and lo is not None:
            for name in ("open", "close"):
                v = getattr(b, name)
                if v is not None and not (lo - 1e-9 <= v <= hi + 1e-9):
                    rep.impossible.append(f"{d} {name}={v} outside [{lo}, {hi}]")
        if b.volume == 0:
            rep.zero_volume += 1
    if rep.first_date and rep.last_date:
        start = max(rep.first_date, cal.first_session)
        sessions = cal.sessions(start, min(rep.last_date, cal.last_session))
        missing = [s for s in sessions if s not in seen]
        rep.missing_sessions = missing
        run: list[date] = []
        for s in missing:
            if run and cal.next_session(run[-1]) == s:
                run.append(s)
            else:
                if run:
                    rep.gap_runs.append((run[0], run[-1], len(run)))
                run = [s]
        if run:
            rep.gap_runs.append((run[0], run[-1], len(run)))
    return rep


@dataclass
class ComparisonStats:
    common: int = 0
    exact_matches: int = 0
    small_differences: int = 0
    large_differences: int = 0
    missing_dates_source_a: list[date] = field(default_factory=list)  # in B, absent in A
    missing_dates_source_b: list[date] = field(default_factory=list)  # in A, absent in B
    large_examples: list[str] = field(default_factory=list)
    field_exact: dict[str, int] = field(default_factory=dict)


def compare_bars(
    a: Iterable[MarketBar],
    b: Iterable[MarketBar],
    *,
    price_abs: float = 5e-5,
    small_rel: float = 5e-3,
    volume_small_rel: float = 5e-2,
    start: date | None = None,
    end: date | None = None,
) -> ComparisonStats:
    """Per common date: ``exact`` = every OHLCV field equal within ``price_abs`` (volume exact);
    ``small`` = every price within ``small_rel`` and volume within ``volume_small_rel``;
    otherwise ``large``. Dates present in only one source are listed. Neither side is ever
    modified or used to correct the other."""
    A = {
        x.session_date: x
        for x in a
        if (start is None or x.session_date >= start) and (end is None or x.session_date <= end)
    }
    B = {
        x.session_date: x
        for x in b
        if (start is None or x.session_date >= start) and (end is None or x.session_date <= end)
    }
    st = ComparisonStats(common=len(A.keys() & B.keys()))
    st.missing_dates_source_a = sorted(B.keys() - A.keys())
    st.missing_dates_source_b = sorted(A.keys() - B.keys())
    fields = ("open", "high", "low", "close", "volume")
    st.field_exact = dict.fromkeys(fields, 0)
    for d in sorted(A.keys() & B.keys()):
        x, y = A[d], B[d]
        exact = small = True
        worst: list[str] = []
        for f in fields:
            u, v = getattr(x, f), getattr(y, f)
            if u is None or v is None:
                if (u is None) != (v is None):
                    exact = small = False
                    worst.append(f"{f}: {u} vs {v}")
                continue
            if f == "volume":
                eq = u == v
                ok_small = abs(u - v) <= volume_small_rel * max(abs(u), abs(v), 1.0)
            else:
                eq = abs(u - v) <= price_abs
                ok_small = abs(u - v) <= small_rel * max(abs(u), abs(v))
            st.field_exact[f] += int(eq)
            exact &= eq
            small &= ok_small
            if not ok_small:
                worst.append(f"{f}: {u} vs {v}")
        if exact:
            st.exact_matches += 1
        elif small:
            st.small_differences += 1
        else:
            st.large_differences += 1
            if len(st.large_examples) < 10:
                st.large_examples.append(f"{d}: " + "; ".join(worst))
    return st


def runs_by_gap(dates: Mapping[date, object], max_gap_days: int = 7) -> list[tuple[date, date]]:
    """Contiguous stretches of a date set (calendar-day gap <= ``max_gap_days``)."""
    out: list[tuple[date, date]] = []
    ds = sorted(dates)
    for d in ds:
        if out and d - out[-1][1] <= timedelta(days=max_gap_days):
            out[-1] = (out[-1][0], d)
        else:
            out.append((d, d))
    return out
