# ruff: noqa: E501
"""S&P 500 membership evidence: temporal semantics, release parsing, discovery matching, replay.
Release texts are REAL_EXTRACT (S&P releases republished by PRNewswire, archived locally);
only the sentences needed are kept. Discovery rows mimic the community CSV layout."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from pitquant.core.errors import DataQualityError
from pitquant.universe.sources.sp500_evidence import (
    Announcement,
    DiscoveryRow,
    EventStatus,
    ReplayEvent,
    SourceTier,
    Timing,
    effective_at,
    effective_session,
    match_discovery,
    members_at_open,
    parse_discovery_csv,
    parse_release,
    replay_events,
    undo_events,
)

# 2010-12-22 17:52 ET, «Standard & Poor's Announces Changes to U.S. Indices»
MMI = (
    "NEW YORK , Dec. 22, 2010 /PRNewswire/ -- S&P will make the following changes to the S&P 500, S&P MidCap 400, "
    "and S&P SmallCap 600 Indices after the close of trading on Monday, January 3, 2011 : Motorola Mobility Holdings "
    "Inc. (NYSE: MMI ) will replace Meredith Corp. (NYSE: MDP ) in the S&P 500 index, Meredith will replace Cincinnati "
    "Bell Inc. (NYSE: CBB ) in the S&P MidCap 400 index, and Cincinnati Bell will replace Penford Corp. (NASD: PENX) "
    "in the S&P SmallCap 600 index. S&P 500 constituent Motorola (NYSE: MOT ) is spinning off Motorola Mobility Holdings "
    "to its shareholders in a transaction expected to be completed after the market close on or about that date."
)
# 2011-03-29 17:44 ET
BLK = (
    "NEW YORK , March 29, 2011 /PRNewswire/ -- BlackRock Inc. (NYSE: BLK ) will replace Genzyme Corp. (NASD: GENZ) in "
    "the S&P 500 index after the close of trading on Friday, April 1, 2011 . S&P Global 1200 constituent Sanofi-aventis "
    "(NYSE: SNY ) is acquiring Genzyme in a deal expected to be completed soon, pending final conditions. Following is a "
    "summary of the change: S&P 500 INDEX – April 1, 2011 COMPANY GICS ECONOMIC SECTOR ADDED BlackRock DELETED Genzyme"
)
# 2011-01-26 18:07 ET: intent without a date
TBA = (
    "NEW YORK , Jan. 26, 2011 /PRNewswire/ -- Covidien plc (NYSE: COV ) will replace McAfee Inc. (NYSE: MFE ) in the "
    "S&P 500 index after the close of trading on a date to be announced. McAfee is being acquired by S&P 100 & 500 "
    "constituent Intel Corp. (Nasdaq: INTC ) in a deal expected to be completed soon. Following is a summary of the "
    "change: S&P 500 INDEX – TBA COMPANY GICS ADDED Covidien DELETED McAfee"
)
# Ensco: wording of the S&P release of 2012-07-26 as given by the owner (the release text is NOT archived yet)
ESV_CLAUSE = (
    "NEW YORK , July 26, 2012 /PRNewswire/ -- Ensco plc (NYSE: ESV) will replace Great Plains Energy (NYSE: GR) in the "
    "S&P 500 index after the close of trading on Monday, July 30 ."
)


def test_after_close_means_next_session_open_with_real_calendar() -> None:
    mon = effective_at(Timing.AFTER_CLOSE, date(2011, 1, 3))
    assert mon is not None and mon.astimezone(UTC).date() == date(2011, 1, 4)
    assert effective_session(Timing.AFTER_CLOSE, date(2011, 1, 3)) == date(2011, 1, 4)
    # Friday after close -> MONDAY, not Saturday (no +1 calendar day heuristic)
    assert effective_session(Timing.AFTER_CLOSE, date(2011, 4, 1)) == date(2011, 4, 4)
    assert effective_session(Timing.AFTER_CLOSE, date(2012, 7, 30)) == date(2012, 7, 31)
    assert effective_session(Timing.BEFORE_OPEN, date(2019, 1, 18)) == date(2019, 1, 18)
    assert (
        effective_session(Timing.TBA, None) is None and effective_at(Timing.UNKNOWN, None) is None
    )
    with pytest.raises(DataQualityError, match="not a XNYS session"):
        effective_at(Timing.AFTER_CLOSE, date(2011, 4, 2))  # a Saturday
    # a holiday: after the close of Friday 2011-04-22 (Good Friday is closed)
    with pytest.raises(DataQualityError):
        effective_at(Timing.AFTER_CLOSE, date(2011, 4, 22))


def test_motorola_mobility_boundary() -> None:
    (c,) = [x for x in parse_release(MMI, date(2010, 12, 22)) if x.added_ticker == "MMI"]
    assert (c.added_ticker, c.removed_ticker) == ("MMI", "MDP")
    assert c.timing is Timing.AFTER_CLOSE and c.stated_change_date == date(2011, 1, 3)
    assert c.reason_class == "SPINOFF"
    base = {"MDP", "AAA"}
    ev = [ReplayEvent(effective_session(c.timing, c.stated_change_date), "MMI", "MDP")]  # type: ignore[arg-type]
    assert members_at_open(base, ev, date(2011, 1, 3)) == {"MDP", "AAA"}  # old membership
    assert members_at_open(base, ev, date(2011, 1, 4)) == {"MMI", "AAA"}  # MMI in, MDP out
    # the other indices' clauses (MidCap, SmallCap) are NOT S&P 500 changes
    assert [x.added_ticker for x in parse_release(MMI, date(2010, 12, 22))] == ["MMI"]


def test_blackrock_and_ensco_boundaries_and_why_datasets_label_the_next_day() -> None:
    (b,) = parse_release(BLK, date(2011, 3, 29))
    assert (b.added_ticker, b.removed_ticker, b.timing, b.stated_change_date) == (
        "BLK",
        "GENZ",
        Timing.AFTER_CLOSE,
        date(2011, 4, 1),
    )
    assert b.header_date == date(2011, 4, 1) and not b.notes  # prose and summary header agree
    assert effective_session(b.timing, b.stated_change_date) == date(2011, 4, 4)
    (e,) = parse_release(ESV_CLAUSE, date(2012, 7, 26))
    assert (e.added_ticker, e.removed_ticker) == ("ESV", "GR")
    assert e.stated_change_date == date(2012, 7, 30)  # release says 30/07 (after the close)...
    assert effective_session(e.timing, e.stated_change_date) == date(
        2012, 7, 31
    )  # ...member from 31/07


def test_tba_release_proves_intent_not_a_date() -> None:
    (c,) = parse_release(TBA, date(2011, 1, 26))
    assert c.timing is Timing.TBA and c.stated_change_date is None
    ann = Announcement(SourceTier.OFFICIAL_REPUBLISHED, "u", "h" * 64, date(2011, 1, 26), c)
    (r,) = match_discovery([DiscoveryRow(date(2011, 2, 22), ("COV",), ("MFE",))], [ann])
    assert r.status is EventStatus.DATE_TBA and r.effective_session is None


def _ann(
    text: str, d: date, tier: SourceTier = SourceTier.OFFICIAL_REPUBLISHED
) -> list[Announcement]:
    return [Announcement(tier, "u", "h" * 64, d, c) for c in parse_release(text, d)]


def test_matching_statuses_and_conflicts_never_edit_official_data() -> None:
    anns = _ann(MMI, date(2010, 12, 22)) + _ann(BLK, date(2011, 3, 29))
    rows = [
        DiscoveryRow(date(2011, 1, 4), ("MMI",), ("MDP",)),   # official session 2011-01-04 -> confirmed
        DiscoveryRow(date(2011, 4, 1), ("BLK",), ("GENZ",)),  # discovery says 04-01, official effective 04-04
        DiscoveryRow(date(2011, 6, 6), ("XYZ",), ()),         # nothing official
    ]  # fmt: skip
    got = {(r.added, r.removed): r for r in match_discovery(rows, anns)}
    assert got[("MMI", "MDP")].status is EventStatus.OFFICIAL_REPUBLISHED_CONFIRMED
    blk = got[("BLK", "GENZ")]
    assert blk.status is EventStatus.CONFLICT and blk.effective_session == date(2011, 4, 4)
    assert blk.announcement is not None and blk.announcement.change.stated_change_date == date(
        2011, 4, 1
    )  # untouched
    assert got[("XYZ", None)].status is EventStatus.DISCOVERY_ONLY
    tier1 = _ann(MMI, date(2010, 12, 22), SourceTier.OFFICIAL_SPDJI)
    (r1,) = [r for r in match_discovery([rows[0]], tier1)]
    assert r1.status is EventStatus.OFFICIAL_CONFIRMED


def test_no_one_to_one_assumption_additions_and_removals_independent() -> None:
    rows = [
        DiscoveryRow(date(2011, 1, 18), (), ("QLGC",)),
        DiscoveryRow(date(2011, 3, 1), ("COV",), ()),
    ]
    res = match_discovery(rows, [])
    assert {(r.added, r.removed) for r in res} == {(None, "QLGC"), ("COV", None)}
    assert all(r.status is EventStatus.DISCOVERY_ONLY for r in res)


def test_replay_is_reversible_and_fails_closed() -> None:
    anchor = {"A", "B", "C", "D"}
    ev = [
        ReplayEvent(date(2020, 1, 2), "C", "X"),
        ReplayEvent(date(2021, 5, 3), "D", "Y"),
        ReplayEvent(date(2022, 2, 1), None, "Z"),
    ]
    history = undo_events(anchor, ev)
    assert history == {"A", "B", "X", "Y", "Z"}
    assert (
        replay_events(history, ev) == anchor
    )  # current_anchor -> undo -> replay -> current_anchor
    assert members_at_open(history, ev, date(2021, 1, 1)) == {"A", "B", "C", "Y", "Z"}
    with pytest.raises(DataQualityError):
        undo_events(
            {"A"}, [ReplayEvent(date(2020, 1, 2), "Q", None)]
        )  # an add that is not in the set
    with pytest.raises(DataQualityError):
        replay_events({"A"}, [ReplayEvent(date(2020, 1, 2), "A", None)])  # double add


def test_discovery_csv_layout_and_since_filter() -> None:
    data = b"date,added_tickers,removed_tickers\n2010-12-01,['A'],['B']\n2011-01-04,['MMI'],['MDP']\n2011-01-18,,['QLGC']\n"
    rows = parse_discovery_csv(data, date(2011, 1, 1))
    assert rows == [
        DiscoveryRow(date(2011, 1, 4), ("MMI",), ("MDP",)),
        DiscoveryRow(date(2011, 1, 18), (), ("QLGC",)),
    ]


def test_aware_effective_at() -> None:
    e = effective_at(Timing.AFTER_CLOSE, date(2011, 1, 3))
    assert isinstance(e, datetime) and e.tzinfo is not None
