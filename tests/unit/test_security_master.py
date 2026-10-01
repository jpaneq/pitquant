"""Security Master: permanent ids, ticker reuse, ticker changes, delistings (§4–5)."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from pitquant.core.errors import OverlappingIntervalError, UnknownSecurityError
from pitquant.db.models import Security
from pitquant.security_master.service import SecurityMaster
from tests.conftest import sid

pytestmark = pytest.mark.pit


def test_ticker_reuse_resolves_to_different_securities_by_date(market: Session) -> None:
    sm = SecurityMaster(market)
    old = sm.resolve("SYNX", "XNYS", date(2002, 6, 3))
    new = sm.resolve("SYNX", "XNYS", date(2013, 6, 3))
    assert old == sid(market, "S-X1")
    assert new == sid(market, "S-X2")
    assert old != new
    with pytest.raises(UnknownSecurityError):  # gap: ticker unused 2003–2012
        sm.resolve("SYNX", "XNYS", date(2008, 1, 2))


def test_ticker_change_keeps_security_id(market: Session) -> None:
    sm = SecurityMaster(market)
    before = sm.resolve("SYNE", "XNYS", date(2016, 8, 31))
    after = sm.resolve("SYNF", "XNYS", date(2016, 9, 1))
    assert before == after == sid(market, "S-E")
    with pytest.raises(UnknownSecurityError):
        sm.resolve("SYNF", "XNYS", date(2016, 8, 31))  # new ticker unknown before the change


def test_delisted_companies_preserved(market: Session) -> None:
    bankrupt = market.get_one(Security, sid(market, "S-B"))
    acquired = market.get_one(Security, sid(market, "S-C"))
    assert bankrupt.delisted and bankrupt.delisting_reason == "bankruptcy"
    assert acquired.delisted and acquired.acquirer_security_id == sid(market, "S-A")
    # still resolvable historically
    assert SecurityMaster(market).resolve("SYNB", "XNYS", date(2005, 1, 3)) == bankrupt.security_id


def test_view_hides_future_delisting(market: Session) -> None:
    sm = SecurityMaster(market)
    b = sid(market, "S-B")
    assert sm.view(b, date(2008, 6, 2)).delisted is False
    assert sm.view(b, date(2008, 6, 2)).delisting_reason is None
    assert sm.view(b, date(2009, 3, 2)).delisted is False  # last trading day: not yet known
    with pytest.raises(UnknownSecurityError):
        sm.view(b, date(2009, 6, 1))  # no ticker after delisting


def test_overlapping_ticker_assignment_rejected(session: Session) -> None:
    sm = SecurityMaster(session)
    a = sm.register(name="A", exchange="XNYS", currency="USD")
    b = sm.register(name="B", exchange="XNYS", currency="USD")
    sm.add_ticker(a.security_id, "AAA", "XNYS", date(2010, 1, 1), date(2015, 1, 1))
    with pytest.raises(OverlappingIntervalError):
        sm.add_ticker(b.security_id, "AAA", "XNYS", date(2014, 6, 1))
    sm.add_ticker(b.security_id, "AAA", "XNYS", date(2015, 1, 1))  # adjacent is fine
    assert sm.resolve("AAA", "XNYS", date(2014, 12, 31)) == a.security_id
    assert sm.resolve("AAA", "XNYS", date(2015, 1, 1)) == b.security_id


def test_identifier_history(session: Session) -> None:
    sm = SecurityMaster(session)
    a = sm.register(name="A", exchange="XMAD", currency="EUR")
    sm.add_identifier(a.security_id, "ISIN", "ES0000000001", date(2000, 1, 1), date(2010, 1, 1))
    sm.add_identifier(a.security_id, "ISIN", "ES0000000002", date(2010, 1, 1))
    assert sm.resolve_identifier("ISIN", "ES0000000001", date(2005, 1, 1)) == a.security_id
    with pytest.raises(UnknownSecurityError):
        sm.resolve_identifier("ISIN", "ES0000000001", date(2011, 1, 1))
