# ruff: noqa: E501
"""Historical anchor graph + local event reconciliation (ADR-0032) on SYNTHETIC anchors, securities and events."""

from __future__ import annotations

import subprocess
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pitquant.db.models import (
    RawSourceArchive,
    Security,
    SP500Anchor,
    SP500AnchorMember,
    SP500Announcement,
    SP500MembershipEvent,
)
from pitquant.universe.sources.spy_sec_anchors import PARSER_VERSION
from pitquant.universe.sp500_anchor_graph import (
    ENGINE_VERSION,
    graph_metrics,
    load_anchors,
    persist_graph,
    reconstruct,
)

ROOT = Path(__file__).resolve().parents[2]
RUN = "run-1"


class World:
    """Synthetic universe: 'SYN <X> Corp' securities, anchors and official/unconfirmed events."""

    def __init__(self, s: Session):
        self.s = s
        self.sec: dict[str, str] = {}
        self.arch = RawSourceArchive(
            provider="TEST",
            source_identifier="fixture",
            retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
            sha256="0" * 64,
            mime_type="text/plain",
            size_bytes=1,
            storage_uri="x",
        )
        s.add(self.arch)
        s.flush()
        self.n = 0
        self.anchor_ids: list[str] = []

    def security(self, tag: str) -> str:
        if tag not in self.sec:
            x = Security(name=f"SYN {tag} Corp", exchange="XNYS", currency="USD")
            self.s.add(x)
            self.s.flush()
            self.sec[tag] = x.security_id
        return self.sec[tag]

    def anchor(
        self,
        as_of: date,
        tags: list[str],
        *,
        form: str = "NPORT-P",
        unresolved: int = 0,
        stubs: list[str] | None = None,
        lei: dict[str, str] | None = None,
    ) -> SP500Anchor:
        self.n += 1
        a = SP500Anchor(
            as_of_date=as_of, source_type="SEC_NPORT_P" if form == "NPORT-P" else "SEC_N30D", evidence_tier="SEC_NPORT_IDENTIFIED_ANCHOR" if form == "NPORT-P" else "SEC_SCHEDULE_ANCHOR",
            form=form, accession=f"FIX-{self.n}", filer_cik="0000884394", source_available_at=datetime(as_of.year, as_of.month, as_of.day, 12, tzinfo=UTC) + (datetime(2030, 1, 1, tzinfo=UTC) - datetime(2030, 1, 1, tzinfo=UTC)),
            archive_id=self.arch.archive_id, source_sha256="0" * 64, member_count=len(tags), resolved_count=len(tags) - unresolved, unresolved_count=unresolved, excluded_count=len(stubs or []),
            status="VERIFIED", notes=[], parser_version=PARSER_VERSION,
        )  # fmt: skip
        a.source_available_at = datetime(as_of.year, as_of.month, as_of.day, 23, tzinfo=UTC)
        self.s.add(a)
        self.s.flush()
        self.anchor_ids.append(a.anchor_id)
        for i, t in enumerate(tags):
            res = not (unresolved and i < unresolved)
            self.s.add(SP500AnchorMember(anchor_id=a.anchor_id, security_id=self.security(t) if res else None, cusip=f"SYN{t}", isin=None, issuer_name=f"SYN {t} Corp", lei=(lei or {}).get(t), source_position=i, shares=1000.0, value_usd=5e7,
                                         classification="INDEX_EQUITY_CANDIDATE", identity_basis="CUSIP", status="RESOLVED" if res else "UNRESOLVED"))  # fmt: skip
        for j, t in enumerate(stubs or []):
            self.s.add(SP500AnchorMember(anchor_id=a.anchor_id, security_id=None, cusip=f"STUB{t}", isin=None, issuer_name=f"SYN {t} Corp", source_position=900 + j, shares=1.0, value_usd=16.7, classification="TRANSIENT_CORPORATE_ACTION", identity_basis="NONE", status="EXCLUDED"))  # fmt: skip
        self.s.flush()
        return a

    def event(
        self, status: str, added: str | None, removed: str | None, eff: date | None, disc: date
    ) -> None:
        ann_id = None
        if eff:
            ann = SP500Announcement(source_tier="OFFICIAL_SPDJI", source_url="u", archive_id=self.arch.archive_id, source_sha256="0" * 64, announcement_at=datetime(eff.year, eff.month, eff.day, tzinfo=UTC), stated_change_date=eff, timing="BEFORE_OPEN",
                                    added_ticker=(added or "").upper(), added_name=f"SYN {added} Corp" if added else "", removed_ticker=(removed or "").upper(), removed_name=f"SYN {removed} Corp" if removed else "", reason_class="X", excerpt="e", notes=[], parser_version="sp500-evidence-3")  # fmt: skip
            self.s.add(ann)
            self.s.flush()
            ann_id = ann.announcement_row_id
        self.s.add(SP500MembershipEvent(run_id=RUN, announcement_row_id=ann_id, added_ticker=(added or "").upper() or None, removed_ticker=(removed or "").upper() or None, effective_at=datetime(eff.year, eff.month, eff.day, 13, 30, tzinfo=UTC) if eff else None,
                                        discovery_date=disc, source_tier="OFFICIAL_SPDJI" if eff else "DISCOVERY_ONLY", status=status, reason="t", created_at=datetime(2026, 10, 3, tzinfo=UTC)))  # fmt: skip
        self.s.flush()


@pytest.fixture
def w(session: Session) -> World:
    return World(session)


def chain(w: World) -> None:
    """2020-03-31 {A,B,C} -> (C leaves, D joins on 2020-05-12, CONFIRMED) -> 2020-06-30 {A,B,D}."""
    w.anchor(date(2020, 3, 31), ["A", "B", "C"])
    w.anchor(date(2020, 6, 30), ["A", "B", "D"])
    w.event("OFFICIAL_CONFIRMED", "D", "C", date(2020, 5, 12), date(2020, 5, 12))


def names(w: World, ids: frozenset[str] | None) -> set[str]:
    inv = {v: k for k, v in w.sec.items()}
    return {inv[i] for i in (ids or ())}


# ───────────────────────────────────────────── replay: forward, backward, symmetric
def test_segment_validates_forward_and_backward_and_cohorts_are_exact(
    w: World, session: Session
) -> None:
    chain(w)
    rep = reconstruct(session, date(2020, 4, 1), date(2020, 6, 30))
    seg = rep.segments[0]
    assert seg.forward_ok and seg.backward_ok and seg.status == "VALIDATED"
    by = {c.date: c for c in rep.cohorts}
    assert names(w, by[date(2020, 4, 1)].members) == {"A", "B", "C"}
    assert names(w, by[date(2020, 5, 1)].members) == {
        "A",
        "B",
        "C",
    }  # before the 2020-05-12 effective session
    assert names(w, by[date(2020, 6, 1)].members) == {"A", "B", "D"}
    assert rep.ready == 3 and rep.longest_run == 3


def test_forward_and_backward_reconstruction_agree_at_every_cohort(
    w: World, session: Session
) -> None:
    chain(w)
    seg = reconstruct(session, date(2020, 4, 1), date(2020, 6, 30)).segments[0]
    d = w.sec["D"]
    fwd = set(seg.a.members)
    for _dt, kind, sid in sorted(
        (leg.lo, leg.kind, leg.security_id) for leg in seg.legs if leg.exact
    ):  # type: ignore[type-var]
        fwd.add(sid) if kind == "ADD" else fwd.discard(sid)  # type: ignore[arg-type]
    bwd = set(seg.b.members)
    bwd.discard(d)
    bwd.add(w.sec["C"])
    assert fwd == set(seg.b.members) and bwd == set(seg.a.members)


# ───────────────────────────────────────────── local blocking
@pytest.mark.pit
def test_a_gap_blocks_only_its_own_segment(w: World, session: Session) -> None:
    chain(w)
    w.anchor(
        date(2020, 9, 30), ["A", "B", "E"]
    )  # D -> E happened between 2020-06-30 and 2020-09-30 with NO event at all
    rep = reconstruct(session, date(2020, 4, 1), date(2020, 9, 30))
    st = {str(c.date): c.status for c in rep.cohorts}
    assert st["2020-04-01"] == st["2020-05-01"] == st["2020-06-01"] == "MEMBERSHIP_READY"
    assert st["2020-07-01"] == st["2020-08-03"] == st["2020-09-01"] == "BLOCKED"
    kinds = {d.difference_type for s in rep.segments for d in s.deltas}
    assert {"MISSING_ADDITION_EVENT", "MISSING_REMOVAL_EVENT"} <= kinds
    assert rep.segments[0].status == "VALIDATED" and rep.segments[1].status == "LOCAL_GAPS"


@pytest.mark.pit
def test_an_unresolved_event_in_2025_does_not_change_the_reconstructibility_of_2020(
    w: World, session: Session
) -> None:
    chain(w)
    before = [
        (str(c.date), c.status, sorted(names(w, c.members)))
        for c in reconstruct(session, date(2020, 4, 1), date(2020, 6, 30)).cohorts
    ]
    w.event("UNRESOLVED", "X", "Y", None, date(2025, 6, 2))
    w.event("DISCOVERY_ONLY", "Q", None, None, date(2025, 7, 7))
    w.anchor(date(2025, 6, 30), ["A", "B", "Z"])  # a later anchor with unexplained changes
    rep = reconstruct(session, date(2020, 4, 1), date(2020, 6, 30))
    after = [(str(c.date), c.status, sorted(names(w, c.members))) for c in rep.cohorts]
    assert after == before and rep.ready == 3 and rep.post_limit_events_used == 0


@pytest.mark.pit
def test_the_2022_09_30_anchor_terminates_the_pre_holdout_chain(w: World, session: Session) -> None:
    w.anchor(date(2022, 6, 30), ["A", "B"])
    w.anchor(date(2022, 9, 30), ["A", "B"])
    w.anchor(
        date(2022, 12, 31), ["A", "B", "Z"]
    )  # inside the sealed holdout period: must not be loaded
    w.event("UNRESOLVED", "Z", "B", None, date(2023, 2, 1))
    assert [a.as_of for a in load_anchors(session)] == [date(2022, 6, 30), date(2022, 9, 30)]
    rep = reconstruct(session, date(2022, 7, 1), date(2022, 9, 30))
    assert (
        rep.ready == 3
        and rep.post_limit_events_used == 0
        and graph_metrics(rep)["post_limit_events_used"] == 0
    )


# ───────────────────────────────────────────── identity
def test_unresolved_anchor_holding_fails_closed(w: World, session: Session) -> None:
    w.anchor(date(2020, 3, 31), ["A", "B", "C"], unresolved=1)
    w.anchor(date(2020, 6, 30), ["A", "B", "C"])
    rep = reconstruct(session, date(2020, 4, 1), date(2020, 6, 30))
    assert (
        rep.ready == 0
        and all("not resolved" in c.reasons[0] for c in rep.cohorts)
        and rep.segments[0].status == "IDENTITY_UNRESOLVED"
    )


def test_stub_positions_are_not_index_members(w: World, session: Session) -> None:
    w.anchor(date(2020, 3, 31), ["A", "B"], stubs=["OLD"])  # 1 share left after the index deletion
    w.anchor(date(2020, 6, 30), ["A", "B"], stubs=["OLD"])
    anchors = load_anchors(session)
    assert all(len(a.members) == 2 for a in anchors) and rep_ok(session)


def rep_ok(session: Session) -> bool:
    return reconstruct(session, date(2020, 4, 1), date(2020, 6, 30)).ready == 3


def test_same_issuer_cusip_change_is_an_identity_transition_not_a_membership_change(
    w: World, session: Session
) -> None:
    lei = {
        "HCP": "LEI1",
        "PEAK": "LEI1",
    }  # same issuer LEI in both filings, new security (CUSIP) after the rename
    w.anchor(date(2020, 3, 31), ["A", "HCP"], lei=lei)
    w.anchor(date(2020, 6, 30), ["A", "PEAK"], lei=lei)
    rep = reconstruct(session, date(2020, 4, 1), date(2020, 6, 30))
    assert rep.segments[0].status == "VALIDATED" and rep.ready == 3
    assert any("same issuer LEI" in a["evidence"] for a in rep.segments[0].alias_candidates)


def test_two_different_issuers_are_never_merged_by_name_or_ticker(
    w: World, session: Session
) -> None:
    w.anchor(date(2020, 3, 31), ["A", "B"], lei={"A": "LEI-A", "B": "LEI-B"})
    w.anchor(date(2020, 6, 30), ["A", "C"], lei={"A": "LEI-A", "C": "LEI-C"})
    seg = reconstruct(session, date(2020, 4, 1), date(2020, 6, 30)).segments[0]
    assert (
        seg.status == "LOCAL_GAPS" and not seg.alias_candidates
    )  # B left and C joined: nothing proves they are one issuer


def test_csv_rename_pair_is_a_ticker_alias_not_a_transient_member(
    w: World, session: Session
) -> None:
    w.anchor(date(2020, 3, 31), ["ALPHA", "B"])
    w.anchor(date(2020, 6, 30), ["ALPHA", "B"])
    # an official release gives both tickers the same company name; the discovery CSV lists the rename as an exit + an entry
    w.event(
        "OFFICIAL_CONFIRMED", "ALPHA", "ALPHA", date(2020, 1, 2), date(2020, 1, 2)
    )  # outside the segment (context only)
    for t in ("OLD1", "NEW1"):
        w.s.add(SP500Announcement(source_tier="OFFICIAL_SPDJI", source_url="u", archive_id=w.arch.archive_id, source_sha256="1" * 64, announcement_at=datetime(2019, 1, 2, tzinfo=UTC), timing="UNKNOWN", added_ticker=t, added_name="SYN ALPHA Corp", removed_ticker="", removed_name="", reason_class="X", excerpt="e", notes=[], parser_version="sp500-evidence-3"))  # fmt: skip
    session.flush()
    w.event("DISCOVERY_ONLY", "NEW1", None, None, date(2020, 5, 4))
    w.event("DISCOVERY_ONLY", None, "OLD1", None, date(2020, 5, 4))
    rep = reconstruct(session, date(2020, 4, 1), date(2020, 6, 30))
    assert rep.segments[0].status == "VALIDATED" and rep.ready == 3
    assert reconstruct(session, date(2020, 4, 1), date(2020, 6, 30), standard="DAILY").ready == 3


# ───────────────────────────────────────────── the pre-trade of a Tier B schedule, conflicts, persistence
def test_tier_b_schedule_pre_trades_next_session_additions(w: World, session: Session) -> None:
    a = w.anchor(date(2022, 6, 30), ["A", "B"])
    w.anchor(
        date(2022, 9, 30), ["A", "B", "N"], form="N-30D"
    )  # N bought at the 9/30 close for its 2022-10-03 effective date
    w.event("OFFICIAL_CONFIRMED", "N", "B", date(2022, 10, 3), date(2022, 10, 3))
    seg = reconstruct(session, date(2022, 7, 1), date(2022, 9, 30)).segments[0]
    assert (
        a
        and w.sec["N"] not in seg.b.members
        and seg.b.pre_traded == [w.sec["N"]]
        and seg.status == "VALIDATED"
    )


def test_official_date_wins_so_a_csv_conflict_blocks_no_cohort(w: World, session: Session) -> None:
    w.anchor(date(2020, 3, 31), ["A", "B"])
    w.anchor(date(2020, 6, 30), ["A", "C"])
    w.event(
        "CONFLICT", "C", "B", date(2020, 5, 5), date(2020, 4, 29)
    )  # official 05-05, CSV 04-29: the primary date stands
    st = {
        str(c.date): c.status
        for c in reconstruct(session, date(2020, 4, 1), date(2020, 6, 30)).cohorts
    }
    assert st["2020-04-01"] == st["2020-05-01"] == st["2020-06-01"] == "MEMBERSHIP_READY"


def test_segments_are_persisted_append_only_and_idempotently(w: World, session: Session) -> None:
    chain(w)
    rep = reconstruct(session, date(2020, 4, 1), date(2020, 6, 30))
    first = persist_graph(session, rep)
    again = persist_graph(session, rep)
    assert first["segments"] == 1 and again["segments"] == 0
    assert ENGINE_VERSION.startswith("anchor-graph")


# ───────────────────────────────────────────── reference truth is never decision information
@pytest.mark.pit
def test_source_publication_must_not_precede_the_period_it_describes(
    w: World, session: Session
) -> None:
    w.anchor(date(2020, 3, 31), ["A"])
    bad = SP500Anchor(as_of_date=date(2020, 6, 30), source_type="SEC_NPORT_P", evidence_tier="T", form="NPORT-P", accession="BAD", filer_cik="0000884394", source_available_at=datetime(2020, 5, 1, tzinfo=UTC),
                      archive_id=w.arch.archive_id, source_sha256="0" * 64, member_count=0, resolved_count=0, unresolved_count=0, excluded_count=0, status="VERIFIED", notes=[], parser_version=PARSER_VERSION)  # fmt: skip
    session.add(bad)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


@pytest.mark.pit
def test_no_feature_decision_or_analysis_code_can_read_the_anchor_graph() -> None:
    """NPORT/N-30D anchors describe a PAST state and were published weeks later: they are reference data, never an input at ``decision_at``."""
    banned = (
        "sp500_anchor_graph",
        "sp500_anchor_ingest",
        "spy_sec_anchors",
        "SP500Anchor",
        "sp500_anchors",
    )
    for pkg in ("features", "analyzer", "backtest", "validation"):
        root = ROOT / "src" / "pitquant" / pkg
        if not root.exists():
            continue
        for f in root.rglob("*.py"):
            text = f.read_text()
            assert not any(b in text for b in banned), f"{f} touches SEC anchors"
    out = subprocess.run(
        ["git", "grep", "-l", "SP500Anchor", "--", "src/pitquant/api", "src/pitquant/dashboard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout
    assert out.strip() == ""
