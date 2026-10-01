"""Historical universes and survivorship bias (§4, §6, §93)."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from pitquant.core.errors import OverlappingIntervalError, ProviderContractError
from pitquant.data.providers.base import IndexMembershipProvider, MembershipRecord, ProviderInfo
from pitquant.jobs.ingest import ingest_memberships
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
        assert not hasattr(m, "exclusion_date")
        assert not hasattr(m, "exclusion_reason")


def test_reinclusion_creates_gap(market: Session) -> None:
    u = IndexUniverse(market)
    n = sid(market, "S-N")
    assert n in u.universe_ids("SYN_IBEX35", date(2011, 1, 3))
    assert n not in u.universe_ids("SYN_IBEX35", date(2015, 1, 2))
    assert n in u.universe_ids("SYN_IBEX35", date(2019, 1, 2))


def test_overlapping_membership_rejected(market: Session) -> None:
    with pytest.raises(OverlappingIntervalError):
        IndexUniverse(market).add_membership(
            security_id=sid(market, "S-A"), index_code="SYN_SP500", inclusion_date=date(2010, 1, 4)
        )


class _CurrentOnly(IndexMembershipProvider):
    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo("current-constituents-scraper", False, is_point_in_time=False)

    def memberships(self, index_code: str) -> list[MembershipRecord]:
        return []


def test_non_point_in_time_membership_provider_rejected(session: Session) -> None:
    with pytest.raises(ProviderContractError):
        ingest_memberships(session, _CurrentOnly(), "SP500")
