"""S&P 500 membership sources (D-02). All rows are FIXTURES (fictional identifiers)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from pitquant.core.errors import ProviderContractError
from pitquant.data.archive import ArchiveStore
from pitquant.db.models import RawSourceArchive
from pitquant.jobs.index_ingest import ingest_event_source
from pitquant.security_master.service import SecurityMaster
from pitquant.universe.events import MembershipSequenceError, SourceConfidence, cross_check
from pitquant.universe.index_membership import IdentityUnresolvedError, IndexUniverse
from pitquant.universe.sources.spdji import (
    SPDJIAnnouncementReconstructionProvider,
    SPDJILicensedFileProvider,
)

pytestmark = pytest.mark.pit

LICENSED = b"""event_id,effective_date,announced_at,action,ticker,new_ticker,identifier,reason
E0A,2010-01-04,,INITIAL,AAA,,FIX:0001,
E0B,2010-01-04,,INITIAL,BBB,,FIX:0002,
E0C,2010-01-04,,INITIAL,CCC,,FIX:0003,
E1,2012-03-19,2012-03-09T22:00:00+00:00,DELETE,BBB,,FIX:0002,acquired by AAA
E2,2012-03-19,2012-03-09T22:00:00+00:00,ADD,DDD,,FIX:0004,replaces BBB
E3,2014-06-02,2014-05-20T22:00:00+00:00,TICKER_CHANGE,CCC,CCX,FIX:0003,
"""

SNAPSHOT = b"""ticker,identifier
AAA,FIX:0001
CCX,FIX:0003
DDD,FIX:0004
"""

ANNOUNCEMENTS = b"""announcement_id,announced_at,effective_date,action,ticker,identifier,reason,\
source_url
A1,2012-03-09T22:00:00+00:00,2012-03-19,DELETE,BBB,FIX:0002,acquired,https://example.invalid/spdji/a1
A2,2012-03-09T22:00:00+00:00,2012-03-19,ADD,DDD,FIX:0004,replaces BBB,https://example.invalid/spdji/a1
"""


def _ingest(session: Session, src, size=(3, 3)):  # type: ignore[no-untyped-def]
    return ingest_event_source(
        session, src, exchange="XNYS", currency="USD", country="US", expected_size=size
    )


def test_licensed_history_builds_canonical_universe(session: Session, tmp_path: Path) -> None:
    p = SPDJILicensedFileProvider(
        LICENSED, "licensed://spdji/history-2026-10", ArchiveStore(tmp_path)
    )
    rep = _ingest(session, p.load(session))
    u = IndexUniverse(session)
    assert rep.status == "ok"
    assert u.source_status("SP500") == SourceConfidence.CANONICAL
    sm = SecurityMaster(session)
    bbb = sm.resolve("BBB", "XNYS", date(2011, 1, 3))
    assert bbb in u.universe_ids("SP500", date(2012, 3, 16))
    assert bbb not in u.universe_ids(
        "SP500", date(2012, 3, 19)
    )  # vanished company preserved in past
    ccc = sm.resolve("CCC", "XNYS", date(2013, 1, 2))
    assert sm.resolve("CCX", "XNYS", date(2015, 1, 2)) == ccc  # ticker change, same security
    # the raw source file is archived with its hash
    arch = session.query(RawSourceArchive).one()
    assert arch.provider == "SPDJI_LICENSED" and len(arch.sha256) == 64


def test_every_entry_and_exit_needs_a_cause(session: Session, tmp_path: Path) -> None:
    bad = LICENSED.replace(b"acquired by AAA", b"")
    p = SPDJILicensedFileProvider(bad, "licensed://bad", ArchiveStore(tmp_path))
    with pytest.raises(ProviderContractError):
        p.load(session)


def test_reconstruction_provider_is_provisional(session: Session, tmp_path: Path) -> None:
    p = SPDJIAnnouncementReconstructionProvider(
        snapshot_date=date(2015, 1, 2),
        snapshot_csv=SNAPSHOT,
        announcements_csv=ANNOUNCEMENTS,
        coverage_start=date(2010, 1, 4),
        store=ArchiveStore(tmp_path),
    )
    src = p.load(session)
    assert src.confidence is SourceConfidence.PROVISIONAL_RESEARCH_SOURCE
    _ingest(session, src)
    u = IndexUniverse(session)
    assert u.source_status("SP500") == "PROVISIONAL_RESEARCH_SOURCE"
    # Reversing the announcements recovers the deleted company in the past ...
    early = u.universe("SP500", date(2011, 1, 3))
    assert len(early) == 3
    # ... but neither its identity nor its ticker at that date is proven: the modern
    # (snapshot) ticker is NOT projected backwards and every interval is unresolved.
    assert {m.identity_status for m in early} == {"IDENTITY_UNRESOLVED"}
    sm = SecurityMaster(session)
    assert {sm.ticker_as_of(m.security_id, date(2011, 1, 3)) for m in early} == {None}
    # Tickers appear only from the date a source states them.
    aaa = sm.resolve("AAA", "XNYS", date(2015, 1, 2))
    assert sm.ticker_as_of(aaa, date(2015, 1, 1)) is None
    bbb = sm.resolve("BBB", "XNYS", date(2012, 3, 9))  # observed in announcement A1
    assert bbb in u.universe_ids("SP500", date(2011, 1, 3))
    # Fail closed for backtests; never eligible for the holdout / final validation.
    with pytest.raises(IdentityUnresolvedError):
        u.backtest_universe("SP500", date(2011, 1, 3))
    build = u.active_build("SP500")
    assert build.eligible_for_final_model_validation is False
    assert build.report["n_identity_unresolved"] == 3
    # A member added by a dated announcement (with identifier) is resolved.
    later = {m.identity_status for m in u.universe("SP500", date(2013, 1, 2))}
    assert later == {"IDENTITY_UNRESOLVED", "RESOLVED"}


def test_licensed_build_is_eligible_and_backtestable(session: Session, tmp_path: Path) -> None:
    p = SPDJILicensedFileProvider(LICENSED, "licensed://spdji/h", ArchiveStore(tmp_path))
    rep = _ingest(session, p.load(session))
    assert rep.eligible_for_final_model_validation and rep.n_identity_unresolved == 0
    u = IndexUniverse(session)
    assert len(u.backtest_universe("SP500", date(2011, 1, 3))) == 3
    assert u.is_eligible_for_final_validation(rep.build_id)


def test_inconsistent_announcements_fail_loudly(session: Session, tmp_path: Path) -> None:
    bad = ANNOUNCEMENTS.replace(b"2012-03-19,ADD,DDD", b"2012-03-19,ADD,ZZZ").replace(
        b"FIX:0004,replaces", b"FIX:0099,replaces"
    )
    p = SPDJIAnnouncementReconstructionProvider(
        date(2015, 1, 2), SNAPSHOT, bad, date(2010, 1, 4), ArchiveStore(tmp_path)
    )
    with pytest.raises(MembershipSequenceError):
        p.load(session)


def test_no_accidental_duplicates_and_size_checked(session: Session, tmp_path: Path) -> None:
    dup = LICENSED + b"E9,2013-01-02,2012-12-20T22:00:00+00:00,ADD,AAA,,FIX:0001,dup\n"
    p = SPDJILicensedFileProvider(dup, "licensed://dup", ArchiveStore(tmp_path))
    with pytest.raises(MembershipSequenceError):
        _ingest(session, p.load(session))
    p2 = SPDJILicensedFileProvider(LICENSED, "licensed://ok", ArchiveStore(tmp_path))
    with pytest.raises(MembershipSequenceError):
        _ingest(session, p2.load(session), size=(495, 510))


def test_crosscheck_detects_discrepancies() -> None:
    canon = {date(2012, 3, 19): {"AAA", "CCC", "DDD"}}
    wiki = {date(2012, 3, 19): {"AAA", "BBB", "CCC"}}
    (d,) = cross_check(canon, wiki)
    assert d.only_in_canonical == {"DDD"} and d.only_in_crosscheck == {"BBB"}
