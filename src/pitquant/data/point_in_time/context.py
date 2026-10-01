"""PITContext: the single gateway through which feature engines read data (ARCHITECTURE §1).

Every accessor takes its ``as_of`` from the context and filters by availability. Engines
receive a ``PITContext`` and nothing else — they cannot reach the database directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.core.timeutils import require_aware
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.data.corporate_actions.adjust import (
    DividendEvent,
    SplitEvent,
    adjusted_closes_as_of,
)
from pitquant.data.point_in_time.engine import FactKey, PITGuard, facts_as_of
from pitquant.db.models import CorporateAction, Dividend, FundamentalFact, Price, Security
from pitquant.security_master.service import SecurityMaster, SecurityView
from pitquant.universe.index_membership import IndexUniverse, UniverseMember


@dataclass
class PITContext:
    session: Session
    as_of: datetime
    ingested_before: datetime | None = None  # data_version pin (reproducibility)
    membership_build: dict[str, str] | None = None  # index_code -> pinned build_id

    def __post_init__(self) -> None:
        self.as_of = require_aware(self.as_of, "as_of")

    # ── identity / universe ────────────────────────────────────────────────
    def _local_date(self, exchange: str) -> date:
        cal = get_calendar(exchange)
        local: date = pd.Timestamp(self.as_of).tz_convert(cal.tz).date()
        return local

    def security(self, security_id: str) -> SecurityView:
        sec = self.session.get_one(Security, security_id)
        return SecurityMaster(self.session).view(security_id, self._local_date(sec.exchange))

    def resolve(self, ticker: str, exchange: str) -> str:
        return SecurityMaster(self.session).resolve(ticker, exchange, self._local_date(exchange))

    def universe(self, index_code: str, exchange: str) -> list[UniverseMember]:
        pin = (self.membership_build or {}).get(index_code)
        return IndexUniverse(self.session).universe(index_code, self._local_date(exchange), pin)

    # ── prices ─────────────────────────────────────────────────────────────
    def raw_bars(self, security_id: str, lookback_sessions: int | None = None) -> pd.DataFrame:
        """Raw daily bars whose close is <= as_of (an unfinished session is never returned)."""
        rows = self.session.execute(
            select(
                Price.session_date,
                Price.open,
                Price.high,
                Price.low,
                Price.close,
                Price.volume,
                Price.bar_close_at,
            )
            .where(
                Price.security_id == security_id,
                Price.bar_close_at <= self.as_of,
                *([Price.ingested_at <= self.ingested_before] if self.ingested_before else []),
            )
            .order_by(Price.session_date)
        ).all()
        if rows:
            PITGuard(self.as_of, context=f"raw_bars:{security_id}").check_all(
                (f"bar:{r.session_date}", r.bar_close_at) for r in rows[-5:]
            )
        df = pd.DataFrame(
            rows, columns=["session_date", "open", "high", "low", "close", "volume", "bar_close_at"]
        ).set_index("session_date")
        return df.tail(lookback_sessions) if lookback_sessions else df

    def _events(self, security_id: str) -> tuple[list[SplitEvent], list[DividendEvent]]:
        splits = [
            SplitEvent(ca.ex_date, float(ca.ratio or 1.0), ca.announced_at)
            for ca in self.session.scalars(
                select(CorporateAction).where(
                    CorporateAction.security_id == security_id,
                    CorporateAction.action_type == "split",
                    CorporateAction.announced_at <= self.as_of,
                )
            )
        ]
        divs = [
            DividendEvent(d.ex_date, d.gross_amount, d.announced_at)
            for d in self.session.scalars(
                select(Dividend).where(
                    Dividend.security_id == security_id, Dividend.announced_at <= self.as_of
                )
            )
        ]
        return splits, divs

    def adjusted_closes(self, security_id: str, *, include_dividends: bool = True) -> pd.Series:
        bars = self.raw_bars(security_id)
        if bars.empty:
            return pd.Series(dtype=float)
        splits, divs = self._events(security_id)
        last = bars.index[-1]
        return adjusted_closes_as_of(
            bars["close"], splits, divs, self.as_of, last, include_dividends=include_dividends
        )

    # ── fundamentals ───────────────────────────────────────────────────────
    def facts(
        self, security_id: str, concepts: list[str] | None = None
    ) -> dict[FactKey, FundamentalFact]:
        return facts_as_of(
            self.session, security_id, self.as_of, concepts, ingested_before=self.ingested_before
        )
