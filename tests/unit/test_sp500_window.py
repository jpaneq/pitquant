# ruff: noqa: E501
"""D-02 window diagnosis (ADR-0031): parser v3 layouts, official-over-CSV conflicts, exact window blockers, demand plan.
Release excerpts are REAL_EXTRACT (S&P DJI releases archived locally); events/anchors are SYNTHETIC."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from pitquant.config.settings import Settings
from pitquant.db.models import SP500MembershipEvent
from pitquant.research.baselines import ELASTIC_NET, LOGISTIC
from pitquant.research.registry import ExperimentSpec, define_experiment, gates_from_readiness
from pitquant.research.walkforward import WalkForwardConfig
from pitquant.universe.sources.sp500_evidence import EventStatus, Timing, parse_release
from pitquant.universe.sp500_reconstruct import compute_d02
from pitquant.universe.sp500_window import window_readiness
from pitquant.universe.us_window_plan import LABEL, backfill_plan
from tests.unit.test_sp500_anchor_d02 import _anchor, _event

MOVE = (
    "NEW YORK , Dec. 3, 2021 / PRNewswire / -- S&P Dow Jones Indices will make the following index changes to the S&P 500, S&P MidCap 400, and S&P SmallCap 600 "
    "to ensure each index is more representative of its market capitalization range. The changes will be effective prior to the open of trading on Monday, December 20, 2021 "
    "to coincide with the quarterly rebalance: S&P MidCap 400 constituents Signature Bank (NASD: SBNY), SolarEdge Technologies Inc. (NASD: SEDG) and FactSet Research Systems Inc. "
    "(NYSE: FDS) will move to the S&P 500, replacing S&P 500 constituents Leggett & Platt Inc. (NYSE: LEG), Hanesbrands Inc. (NYSE: HBI) and The Western Union Co. (NYSE: WU), "
    "all of which will move to the S&P MidCap 400. S&P SmallCap 600 constituents Macy's Inc. (NYSE: M) will move to the S&P MidCap 400."
)
SWITCH = (
    "S&P Dow Jones Indices will make the following index adjustments. The changes will be effective prior to the open of trading on Monday, June 18 to coincide with the June rebalance. "
    "S&P MidCap 400 constituents HollyFrontier Corp. (NYSE: HFC) and Broadridge Financial Solutions Inc. (NYSE: BR) will switch places with Acuity Brands Inc. (NYSE: AYI) and "
    "Range Resources Corp. (NYSE: RRC) respectively in the S&P 500. S&P SmallCap 600 constituents Chemed Corp. (NYSE: CHE) will switch places with Endo International plc (NASD: ENDP) in the S&P MidCap 400."
)
NAME_ONLY = (
    "NEW YORK , Sept. 30, 2015 / PRNewswire / -- S&P 500 constituent Joy Global Inc. (NYSE: JOY) will replace Thoratec Corp. (NASDAQ: THOR) in the S&P MidCap 400, and Verisk Analytics Inc. "
    "(NASDAQ: VRSK) will replace Joy Global in the S&P 500 after the close of trading on Wednesday, October 7 ."
)
SPACED = (
    "S&P DJI will make the following changes effective prior to the open of trading on Monday, September 19 to coincide with the quarterly rebalance: CoStar Group Inc. ( NASD : CSGP ) and "
    "Invitation Homes Inc. (NYSE: INVH ) will replace PVH Corp. (NYSE: PVH ) and PENN Entertainment Inc. ( NASD : PENN) respectively in the S& P 500."
)
BEFORE = "Norwegian Cruise Line Holdings Ltd. (NASD: NCLH) will replace Level 3 Communications Inc. (NYSE: LVLT) in the S&P 500 effective before the open of trading on Friday, October 13 ."


def pairs(text: str, d: date) -> dict[tuple[str, str], date | None]:
    return {
        (c.added_ticker, c.removed_ticker): c.stated_change_date for c in parse_release(text, d)
    }


def test_parser_v3_layouts_pair_positionally_and_take_the_stated_date() -> None:
    assert pairs(MOVE, date(2021, 12, 3)) == {
        ("SBNY", "LEG"): date(2021, 12, 20),
        ("SEDG", "HBI"): date(2021, 12, 20),
        ("FDS", "WU"): date(2021, 12, 20),
    }
    sw = pairs(SWITCH, date(2018, 5, 31))
    assert set(sw) == {
        ("HFC", "AYI"),
        ("BR", "RRC"),
    }  # the SmallCap/MidCap switch is not S&P 500 membership
    assert pairs(NAME_ONLY, date(2015, 9, 30)) == {("VRSK", "JOY"): date(2015, 10, 7)}
    assert set(pairs(SPACED, date(2022, 9, 2))) == {("CSGP", "PVH"), ("INVH", "PENN")}
    ch = parse_release(BEFORE, date(2017, 10, 4))
    assert (
        ch and ch[0].timing is Timing.BEFORE_OPEN and ch[0].stated_change_date == date(2017, 10, 13)
    )


def test_unequal_lists_are_never_paired_by_guessing() -> None:
    t = "S&P MidCap 400 constituents A Corp. (NYSE: AAA) and B Corp. (NYSE: BBB) will move to the S&P 500, replacing C Corp. (NYSE: CCC), all of which will move to the S&P MidCap 400."
    assert pairs(t, date(2021, 1, 4)) == {}


def _official(
    session: Session, run: str, added: str, removed: str, official: date, csv: date, status: str
) -> None:
    _event(session, run, status, added, removed, csv, official)


def test_conflict_is_resolved_with_the_official_date_only_when_no_cohort_open_lies_between(
    session: Session,
) -> None:
    _anchor(session, ["AAA", "BBB", "N1", "N2"], date(2026, 10, 1))
    # official 2022-03-15, CSV 2022-03-17: no month-start session in [03-15, 03-17) -> immaterial
    _official(
        session, "r", "N1", "O1", date(2022, 3, 15), date(2022, 3, 17), EventStatus.CONFLICT.value
    )
    # official 2024-06-04 vs CSV 2024-05-29: the 2024-06-03 open lies between -> material, still blocks
    _official(
        session, "r", "N2", "O2", date(2024, 6, 4), date(2024, 5, 29), EventStatus.CONFLICT.value
    )
    rep = compute_d02(session)
    assert [m[1].split()[0] for m in rep.immaterial_conflicts] == ["+N1"]
    assert any("+N2" in b[1] for b in rep.breaks) and not any("+N1" in b[1] for b in rep.breaks)
    assert rep.reversible is True


def test_window_readiness_separates_inside_chain_and_hypothetical_anchor(
    session: Session, settings: Settings
) -> None:
    _anchor(session, ["AAA", "BBB", "N3", "N4"], date(2026, 10, 1))
    # unconfirmed event INSIDE the window (2019-05) and one AFTER it (2024-02, chain)
    session.add(
        SP500MembershipEvent(
            run_id="r",
            added_ticker="N3",
            removed_ticker="O3",
            discovery_date=date(2019, 5, 20),
            source_tier="DISCOVERY_ONLY",
            status=EventStatus.DISCOVERY_ONLY.value,
            reason="no official evidence found for this addition",
            created_at=datetime(2026, 10, 2, tzinfo=UTC),
        )
    )
    session.add(
        SP500MembershipEvent(
            run_id="r",
            added_ticker="N4",
            removed_ticker="O4",
            discovery_date=date(2024, 2, 20),
            source_tier="DISCOVERY_ONLY",
            status=EventStatus.DISCOVERY_ONLY.value,
            reason="no official evidence found for this addition",
            created_at=datetime(2026, 10, 2, tzinfo=UTC),
        )
    )
    session.flush()
    r = window_readiness(session, date(2017, 10, 1), date(2022, 9, 30), settings=settings)
    assert r.monthly_cohorts == 60 and r.reconstructible_cohorts == 0 and not r.holdout_overlap
    assert len(r.blocking_events) == 1 and r.blocking_events[0].added_ticker == "N3"
    assert (
        r.blocking_events[0].parser_status == "NO_DOCUMENT"
        and "external source" in r.blocking_events[0].missing_evidence
    )
    assert r.chain_blocking_events == 1 and r.chain_blocking_by_year == {"2024": 1}
    # a verified anchor at the window end would prove only the cohorts AFTER the 2019-05 event
    assert (
        0 < r.intrinsic_reconstructible_cohorts < 60 and r.status == "BLOCKED_BY_EVENTS_IN_WINDOW"
    )
    assert r.first_failure and "2017-10" in r.first_failure


def test_window_touching_the_holdout_is_flagged(session: Session, settings: Settings) -> None:
    _anchor(session, ["AAA"], date(2026, 10, 1))
    assert (
        window_readiness(
            session, date(2021, 1, 1), date(2023, 12, 31), settings=settings
        ).holdout_overlap
        is True
    )


def test_backfill_plan_is_labelled_candidate_and_never_claims_vendor_coverage(
    session: Session,
) -> None:
    _anchor(session, ["AAA", "BBB", "N5"], date(2026, 10, 1))
    session.add(
        SP500MembershipEvent(
            run_id="r",
            added_ticker="N5",
            removed_ticker="OLD5",
            discovery_date=date(2020, 6, 22),
            source_tier="DISCOVERY_ONLY",
            status=EventStatus.DISCOVERY_ONLY.value,
            reason="t",
            created_at=datetime(2026, 10, 2, tzinfo=UTC),
        )
    )
    session.flush()
    p = backfill_plan(session, date(2017, 10, 1), date(2022, 9, 30))
    assert p.summary["label"] == LABEL and p.summary["already_available"] == 0
    assert (
        p.summary["unique_securities_required"] == 4
    )  # AAA, BBB, N5 (from 2020-07) and OLD5 (until 2020-06)
    assert p.summary["active_securities"] == 3 and p.summary["former_securities"] == 1
    assert all(
        r.dividend_coverage == "REQUIRED_UNVERIFIED" and r.complex_ca == "UNKNOWN" for r in p.rows
    )
    assert all(
        r.price_required_to < date(2022, 10, 1) for r in p.rows
    )  # never asks for holdout-era prices
    old = next(r for r in p.rows if r.ticker == "OLD5")
    assert old.membership_end < date(2020, 7, 1) and not old.active_today


def test_blocked_experiment_reasons_come_from_readiness_not_a_hand_list(session: Session) -> None:
    gates = gates_from_readiness(
        [
            "gate D02_RESEARCH_READY = False",
            "gate total_return_real_validated = True",
            "gate SPY_benchmark_available = False",
        ]
    )
    assert gates == {"D02_RESEARCH_READY": False, "SPY_benchmark_available": False}
    spec = ExperimentSpec(
        "US_BASELINE_V0",
        ELASTIC_NET,
        WalkForwardConfig(),
        6,
        "SP500@FEATURE_V0_51",
        "SPY_TOTAL_RETURN_PROXY",
        horizons=(6, 12),
        extra_models=(LOGISTIC,),
    )
    ex = define_experiment(session, spec, None, gates)
    assert ex.status == "BLOCKED" and "gate D02_RESEARCH_READY = false" in ex.blocked_reasons
    assert ex.spec["horizons"] == [6, 12] and len(ex.spec["extra_models"]) == 1
    assert (
        define_experiment(session, spec, None, gates).experiment_id == ex.experiment_id
    )  # idempotent


TIMED_LEGS = (
    "S&P Dow Jones Indices will make the following changes to the S&P 500: Dow Inc. (NYSE: DOW) will be added to the S&P 500 prior to the open of trading on Tuesday, April 2 . "
    "Dow will replace Brighthouse Financial Inc. (NASD: BHF), which will be removed from the S&P 500 effective prior to the open of trading on Wednesday, April 3 ."
)
TWO_ADDS = (
    "Otis Worldwide Corp. (NYSE: OTIS) and Carrier Global Corp. (NYSE: CARR) will be added to the S&P 500 prior to the open of trading on Friday, April 3 . Otis Worldwide will replace "
    "Raytheon Co. (NYSE: RTN), and Carrier Global will replace Macy's Inc. (NYSE: M) both of which will be removed from the S&P 500 effective prior to the open of trading on Monday, April 6 ."
)


def test_legs_with_different_dates_are_separate_changes_not_a_swap() -> None:
    ch = {
        (c.added_ticker, c.removed_ticker): c.stated_change_date
        for c in parse_release(TIMED_LEGS, date(2019, 3, 26))
    }
    assert ch == {
        ("DOW", ""): date(2019, 4, 2),
        ("", "BHF"): date(2019, 4, 3),
    }  # 501 members between the two dates
    two = {
        (c.added_ticker, c.removed_ticker): c.stated_change_date
        for c in parse_release(TWO_ADDS, date(2020, 3, 31))
    }
    assert two == {
        ("OTIS", ""): date(2020, 4, 3),
        ("CARR", ""): date(2020, 4, 3),
        ("", "RTN"): date(2020, 4, 6),
        ("", "M"): date(2020, 4, 6),
    }
