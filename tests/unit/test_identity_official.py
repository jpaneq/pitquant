"""Official code<->ISIN evidence and ISIN transitions in the IdentityResolutionEngine
(ADR-0022). Every ANCV line and every document below is a FIXTURE shaped like the real case it
reproduces (MTS, ABG.P, GRF, PHM, PUIG, FER); dates are those of the real events but the
lines are invented excerpts, never presented as historical data."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.core.hashing import content_hash
from pitquant.db.models import (
    IdentifierHistory,
    RawSourceArchive,
    Security,
    SecurityIdentitySnapshot,
    TickerHistory,
)
from pitquant.jobs.index_ingest import ingest_event_source
from pitquant.security_master.identity import (
    BACKTESTABLE,
    CodePeriod,
    IdentityResolutionEngine,
    IdentityResolutionStatus,
    IsinTransition,
    MembershipSpan,
    OfficialIdentifier,
    SnapshotIndex,
    SnapshotLine,
)
from pitquant.security_master.identity_store import load_snapshot_index, run_identity_resolution
from pitquant.universe.events import EventSource, SourceConfidence
from pitquant.universe.index_membership import IndexUniverse
from pitquant.universe.sources.bme import BMEHistoryRow, RowStyle, classify_rows

pytestmark = pytest.mark.pit
M = IdentityResolutionStatus.MULTI_SOURCE_CONFIRMED


def _l(d: str, isin: str, name: str, issuer: str = "FIXTURE SA", **kw: object) -> SnapshotLine:
    return SnapshotLine(date.fromisoformat(d), isin, issuer, name, **kw)  # type: ignore[arg-type]


def _span(code: str, f: str, t: str | None) -> MembershipSpan:
    ff, tt = date.fromisoformat(f), date.fromisoformat(t) if t else None
    return MembershipSpan("k", ff, tt, (CodePeriod(code, ff, tt),))


def _o(code: str, isin: str, d: str) -> OfficialIdentifier:
    return OfficialIdentifier(code, isin, date.fromisoformat(d), "FIXTURE_DOC", "a" * 64, True)


def _isins(segs, d: date):  # type: ignore[no-untyped-def]
    return {s.isin for s in segs if s.start <= d and (s.end is None or d < s.end) and _ok(s)}


def _ok(s) -> bool:  # type: ignore[no-untyped-def]
    return s.status in BACKTESTABLE


# ───────────────────────── MTS: code != ANCV label, foreign ISIN, reverse split ─────────────


def _mts_engine(with_transition: bool = True) -> IdentityResolutionEngine:
    old, new = "LU0000000012", "LU0000000020"
    lines = [  # ANCV labels the shares «ARCELORMITTAL», never the BME code MTS
        _l("2011-06-30", old, "ARCELORMITTAL/AC SVN", "ARCELORMITTAL, S.A."),
        _l("2016-12-31", old, "ARCELORMITTAL/AC SVN", "ARCELORMITTAL, S.A."),
        _l(
            "2017-06-30",
            new,
            "ARCELORMITTAL/AC",
            "ARCELORMITTAL, S.A.",
            issue_date=date(2017, 5, 18),
        ),
        _l(
            "2018-06-30",
            new,
            "ARCELORMITTAL/AC",
            "ARCELORMITTAL, S.A.",
            issue_date=date(2017, 5, 18),
        ),
    ]
    off = [
        _o("MTS", old, "2013-07-11"),
        _o("MTS", old, "2017-01-11"),
        _o("MTS", new, "2017-07-21"),
        _o("MTS", new, "2019-12-10"),
    ]
    tr = [
        IsinTransition(old, new, date(2017, 5, 22), "REVERSE_SPLIT", "SAME_SECURITY", ("c" * 64,))
    ]
    return IdentityResolutionEngine(
        SnapshotIndex(lines),
        off,
        horizon=date(2020, 1, 1),
        transitions=tr if with_transition else (),
    )


def test_mts_is_resolved_by_official_code_isin_documents_not_by_the_label() -> None:
    segs = _mts_engine().resolve(_span("MTS", "2009-05-05", None))
    assert _isins(segs, date(2012, 3, 1)) == {"LU0000000012"}
    assert _isins(segs, date(2019, 1, 2)) == {"LU0000000020"}
    # the reverse split boundary is the OFFICIAL trading date, not the ANCV issue date (05-18)
    assert _isins(segs, date(2017, 5, 19)) == {"LU0000000012"}
    assert _isins(segs, date(2017, 5, 22)) == {"LU0000000020"}
    assert all(
        _ok(s)
        for s in segs
        if s.start >= date(2011, 1, 1) and (s.end or date.max) <= date(2019, 12, 11)
    )


def test_es_only_ancv_snapshots_do_not_interrupt_a_foreign_isin() -> None:
    """From 12/2018 ANCV lists ES ISINs only: a snapshot without the LU ISIN proves nothing."""
    eng = _mts_engine()
    other = [
        _l(d, "ES0000000045", "ZZZ/AC 1,00", "OTHER SA")
        for d in ("2019-06-30", "2019-12-31", "2020-06-30")
    ]
    ix = SnapshotIndex([*[ln for d in eng.ix.dates for ln in eng.ix.by_date[d]], *other])
    off = [
        _o("MTS", "LU0000000012", "2013-07-11"),
        _o("MTS", "LU0000000012", "2017-01-11"),
        _o("MTS", "LU0000000020", "2017-07-21"),
        _o("MTS", "LU0000000020", "2019-12-10"),
        _o("MTS", "LU0000000020", "2020-09-15"),
    ]
    segs = IdentityResolutionEngine(
        ix, off, horizon=date(2020, 10, 1), transitions=list(eng.transitions.values())
    ).resolve(_span("MTS", "2009-05-05", None))
    for d in (date(2019, 7, 1), date(2020, 1, 2), date(2020, 7, 1)):
        assert _isins(segs, d) == {"LU0000000020"}


def test_without_the_official_documents_mts_stays_unresolved() -> None:
    eng = IdentityResolutionEngine(
        _mts_engine().ix, [], horizon=date(2020, 1, 1)
    )  # ANCV alone: label ARCELORMITTAL != MTS
    segs = eng.resolve(_span("MTS", "2009-05-05", None))
    assert not any(_ok(s) for s in segs)


def test_label_equality_alone_never_resolves_a_different_code() -> None:
    """The ISIN labelled XYZ in ANCV must not be assigned to code ABC by name similarity."""
    ix = SnapshotIndex([_l("2015-06-30", "ES0000000011", "XYZ/AC 1,00")])
    segs = IdentityResolutionEngine(ix, horizon=date(2016, 1, 1)).resolve(
        _span("ABC", "2015-01-02", "2015-12-01")
    )
    assert not any(_ok(s) for s in segs)


# ───────────────────────── ABG.P: class B code, class A must never be chosen ───────────────


def test_abg_p_resolves_to_class_b_and_never_to_class_a() -> None:
    a, b = "ES0000000011", "ES0000000029"
    lines = [
        _l(d, a, "ABG/AC A 1,00", "ABENGOA, S.A.")
        for d in ("2013-06-30", "2013-12-31", "2014-06-30")
    ] + [
        _l(d, b, "ABG/AC B 0,01", "ABENGOA, S.A.")
        for d in ("2013-06-30", "2013-12-31", "2014-06-30")
    ]
    off = [_o("ABG.P", b, "2013-01-13"), _o("ABG.P", b, "2014-07-26")]
    segs = IdentityResolutionEngine(SnapshotIndex(lines), off, horizon=date(2015, 1, 1)).resolve(
        _span("ABG.P", "2012-10-26", "2014-09-01")
    )
    assert {s.isin for s in segs if s.isin} == {b}
    assert a not in {c for s in segs for c in s.candidates}


# ───────────────────────── GRF / REE / PHM: dated splits ───────────────────────────────────


def test_grifols_split_boundaries_around_2016_01_04() -> None:
    old, new = "ES0000000011", "ES0000000029"
    lines = [
        _l("2015-12-31", old, "GRF/AC A 0,50", "GRIFOLS, S.A."),
        _l("2016-06-30", new, "GRF/AC A 0,25", "GRIFOLS, S.A."),
    ]
    tr = [IsinTransition(old, new, date(2016, 1, 4), "SPLIT", "SAME_SECURITY", ("d" * 64,))]
    segs = IdentityResolutionEngine(
        SnapshotIndex(lines), horizon=date(2017, 1, 1), transitions=tr
    ).resolve(_span("GRF", "2008-01-02", None))
    assert _isins(segs, date(2015, 12, 31)) == {old}
    assert _isins(segs, date(2016, 1, 4)) == {new}  # first session of the new ISIN
    assert _isins(segs, date(2016, 1, 5)) == {new}


def test_phm_uses_the_trading_date_not_the_ancv_issue_date() -> None:
    old, new = "ES0000000011", "ES0000000029"
    lines = [
        _l("2020-06-30", old, "PHM/AC 0,05", "PHARMA MAR, S.A."),
        _l("2020-12-31", new, "PHM/AC 0,60", "PHARMA MAR, S.A.", issue_date=date(2020, 7, 13)),
    ]
    tr = [
        IsinTransition(old, new, date(2020, 7, 22), "REVERSE_SPLIT", "SAME_SECURITY", ("e" * 64,))
    ]
    segs = IdentityResolutionEngine(
        SnapshotIndex(lines), horizon=date(2021, 6, 1), transitions=tr
    ).resolve(_span("PHM", "2010-01-04", None))
    assert _isins(segs, date(2020, 7, 21)) == {old}  # after the ANCV issue date 07-13: still old
    assert _isins(segs, date(2020, 7, 22)) == {new}


def test_transition_outside_the_evidence_bracket_fails_closed() -> None:
    """A transition dated BEFORE the last evidence of the old ISIN contradicts the evidence."""
    old, new = "ES0000000011", "ES0000000029"
    lines = [
        _l("2016-06-30", old, "REE/AC 2,00", "RED ELECTRICA"),
        _l("2016-12-31", new, "REE/AC 0,50", "RED ELECTRICA"),
    ]
    tr = [IsinTransition(old, new, date(2016, 3, 1), "SPLIT", "SAME_SECURITY", ())]
    segs = IdentityResolutionEngine(
        SnapshotIndex(lines), horizon=date(2017, 6, 1), transitions=tr
    ).resolve(_span("REE", "2010-01-04", None))
    assert not _isins(segs, date(2016, 9, 1))  # the window stays unresolved


# ───────────────────────── PUIG: a tie only an EXACT document may break ────────────────────


def test_puig_class_b_selected_by_an_exact_document_never_class_a() -> None:
    a, b = "ES0000000011", "ES0000000029"
    lines = [
        _l(d, a, "PUIG/AC 0.30 A", "PUIG BRANDS, S.A.") for d in ("2024-06-30", "2024-12-31")
    ] + [_l(d, b, "PUIG/AC 0.06 B", "PUIG BRANDS, S.A.") for d in ("2024-06-30", "2024-12-31")]
    span = _span("PUIG", "2024-07-22", None)
    exact = _o("PUIG", b, "2024-05-03")
    exact2 = _o("PUIG", b, "2025-01-10")  # a later exact point brackets the 2024-12-31 snapshot
    segs = IdentityResolutionEngine(
        SnapshotIndex(lines), [exact, exact2], horizon=date(2025, 3, 1)
    ).resolve(span)
    assert a not in {s.isin for s in segs if s.isin}
    assert _isins(segs, date(2024, 9, 2)) == {b}
    transcription = OfficialIdentifier(
        "PUIG", b, date(2026, 10, 1), "BME rendered page", "b" * 64, False
    )
    weak = IdentityResolutionEngine(
        SnapshotIndex(lines), [transcription], horizon=date(2026, 10, 1)
    ).resolve(span)
    assert not any(_ok(s) for s in weak)  # a transcription still cannot break the tie


def test_stale_exact_evidence_does_not_break_a_tie_far_away() -> None:
    a, b = "ES0000000011", "ES0000000029"
    lines = [_l("2026-06-30", a, "PUIG/AC 0.30 A"), _l("2026-06-30", b, "PUIG/AC 0.06 B")]
    segs = IdentityResolutionEngine(
        SnapshotIndex(lines), [_o("PUIG", b, "2024-05-03")], horizon=date(2026, 10, 1)
    ).resolve(_span("PUIG", "2024-07-22", None))
    assert not any(_ok(s) for s in segs)  # > 200 days away: not accepted


# ───────────────────────── FER: merger = NEW security, no backward projection ──────────────


def _fer_build(session: Session) -> str:
    rows = [BMEHistoryRow(date(2011, 1, 3), ("FER", "AAA", "BBB"), (), RowStyle.UNKNOWN, "r1")]
    res = classify_rows(rows, (), "FIX_IDX")
    src = EventSource("FIXTURE_BME", SourceConfidence.SYNTHETIC, res.events, "fixture-fer-1")
    return ingest_event_source(
        session, src, exchange="XMAD", currency="EUR", country="ES", expected_size=(3, 3)
    ).build_id


def test_cross_border_merger_creates_a_new_security_from_the_effective_date(
    session: Session,
) -> None:
    es, nl = "ES0000000011", "NL0000000015"
    bid = _fer_build(session)
    arch = RawSourceArchive(
        provider="FIXTURE",
        source_identifier="f",
        retrieved_at=datetime.now(UTC),
        sha256="0" * 64,
        mime_type="application/zip",
        size_bytes=0,
        storage_uri="-",
    )
    session.add(arch)
    session.flush()
    for d in [date(y, m, 30 if m == 6 else 31) for y in range(2010, 2025) for m in (6, 12)]:
        for code, isin in (("FER", es), ("AAA", "ES0000000029"), ("BBB", "ES0000000037")):
            if code == "FER" and d > date(2022, 12, 31):
                continue  # the ES ISIN is retired after 2023-06-15 (no later ANCV line)
            session.add(
                SecurityIdentitySnapshot(
                    source="CNMV_ANCV",
                    reference_date=d,
                    scope="ACTIVE_IN_ANCV",
                    isin=isin,
                    issuer_legal_name=f"FIXTURE {code}, S.A.",
                    instrument_name=f"{code}/AC 1,00",
                    instrument_class="RV",
                    member_name="f",
                    source_hash="0" * 64,
                    archive_id=arch.archive_id,
                    parser_version="fixture",
                )
            )
    session.flush()
    off = [_o("FER", nl, "2023-06-16"), _o("FER", nl, "2024-01-10")]
    tr = [
        IsinTransition(
            es, nl, date(2023, 6, 16), "CROSS_BORDER_MERGER", "NEW_SECURITY", ("f" * 64,)
        )
    ]
    eng = IdentityResolutionEngine(
        load_snapshot_index(session), off, horizon=date(2024, 6, 1), transitions=tr
    )
    res_first = run_identity_resolution(
        session,
        index_code="FIX_IDX",
        build_id=bid,
        engine=eng,
        canonical_start=date(2011, 1, 1),
        inputs_hash=content_hash(["fer"]),
        official=off,
    )
    (sec_es,) = set(
        session.scalars(select(IdentifierHistory.security_id).where(IdentifierHistory.value == es))
    )
    (sec_nl,) = set(
        session.scalars(select(IdentifierHistory.security_id).where(IdentifierHistory.value == nl))
    )
    assert sec_es != sec_nl  # distinct securities (ADR-0020), never one reused for both ISINs
    old, new = session.get_one(Security, sec_es), session.get_one(Security, sec_nl)
    assert old.successor_security_id == sec_nl and old.listing_end == date(2023, 6, 16)
    assert new.issuer_id == old.issuer_id  # economic continuity of the issuer
    u = IndexUniverse(session)
    assert {m.security_id for m in u.backtest_universe("FIX_IDX", date(2023, 6, 15), bid)} >= {
        sec_es
    }
    after = {m.security_id for m in u.backtest_universe("FIX_IDX", date(2023, 6, 16), bid)}
    assert sec_nl in after and sec_es not in after
    # the NL ISIN is NOT proven before the effective date (no backward projection)
    nl_rows = session.scalars(select(IdentifierHistory).where(IdentifierHistory.value == nl)).all()
    assert min(r.valid_from for r in nl_rows) == date(2023, 6, 16)
    # a SECOND run (the predecessor's ticker is now closed in ticker_history) must give the
    # same answer: spans come from the immutable build events, not from mutated tables
    again = run_identity_resolution(
        session,
        index_code="FIX_IDX",
        build_id=bid,
        engine=eng,
        canonical_start=date(2011, 1, 1),
        inputs_hash=content_hash(["fer", "second"]),
        official=off,
    )
    assert again.metrics == res_first.metrics  # same answer on the second run
    assert sec_nl in {
        m.security_id for m in u.backtest_universe("FIX_IDX", date(2023, 12, 29), bid)
    }
    tick = session.scalars(select(TickerHistory).where(TickerHistory.security_id == sec_es)).all()
    assert any(t.ticker == "FER" and t.valid_to == date(2023, 6, 16) for t in tick)
