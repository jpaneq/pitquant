"""Internal price series for Feature Engine V0 (ADR-0027).

Two SEPARATE concepts, both from RAW bars + corporate actions known at the decision time (never
vendor adjusted prices):

* ``split_adjusted``: OHLCV adjusted ONLY for splits/reverse splits (technical indicators).
* ``tr_index``: Total Return Index from raw prices, splits and cash dividends (momentum, relative
  strength, volatility, drawdown, labels).

Only bars with ``session < decision session`` are admitted: the last usable price is the previous
session close; nothing of the decision session enters.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

from pitquant.core.errors import DataQualityError
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.market.normalized import CorporateAction, CorporateActionKind
from pitquant.market.total_return import total_return

SHARE_KINDS = {
    CorporateActionKind.SPLIT,
    CorporateActionKind.REVERSE_SPLIT,
}


@dataclass
class PriceSeries:
    exchange: str
    decision_session: date
    split_adjusted: pd.DataFrame  # index session_date; open high low close volume
    tr_gross: (
        pd.Series
    )  # daily gross total-return factor R_t (index session_date, from the 2nd bar)
    tr_level: pd.Series  # TR index, 1.0 on the first bar
    raw_close: pd.Series
    n_bars: int

    @property
    def last_session(self) -> date | None:
        return None if self.raw_close.empty else self.raw_close.index[-1]

    def contiguous(self, n_returns: int) -> bool:
        """True iff the last ``n_returns + 1`` bars are consecutive NYSE sessions (no hole)."""
        if self.n_bars < n_returns + 1:
            return False
        idx = list(self.raw_close.index[-(n_returns + 1) :])
        cal = get_calendar(self.exchange)
        return idx == cal.sessions(idx[0], idx[-1])


def split_factor_series(dates: Sequence[date], actions: Sequence[CorporateAction]) -> pd.Series:
    """Cumulative factor f_d = product of ratios of splits anchored AFTER d: adj = raw / f."""
    splits = sorted(
        (
            (a.anchor_date, a.ratio)
            for a in actions
            if a.kind in SHARE_KINDS and a.anchor_date and a.ratio
        ),
        key=lambda x: x[0],
    )
    out = []
    for d in dates:
        f = 1.0
        for sd, r in splits:
            if sd > d:
                f *= r
        out.append(f)
    return pd.Series(out, index=list(dates), dtype=float)


def build_series(
    bars: pd.DataFrame,
    actions: Sequence[CorporateAction],
    decision_at: datetime,
    decision_session: date,
    exchange: str = "XNYS",
) -> PriceSeries:
    """``bars``: index session_date, columns open high low close volume (RAW)."""
    b = bars[bars.index < decision_session].sort_index()
    if not b.index.is_unique:
        raise DataQualityError("duplicate sessions in the price history")
    known = [a for a in actions if a.available_at < decision_at]
    if b.empty:
        empty = pd.Series(dtype=float)
        return PriceSeries(exchange, decision_session, b.copy(), empty, empty, empty, 0)
    f = split_factor_series(list(b.index), known)
    adj = pd.DataFrame(
        {
            "open": b["open"] / f,
            "high": b["high"] / f,
            "low": b["low"] / f,
            "close": b["close"] / f,
            "volume": b["volume"] * f,
        }
    )
    closes = {d: float(c) for d, c in b["close"].items()}
    start, end = b.index[0], b.index[-1]
    if len(b) == 1:
        gross = pd.Series(dtype=float)
        level = pd.Series([1.0], index=[start])
    else:
        # the engine refuses a window with an action on a day without a bar: the series is
        # then not computable and the caller records coverage_gap (fail closed)
        res = total_return(closes, known, start, end, decision_at)
        gross = pd.Series({s.session: s.gross for s in res.steps}, dtype=float)
        level = pd.concat([pd.Series([1.0], index=[start]), gross.cumprod()])
    return PriceSeries(
        exchange, decision_session, adj, gross, level, b["close"].astype(float), len(b)
    )
