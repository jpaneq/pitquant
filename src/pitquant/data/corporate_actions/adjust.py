"""As-of price adjustment and total return (ADR-0004).

Only RAW closes are stored. Adjusted series are rebuilt for a given ``as_of`` applying
exclusively events with ``ex_date <= as_of_session`` AND ``announced_at <= as_of``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

from pitquant.core.errors import DataQualityError
from pitquant.core.timeutils import require_aware


@dataclass(frozen=True)
class SplitEvent:
    ex_date: date
    ratio: float  # new shares per old share: 2-for-1 -> 2.0, 1-for-10 reverse -> 0.1
    announced_at: datetime

    def __post_init__(self) -> None:
        if self.ratio <= 0:
            raise DataQualityError(f"split ratio must be > 0, got {self.ratio}")
        require_aware(self.announced_at, "announced_at")


@dataclass(frozen=True)
class DividendEvent:
    ex_date: date
    amount: float  # gross, per share outstanding AFTER any same-day split
    announced_at: datetime

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise DataQualityError("dividend amount must be >= 0")
        require_aware(self.announced_at, "announced_at")


def _validate_closes(closes: pd.Series) -> pd.Series:
    if not closes.index.is_monotonic_increasing or closes.index.has_duplicates:
        raise DataQualityError("closes index must be strictly increasing session dates")
    if (closes <= 0).any() or closes.isna().any():
        raise DataQualityError("closes must be positive and non-null")
    return closes.astype(float)


def adjusted_closes_as_of(
    closes: pd.Series,
    splits: Sequence[SplitEvent],
    dividends: Sequence[DividendEvent],
    as_of: datetime,
    as_of_session: date,
    *,
    include_dividends: bool = True,
) -> pd.Series:
    """Back-adjusted closes up to ``as_of_session`` using only events known at ``as_of``.

    ``closes``: raw closes indexed by session ``date``. Rows after ``as_of_session`` are
    dropped first, so neither future prices nor future events can affect the output.
    """
    as_of = require_aware(as_of, "as_of")
    raw = _validate_closes(closes)
    raw = raw[raw.index <= as_of_session]
    if raw.empty:
        return raw
    factor = pd.Series(1.0, index=raw.index)
    idx = list(raw.index)

    for sp in splits:
        if sp.ex_date > as_of_session or sp.announced_at > as_of:
            continue
        factor[[d < sp.ex_date for d in idx]] /= sp.ratio

    if include_dividends:
        for dv in dividends:
            if dv.ex_date > as_of_session or dv.announced_at > as_of or dv.amount == 0:
                continue
            prior = [d for d in idx if d < dv.ex_date]
            if not prior:
                continue
            prev_close = float(raw[prior[-1]])
            if dv.amount >= prev_close:
                raise DataQualityError(
                    f"dividend {dv.amount} >= previous close {prev_close} on {dv.ex_date}"
                )
            factor[[d < dv.ex_date for d in idx]] *= 1.0 - dv.amount / prev_close

    return raw * factor


@dataclass(frozen=True)
class TerminalEvent:
    """How a position ends if the security disappears before the horizon (§68–69)."""

    date: date
    value_per_share: float  # cash consideration, last price, or 0.0 on bankruptcy
    reason: str


def total_return(
    closes: pd.Series,
    splits: Sequence[SplitEvent],
    dividends: Sequence[DividendEvent],
    start_session: date,
    end_session: date,
    *,
    entry_price: float | None = None,
    terminal: TerminalEvent | None = None,
) -> float:
    """Simple total shareholder return from ``start_session`` to ``end_session``.

    Daily relative: ``(close_t + div_t) * split_t / close_{t-1}``; dividends reinvested on
    the ex-date. ``entry_price`` overrides the start close (e.g. next-session OPEN fill).
    If ``terminal`` occurs before ``end_session`` the position is closed at its
    ``value_per_share`` (never dropped as missing data).
    """
    raw = _validate_closes(closes)
    split_on = {s.ex_date: s.ratio for s in splits}
    div_on: dict[date, float] = {}
    for d in dividends:
        div_on[d.ex_date] = div_on.get(d.ex_date, 0.0) + d.amount

    window = raw[(raw.index >= start_session) & (raw.index <= end_session)]
    if window.empty or window.index[0] != start_session:
        raise DataQualityError(f"no close on start session {start_session}")
    prev = float(window.iloc[0])
    # An OPEN fill on start_session already trades ex any same-day dividend/split.
    growth = prev / float(entry_price) if entry_price is not None else 1.0
    for d, c in list(window.items())[1:]:
        if terminal is not None and d > terminal.date:
            break
        growth *= (float(c) + div_on.get(d, 0.0)) * split_on.get(d, 1.0) / prev
        prev = float(c)
    if terminal is not None and terminal.date <= end_session:
        last_obs = window.index[window.index <= terminal.date]
        last_px = float(window[last_obs[-1]]) if len(last_obs) else prev
        growth *= terminal.value_per_share / last_px if last_px > 0 else 0.0
    elif window.index[-1] != end_session:
        raise DataQualityError(
            f"price history ends {window.index[-1]} before {end_session} without terminal event"
        )
    return growth - 1.0
