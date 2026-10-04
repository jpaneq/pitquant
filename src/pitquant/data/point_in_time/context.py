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

from pitquant.core.errors import LookAheadError
from pitquant.core.timeutils import require_aware
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.data.corporate_actions.adjust import (
    DividendEvent,
    SplitEvent,
    adjusted_closes_as_of,
)
from pitquant.data.point_in_time.engine import FactKey, PITGuard, facts_as_of
from pitquant.db.models import (
    CorporateAction,
    CorporateActionEvent,
    DataQualityIssue,
    DataSource,
    Dividend,
    FundamentalFact,
    Price,
    Security,
)
from pitquant.market.ca_resolve import collapse_equivalent
from pitquant.market.normalized import CorporateAction as NormalizedAction
from pitquant.market.normalized import CorporateActionKind, Provenance, SourceTier
from pitquant.market.total_return import InsufficientValuationError, TotalReturnResult
from pitquant.market.total_return import total_return as market_total_return
from pitquant.security_master.service import SecurityMaster, SecurityView
from pitquant.universe.index_membership import IndexUniverse, UniverseMember


@dataclass
class PITContext:
    session: Session
    as_of: datetime
    ingested_before: datetime | None = None  # data_version pin (reproducibility)
    membership_build: dict[str, str] | None = None  # index_code -> pinned build_id

    market_source: str | None = None  # optional research-only provider isolation

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
        selected_source = self.market_source
        if selected_source is None and self.session.scalar(
            select(Price.security_id)
            .join(DataSource)
            .where(
                Price.security_id == security_id,
                DataSource.name == "YAHOO_CHART:eod",
                Price.bar_close_at <= self.as_of,
            )
            .limit(1)
        ):
            selected_source = "YAHOO_CHART:eod"
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
                *(
                    [
                        Price.source_id.in_(
                            select(DataSource.source_id).where(DataSource.name == selected_source)
                        )
                    ]
                    if selected_source
                    else []
                ),
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

    def market_actions(self, security_id: str) -> list[NormalizedAction]:
        """Normalized corporate actions (ADR-0021) known at ``as_of``."""
        rows = self.session.scalars(
            select(CorporateActionEvent).where(
                CorporateActionEvent.security_id == security_id,
                *(
                    [CorporateActionEvent.provider.like("YAHOO_CHART:%")]
                    if self.market_source == "YAHOO_CHART:eod"
                    else []
                ),
                CorporateActionEvent.available_at <= self.as_of,
                *(
                    [CorporateActionEvent.ingested_at <= self.ingested_before]
                    if self.ingested_before
                    else []
                ),
            )
        ).all()
        # the same provider event re-ingested from a NEW version of the page/payload is ONE
        # event (append-only: a correction is a newer row); the latest version known wins
        latest: dict[tuple[str, str, str], CorporateActionEvent] = {}
        for r in sorted(rows, key=lambda x: x.ingested_at):
            latest[(r.provider, r.provider_event_id, r.event_type)] = r
        rows = list(latest.values())
        PITGuard(self.as_of, context=f"market_actions:{security_id}").check_all(
            (f"ca:{r.event_type}:{r.ex_date or r.effective_date}", r.available_at) for r in rows
        )
        return collapse_equivalent(
            [
                NormalizedAction(
                    security_key=security_id,
                    kind=CorporateActionKind(r.event_type),
                    available_at=r.available_at,
                    provenance=Provenance(
                        r.provider,
                        SourceTier(r.source_tier),
                        r.provider_event_id,
                        r.source_hash,
                        r.parser_version,
                        r.archive_id,
                    ),
                    announcement_date=r.announcement_date,
                    ex_date=r.ex_date,
                    record_date=r.record_date,
                    payment_date=r.payment_date,
                    effective_date=r.effective_date,
                    ratio=r.ratio,
                    cash_amount=r.cash_amount,
                    currency=r.currency,
                    target_key=r.target_security_id,
                    details=dict(r.details or {}),
                )
                for r in rows
            ]
        )

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
        # normalized table (ADR-0021): the source for vendor/official data from now on
        for a in self.market_actions(security_id):
            if a.kind in (CorporateActionKind.SPLIT, CorporateActionKind.REVERSE_SPLIT) and (
                a.ex_date and a.ratio
            ):
                splits.append(SplitEvent(a.ex_date, a.ratio, a.available_at))
            elif a.kind in (
                CorporateActionKind.CASH_DIVIDEND,
                CorporateActionKind.SPECIAL_DIVIDEND,
            ) and (a.ex_date and a.cash_amount is not None):
                divs.append(DividendEvent(a.ex_date, a.cash_amount, a.available_at))
        return splits, divs

    def total_return(self, security_id: str, start: date, end: date) -> TotalReturnResult:
        """Total return on RAW closes known at ``as_of`` and normalized actions known at
        ``as_of`` (``pitquant.market.total_return``). ``end`` after the last closed session
        is refused: the future is never read."""
        bars = self.raw_bars(security_id)
        if bars.empty or end > bars.index[-1]:
            raise LookAheadError(f"total_return {security_id}: end {end} not closed at as_of")
        closes = {d: float(c) for d, c in bars["close"].items()}
        self._refuse_unresolved_dividends(security_id, start, end)
        return market_total_return(closes, self.market_actions(security_id), start, end, self.as_of)

    def _refuse_unresolved_dividends(self, security_id: str, start: date, end: date) -> None:
        """A dividend whose ex-date the source does not publish cannot be placed in time: a
        window it may fall into has NO defined total return (never silently ignored)."""
        issues = self.session.scalars(
            select(DataQualityIssue).where(
                DataQualityIssue.security_id == security_id,
                DataQualityIssue.check_name == "ca_unresolved_ex_date",
                DataQualityIssue.resolved_at.is_(None),
            )
        ).all()
        for i in issues:
            lo, hi = (
                date.fromisoformat(i.details["window_from"]),
                date.fromisoformat(i.details["window_to"]),
            )
            if lo <= end and hi > start:
                raise InsufficientValuationError(
                    f"{security_id}: dividend with unknown ex-date "
                    f"(paid {i.details.get('payment_date')}) may fall in {start}..{end}"
                )

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
