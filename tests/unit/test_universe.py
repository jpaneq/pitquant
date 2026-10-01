"""Historical universes and survivorship bias (§4, §6, §93)."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from pitquant.core.errors import ProviderContractError
from pitquant.universe.events import (
    EventSource,
    EventType,
    IndexEventRecord,
    SourceConfidence,
    build_membership,
)
from pitquant.universe.index_membership import IndexUniverse, UniverseMember
from tests.conftest import sid

pytestmark = pytest.mark.pit


def test_historical_index_membership(market: Session) -> None:
    u = IndexUniverse(market)
    a, b, c, x1, x2, e = (sid(market, k) for k in ("S-A", "S-B", "S-C", "S-X1", "S-X2", "S-E"))
    assert set(u.universe_ids("SYN_SP500", date(2002, 1, 2))) == {a, b, x1, e}
    assert set(u.universe_ids("SYN_SP500", date(2008, 1, 2))) == {a, b, c, e}
    # Exclusion date is exclusive: on the effective date the member is already out.
    assert b in u.universe_ids("SYN_SP500", date(2009, 2, 16))
    assert b not in u.universe_ids("SYN_SP500", date(2009, 2, 17))
    assert set(u.universe_ids("SYN_SP500", date(2020, 1, 2))) == {a, x2, e}


def test_universe_never_built_from_current_constituents(market: Session) -> None:
    """The bankrupt and acquired companies are NOT current members but must appear in the past."""
    u = IndexUniverse(market)
    current = set(u.universe_ids("SYN_SP500", date(2025, 6, 2)))
    past = set(u.universe_ids("SYN_SP500", date(2005, 6, 1)))
    gone = past - current
    assert {sid(market, "S-B"), sid(market, "S-C")} <= gone


def test_universe_member_does_not_expose_future_exit(market: Session) -> None:
    members = IndexUniverse(market).universe("SYN_SP500", date(2008, 1, 2))
    assert all(isinstance(m, UniverseMember) for m in members)
    for m in members:
        assert not hasattr(m, "effective_to")
        assert not hasattr(m, "exclusion_reason")


def test_reinclusion_creates_gap(market: Session) -> None:
    u = IndexUniverse(market)
    n = sid(market, "S-N")
    assert n in u.universe_ids("SYN_IBEX35", date(2011, 1, 3))
    assert n not in u.universe_ids("SYN_IBEX35", date(2015, 1, 2))
    assert n in u.universe_ids("SYN_IBEX35", date(2019, 1, 2))


def test_membership_is_derived_from_events_with_causes(market: Session) -> None:
    """Every interval starts and ends with a sourced event (no cause-less entries/exits)."""
    from sqlalchemy import select

    from pitquant.db.models import IndexEvent, IndexMembership

    rows = market.scalars(
        select(IndexMembership).where(IndexMembership.index_code == "SYN_SP500")
    ).all()
    assert rows
    for r in rows:
        start = market.get_one(IndexEvent, r.source_event_id)
        assert start.event_type in ("INDEX_ADD", "INITIAL_SNAPSHOT")
        if r.effective_to is not None:
            assert r.exclusion_event_id is not None
            end = market.get_one(IndexEvent, r.exclusion_event_id)
            assert end.event_type == "INDEX_DELETE" and end.effective_date == r.effective_to


def test_crosscheck_only_sources_cannot_build_membership(session: Session) -> None:
    src = EventSource(
        "WIKIPEDIA",
        SourceConfidence.CROSSCHECK_ONLY,
        [IndexEventRecord("SP500", EventType.INDEX_ADD, date(2020, 1, 2), "w1", "k", "X")],
        "h",
    )
    with pytest.raises(ProviderContractError):
        build_membership(session, src, {"k": "irrelevant"})
