# ruff: noqa: E501
"""Market-data access for the Analyzer: ONE path for current analysis and for backtests.

``load_market(session, security_id, decision_at)`` returns only completed bars known at
``decision_at`` (``PITContext.raw_bars``) and the tier-resolved corporate actions known then; the
series are built by ``features.v0.series.build_series`` (the Feature Engine's own builder), so product
and research can never drift. ``decision_at`` is a parameter everywhere; ``now`` is only the value a
caller passes for the CURRENT view (never read inside an engine).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.data.point_in_time.context import PITContext
from pitquant.db.models import DataSource, Price, TickerHistory
from pitquant.features.v0.series import PriceSeries, build_series
from pitquant.market.normalized import CorporateAction

MARKET_ENGINE_VERSION = "market-series-1"
BENCHMARK_PREFERENCE = ("SPY", "VTI")  # SPY first; VTI only as an explicit fallback proxy


@dataclass
class MarketData:
    security_id: str
    decision_at: datetime
    exchange: str
    bars: pd.DataFrame  # RAW OHLCV, completed sessions only
    actions: list[CorporateAction]
    series: PriceSeries
    sources: list[str] = field(default_factory=list)
    last_close_at: datetime | None = None

    @property
    def last_session(self) -> date | None:
        return self.series.last_session


def load_market(
    session: Session,
    security_id: str,
    decision_at: datetime,
    exchange: str = "XNYS",
    *,
    market_source: str | None = None,
) -> MarketData:
    ctx = PITContext(session, decision_at, market_source=market_source)
    bars = ctx.raw_bars(security_id)
    actions = ctx.market_actions(security_id)
    if bars.empty:
        empty = build_series(bars, actions, decision_at, decision_at.date(), exchange)
        return MarketData(security_id, decision_at, exchange, bars, actions, empty)
    last = bars.index[-1]
    series = build_series(bars, actions, decision_at, last + timedelta(days=1), exchange)
    srcs = [
        n
        for (n,) in session.execute(
            select(DataSource.name)
            .join(Price, Price.source_id == DataSource.source_id)
            .where(Price.security_id == security_id, Price.bar_close_at <= decision_at)
            .distinct()
        )
    ]
    return MarketData(
        security_id,
        decision_at,
        exchange,
        bars,
        actions,
        series,
        sorted(srcs),
        bars["bar_close_at"].iloc[-1],
    )


def benchmark_security(session: Session) -> tuple[str, str] | None:
    """(security_id, ticker) of the first available benchmark proxy that has prices."""
    for t in BENCHMARK_PREFERENCE:
        sid = session.scalars(
            select(TickerHistory.security_id).where(TickerHistory.ticker == t)
        ).first()
        if (
            sid
            and (
                session.scalar(
                    select(func.count()).select_from(Price).where(Price.security_id == sid)
                )
                or 0
            )
            > 0
        ):
            return sid, t
    return None


def freshness(
    last_close_at: datetime | None, now: datetime, exchange: str = "XNYS"
) -> dict[str, object]:
    """EOD freshness: how many completed sessions old the latest bar is, and a status badge."""
    if last_close_at is None:
        return {"status": "NO_DATA", "sessions_behind": None, "age_hours": None}
    cal = get_calendar(exchange)
    last_completed = cal.last_closed_session(now)
    last_bar = pd.Timestamp(last_close_at).tz_convert(cal.tz).date()
    behind = (
        len([d for d in cal.sessions(last_bar, last_completed) if d > last_bar])
        if last_bar < last_completed
        else 0
    )
    age_h = (now - last_close_at).total_seconds() / 3600
    status = "EOD" if behind == 0 else "STALE"
    return {
        "status": status,
        "sessions_behind": behind,
        "age_hours": round(age_h, 1),
        "last_bar_session": str(last_bar),
        "last_completed_session": str(last_completed),
    }
