"""Labels: execution time, horizon end and label availability (§9, §33, §39)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from pitquant.core.timeutils import require_aware
from pitquant.core.types import ExecutionMode, Horizon
from pitquant.data.calendars.market_calendar import MarketCalendar


@dataclass(frozen=True)
class LabelWindow:
    signal_at: datetime  # = as_of
    t_exec: datetime  # first allowed fill
    label_end: datetime  # close of the horizon-end session
    label_available_at: datetime  # when the outcome is knowable (close + data lag)
    horizon: Horizon

    def __post_init__(self) -> None:
        if not (self.signal_at < self.t_exec < self.label_end <= self.label_available_at):
            raise ValueError(f"inconsistent label window {self}")


def label_window(
    cal: MarketCalendar,
    as_of: datetime,
    horizon: Horizon,
    *,
    execution_mode: ExecutionMode = ExecutionMode.NEXT_OPEN,
    delay_sessions: int = 0,
    data_lag_minutes: int = 60,
) -> LabelWindow:
    as_of = require_aware(as_of, "as_of")
    t_exec = cal.execution_time(as_of, execution_mode.value, delay_sessions)
    end_session = cal.horizon_end(t_exec, horizon.months)
    label_end = cal.session_close(end_session)
    return LabelWindow(
        signal_at=as_of,
        t_exec=t_exec,
        label_end=label_end,
        label_available_at=label_end + timedelta(minutes=data_lag_minutes),
        horizon=horizon,
    )


def excess_return(stock_tr: float, benchmark_tr: float) -> float:
    """Primary target: simple excess total return (stock TR − benchmark TR)."""
    return stock_tr - benchmark_tr
