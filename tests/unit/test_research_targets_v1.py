# ruff: noqa: E501
"""Research targets V1: benchmark by instant, holdout sealing, drawdown, excess. SYNTHETIC bars."""

from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest

from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.research import features_v1 as FT
from pitquant.research import targets_v1 as TG
from tests.unit.test_research_features_v1 import synth_bars

HOLD = (date(2022, 10, 1), date(2025, 9, 30))

pytestmark = pytest.mark.pit


def mk(
    seed: int, drift: float = 0.0003, start: date = date(2015, 1, 5), end: date = date(2020, 12, 31)
) -> FT.SeriesBundle:
    cal = get_calendar("XNYS")
    days = cal.sessions(start, end)
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(rng.normal(drift, 0.01, len(days))))
    return FT.build_bundle(
        f"SYN-{seed}",
        f"SYN{seed}",
        "XNYS",
        pd.DataFrame(
            {"open": c, "high": c * 1.005, "low": c * 0.995, "close": c, "volume": 1e6},
            index=pd.Index(days),
        ),
        [],
    )


def at(d: date) -> datetime:
    return get_calendar("XNYS").session_open(d)


def test_excess_is_security_minus_benchmark_and_outperform_consistent():
    s, b = mk(1), mk(2)
    t = TG.compute_targets(s, b, TG.US, at(date(2016, 3, 1)), HOLD, (6,))[0]
    assert t["status"] == "OK"
    assert t["excess_total_return"] == pytest.approx(
        t["security_total_return"] - t["benchmark_total_return"]
    )
    assert t["outperform"] == (t["excess_total_return"] > 0) and t["direction_up"] == (
        t["security_total_return"] > 0
    )


def test_entry_is_last_known_close_exit_is_horizon_end_and_label_after_exit():
    s = mk(1)
    d = at(date(2016, 3, 1))
    t = TG.compute_targets(s, mk(2), TG.US, d, HOLD, (6,))[0]
    assert t["entry_session"] < date(2016, 3, 1)  # the bar BEFORE the decision session
    assert (
        t["exit_session"] <= date(2016, 9, 1) and (date(2016, 9, 1) - t["exit_session"]).days <= 5
    )
    assert (
        t["label_available_at"]
        > pd.Timestamp(s.close_instants[s.index.get_loc(t["exit_session"])])
        .tz_localize("UTC")
        .to_pydatetime()
    )


def test_window_not_elapsed_is_unavailable():
    s = mk(1, end=date(2016, 6, 30))
    t = TG.compute_targets(s, None, TG.US, at(date(2016, 3, 1)), HOLD, (6, 1))
    assert t[0]["status"] == "UNAVAILABLE" and t[0]["reason"] == "WINDOW_NOT_ELAPSED"
    assert t[1]["status"] == "OK"


def test_holdout_is_never_read():
    s = mk(1, start=date(2019, 1, 2), end=date(2026, 9, 30))
    inside = TG.compute_targets(s, None, TG.US, at(date(2023, 1, 3)), HOLD, (6,))[0]
    touching = TG.compute_targets(s, None, TG.US, at(date(2022, 6, 1)), HOLD, (6, 24))
    assert inside["reason"] == "DECISION_INSIDE_HOLDOUT"
    assert [x["reason"] for x in touching] == ["LABEL_WINDOW_TOUCHES_HOLDOUT"] * 2 and all(
        "security_total_return" not in x for x in touching
    )
    assert (
        TG.compute_targets(s, None, TG.US, at(date(2025, 10, 1)), HOLD, (1,))[0]["status"] == "OK"
    )  # after the holdout: out-of-time diagnostic


def test_max_drawdown_and_flags():
    cal = get_calendar("XNYS")
    days = cal.sessions(date(2016, 1, 4), date(2017, 6, 30))
    path = np.full(len(days), 100.0)
    path[60:120] = 80.0  # -20% inside the window
    path[120:] = 90.0
    s = FT.build_bundle(
        "SYN-D",
        "SYND",
        "XNYS",
        pd.DataFrame(
            {"open": path, "high": path, "low": path, "close": path, "volume": 1e6},
            index=pd.Index(days),
        ),
        [],
    )
    t = TG.compute_targets(s, None, TG.US, at(days[30]), HOLD, (6,))[0]
    assert (
        t["max_drawdown"] == pytest.approx(-0.20)
        and t["drawdown_10"]
        and t["drawdown_15"]
        and t["drawdown_20"]
    )


def test_missing_benchmark_gives_no_excess_and_says_why():
    t = TG.compute_targets(mk(1), None, TG.US, at(date(2016, 3, 1)), HOLD, (6,))[0]
    assert (
        t["excess_total_return"] is None
        and t["outperform"] is None
        and t["details"]["benchmark_status"] == "BENCHMARK_NOT_INGESTED"
    )


def test_benchmark_is_read_by_instant_not_by_session_date():
    """A benchmark on another calendar is read at its last close <= the decision instant, never at a later one."""
    b = mk(2)
    d = at(date(2016, 3, 1))
    pos = TG._pos_at(b, d)
    assert pos is not None and pd.Timestamp(b.close_instants[pos]).tz_localize("UTC") <= d


def test_benchmark_contract_per_exchange_is_explicit():
    assert TG.benchmark_for("XNYS", "USD").benchmark_type == "ETF_PROXY"
    es = TG.benchmark_for("XMAD", "EUR")
    assert (
        es.ticker == "^IBEX"
        and es.benchmark_type == "PRICE_INDEX"
        and any("NO_DIVIDENDS" in n for n in es.notes)
    )
    w = TG.benchmark_for("XLON", "GBP")
    assert (
        w.benchmark_type == "MSCI_WORLD_ETF_PROXY"
        and any("CURRENCY_MISMATCH" in n for n in w.notes)
        and not any("CURRENCY_MISMATCH" in n for n in TG.benchmark_for("XTSE", "USD").notes)
    )


def test_synth_helper_is_labelled_synthetic():
    assert synth_bars().shape[0] > 0 and mk(1).security_id.startswith("SYN")
