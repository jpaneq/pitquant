"""Total return, dividends, splits, mergers and delisting returns (§8, §68–70)."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from pitquant.backtest.labels import excess_return
from pitquant.core.errors import DataQualityError
from pitquant.data.corporate_actions.adjust import (
    DividendEvent,
    SplitEvent,
    TerminalEvent,
    adjusted_closes_as_of,
    total_return,
)
from tests.conftest import utc

D = [date(2020, 1, d) for d in (2, 3, 6, 7, 8)]
ANN = utc(2019, 12, 1)


def closes(*v: float) -> pd.Series:
    return pd.Series(list(v), index=D[: len(v)], dtype=float)


def test_dividend_total_return() -> None:
    c = closes(100, 100, 99, 99)
    div = [DividendEvent(D[2], 1.0, ANN)]
    tr = total_return(c, [], div, D[0], D[3])
    assert tr == pytest.approx(0.0)  # price fell exactly by the dividend
    assert total_return(c, [], [], D[0], D[3]) == pytest.approx(-0.01)  # price-only would lie


def test_split_total_return_is_continuous() -> None:
    c = closes(100, 102, 51, 52)  # 2-for-1 on D[2]
    tr = total_return(c, [SplitEvent(D[2], 2.0, ANN)], [], D[0], D[3])
    assert tr == pytest.approx(0.04)


def test_reverse_split() -> None:
    c = closes(1.0, 1.1, 11.0)  # 1-for-10 reverse on D[2]
    tr = total_return(c, [SplitEvent(D[2], 0.1, ANN)], [], D[0], D[2])
    assert tr == pytest.approx(0.10)


def test_next_open_entry_price_used() -> None:
    c = closes(100, 110)
    assert total_return(c, [], [], D[0], D[1], entry_price=105) == pytest.approx(110 / 105 - 1)


def test_merger_handling_cash_consideration() -> None:
    c = closes(40, 45, 49)  # acquired for 50 cash after D[2]
    tr = total_return(c, [], [], D[0], D[4], terminal=TerminalEvent(D[2], 50.0, "acquired"))
    assert tr == pytest.approx(50 / 40 - 1)


def test_bankruptcy_delisting_return_is_minus_100pct() -> None:
    c = closes(5.0, 3.0, 1.0)
    tr = total_return(c, [], [], D[0], D[4], terminal=TerminalEvent(D[2], 0.0, "bankruptcy"))
    assert tr == pytest.approx(-1.0)


def test_missing_history_without_terminal_event_fails_loudly() -> None:
    with pytest.raises(DataQualityError):
        total_return(closes(5.0, 3.0), [], [], D[0], D[4])


def test_adjustment_ignores_events_not_yet_announced() -> None:
    c = closes(100, 100, 50, 50)
    late_announce = [SplitEvent(D[2], 2.0, utc(2020, 1, 7, 12))]
    adj = adjusted_closes_as_of(c, late_announce, [], utc(2020, 1, 6, 22), D[2])
    assert adj[D[0]] == 100  # announced after as_of: not applied
    adj2 = adjusted_closes_as_of(c, late_announce, [], utc(2020, 1, 8, 22), D[3])
    assert adj2[D[0]] == 50


def test_excess_return_definition() -> None:
    assert excess_return(0.05, 0.18) == pytest.approx(-0.13)  # §39 example
