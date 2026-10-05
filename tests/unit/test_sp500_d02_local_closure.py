# ruff: noqa: E501
"""D-02 local closure (ADR-0035): parser ``sp500-evidence-4``, S&P rename statements, share-class sets, 13F abbreviation bridge, monthly
boundaries. Release excerpts are REAL_EXTRACT (S&P DJI releases archived locally, shortened); anchors, securities, 13F lines are SYNTHETIC."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pitquant.config.settings import Settings
from pitquant.db.models import (
    SecurityIdentifierEvidence,
    SecuritySuccession,
)
from pitquant.universe.identity_bridge import (
    bridge_name_only,
    candidates_for,
    expand13f,
    n30d_key,
)
from pitquant.universe.sources.sp500_evidence import (
    PARSER_VERSION,
    Timing,
    collect_name_tickers,
    effective_session,
    parse_release,
)
from pitquant.universe.sources.sp500_renames import RenameStatement, parse_rename_statements
from pitquant.universe.sp500_anchor_graph import (
    AnchorNode,
    SegmentResult,
    reconstruct,
    sets_at,
)
from pitquant.universe.sp500_rename_links import ReleaseDoc, apply_rename_links
from tests.unit.test_identity_bridge import F13World
from tests.unit.test_sp500_anchor_graph import World, names

# ───────────────────────────────────────────── REAL_EXTRACT release excerpts
ORGANON = (
    "NEW YORK , May 27, 2021 / PRNewswire / -- Organon & Co. (NYSE: OGN) will be added to the S&P 500 prior to the open of trading on Thursday, June 3 , replacing HollyFrontier, "
    "which will be removed from the S&P 500 effective prior to the open of trading on Friday, June 4 . HollyFrontier will replace Service Properties Trust (NASD:SVC) in the S&P MidCap 400, "
    "and Service Properties Trust will replace Lannett Co Inc. (NYSE:LCI) in the S&P SmallCap 600 also effective prior to the open on June 4 ."
)
FOX = (
    'NEW YORK , March 14, 2019 / PRNewswire / -- S&P Dow Jones Indices ("S&P DJI") will make the following changes to the S&P 500 & S&P 100: Fox Corp. (NASD: FOXAV; FOXBV) will be added to the '
    "S&P 500 prior to the open of trading on Tuesday, March 19 . Fox will replace Twenty-First Century Fox Inc. (NASD: FOXA; FOX), which will be removed from the S&P 500 and S&P 100 effective prior to "
    "the open of trading on Wednesday, March 20 . For index purposes, S&P DJI considers Fox Corp. to be the surviving entity of Twenty-First Century Fox and therefore both the Class A and Class B "
    "common stock lines will continue to be included in the S&P 500."
)
KDP = (
    'NEW YORK , June 3, 2022 / PRNewswire / -- S&P Dow Jones Indices ("S&P DJI") will make the following changes to the S&P 500, S&P MidCap 400 and S&P SmallCap 600 indices: VICI Properties Inc. (NYSE:VICI) '
    "will replace Cerner Corp. (NASD: CERN) in the S&P 500 prior to the open of trading on Wednesday, June 8 . S&P 500 constituent Oracle Corp. (NYSE:ORCL) is acquiring Cerner in a deal expected to be completed soon. "
    "The following changes to the S&P 500, S&P MidCap 400 and S&P SmallCap 600 are being made to ensure each index is more representative of its market capitalization range. These changes will be effective "
    "prior to the open of trading on Tuesday, June 21 , (post close on Friday, June 17 ) to coincide with the quarterly rebalance: Keurig Dr Pepper Inc. (NASD:KDP) and ON Semiconductor Corp. (NASD: ON) will replace "
    "Under Armour Inc. (NYSE:UA/UAA) and IPG Photonics Corp. (NASD: IPGP) respectively in the S&P 500. Under Armour and IPG Photonics will replace Trinity Industries Inc. (NYSE:TRN) and Yelp Inc. (NYSE:YELP) respectively in the S&P MidCap 400."
)
EVERGY = (
    "NEW YORK , May 31, 2018 / PRNewswire / -- S&P Midcap 400 constituent Westar Energy Inc. (NYSE: WR), to be renamed Evergy, will replace Navient Corp. (NASD: NAVI) in the S&P 500, Navient will replace Westar Energy "
    "in the S&P Midcap 400 effective prior to the open of trading on Tuesday, June 5 ."
)
TESLA = (
    "NEW YORK , Dec. 11, 2020 / PRNewswire / -- S&P Dow Jones Indices will make the following changes to the S&P 500, S&P 100 and S&P MidCap 400 effective prior to the open of trading on Monday, December 21 : "
    "As previously announced on November 16 , Tesla Inc. (NASD:TSLA) will be added to the S&P 500. Tesla will replace Apartment Investment and Management Co. (NYSE:AIV). Tesla will also be added to the S&P 100, "
    "replacing Occidental Petroleum Corp. (NYSE:OXY)."
)
DOW = (
    "NEW YORK , March 26, 2019 / PRNewswire / -- Dow Inc. (NYSE: DOW) will be added to the S&P 500 prior to the open of trading on Tuesday, April 2 . Dow will replace Brighthouse Financial Inc. (NASD: BHF), "
    "which will be removed from the S&P 500 effective prior to the open of trading on Wednesday, April 3 ."
)
DELPHI = (
    "NEW YORK , Nov. 28, 2017 / PRNewswire / -- S&P 500 constituent Delphi Automotive plc (NYSE: DLPH), to be renamed Aptiv plc and trade under new symbol APTV, is spinning off Delphi Technologies in a transaction "
    "expected to be completed post close on Monday, December 4 , pending final conditions. The renamed Aptiv plc will remain in the S&P 500 following the spin-off transaction."
)
DOWDUPONT = (
    "NEW YORK , May 28, 2019 / PRNewswire / -- S&P 500 & 100 constituent DowDuPont Inc. (NYSE: DWDP) is spinning off Corteva in a transaction expected to be completed on June 3 . Post spin-off, DowDuPont will remain in "
    "the S&P 500 & 100 indices. It will change its name to DuPont de Nemours Inc. and its ticker symbol to DD. Fluor has a market capitalization more representative of the mid-cap market space."
)
GARDNER = (
    "NEW YORK , Feb. 27, 2020 / PRNewswire / -- Gardner Denver Holdings Inc. (NYSE:GDI) will replace Cimarex Energy Co. (NYSE :XEC) in the S&P 500 effective prior to the open of trading on Tuesday, March 3 . "
    'Immediately following its merger with the industrial segment business, Gardner Denver will have a name and ticker change to "new" Ingersoll Rand Inc. (NYSE:IR). Cimarex Energy has a market capitalization.'
)
BEMIS = (
    "NEW YORK , June 3, 2019 / PRNewswire / -- S&P MidCap 400 constituent Bemis Company Inc. (NYSE: BMS) will replace Mattel Inc. (NASD: MAT) in the S&P 500 effective prior to the open of trading on Friday, June 7 . "
    "Amcor Limited (ASX: AMC) is merging with Bemis in a transaction expected to be completed soon pending final conditions. The combined company will be considered US domiciled for index purposes, and Bemis will be "
    'treated as the surviving entity. Post merger, the company will be named Amcor plc and will trade on the New York Stock Exchange under ticker symbol "AMCR".'
)


def pairs(
    text: str, d: date, nt: dict[str, set[str]] | None = None
) -> dict[tuple[str, str], tuple[date | None, Timing]]:
    return {
        (c.added_ticker, c.removed_ticker): (c.stated_change_date, c.timing)
        for c in parse_release(text, d, nt)
    }


# ───────────────────────────────────────────── parser v4
def test_parser_version_is_bumped_so_v3_rows_are_never_mixed_in() -> None:
    assert PARSER_VERSION == "sp500-evidence-8"


def test_a_removal_named_without_ticker_never_takes_the_added_companys_ticker() -> None:
    """v3 bug: «OGN will be added … replacing HollyFrontier, which will be removed» produced a REMOVAL of OGN (the nearest earlier ticker)."""
    p = pairs(ORGANON, date(2021, 5, 27))
    assert ("", "OGN") not in p and not any(r == "OGN" for _a, r in p)
    assert p[("OGN", "")] == (date(2021, 6, 3), Timing.BEFORE_OPEN)
    # no ticker known for HollyFrontier -> no removal leg at all (never a guess)
    assert not any(a == "" and r for (a, r) in p)


def test_a_removal_ticker_comes_only_from_an_exact_name_in_an_earlier_official_release() -> None:
    earlier = collect_name_tickers(
        "HollyFrontier Corp. (NYSE: HFC) will be added to the S&P 500 prior to the open of trading on Monday, June 18 ."
    )
    assert ("hollyfrontier", "HFC") in earlier
    nt: dict[str, set[str]] = {}
    for k, t in earlier:
        nt.setdefault(k, set()).add(t)
    p = pairs(ORGANON, date(2021, 5, 27), nt)
    assert p[("", "HFC")] == (date(2021, 6, 4), Timing.BEFORE_OPEN) and p[("OGN", "")][0] == date(
        2021, 6, 3
    )
    # an ambiguous name (two tickers) is not used
    assert ("", "HFC") not in pairs(ORGANON, date(2021, 5, 27), {"hollyfrontier": {"HFC", "HFCX"}})


def test_multi_ticker_share_classes_are_enumerated_legs_with_their_own_dates() -> None:
    p = pairs(FOX, date(2019, 3, 14))
    assert p[("FOXAV", "")] == (date(2019, 3, 19), Timing.BEFORE_OPEN) and p[("FOXBV", "")][
        0
    ] == date(2019, 3, 19)
    assert p[("", "FOXA")][0] == date(2019, 3, 20) and p[("", "FOX")][0] == date(2019, 3, 20)


def test_respectively_with_share_class_slash_keeps_each_clause_date() -> None:
    p = pairs(KDP, date(2022, 6, 3))
    assert p[("VICI", "CERN")][0] == date(2022, 6, 8)  # the first sentence: NOT the rebalance date
    assert p[("ON", "IPGP")][0] == date(2022, 6, 21)
    assert (
        p[("KDP", "")][0] == date(2022, 6, 21)
        and p[("", "UA")][0] == date(2022, 6, 21)
        and p[("", "UAA")][0] == date(2022, 6, 21)
    )


def test_to_be_renamed_is_kept_in_the_added_name() -> None:
    (c,) = [x for x in parse_release(EVERGY, date(2018, 5, 31)) if x.added_ticker == "WR"]
    assert (
        c.removed_ticker == "NAVI"
        and c.stated_change_date == date(2018, 6, 5)
        and "to be renamed Evergy" in c.added_name
    )


def test_added_company_named_by_short_name_in_the_next_sentence() -> None:
    p = pairs(TESLA, date(2020, 12, 11))
    assert p[("TSLA", "AIV")] == (date(2020, 12, 21), Timing.BEFORE_OPEN)


def test_add_and_remove_with_different_dates_are_never_fused_into_one_pair() -> None:
    p = pairs(DOW, date(2019, 3, 26))
    assert (
        p[("DOW", "")][0] == date(2019, 4, 2)
        and p[("", "BHF")][0] == date(2019, 4, 3)
        and ("DOW", "BHF") not in p
    )


def test_after_close_of_friday_is_effective_at_the_next_session_open() -> None:
    assert effective_session(Timing.AFTER_CLOSE, date(2020, 5, 29)) == date(
        2020, 6, 1
    )  # Friday close -> Monday open
    assert effective_session(Timing.BEFORE_OPEN, date(2020, 5, 29)) == date(2020, 5, 29)
    assert effective_session(Timing.AFTER_CLOSE, date(2019, 12, 31)) == date(
        2020, 1, 2
    )  # 2020-01-01 is a holiday


# ───────────────────────────────────────────── S&P rename statements
def test_rename_statements_closed_forms() -> None:
    d = parse_rename_statements(DELPHI, date(2017, 11, 28))
    assert [(s.kind, s.old_name, s.new_name, s.new_ticker, s.remains_in_index) for s in d] == [
        ("TO_BE_RENAMED", "Delphi Automotive plc", "Aptiv plc", "APTV", True)
    ]
    dd = parse_rename_statements(DOWDUPONT, date(2019, 5, 28))
    assert [(s.old_name, s.new_name, s.new_ticker, s.remains_in_index) for s in dd] == [
        ("DowDuPont", "DuPont de Nemours Inc", "DD", True)
    ]
    g = parse_rename_statements(GARDNER, date(2020, 2, 27))
    assert [(s.kind, s.old_name, s.new_name, s.new_ticker, s.remains_in_index) for s in g] == [
        ("NAME_AND_TICKER", "Gardner Denver", "Ingersoll Rand Inc", "IR", False)
    ]
    b = parse_rename_statements(BEMIS, date(2019, 6, 3))
    assert [(s.kind, s.old_name, s.new_name, s.new_ticker) for s in b] == [
        ("SURVIVING_ENTITY", "Bemis", "Amcor plc", "AMCR")
    ]


def test_a_spin_off_without_a_rename_is_not_a_rename_statement() -> None:
    assert (
        parse_rename_statements(
            "S&P 500 constituent Merck & Co (NYSE: MRK) is spinning off Organon. Post spin-off, Merck will remain in the S&P 500 and 100 indices.",
            date(2021, 5, 27),
        )
        == []
    )


# ───────────────────────────────────────────── 13(f) bridge: fixed abbreviations, classes, sole class
def test_13f_abbreviations_are_a_fixed_table_and_never_touch_the_class() -> None:
    assert expand13f("HARRIS CORP DEL") == "HARRIS CORP"
    assert expand13f("SCRIPPS NETWORKS INTERACT IN") == "SCRIPPS NETWORKS INTERACTIVE INC"
    assert expand13f("TWENTY FIRST CENTY FOX INC") == "TWENTY FIRST CENTURY FOX INC"
    assert expand13f("ANADARKO PETE CORP") == "ANADARKO PETROLEUM CORP"
    assert (
        n30d_key("Celanese Corp. Series A")[1] == "A"
        and n30d_key("Alphabet Inc. Class C")[1] == "C"
    )
    assert n30d_key("Patterson Cos., Inc.")[0] == "patterson companies"


@pytest.fixture
def fw(session: Session) -> F13World:
    return F13World(session)


@pytest.fixture
def w(session: Session) -> World:
    return World(session)


def test_class_a_and_class_c_are_never_confused_and_a_sole_common_entry_serves_a_series_label(
    fw: F13World, session: Session
) -> None:
    fw.e13("2019Q1", "02079K305", "ALPHABET INC", "CAP STK CL A")
    fw.e13("2019Q1", "02079K107", "ALPHABET INC", "CAP STK CL C")
    assert [e.cusip for e in candidates_for(session, "Alphabet Inc. Class C", "2019Q1")] == [
        "02079K107"
    ]
    fw.e13(
        "2019Q1", "150870103", "CELANESE CORP DEL", "COM"
    )  # «Series A Common Stock»: the list carries ONE entry without a class
    assert [e.cusip for e in candidates_for(session, "Celanese Corp. Series A", "2019Q1")] == [
        "150870103"
    ]
    # two unclassed entries -> the sole-class tolerance does not apply (fail closed)
    fw.e13("2019Q1", "150870999", "CELANESE CORP DEL", "COM NEW")
    assert candidates_for(session, "Celanese Corp. Series A", "2019Q1") == []


def test_when_issued_lines_are_not_the_common_stock(fw: F13World, session: Session) -> None:
    fw.e13("2019Q1", "26078J100", "DOWDUPONT INC", "COM")
    fw.e13("2019Q1", "26078J118", "DOWDUPONT INC", "WHEN ISSUED", "ADDED")
    assert [e.cusip for e in candidates_for(session, "DowDuPont, Inc.", "2019Q1")] == ["26078J100"]


def test_name_only_bridge_resolves_with_abbreviations_and_is_idempotent(
    fw: F13World, session: Session
) -> None:
    fw.e13("2019Q1", "413875105", "HARRIS CORP DEL", "COM")
    sid = fw.sec("SYN Harris")
    fw.member(sid, "Harris Corp.", "NAME_ONLY")
    r1 = bridge_name_only(session)
    n1 = session.scalar(
        select(func.count())
        .select_from(SecurityIdentifierEvidence)
        .where(SecurityIdentifierEvidence.security_id == sid)
    )
    r2 = bridge_name_only(session)
    n2 = session.scalar(
        select(func.count())
        .select_from(SecurityIdentifierEvidence)
        .where(SecurityIdentifierEvidence.security_id == sid)
    )
    assert [b.status for b in r1] == [b.status for b in r2] == ["RESOLVED"] and n1 == n2 == 1


# ───────────────────────────────────────────── rename links: S&P statement + 13(f) verification
def _doc(d: date, text: str = "x") -> ReleaseDoc:
    return ReleaseDoc(d, f"https://press.spglobal.com/{d}-fixture", "a" * 64, "arch", text)


def _chain(fw: F13World, session: Session, *, replacement: bool = True) -> tuple[str, str]:
    """Anchor A (2017-09-30) holds «Delphi Automotive PLC», anchor B (2018-03-31) holds «Aptiv PLC»; both are SYNTHETIC name-only members.
    ``replacement=False``: the 13(f) list does not flag DELETED/ADDED (the identifier change is not verifiable)."""
    from pitquant.db.models import SP500Anchor, SP500AnchorMember
    from pitquant.universe.sources.spy_sec_anchors import PARSER_VERSION as ANCHOR_V

    anchors = []
    for i, d in enumerate((date(2017, 9, 30), date(2018, 3, 31))):
        a = SP500Anchor(as_of_date=d, source_type="SEC_N30D", evidence_tier="SEC_SCHEDULE_ANCHOR", form="N-30D", accession=f"F13-X{i}", filer_cik="0000884394", source_available_at=datetime(d.year, d.month, d.day, 23, tzinfo=UTC) + timedelta(days=40),
                        archive_id=fw.arch.archive_id, source_sha256="0" * 64, member_count=0, resolved_count=0, unresolved_count=0, excluded_count=0, status="VERIFIED", notes=[], parser_version=ANCHOR_V)  # fmt: skip
        session.add(a)
        anchors.append(a)
    session.flush()
    old, new = fw.sec("SYN Delphi"), fw.sec("SYN Aptiv")
    for anchor, sid, name in (
        (anchors[0], old, "Delphi Automotive PLC"),
        (anchors[1], new, "Aptiv PLC"),
    ):
        session.add(SP500AnchorMember(anchor_id=anchor.anchor_id, security_id=sid, cusip=None, isin=None, issuer_name=name, source_position=1, shares=1.0, value_usd=5e7, classification="INDEX_EQUITY_CANDIDATE", identity_basis="NAME_ONLY", status="RESOLVED"))  # fmt: skip
    session.flush()
    fw.e13("2017Q3", "G27823106", "DELPHI AUTOMOTIVE", "PLC SHS")
    fw.e13(
        "2017Q4", "G27823106", "DELPHI AUTOMOTIVE", "PLC SHS", "DELETED" if replacement else None
    )
    fw.e13("2017Q4", "G6095L109", "APTIV", "PLC SHS", "ADDED" if replacement else None)
    fw.e13("2018Q1", "G6095L109", "APTIV", "PLC SHS")
    return old, new


STATEMENT = RenameStatement(
    "TO_BE_RENAMED",
    "Delphi Automotive plc",
    "Aptiv plc",
    "DLPH",
    "APTV",
    True,
    "…to be renamed Aptiv plc … will remain in the S&P 500",
    date(2017, 11, 28),
)


def test_a_statement_plus_a_13f_identifier_change_links_the_two_securities_once(
    fw: F13World, session: Session, settings: Settings
) -> None:
    old, new = _chain(fw, session)
    st = [(_doc(date(2017, 11, 28)), STATEMENT)]
    r1 = apply_rename_links(session, settings, st)
    r2 = apply_rename_links(session, settings, st)
    assert [x.status for x in r1] == ["APPLIED"] and [x.status for x in r2] == ["ALREADY_LINKED"]
    (link,) = session.scalars(select(SecuritySuccession)).all()
    assert (
        link.security_predecessor_id,
        link.security_successor_id,
        link.membership_continuity,
    ) == (old, new, True)
    assert (
        link.event_type == "NAME_TICKER_IDENTIFIER_CHANGE_SAME_SECURITY"
        and link.source_hash == "a" * 64
        and link.effective_at is None
    )


def test_a_13f_change_alone_never_links_and_a_non_remaining_statement_never_links(
    fw: F13World, session: Session, settings: Settings
) -> None:
    _chain(fw, session)
    assert (
        apply_rename_links(session, settings, []) == []
    )  # 13F shows DELETED/ADDED, but there is no S&P statement
    not_remaining = RenameStatement(
        "TO_BE_RENAMED",
        "Delphi Automotive plc",
        "Aptiv plc",
        "DLPH",
        "APTV",
        False,
        "x",
        date(2017, 11, 28),
    )
    assert apply_rename_links(session, settings, [(_doc(date(2017, 11, 28)), not_remaining)]) == []
    assert session.scalars(select(SecuritySuccession)).all() == []


def test_a_statement_whose_13f_does_not_verify_is_skipped_with_the_reason(
    fw: F13World, session: Session, settings: Settings
) -> None:
    _chain(fw, session, replacement=False)
    (r,) = apply_rename_links(session, settings, [(_doc(date(2017, 11, 28)), STATEMENT)])
    assert (
        r.status == "SKIPPED"
        and "do not coincide" in r.reason
        and session.scalars(select(SecuritySuccession)).all() == []
    )


def test_a_statement_after_the_sealed_holdout_start_is_never_read(
    fw: F13World, session: Session, settings: Settings
) -> None:
    _chain(fw, session)
    late = RenameStatement(
        "TO_BE_RENAMED",
        "Delphi Automotive plc",
        "Aptiv plc",
        "DLPH",
        "APTV",
        True,
        "x",
        date(2023, 1, 5),
    )
    assert apply_rename_links(session, settings, [(_doc(date(2023, 1, 5)), late)]) == []


# ───────────────────────────────────────────── share-class set rule (graph)
def _class_world(w: World, adds: list[str], removes: list[str]) -> None:
    from pitquant.db.models import SP500Announcement, SP500MembershipEvent

    w.anchor(date(2019, 3, 15), ["OLD Class A", "OLD Class B", "X"])
    w.anchor(date(2019, 4, 15), ["NEW Class A", "NEW Class B", "X"])
    for kind, tickers, nm, eff in (
        ("ADD", adds, "SYN NEW Corp", date(2019, 3, 19)),
        ("REMOVE", removes, "SYN OLD Corp", date(2019, 3, 20)),
    ):
        for tk in tickers:
            ann = SP500Announcement(source_tier="OFFICIAL_SPDJI", source_url="u", archive_id=w.arch.archive_id, source_sha256="0" * 64, announcement_at=datetime(2019, 3, 14, tzinfo=UTC), stated_change_date=eff, timing="BEFORE_OPEN",
                                    added_ticker=tk if kind == "ADD" else "", added_name=nm if kind == "ADD" else "", removed_ticker=tk if kind == "REMOVE" else "", removed_name=nm if kind == "REMOVE" else "", reason_class="X", excerpt="e", notes=[], parser_version=PARSER_VERSION)  # fmt: skip
            w.s.add(ann)
            w.s.flush()
            w.s.add(SP500MembershipEvent(run_id="run-1", announcement_row_id=ann.announcement_row_id, added_ticker=tk if kind == "ADD" else None, removed_ticker=tk if kind == "REMOVE" else None, effective_at=datetime(eff.year, eff.month, eff.day, 13, 30, tzinfo=UTC),
                                         discovery_date=eff, source_tier="OFFICIAL_SPDJI", status="OFFICIAL_CONFIRMED", reason="t", created_at=datetime(2026, 10, 3, tzinfo=UTC)))  # fmt: skip
    w.s.flush()


def test_class_set_rule_resolves_when_ticker_count_equals_class_count(
    w: World, session: Session
) -> None:
    _class_world(w, ["NA", "NB"], ["OA", "OB"])
    rep = reconstruct(session, date(2019, 3, 18), date(2019, 4, 12))
    by = {c.date: c for c in rep.cohorts}
    assert rep.segments[0].status == "VALIDATED" and not rep.segments[0].windows
    assert names(w, by[date(2019, 3, 18)].members) == {"OLD Class A", "OLD Class B", "X"}
    assert names(w, by[date(2019, 4, 1)].members) == {"NEW Class A", "NEW Class B", "X"}


def test_class_set_rule_fails_closed_when_counts_differ(w: World, session: Session) -> None:
    _class_world(w, ["NA"], ["OA", "OB"])  # one added ticker for two classes: which class? unknown
    rep = reconstruct(session, date(2019, 4, 1), date(2019, 4, 12))
    seg = rep.segments[0]
    assert (
        seg.status != "VALIDATED" and seg.windows
    )  # the unresolved legs keep an uncertainty window
    assert all(c.status == "BLOCKED" for c in rep.cohorts)


# ───────────────────────────────────────────── monthly boundaries
def _node(d: date, members: set[str]) -> AnchorNode:
    return AnchorNode(
        "a", d, "T", "NPORT-P", datetime(2030, 1, 1, tzinfo=UTC), frozenset(members), 0, {}, {}, {}
    )


def _seg(windows: dict[str, tuple[date, date]]) -> SegmentResult:
    a, b = _node(date(2020, 3, 31), {"S"}), _node(date(2020, 6, 30), set())
    return SegmentResult(a, b, 0, False, False, "LOCAL_GAPS", [], windows, None, [])


def test_interval_boundaries_are_lo_exclusive_of_certainty_and_hi_inclusive() -> None:
    """A change with possible effective sessions [lo, hi] (hi = last possible session): at the open of ``hi`` it has CERTAINLY happened;
    before ``lo`` it has certainly not; between them forward and backward disagree (the ambiguity that blocks that cohort only)."""
    seg = _seg({"S": (date(2020, 5, 12), date(2020, 5, 14))})
    f, b = sets_at(seg, date(2020, 5, 11))
    assert f == b == frozenset({"S"})
    f, b = sets_at(seg, date(2020, 5, 12))
    assert f != b
    f, b = sets_at(seg, date(2020, 5, 13))
    assert f != b
    f, b = sets_at(seg, date(2020, 5, 14))
    assert f == b == frozenset()


def test_event_effective_exactly_at_the_decision_session_is_already_applied(
    w: World, session: Session
) -> None:
    w.anchor(date(2020, 3, 31), ["A", "B", "C"])
    w.anchor(date(2020, 6, 30), ["A", "B", "D"])
    w.event(
        "OFFICIAL_CONFIRMED", "D", "C", date(2020, 6, 1), date(2020, 6, 1)
    )  # «prior to the open of trading on Monday, June 1»
    rep = reconstruct(session, date(2020, 4, 1), date(2020, 6, 30))
    by = {c.date: c for c in rep.cohorts}
    assert names(w, by[date(2020, 5, 1)].members) == {"A", "B", "C"}
    assert names(w, by[date(2020, 6, 1)].members) == {"A", "B", "D"}


def test_one_cohorts_ambiguity_does_not_block_the_rest_of_the_segment(
    w: World, session: Session
) -> None:
    """A release without a date (DATE_TBA) announced 2020-05-12: the cohorts BEFORE the announcement are exact; only those after it are open."""
    from pitquant.db.models import SP500Announcement, SP500MembershipEvent

    w.anchor(date(2020, 3, 31), ["A", "B", "C"])
    w.anchor(date(2020, 6, 30), ["A", "B", "D"])
    ann = SP500Announcement(source_tier="OFFICIAL_SPDJI", source_url="u", archive_id=w.arch.archive_id, source_sha256="0" * 64, announcement_at=datetime(2020, 5, 12, tzinfo=UTC), stated_change_date=None, timing="TBA",
                            added_ticker="D", added_name="SYN D Corp", removed_ticker="C", removed_name="SYN C Corp", reason_class="X", excerpt="e", notes=[], parser_version=PARSER_VERSION)  # fmt: skip
    session.add(ann)
    session.flush()
    session.add(SP500MembershipEvent(run_id="run-1", announcement_row_id=ann.announcement_row_id, added_ticker="D", removed_ticker="C", effective_at=None, discovery_date=date(2020, 5, 12), source_tier="OFFICIAL_SPDJI", status="DATE_TBA", reason="t", created_at=datetime(2026, 10, 3, tzinfo=UTC)))  # fmt: skip
    session.flush()
    rep = reconstruct(session, date(2020, 4, 1), date(2020, 6, 30))
    st = {c.date: c.status for c in rep.cohorts}
    assert st[date(2020, 4, 1)] == "MEMBERSHIP_READY" and st[date(2020, 5, 1)] == "MEMBERSHIP_READY"
    assert st[date(2020, 6, 1)] == "BLOCKED"
    assert names(w, {c.date: c for c in rep.cohorts}[date(2020, 5, 1)].members) == {"A", "B", "C"}


def test_unconfirmed_discovery_leg_never_blocks_a_monthly_cohort(
    w: World, session: Session
) -> None:
    w.anchor(date(2020, 3, 31), ["A", "B", "C"])
    w.anchor(date(2020, 6, 30), ["A", "B", "C"])
    w.event("DISCOVERY_ONLY", "Z", None, None, date(2020, 5, 5))
    rep = reconstruct(session, date(2020, 4, 1), date(2020, 6, 30))
    assert all(c.status == "MEMBERSHIP_READY" for c in rep.cohorts)
