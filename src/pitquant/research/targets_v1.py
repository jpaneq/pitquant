# ruff: noqa: E501
"""Research targets V1 (ADR-0048): future total return, excess vs an EXPLICIT benchmark, outperform, direction (auxiliary) and drawdown risk targets.

* Entry = the last close KNOWN at ``decision_at`` (the same bar the features of that decision end at); exit = the close of the last session on or before ``decision_at`` + H calendar months.
  Both use the TOTAL-RETURN level of the security (a price level for an index symbol). The benchmark is read by INSTANT (its last close <= each instant), so a different calendar never leaks.
* Benchmark contract per exchange: XNYS -> SPY (``ETF_PROXY``, USD total return); XMAD -> ^IBEX (``PRICE_INDEX``: dividends missing, documented, understates the benchmark);
  every other exchange -> URTH (``MSCI_WORLD_ETF_PROXY``: USD ETF, ``CURRENCY_MISMATCH`` for non-USD securities). A proxy is never presented as the official index.
* Nothing is computed when the window is not elapsed, a price is missing, or the window touches the sealed holdout (no outcome is read: ``LABEL_WINDOW_TOUCHES_HOLDOUT``).
* ``label_available_at`` = exit close + 60 min: a model may use a target only after it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

from pitquant.research.features_v1 import SeriesBundle

TARGET_SET_VERSION = "research-targets-v1"
HORIZONS = (1, 3, 6, 12, 24)
PRIORITY_HORIZONS = (6, 12)
LAG = timedelta(minutes=60)
EPS = 1e-9  # float round-off at the exact threshold: -20% counts as >= 20%
MAX_INSTANT_GAP_DAYS = (
    7  # a benchmark bar older than this at an instant means the benchmark has a hole there
)


@dataclass(frozen=True)
class BenchmarkContract:
    ticker: str
    benchmark_type: str
    source: str
    notes: tuple[str, ...] = ()


US = BenchmarkContract("SPY", "ETF_PROXY", "SPY total-return ETF (USD)")
ES = BenchmarkContract(
    "^IBEX",
    "PRICE_INDEX",
    "IBEX 35 price index",
    ("NO_DIVIDENDS: price index understates the benchmark total return",),
)
WORLD = BenchmarkContract(
    "URTH",
    "MSCI_WORLD_ETF_PROXY",
    "iShares MSCI World ETF (USD), proxy only",
    ("PROXY_NOT_OFFICIAL_INDEX",),
)


def benchmark_for(exchange: str, currency: str) -> BenchmarkContract:
    if exchange == "XNYS":
        return US
    if exchange == "XMAD":
        return ES
    notes = WORLD.notes + (
        ("CURRENCY_MISMATCH: USD benchmark vs a non-USD security",) if currency != "USD" else ()
    )
    return BenchmarkContract(WORLD.ticker, WORLD.benchmark_type, WORLD.source, notes)


def _pos_at(b: SeriesBundle, instant: datetime) -> int | None:
    """Index of the last bar whose close is <= ``instant`` (None when there is none)."""
    t = np.datetime64(pd.Timestamp(instant).tz_convert("UTC").tz_localize(None), "ns")
    i = int(np.searchsorted(b.close_instants, t, side="right")) - 1
    return i if i >= 0 else None


def add_months(instant: datetime, months: int) -> datetime:
    r: datetime = instant + relativedelta(months=months)
    return r


def _unavailable(reason: str, h: int, avail: datetime) -> dict[str, Any]:
    return {
        "horizon_months": h,
        "status": "UNAVAILABLE",
        "reason": reason,
        "label_available_at": avail,
    }


def compute_targets(
    sec: SeriesBundle,
    bench: SeriesBundle | None,
    contract: BenchmarkContract,
    decision_at: datetime,
    holdout: tuple[date, date],
    horizons: tuple[int, ...] = HORIZONS,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    e = _pos_at(sec, decision_at)
    last_bar = pd.Timestamp(sec.close_instants[-1]).tz_localize("UTC").to_pydatetime()
    for h in horizons:
        target_at = add_months(decision_at, h)
        if holdout[0] <= decision_at.date() <= holdout[1]:
            out.append(_unavailable("DECISION_INSIDE_HOLDOUT", h, target_at + LAG))
            continue
        if decision_at.date() < holdout[0] <= target_at.date():
            out.append(_unavailable("LABEL_WINDOW_TOUCHES_HOLDOUT", h, target_at + LAG))
            continue
        if e is None:
            out.append(_unavailable("NO_PRICE_AT_DECISION", h, target_at + LAG))
            continue
        if last_bar < target_at.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
            days=1
        ):
            out.append(_unavailable("WINDOW_NOT_ELAPSED", h, target_at + LAG))
            continue
        x = _pos_at(sec, target_at)
        assert x is not None
        if x <= e:
            out.append(_unavailable("NO_PRICE_IN_WINDOW", h, target_at + LAG))
            continue
        lv = sec.level.iloc[e : x + 1].to_numpy(float)
        if np.isnan(lv).any():
            out.append(_unavailable("PRICE_GAP_IN_WINDOW", h, target_at + LAG))
            continue
        exit_close = pd.Timestamp(sec.close_instants[x]).tz_localize("UTC").to_pydatetime()
        ret = float(lv[-1] / lv[0] - 1.0)
        dd = float((lv / np.maximum.accumulate(lv)).min() - 1.0)
        row: dict[str, Any] = {
            "horizon_months": h, "status": "OK", "reason": None, "label_available_at": exit_close + LAG, "entry_session": sec.index[e], "exit_session": sec.index[x],
            "security_total_return": ret, "benchmark_total_return": None, "excess_total_return": None, "outperform": None, "direction_up": ret > 0.0,
            "max_drawdown": dd, "drawdown_10": dd <= -0.10 + EPS, "drawdown_15": dd <= -0.15 + EPS, "drawdown_20": dd <= -0.20 + EPS,
            "benchmark_ticker": contract.ticker, "benchmark_type": contract.benchmark_type, "benchmark_source": contract.source,
            "details": {"benchmark_notes": list(contract.notes), "security_return_type": sec.return_type, "entry_rule": "LAST_CLOSE_KNOWN_AT_DECISION"},
        }  # fmt: skip
        if bench is None:
            row["details"]["benchmark_status"] = "BENCHMARK_NOT_INGESTED"
        else:
            be, bx = _pos_at(bench, decision_at), _pos_at(bench, target_at)
            ok = be is not None and bx is not None and bx > be
            if ok:
                assert be is not None and bx is not None
                stale = (
                    decision_at
                    - pd.Timestamp(bench.close_instants[be]).tz_localize("UTC").to_pydatetime()
                ).days > MAX_INSTANT_GAP_DAYS or (
                    target_at
                    - pd.Timestamp(bench.close_instants[bx]).tz_localize("UTC").to_pydatetime()
                ).days > MAX_INSTANT_GAP_DAYS
                bl = bench.level.iloc[[be, bx]].to_numpy(float)
                if stale or np.isnan(bl).any():
                    row["details"]["benchmark_status"] = "BENCHMARK_GAP"
                else:
                    b_ret = float(bl[1] / bl[0] - 1.0)
                    row.update(
                        benchmark_total_return=b_ret,
                        excess_total_return=ret - b_ret,
                        outperform=ret > b_ret,
                    )
                    row["details"]["benchmark_status"] = "OK"
            else:
                row["details"]["benchmark_status"] = "BENCHMARK_NO_PRICE"
        out.append(row)
    return out
