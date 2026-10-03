# ruff: noqa: E501
"""SEC 8-K identity events (ADR-0034): Priceline->Booking, Coach->Tapestry, Praxair->Linde. 8-K texts and 13F lines are SYNTHETIC FIXTURES."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.db.models import SecuritySuccession, SecurityTickerAlias
from pitquant.universe.identity_events import EVENTS, Fetched, apply_events
from pitquant.universe.sp500_anchor_graph import reconstruct
from tests.unit.test_identity_bridge import F13World
from tests.unit.test_sp500_anchor_graph import World

TEXT = {
    "0001075531-18-000008": "Booking Holdings Inc. name change",
    "0001157523-17-002666": "Coach, Inc. to Tapestry, Inc.",
    "0001193125-18-313073": "Linde plc successor issuer",
}


def fetched(fw: F13World, form: str = "8-K") -> dict[str, Fetched]:
    return {a: Fetched("a" * 64, fw.arch.archive_id, t, form) for a, t in TEXT.items()}


def seed(fw: F13World) -> dict[str, str]:
    ids = {
        "pcln": fw.sec("Priceline Group, Inc."), "bkng": fw.sec("Booking Holdings Inc"), "coh": fw.sec("Coach, Inc."), "tpr": fw.sec("Tapestry Inc"), "px": fw.sec("Praxair, Inc."), "lin": fw.sec("Linde PLC"),
    }  # fmt: skip
    for k, n in (
        ("pcln", "Priceline Group, Inc."),
        ("coh", "Coach, Inc."),
        ("px", "Praxair, Inc."),
    ):
        fw.member(ids[k], n, "NAME_ONLY")
    fw.evidence(ids["bkng"], "09857L108")
    fw.evidence(ids["tpr"], "876030107")
    fw.member(ids["lin"], "Linde PLC", "ISIN", isin="IE00BZ12WP82")
    for q, c, n in (
        ("2017Q4", "741503403", "PRICELINE GRP INC"),
        ("2018Q2", "09857L108", "BOOKING HLDGS INC"),
        ("2017Q3", "189754104", "COACH INC"),
        ("2018Q1", "876030107", "TAPESTRY INC"),
        ("2018Q3", "74005P104", "PRAXAIR INC"),
        ("2019Q2", "G5494J103", "LINDE"),
    ):
        fw.e13(q, c, n, "COM")
    return ids


def test_booking_is_the_same_security_with_exact_ticker_dates_and_no_exit_entry(
    session: Session,
) -> None:
    fw = F13World(session)
    ids = seed(fw)
    res = {r.key: r for r in apply_events(session, None, None, fetched=fetched(fw))}
    assert res["PRICELINE_BOOKING"].applied, res["PRICELINE_BOOKING"].reason
    r = session.scalars(
        select(SecuritySuccession).where(SecuritySuccession.security_predecessor_id == ids["pcln"])
    ).one()
    assert (r.event_type, r.membership_continuity, r.effective_at) == (
        "NAME_TICKER_IDENTIFIER_CHANGE_SAME_SECURITY",
        True,
        datetime(2018, 2, 21, tzinfo=UTC),
    )
    assert "PARTIAL" in (r.note or "")  # CUSIP transition date is not stated
    al = {
        a.ticker: a
        for a in session.scalars(
            select(SecurityTickerAlias).where(SecurityTickerAlias.security_id == ids["bkng"])
        )
    }
    assert al["PCLN"].valid_to == date(2018, 2, 26) and al["BKNG"].valid_from == date(2018, 2, 27)
    assert (
        r.security_successor_id == ids["bkng"] and ids["pcln"] != ids["bkng"]
    )  # linked as one canonical security; not a successor replacement


def test_tapestry_is_a_name_and_ticker_change_with_membership_continuity(session: Session) -> None:
    fw = F13World(session)
    ids = seed(fw)
    apply_events(session, None, None, fetched=fetched(fw))
    r = session.scalars(
        select(SecuritySuccession).where(SecuritySuccession.security_predecessor_id == ids["coh"])
    ).one()
    assert (
        r.event_type == "NAME_TICKER_CHANGE_SAME_SECURITY"
        and r.membership_continuity
        and r.effective_at == datetime(2017, 10, 31, tzinfo=UTC)
    )
    tk = {
        a.ticker: a
        for a in session.scalars(
            select(SecurityTickerAlias).where(SecurityTickerAlias.security_id == ids["tpr"])
        )
    }
    assert tk["COH"].valid_to == date(2017, 10, 30) and tk["TPR"].valid_from == date(2017, 10, 31)


def test_membership_is_ready_while_the_cusip_transition_date_stays_partial(
    session: Session,
) -> None:
    """MEMBERSHIP = READY, IDENTITY = PARTIAL: the slot is the same even though the day of the CUSIP change is unknown."""
    w = World(session)
    w.anchor(date(2020, 3, 31), ["A", "COH"])
    w.anchor(date(2020, 6, 30), ["A", "TPR"])
    assert reconstruct(session, date(2020, 4, 1), date(2020, 6, 30)).ready == 0
    session.add(
        SecuritySuccession(
            security_predecessor_id=w.security("COH"),
            security_successor_id=w.security("TPR"),
            effective_at=datetime(2017, 10, 31, tzinfo=UTC),
            event_type="NAME_TICKER_CHANGE_SAME_SECURITY",
            exchange_ratio=None,
            membership_continuity=True,
            source="SEC_8K",
            source_hash=None,
            note="CUSIP transition date: PARTIAL",
        )
    )
    session.flush()
    assert reconstruct(session, date(2020, 4, 1), date(2020, 6, 30)).ready == 3


def test_praxair_linde_is_a_one_to_one_successor_security_not_a_membership_change(
    session: Session,
) -> None:
    fw = F13World(session)
    ids = seed(fw)
    apply_events(session, None, None, fetched=fetched(fw))
    r = session.scalars(
        select(SecuritySuccession).where(SecuritySuccession.security_predecessor_id == ids["px"])
    ).one()
    assert (r.event_type, r.exchange_ratio, r.membership_continuity, r.effective_at) == (
        "SECURITY_REPLACEMENT_SUCCESSOR",
        1.0,
        True,
        datetime(2018, 10, 31, tzinfo=UTC),
    )
    assert ids["px"] != ids["lin"]  # a NEW security_id for Linde plc
    px = {a.ticker: a for a in session.scalars(select(SecurityTickerAlias))}
    assert px["PX"].valid_to == date(2018, 10, 30) and px["LIN"].valid_from == date(2018, 10, 31)


def test_an_event_is_not_applied_when_the_8k_or_the_13f_do_not_verify_it(session: Session) -> None:
    fw = F13World(session)
    ids = seed(fw)
    bad = apply_events(session, None, None, fetched=fetched(fw, form="8-K/A"))
    assert not any(r.applied for r in bad)
    assert not session.scalars(
        select(SecuritySuccession).where(SecuritySuccession.security_predecessor_id == ids["px"])
    ).all()
    only = tuple(e for e in EVENTS if e.key == "COACH_TAPESTRY")
    wrong = {
        "0001157523-17-002666": Fetched("a" * 64, fw.arch.archive_id, "nothing relevant", "8-K")
    }
    assert not apply_events(session, None, None, only, fetched=wrong)[0].applied
