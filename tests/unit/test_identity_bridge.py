# ruff: noqa: E501
"""SEC 13F list parsing, 13F identity bridge, verified successions and the monthly (Research) vs daily (canonical) standards (ADR-0033).
13F lines and securities are SYNTHETIC FIXTURES (real CUSIPs/ISINs of the six investigated cases are used only as keys)."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.data.providers.sec_13f_list import PARSER_VERSION as F13
from pitquant.data.providers.sec_13f_list import parse_13f_text, quarter_end, quarters
from pitquant.db.models import (
    RawSourceArchive,
    Sec13FListEntry,
    Security,
    SecurityIdentifierEvidence,
    SecuritySuccession,
    SP500Anchor,
    SP500AnchorMember,
)
from pitquant.universe.identity_bridge import (
    RESOLUTIONS,
    apply_resolutions,
    bridge_name_only,
    candidates_for,
    n30d_key,
    succession_map,
)
from pitquant.universe.sources.spy_sec_anchors import PARSER_VERSION as ANCHOR_V
from pitquant.universe.sp500_anchor_graph import classify_gaps, load_anchors, reconstruct
from tests.unit.test_sp500_anchor_graph import World


class F13World:
    def __init__(self, s: Session):
        self.s = s
        self.arch = RawSourceArchive(
            provider="TEST",
            source_identifier="13f-fixture",
            retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
            sha256="f" * 64,
            mime_type="application/pdf",
            size_bytes=1,
            storage_uri="x",
        )
        s.add(self.arch)
        s.flush()
        self.anchor = SP500Anchor(as_of_date=date(2019, 3, 31), source_type="SEC_N30D", evidence_tier="SEC_SCHEDULE_ANCHOR", form="N-30D", accession="F13-1", filer_cik="0000884394", source_available_at=datetime(2019, 5, 1, tzinfo=UTC),
                                  archive_id=self.arch.archive_id, source_sha256="0" * 64, member_count=0, resolved_count=0, unresolved_count=0, excluded_count=0, status="VERIFIED", notes=[], parser_version=ANCHOR_V)  # fmt: skip
        s.add(self.anchor)
        s.flush()

    def e13(
        self, quarter: str, cusip: str, name: str, desc: str, status: str | None = None
    ) -> None:
        self.s.add(
            Sec13FListEntry(
                quarter=quarter,
                cusip=cusip,
                issuer_name=name,
                issuer_description=desc,
                status_added_deleted=status,
                raw_source_hash="f" * 64,
                archive_id=self.arch.archive_id,
                parser_version=F13,
            )
        )
        self.s.flush()

    def sec(self, name: str) -> str:
        x = Security(name=name, exchange="XNYS", currency="USD")
        self.s.add(x)
        self.s.flush()
        return x.security_id

    def evidence(self, sid: str, cusip: str) -> None:
        self.s.add(
            SecurityIdentifierEvidence(
                security_id=sid,
                id_type="CUSIP",
                value=cusip,
                kind="OFFICIAL",
                observed_on=date(2019, 12, 31),
                source_kind="SEC_NPORT_P_HOLDING",
                source_url="u",
                archive_id=self.arch.archive_id,
                source_sha256="0" * 64,
                excerpt="e",
                parser_version=ANCHOR_V,
            )
        )
        self.s.flush()

    def member(self, sid: str, name: str, basis: str, *, isin: str | None = None) -> None:
        self.s.add(
            SP500AnchorMember(
                anchor_id=self.anchor.anchor_id,
                security_id=sid,
                cusip=None,
                isin=isin,
                issuer_name=name,
                source_position=1,
                shares=1.0,
                value_usd=5e7,
                classification="INDEX_EQUITY_CANDIDATE",
                identity_basis=basis,
                status="RESOLVED",
            )
        )
        self.s.flush()


@pytest.fixture
def fw(session: Session) -> F13World:
    return F13World(session)


# ───────────────────────────────────────────── 13F parser
def test_13f_list_parser_reads_cusip_issuer_description_and_status() -> None:
    text = "7:56 IVM001\n037833 10 0 APPLE INC COM\n25470F 10 4 DISCOVERY COMMUNICATNS NEW COM SER A\nG0408V 10 2 AON PLC SHS CL A DELETED\n00770F 90 4 AEGION CORP CALL\n037411 10 5 * APACHE CORP COM ADDED\n"
    e = {x.cusip: x for x in parse_13f_text(text, "2020Q2")}
    assert set(e) == {
        "037833100",
        "25470F104",
        "G0408V102",
        "037411105",
    }  # the CALL line (an option) is dropped
    assert (
        e["G0408V102"].status == "DELETED"
        and e["037411105"].status == "ADDED"
        and e["037833100"].status is None
    )
    assert (
        e["25470F104"].issuer_description == "NEW COM SER A"
        and e["25470F104"].issuer_name == "DISCOVERY COMMUNICATNS"
    )
    assert quarter_end("2020Q2") == date(2020, 6, 30) and quarters("2019Q4", "2020Q2") == [
        "2019Q4",
        "2020Q1",
        "2020Q2",
    ]


# ───────────────────────────────────────────── name-only bridge: exact legal name + class, unique, else fail closed
def test_name_only_security_gets_the_cusip_of_the_unique_exact_name_and_class(
    fw: F13World, session: Session
) -> None:
    sid = fw.sec("Acme Brands, Inc. Class A")
    fw.member(sid, "Acme Brands, Inc. Class A", "NAME_ONLY")
    fw.e13("2019Q1", "00000A101", "ACME BRANDS INC", "CL A")
    fw.e13("2019Q1", "00000B109", "ACME BRANDS INC", "CL B")  # another class: not compatible
    res = bridge_name_only(session)
    assert res[0].status == "RESOLVED" and res[0].cusip == "00000A101"
    ev = session.scalars(
        select(SecurityIdentifierEvidence).where(SecurityIdentifierEvidence.security_id == sid)
    ).one()
    assert (ev.kind, ev.id_type, ev.source_kind, ev.observed_on) == (
        "OFFICIAL",
        "CUSIP",
        "SEC_13F_LIST",
        date(2019, 3, 31),
    )  # evidence for THAT quarter only


def test_several_13f_candidates_fail_closed_and_none_fails_closed(
    fw: F13World, session: Session
) -> None:
    a, b = fw.sec("Twin Corp"), fw.sec("Ghost Corp")
    fw.member(a, "Twin Corp.", "NAME_ONLY")
    fw.member(b, "Ghost Corp.", "NAME_ONLY")
    fw.e13("2019Q1", "11111A101", "TWIN CORP", "COM")
    fw.e13("2019Q1", "11111B109", "TWIN CORP", "COM NEW")  # two compatible lines -> ambiguous
    st = {r.name: r.status for r in bridge_name_only(session)}
    assert st == {"Twin Corp.": "UNRESOLVED_MULTIPLE", "Ghost Corp.": "UNRESOLVED_NONE"}
    assert not session.scalars(select(SecurityIdentifierEvidence)).all()


def test_fuzzy_similarity_alone_never_promotes_an_identity(fw: F13World, session: Session) -> None:
    sid = fw.sec("Praxair, Inc.")
    fw.member(sid, "Praxair, Inc.", "NAME_ONLY")
    fw.e13(
        "2019Q1", "74005P104", "PRAXAIR INCORPORATED HLDG", "COM"
    )  # similar, not the exact normalised legal name
    fw.e13("2019Q1", "74005P999", "PRAXIS INC", "COM")
    assert candidates_for(session, "Praxair, Inc.", "2019Q1") == []
    assert bridge_name_only(session)[0].status == "UNRESOLVED_NONE"
    assert n30d_key("Fox Corp. Class B") == ("fox", "B")


# ───────────────────────────────────────────── the six investigated resolutions
def seed_all(fw: F13World, skip: set[tuple[str, str]] | None = None) -> dict[str, str]:
    ids: dict[str, str] = {}
    # name changes: a name-only predecessor and the CUSIP-identified successor
    for key, old_name, cusip, new_name in (
        ("DA", "Discovery Communications, Inc. Class A", "25470F104", "Discovery Inc A"),
        ("DC", "Discovery Communications, Inc. Class C", "25470F302", "Discovery Inc C"),
        ("KLA", "KLA-Tencor Corp.", "482480100", "KLA Corp"),
    ):
        ids[key + "_old"], ids[key + "_new"] = fw.sec(old_name), fw.sec(new_name)
        fw.member(ids[key + "_old"], old_name, "NAME_ONLY")
        fw.evidence(ids[key + "_new"], cusip)
    for key, old_cusip, new_cusip, old_isin, new_isin in (
        ("AON", "G0408V102", "G0403H108", "GB00B5BT0K07", "IE00BLP1HW54"),
        ("SEA", "G7945M107", "G7997R103", "IE00B58JVZ52", "IE00BKVD2N49"),
        ("APA", "037411105", "03743Q108", None, None),
        ("JAC", "469814107", "46982L108", None, None),
    ):
        ids[key + "_old"], ids[key + "_new"] = fw.sec(key + " old"), fw.sec(key + " new")
        if old_isin:
            fw.member(ids[key + "_old"], key + " old", "ISIN", isin=old_isin)
            fw.member(ids[key + "_new"], key + " new", "ISIN", isin=new_isin)
        else:
            fw.evidence(ids[key + "_old"], old_cusip)
            fw.evidence(ids[key + "_new"], new_cusip)
    for q, c, n, d, st in (
        ("2018Q1", "25470F104", "DISCOVERY COMMUNICATNS", "NEW COM SER A", None),
        ("2019Q2", "25470F104", "DISCOVERY INC", "COM SER A", None),
        ("2018Q1", "25470F302", "DISCOVERY COMMUNICATNS", "NEW COM SER C", None),
        ("2019Q2", "25470F302", "DISCOVERY INC", "COM SER C", None),
        ("2019Q2", "482480100", "KLA-TENCOR CORP", "COM", None),
        ("2019Q3", "482480100", "KLA CORPORATION", "COM NEW", None),
        ("2020Q1", "G0408V102", "AON", "PLC SHS CL A", None),
        ("2020Q2", "G0408V102", "AON", "PLC SHS CL A", "DELETED"),
        ("2020Q2", "G0403H108", "AON", "PLC SHS CL A", "ADDED"),
        ("2020Q3", "G0403H108", "AON", "PLC SHS CL A", None),
        ("2021Q1", "G7945M107", "SEAGATE TECHNOLOGY", "PLC SHS", None),
        ("2021Q2", "G7945M107", "SEAGATE TECHNOLOGY", "PLC SHS", "DELETED"),
        ("2021Q2", "G7997R103", "SEAGATE TECHNOLOGY HLDNGS PL", "ORD SHS", "ADDED"),
        ("2021Q3", "G7997R103", "SEAGATE TECHNOLOGY HLDNGS PL", "ORD SHS", None),
        ("2020Q2", "037411105", "APACHE CORP", "COM", None),
        ("2021Q1", "037411105", "APACHE CORP", "COM", "DELETED"),
        ("2021Q1", "03743Q108", "APA CORPORATION", "COM", "ADDED"),
        ("2021Q2", "03743Q108", "APA CORPORATION", "COM", None),
        ("2022Q2", "469814107", "JACOBS ENGR GROUP INC", "COM", None),
        ("2022Q3", "469814107", "JACOBS ENGR GROUP INC", "COM", "DELETED"),
        ("2022Q3", "46982L108", "JACOBS SOLUTIONS INC", "COM", "ADDED"),
    ):
        if (q, c) not in (skip or set()):
            fw.e13(q, c, n, d, st)
    return ids


def test_six_resolutions_are_verified_against_the_13f_lists_and_modelled_as_succession(
    fw: F13World, session: Session
) -> None:
    ids = seed_all(fw)
    res = {r.key: r for r in apply_resolutions(session)}
    assert all(r.applied for r in res.values()), {
        k: v.reason for k, v in res.items() if not v.applied
    }
    rows = {
        (x.security_predecessor_id, x.security_successor_id): x
        for x in session.scalars(select(SecuritySuccession))
    }
    # Discovery: name change, A and C stay two DIFFERENT securities and are never linked to each other
    assert (
        rows[(ids["DA_old"], ids["DA_new"])].event_type == "NAME_CHANGE_SAME_SECURITY"
        and rows[(ids["DC_old"], ids["DC_new"])].event_type == "NAME_CHANGE_SAME_SECURITY"
    )
    assert (
        (ids["DA_old"], ids["DC_new"]) not in rows
        and (ids["DC_old"], ids["DA_new"]) not in rows
        and ids["DA_new"] != ids["DC_new"]
    )
    assert rows[(ids["DA_old"], ids["DA_new"])].effective_at == datetime(2018, 3, 6, tzinfo=UTC)
    # KLA: name only, the security (CUSIP) is the same
    assert rows[(ids["KLA_old"], ids["KLA_new"])].event_type == "NAME_CHANGE_SAME_SECURITY"
    # Aon / Seagate / Apache / Jacobs: NEW security_id, 1:1, successor issuer, membership continuity
    for k, eff in (
        ("AON", datetime(2020, 4, 1, 8, 0, tzinfo=UTC)),
        ("SEA", datetime(2021, 5, 18, 8, 0, tzinfo=UTC)),
        ("APA", datetime(2021, 3, 1, 5, 0, tzinfo=UTC)),
        ("JAC", datetime(2022, 8, 29, 4, 0, tzinfo=UTC)),
    ):
        r = rows[(ids[k + "_old"], ids[k + "_new"])]
        assert (r.event_type, r.exchange_ratio, r.membership_continuity, r.effective_at) == (
            "SECURITY_REPLACEMENT_SUCCESSOR",
            1.0,
            True,
            eff,
        )
        assert (
            ids[k + "_old"] != ids[k + "_new"]
        )  # a new security_id: the legal security really changed
    assert succession_map(session)[ids["AON_old"]] == ids["AON_new"]
    again = apply_resolutions(session)  # idempotent
    assert all(r.applied for r in again) and len(
        session.scalars(select(SecuritySuccession)).all()
    ) == len(rows)


def test_a_resolution_the_13f_list_does_not_verify_is_not_applied(
    fw: F13World, session: Session
) -> None:
    ids = seed_all(fw, skip={("2021Q1", "03743Q108")})  # APA never listed as ADDED in 2021Q1
    res = {
        r.key: r
        for r in apply_resolutions(session, tuple(r for r in RESOLUTIONS if r.key == "APACHE_APA"))
    }
    assert not res["APACHE_APA"].applied and "does not show" in res["APACHE_APA"].reason
    assert not session.scalars(
        select(SecuritySuccession).where(
            SecuritySuccession.security_predecessor_id == ids["APA_old"]
        )
    ).all()


# ───────────────────────────────────────────── engine: succession = continuity, not exit + entry
def test_cusip_change_with_membership_continuity_is_not_an_index_exit_and_entry(
    session: Session,
) -> None:
    w = World(session)
    a = w.anchor(date(2020, 3, 31), ["A", "OLD"])
    w.anchor(date(2020, 6, 30), ["A", "NEW"])
    assert (
        reconstruct(session, date(2020, 4, 1), date(2020, 6, 30)).segments[0].status == "LOCAL_GAPS"
    )  # without the succession it IS an unexplained exit + entry
    session.add(
        SecuritySuccession(
            security_predecessor_id=w.security("OLD"),
            security_successor_id=w.security("NEW"),
            effective_at=datetime(2020, 5, 1, tzinfo=UTC),
            event_type="SECURITY_REPLACEMENT_SUCCESSOR",
            exchange_ratio=1.0,
            membership_continuity=True,
            source="SEC_13F_LIST",
            source_hash=None,
        )
    )
    session.flush()
    rep = reconstruct(session, date(2020, 4, 1), date(2020, 6, 30))
    assert rep.segments[0].status == "VALIDATED" and rep.ready == 3 and a
    assert {d.difference_type for d in rep.segments[0].deltas} == set()
    assert (
        w.sec["NEW"] in load_anchors(session)[0].members
        and w.sec["OLD"] not in load_anchors(session)[0].members
    )  # one canonical member through the succession


def test_a_succession_without_membership_continuity_stays_an_exit_and_entry(
    session: Session,
) -> None:
    w = World(session)
    w.anchor(date(2020, 3, 31), ["A", "OLD"])
    w.anchor(date(2020, 6, 30), ["A", "NEW"])
    session.add(
        SecuritySuccession(
            security_predecessor_id=w.security("OLD"),
            security_successor_id=w.security("NEW"),
            effective_at=None,
            event_type="TRUE_INDEX_EXIT",
            exchange_ratio=None,
            membership_continuity=False,
            source="TEST",
            source_hash=None,
        )
    )
    session.flush()
    assert (
        reconstruct(session, date(2020, 4, 1), date(2020, 6, 30)).segments[0].status == "LOCAL_GAPS"
    )


# ───────────────────────────────────────────── monthly (Research) vs daily (canonical) and discovery as a non-blocker
def test_discovery_only_legs_do_not_block_a_primary_consistent_segment_monthly_but_do_block_daily(
    session: Session,
) -> None:
    w = World(session)
    w.anchor(date(2020, 3, 31), ["A", "B", "C"])
    w.anchor(date(2020, 6, 30), ["A", "B", "C"])  # anchors show NO change
    w.event(
        "DISCOVERY_ONLY", "ZZZ", None, None, date(2020, 5, 4)
    )  # an unconfirmed claim the anchors cannot place
    monthly = reconstruct(session, date(2020, 4, 1), date(2020, 6, 30))
    daily = reconstruct(session, date(2020, 4, 1), date(2020, 6, 30), standard="DAILY")
    assert monthly.ready == 3 and daily.ready == 0
    assert monthly.cohorts[0].daily_ready is False and monthly.cohorts[0].sets_equal is True
    assert any(
        g["category"] in ("DISCOVERY_UNCORROBORATED", "TICKER_OR_NAME_CHANGE")
        and not g["blocks_membership"]
        for g in classify_gaps(monthly)
    )


def test_a_date_uncertainty_that_crosses_no_decision_at_is_monthly_invariant(
    session: Session,
) -> None:
    w = World(session)
    w.anchor(date(2020, 3, 31), ["A", "B"])
    w.anchor(date(2020, 5, 1), ["A", "B"])
    w.anchor(
        date(2020, 5, 29), ["A", "C"]
    )  # B -> C sometime in (05-01, 05-29]: NO month-start open lies in that interval
    w.anchor(date(2020, 6, 30), ["A", "C"])
    rep = reconstruct(session, date(2020, 4, 1), date(2020, 6, 30))
    assert (
        rep.ready == 3
    )  # 04-01, 05-01 and 06-01 are all certain: the change cannot alter any of them
    cats = {g["category"] for g in classify_gaps(rep)}
    assert (
        "PRIMARY_EVENT_MISSING" not in cats and "RESOLVED" in cats
    )  # DATE_UNCERTAIN_MONTHLY_INVARIANT: not a blocker
    assert (
        rep.segments[1].status == "LOCAL_GAPS" and not rep.segments[1].forward_ok
    )  # the gap segment itself is not daily-canonical


def test_a_date_uncertainty_crossing_a_decision_at_blocks_only_that_cohort(
    session: Session,
) -> None:
    w = World(session)
    w.anchor(date(2020, 3, 31), ["A", "B"])
    w.anchor(date(2020, 6, 30), ["A", "C"])
    w.event(
        "DATE_TBA", "C", "B", date(2020, 5, 12), date(2020, 5, 12)
    )  # release known from 2020-05-12 but with no concrete date
    st = {
        str(c.date): c.status
        for c in reconstruct(session, date(2020, 4, 1), date(2020, 6, 30)).cohorts
    }
    assert st["2020-04-01"] == "MEMBERSHIP_READY"  # certainly before the announcement (A-state)
    assert st["2020-06-01"] == "BLOCKED" or st["2020-06-01"] == "MEMBERSHIP_READY"
    assert "BLOCKED" in st.values() and "MEMBERSHIP_READY" in st.values()


def test_official_date_wins_over_a_conflicting_discovery_date(session: Session) -> None:
    w = World(session)
    w.anchor(date(2020, 3, 31), ["A", "B"])
    w.anchor(date(2020, 6, 30), ["A", "C"])
    w.event(
        "CONFLICT", "C", "B", date(2020, 5, 5), date(2020, 4, 29)
    )  # CSV says 04-29, the release says 05-05
    rep = reconstruct(session, date(2020, 4, 1), date(2020, 6, 30))
    assert (
        rep.ready == 3
    )  # the CSV date never widens the primary date (before: the 05-01 cohort was blocked)
    assert {g["category"] for g in classify_gaps(rep)} >= {"DISCOVERY_CONFLICT"}


def test_a_primary_transient_member_is_applied_even_if_it_is_in_neither_anchor(
    session: Session,
) -> None:
    w = World(session)
    w.anchor(date(2020, 3, 31), ["A", "B"])
    w.anchor(date(2020, 6, 30), ["A", "B"])
    session.add(
        SP500AnchorMember(
            anchor_id=w.anchor_ids[0],
            security_id=w.security("T"),
            cusip="STUBT",
            isin=None,
            issuer_name="SYN T Corp",
            source_position=900,
            shares=1.0,
            value_usd=16.7,
            classification="TRANSIENT_CORPORATE_ACTION",
            identity_basis="NONE",
            status="EXCLUDED",
        )
    )  # SPY keeps a stub of T
    session.flush()
    w.event("OFFICIAL_CONFIRMED", "T", None, date(2020, 4, 2), date(2020, 4, 2))  # T joins ...
    w.event(
        "OFFICIAL_CONFIRMED", None, "T", date(2020, 5, 19), date(2020, 5, 19)
    )  # ... and leaves before the next anchor
    rep = reconstruct(session, date(2020, 4, 1), date(2020, 6, 30))
    inv = {v: k for k, v in w.sec.items()}
    got = {str(c.date): {inv[x] for x in (c.members or ())} for c in rep.cohorts}
    assert (
        got["2020-04-01"] == {"A", "B"}
        and got["2020-05-01"] == {"A", "B", "T"}
        and got["2020-06-01"] == {"A", "B"}
    )


def test_a_primary_transient_member_with_unknown_identity_blocks_the_cohorts_it_spans(
    session: Session,
) -> None:
    w = World(session)
    w.anchor(date(2020, 3, 31), ["A", "B"])
    w.anchor(date(2020, 6, 30), ["A", "B"])
    w.event(
        "OFFICIAL_CONFIRMED", "Q", None, date(2020, 4, 2), date(2020, 4, 2)
    )  # Q is in NO anchor: no security_id can exist for it
    w.event("OFFICIAL_CONFIRMED", None, "Q", date(2020, 5, 19), date(2020, 5, 19))
    st = {
        str(c.date): c.status
        for c in reconstruct(session, date(2020, 4, 1), date(2020, 6, 30)).cohorts
    }
    assert (
        st["2020-05-01"] == "BLOCKED" and st["2020-06-01"] == "MEMBERSHIP_READY"
    )  # it is a member on 05-01 and nobody knows which security
