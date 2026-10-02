# ruff: noqa: E501
"""Label Engine V0: 6M / 12M excess total return vs an explicit benchmark (ADR-0027).

* Entry: the OPEN of the decision session T (the features saw only information before it).
* Target date: T + 6 / 12 CALENDAR months; a non-session rolls to the first NYSE session after.
* Exit: the CLOSE of the target session (or the terminal event inside the window).
* Total return: raw prices + splits + cash dividends + supported corporate actions
  (``market.total_return``); never a vendor adjusted close. The entry-day action is excluded:
  a buyer at the open of an ex-date does not receive that dividend (the open is already ex).
* Benchmark: same entry/exit on the same sessions. ``benchmark_type = ETF_PROXY`` (SPY), never the
  official index.
* No BUY/HOLD/SELL: only ``excess_total_return`` and ``outperform``.
* A label is usable for training only at/after ``label_available_at`` (its outcome date + lag).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pandas as pd
from sqlalchemy.orm import Session

from pitquant.core.errors import LabelLeakageError
from pitquant.core.timeutils import require_aware
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.data.point_in_time.context import PITContext
from pitquant.market.total_return import InsufficientValuationError, total_return

LABEL_VERSION = "labels-v0.1"
BENCHMARK_NAME = "US_BENCHMARK_SPY_TOTAL_RETURN"
BENCHMARK_TYPE = "ETF_PROXY"
DATA_LAG_MINUTES = 60


@dataclass(frozen=True)
class Label:
    security_id: str
    decision_session: date
    horizon_months: int
    entry_session: date
    target_session: date
    label_available_at: datetime
    security_total_return: float | None
    benchmark_total_return: float | None
    excess_total_return: float | None
    outperform: bool | None
    status: str  # OK | UNAVAILABLE
    reason: str | None = None
    terminal: str | None = None
    benchmark: str = BENCHMARK_NAME
    benchmark_type: str = BENCHMARK_TYPE
    label_version: str = LABEL_VERSION


def target_session(decision_session: date, months: int, exchange: str = "XNYS") -> date:
    cal = get_calendar(exchange)
    return cal.horizon_end(cal.session_open(decision_session), months)


def _leg(
    bars: pd.DataFrame, ctx: PITContext, security_id: str, entry: date, target: date
) -> tuple[float | None, str | None, str | None]:
    """(total return, reason, terminal note) for one security from open(entry) to close(target)."""
    if entry not in bars.index:
        return None, "no_bar_at_entry", None
    window = bars[(bars.index >= entry) & (bars.index <= target)]
    open_entry, close_entry = float(window.loc[entry, "open"]), float(window.loc[entry, "close"])
    if not open_entry > 0:
        return None, "no_open_at_entry", None
    closes = {d: float(c) for d, c in window["close"].items()}
    try:
        res = total_return(
            closes, ctx.market_actions(security_id), entry, window.index[-1], ctx.as_of
        )
    except InsufficientValuationError as e:
        return None, f"valuation_unresolved: {e}", None
    except Exception as e:  # DataQualityError: an action on a day without a bar, etc.
        return None, f"data_quality: {e}", None
    if res.terminal is None and window.index[-1] != target:
        return None, "no_bar_at_target", None
    day1 = close_entry / open_entry
    return day1 * (1.0 + res.total_return) - 1.0, None, res.terminal


def compute_label(
    session: Session,
    security_id: str,
    benchmark_security_id: str,
    decision_session: date,
    months: int,
    *,
    exchange: str = "XNYS",
) -> Label:
    if months not in (6, 12):
        raise ValueError("labels exist for 6M and 12M only")
    cal = get_calendar(exchange)
    tgt = target_session(decision_session, months, exchange)
    avail = cal.session_close(tgt) + timedelta(minutes=DATA_LAG_MINUTES)
    ctx = PITContext(session, avail)  # outcome time: everything known when the label is knowable
    bars = ctx.raw_bars(security_id)
    bbars = ctx.raw_bars(benchmark_security_id)

    def fail(reason: str) -> Label:
        return Label(
            security_id,
            decision_session,
            months,
            decision_session,
            tgt,
            avail,
            None,
            None,
            None,
            None,
            "UNAVAILABLE",
            reason,
        )

    s_tr, s_reason, term = _leg(bars, ctx, security_id, decision_session, tgt)
    if s_tr is None:
        return fail(f"security: {s_reason}")
    b_tr, b_reason, _ = _leg(bbars, ctx, benchmark_security_id, decision_session, tgt)
    if b_tr is None:
        return fail(f"benchmark: {b_reason}")
    ex = s_tr - b_tr
    return Label(
        security_id,
        decision_session,
        months,
        decision_session,
        tgt,
        avail,
        s_tr,
        b_tr,
        ex,
        ex > 0,
        "OK",
        None,
        term,
    )


def assert_label_usable(label: Label, training_cutoff: datetime) -> None:
    """A label whose outcome is not yet knowable at ``training_cutoff`` must never train a model."""
    require_aware(training_cutoff, "training_cutoff")
    if label.status != "OK":
        raise LabelLeakageError(
            f"label {label.security_id} {label.decision_session} is {label.status}: {label.reason}"
        )
    if label.label_available_at > training_cutoff:
        raise LabelLeakageError(
            f"label for {label.decision_session} ({label.horizon_months}M) is available at {label.label_available_at}, after the training cutoff {training_cutoff}"
        )
