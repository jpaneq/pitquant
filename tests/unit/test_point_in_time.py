"""Look-ahead prevention for fundamentals and prices (§2–3, §7)."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from sqlalchemy.orm import Session

from pitquant.core.errors import LookAheadError
from pitquant.data.point_in_time.context import PITContext
from pitquant.data.point_in_time.engine import (
    PITGuard,
    PITRecord,
    as_of_view,
    latest_for_period,
)
from tests.conftest import ny, sid, utc

pytestmark = pytest.mark.pit


def test_no_future_financial_data(market: Session) -> None:
    """Exactly the prompt's example: Q3 2020 published 5-Nov-2020 is invisible on 31-Oct-2020."""
    a = sid(market, "S-A")
    q3 = date(2020, 9, 30)
    before = PITContext(market, ny(2020, 10, 31, 16, 0)).facts(a, ["revenue"])
    after = PITContext(market, ny(2020, 11, 5, 16, 0)).facts(a, ["revenue"])
    assert latest_for_period(before, "revenue", q3) is None
    hit = latest_for_period(after, "revenue", q3)
    assert hit is not None
    assert max(f.available_at for f in before.values()) <= ny(2020, 10, 31, 16, 0)
    # published 07:30 NY + 60 min lag -> available 08:30 NY, not before
    assert hit.available_at == ny(2020, 11, 5, 8, 30)
    early = PITContext(market, ny(2020, 11, 5, 8, 29)).facts(a, ["revenue"])
    assert latest_for_period(early, "revenue", q3) is None


def test_restatement_only_visible_after_publication(market: Session) -> None:
    a = sid(market, "S-A")
    pe = date(2010, 12, 31)
    original = latest_for_period(PITContext(market, ny(2011, 6, 1, 16, 0)).facts(a), "revenue", pe)
    restated = latest_for_period(PITContext(market, ny(2012, 1, 3, 16, 0)).facts(a), "revenue", pe)
    assert original is not None and restated is not None
    assert original.revision_id == 0 and restated.revision_id == 1
    assert restated.value == 1111.0 and original.value != 1111.0


def test_no_future_price_data(market: Session) -> None:
    a = sid(market, "S-A")
    intraday = PITContext(market, ny(2020, 6, 15, 12, 0)).raw_bars(a)
    at_close = PITContext(market, ny(2020, 6, 15, 16, 0)).raw_bars(a)
    assert intraday.index[-1] == date(2020, 6, 12)  # today's bar is unfinished
    assert at_close.index[-1] == date(2020, 6, 15)
    assert (pd.to_datetime(at_close["bar_close_at"], utc=True) <= ny(2020, 6, 15, 16, 0)).all()


def test_split_adjustment_is_as_of(market: Session) -> None:
    """A split must not alter the series seen by a snapshot taken before it happened."""
    a = sid(market, "S-A")
    pre_ctx = PITContext(market, ny(2014, 6, 6, 16, 0))
    post_ctx = PITContext(market, ny(2014, 6, 10, 16, 0))
    pre = pre_ctx.adjusted_closes(a, include_dividends=False)
    post = post_ctx.adjusted_closes(a, include_dividends=False)
    raw_pre = pre_ctx.raw_bars(a)["close"]
    d = date(2014, 6, 2)
    assert pre[d] == pytest.approx(raw_pre[d])  # split unknown-to-history yet: untouched
    assert post[d] == pytest.approx(raw_pre[d] / 2)  # after the ex-date: back-adjusted
    # Even though the split was ANNOUNCED on 2014-04-23, before the ex-date it is not applied.
    mid = PITContext(market, ny(2014, 5, 1, 16, 0)).adjusted_closes(a, include_dividends=False)
    assert mid[date(2014, 4, 1)] == pytest.approx(raw_pre[date(2014, 4, 1)])


def test_as_of_view_picks_latest_known_revision() -> None:
    recs = [
        PITRecord(("X", "eps"), date(2020, 3, 31), utc(2020, 5, 1), 1.0, 0),
        PITRecord(("X", "eps"), date(2020, 3, 31), utc(2020, 8, 1), 1.2, 1),
        PITRecord(("X", "eps"), date(2020, 6, 30), utc(2020, 8, 5), 2.0, 0),
    ]
    v = as_of_view(recs, utc(2020, 7, 1))
    assert v[(("X", "eps"), date(2020, 3, 31))].value == 1.0
    assert (("X", "eps"), date(2020, 6, 30)) not in v
    v2 = as_of_view(recs, utc(2020, 8, 2))
    assert v2[(("X", "eps"), date(2020, 3, 31))].value == 1.2


def test_guard_fails_loudly() -> None:
    g = PITGuard(utc(2020, 6, 15, 20, 0), context="t")
    g.check("ok", utc(2020, 6, 15, 20, 0))  # equality allowed
    with pytest.raises(LookAheadError):
        g.check("future", utc(2020, 6, 15, 20, 0, 1))
    with pytest.raises(LookAheadError):
        g.check_all([("a", utc(2020, 1, 1)), ("b", utc(2021, 1, 1))])


def test_canonical_source_isolation_preserves_ingestion_pin(market: Session) -> None:
    from sqlalchemy import select

    from pitquant.db.models import DataSource, Price

    a = sid(market, "S-A")
    original = market.scalars(select(Price).where(Price.security_id == a)).first()
    assert original is not None
    original.ingested_at = utc(2020, 1, 1)
    source = DataSource(name="YAHOO_CHART:eod", provider_type="market")
    market.add(source)
    market.flush()
    market.add(
        Price(
            security_id=a,
            session_date=original.session_date,
            source_id=source.source_id,
            open=200,
            high=210,
            low=190,
            close=205,
            volume=100,
            currency="USD",
            bar_close_at=original.bar_close_at,
            ingested_at=utc(2026, 10, 5),
        )
    )
    market.flush()
    now = utc(2026, 10, 6)
    canonical = PITContext(market, now).raw_bars(a)
    assert len(canonical) == 1 and canonical.iloc[0]["close"] == 205
    pinned = PITContext(market, now, ingested_before=utc(2026, 10, 4)).raw_bars(a)
    assert pinned.loc[original.session_date, "close"] == original.close
    explicit = PITContext(market, now, market_source="YAHOO_CHART:eod").raw_bars(a)
    assert explicit.index.is_unique and explicit.iloc[0]["close"] == 205
    assert (
        market.scalar(
            select(Price.close).where(
                Price.security_id == a,
                Price.session_date == original.session_date,
                Price.source_id == original.source_id,
            )
        )
        == original.close
    )
