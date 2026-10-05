"""UA issuer, distribution and reused ticker cannot create index membership."""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from pitquant.db.models import Issuer, Security, TickerHistory
from pitquant.universe.identity_bridge import candidates_for
from pitquant.universe.sources.sp500_evidence import parse_release
from pitquant.universe.sp500_anchor_graph import Resolver, load_anchors, reconstruct
from pitquant.universe.us_window_plan import _sec_for
from tests.unit.test_identity_bridge import F13World
from tests.unit.test_sp500_anchor_graph import World

pytestmark = pytest.mark.pit


def test_under_armour_classes_are_distinct_even_with_shared_issuer(session: Session):
    issuer = Issuer(name="Under Armour, Inc.", country="US")
    session.add(issuer)
    session.flush()
    a = Security(
        name="Under Armour, Inc. Class A",
        issuer_id=issuer.issuer_id,
        exchange="XNYS",
        currency="USD",
    )
    c = Security(
        name="Under Armour, Inc. Class C",
        issuer_id=issuer.issuer_id,
        exchange="XNYS",
        currency="USD",
        listing_start=date(2016, 4, 8),
    )
    session.add_all([a, c])
    session.flush()
    assert a.security_id != c.security_id
    assert a.issuer_id == c.issuer_id
    tickers = {
        "UA": [
            TickerHistory(
                security_id=a.security_id,
                ticker="UA",
                exchange="XNYS",
                valid_from=date(2014, 1, 1),
                valid_to=date(2016, 12, 6),
            ),
            TickerHistory(
                security_id=c.security_id,
                ticker="UA",
                exchange="XNYS",
                valid_from=date(2016, 12, 7),
            ),
        ],
        "UAA": [
            TickerHistory(
                security_id=a.security_id,
                ticker="UAA",
                exchange="XNYS",
                valid_from=date(2016, 12, 7),
            )
        ],
        "UA.C": [
            TickerHistory(
                security_id=c.security_id,
                ticker="UA.C",
                exchange="XNYS",
                valid_from=date(2016, 4, 8),
                valid_to=date(2016, 12, 6),
            )
        ],
    }
    assert _sec_for("UA", date(2016, 12, 6), tickers) == a.security_id
    assert _sec_for("UA", date(2016, 12, 7), tickers) == c.security_id
    assert _sec_for("UAA", date(2016, 12, 7), tickers) == a.security_id
    assert _sec_for("UA.C", date(2016, 4, 7), tickers) is None
    assert _sec_for("UA.C", date(2016, 4, 8), tickers) == c.security_id
    assert _sec_for("UA.C", date(2016, 12, 7), tickers) is None


def test_official_cusip_bridge_does_not_fuzzy_merge_classes(session: Session):
    fw = F13World(session)
    fw.e13("2016Q2", "904311107", "UNDER ARMOUR INC", "CL A")
    fw.e13("2016Q2", "904311206", "UNDER ARMOUR INC", "CL C")
    a = candidates_for(session, "Under Armour, Inc. Class A", "2016Q2")
    c = candidates_for(session, "Under Armour, Inc. Class C", "2016Q2")
    assert {r.cusip for r in a} == {"904311107"}
    assert {r.cusip for r in c} == {"904311206"}
    assert candidates_for(session, "Under Armur, Inc. Class C", "2016Q2") == []


@pytest.mark.parametrize(
    "text",
    [
        "Under Armour Class C (NYSE: UA.C) begins trading April 8, 2016.",
        "Under Armour Class C (NYSE: UA.C) shares distributed April 7, 2016. "
        "Class A remains in the S&P 500.",
        "Under Armour expects Class C stock to qualify for S&P 500 inclusion "
        "at the discretion of S&P.",
    ],
)
def test_corporate_or_listing_evidence_is_not_an_index_event(text):
    assert parse_release(text, date(2016, 4, 7)) == []


@pytest.mark.parametrize("confirmed", [False, True])
def test_class_c_missing_index_notice_blocks_month_despite_listing(session: Session, confirmed):
    w = World(session)
    w.anchor(date(2016, 3, 31), ["UA_A"], form="N-30D")
    w.anchor(date(2016, 9, 30), ["UA_A", "UA_C"], form="N-30D")
    a = session.get_one(Security, w.security("UA_A"))
    c = session.get_one(Security, w.security("UA_C"))
    # Fixture-only setup: production securities are never updated by this task.
    c.listing_start = date(2016, 4, 8)
    session.flush()
    if confirmed:
        w.event("OFFICIAL_CONFIRMED", "UA_C", None, date(2016, 4, 8), date(2016, 4, 8))
    report = reconstruct(session, date(2016, 5, 1), date(2016, 9, 30))
    assert (report.ready == 5) is confirmed
    if confirmed:
        assert {a.security_id, c.security_id} <= report.cohorts[0].members
    else:
        assert all(r.status == "BLOCKED" for r in report.cohorts)
    resolver = Resolver(session, load_anchors(session))
    assert resolver._by_containment("SYN UA_C Corp") == {c.security_id}
    assert resolver._by_containment("SYN UA_CC Corp") == set()


def test_reviewed_alias_specs_preserve_classes_and_do_not_claim_index_date():
    from scripts.apply_under_armour_ticker_evidence import alias_specs

    annual = (
        'Our Class A Common Stock was listed on the NYSE under the symbol "UA" '
        'until December 6, 2016 and under the symbol "UAA" since December 7, 2016. '
        'Our Class C Common Stock was listed on the NYSE under the symbol "UA.C" '
        "since its initial issuance on April 8, 2016 and until December 6, 2016 "
        'and under the symbol "UA" since December 7, 2016.'
    )
    occ = "UA: 904311107 UA.C: 904311206 Class A Common Shares Class C Common Shares"
    aliases = alias_specs(annual, occ)
    assert aliases[0] == ("904311107", "UA", None, date(2016, 12, 6), "PARTIAL")
    assert aliases[2] == ("904311206", "UA.C", date(2016, 4, 8), date(2016, 12, 6), "EXACT")
    assert aliases[3][0] != aliases[0][0]  # recycled UA belongs to a different class
    with pytest.raises(ValueError, match="class-specific"):
        alias_specs(annual.replace("Class C", "Class A"), occ)
    with pytest.raises(ValueError, match="CUSIP"):
        alias_specs(annual, occ.replace("904311206", "904311107"))
