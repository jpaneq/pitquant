"""Synthetic documentary guards and dated legal-security reconstruction."""

from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pitquant.core.errors import DataQualityError
from pitquant.data.archive import ArchiveStore, archive_document
from pitquant.db.models import SecuritySuccession, SecurityTickerAlias
from pitquant.universe.d02_documentary import DocumentaryEvent, apply_documentary_events
from pitquant.universe.succession_timeline import SuccessionTimeline
from tests.unit.test_identity_bridge import F13World

pytestmark = pytest.mark.pit

LIMIT = date(2022, 9, 30)
WHEN = datetime(2020, 11, 17, tzinfo=UTC)


def event_world(session: Session, tmp_path: Path, *, published_at=WHEN):
    world = F13World(session)
    old, new = world.sec("SYN OLD"), world.sec("SYN NEW")
    world.evidence(old, "SYNOLD001")
    world.evidence(new, "SYNNEW001")
    world.e13("2020Q3", "SYNOLD001", "SYN OLD", "COM")
    world.e13("2021Q1", "SYNNEW001", "SYN NEW", "COM")
    store = ArchiveStore(tmp_path)
    event = DocumentaryEvent(
        "SYN",
        "https://example.test/primary",
        date(2020, 11, 16),
        ("closed", "one share"),
        "SYN OLD",
        "SYNOLD001",
        "SYNNEW001",
        "2020Q3",
        "2021Q1",
        date(2020, 11, 16),
        date(2020, 11, 17),
        "OLD",
        "NEW",
        event_type="SECURITY_REPLACEMENT_SUCCESSOR",
        ratio=1.0,
    )
    row = archive_document(
        session,
        store,
        provider="D02_PRIMARY_CORPORATE_RELEASE",
        source_identifier=event.url,
        data=b"<html>closed one share</html>",
        mime_type="text/html",
        published_at=published_at,
    )
    return store, event, row, old, new


def test_documentary_is_idempotent_and_preserves_replacement(session: Session, tmp_path: Path):
    store, event, _, old, new = event_world(session, tmp_path)
    for _ in range(2):
        assert apply_documentary_events(session, store, limit=LIMIT, events=(event,))[0].applied
    assert session.scalar(select(func.count()).select_from(SecuritySuccession)) == 1
    assert session.scalar(select(func.count()).select_from(SecurityTickerAlias)) == 2
    timeline = SuccessionTimeline(session)
    assert timeline.at(frozenset({new}), datetime(2020, 11, 16, tzinfo=UTC)) == {old}
    assert timeline.at(frozenset({new}), WHEN) == {new}


@pytest.mark.parametrize("case", ["clause", "publication", "support", "future"])
def test_missing_proof_never_adds_identity_links(session: Session, tmp_path: Path, case: str):
    store, event, _row, _, _ = event_world(
        session,
        tmp_path,
        published_at=datetime(2023, 1, 1, tzinfo=UTC) if case == "publication" else WHEN,
    )
    if case == "clause":
        event = replace(event, clauses=("unproven",))
    elif case == "publication":
        pass
    elif case == "support":
        event = replace(
            event, support=(("https://example.test/missing", date(2020, 11, 16), ("proof",)),)
        )
    else:
        event = replace(event, ticker_date=date(2023, 1, 1))
    assert not apply_documentary_events(session, store, limit=LIMIT, events=(event,))[0].applied
    assert session.scalar(select(func.count()).select_from(SecuritySuccession)) == 0


def test_corrupt_original_fails_loudly(session: Session, tmp_path: Path):
    store, event, row, _, _ = event_world(session, tmp_path)
    store.path_for(row.sha256).write_bytes(b"tampered")
    with pytest.raises(DataQualityError, match="hash verification"):
        apply_documentary_events(session, store, limit=LIMIT, events=(event,))


def edge(session, pred, succ, kind="SECURITY_REPLACEMENT_SUCCESSOR", effective=WHEN):
    session.add(
        SecuritySuccession(
            security_predecessor_id=pred,
            security_successor_id=succ,
            event_type=kind,
            effective_at=effective,
            membership_continuity=True,
            source="SYNTHETIC",
        )
    )
    session.flush()


def test_class_conversion_recovers_both_previous_classes(session: Session):
    w = F13World(session)
    a, c, new = (w.sec(n) for n in ("A", "C", "NEW"))
    edge(session, a, new, "SHARE_CLASS_CHANGE")
    edge(session, c, new, "SHARE_CLASS_CHANGE")
    t = SuccessionTimeline(session)
    assert t.at(frozenset({new}), datetime(2020, 11, 16, tzinfo=UTC)) == {a, c}
    assert t.at(frozenset({new}), WHEN) == {new}


@pytest.mark.parametrize("case", ["undated", "conflicting", "unproven_classes", "cycle"])
def test_replacement_ambiguity_is_fail_closed(session: Session, case: str):
    w = F13World(session)
    a, b, new = (w.sec(n) for n in ("A", "B", "NEW"))
    edge(session, a, new, effective=None if case == "undated" else WHEN)
    if case == "conflicting":
        edge(session, b, new, effective=datetime(2020, 11, 18, tzinfo=UTC))
    elif case == "unproven_classes":
        edge(session, b, new)
    elif case == "cycle":
        edge(session, new, a)
    with pytest.raises(DataQualityError):
        SuccessionTimeline(session).at(frozenset({new}), datetime(2020, 11, 16, tzinfo=UTC))


def test_successive_replacements_return_correct_intermediate_security(session: Session):
    w = F13World(session)
    a, b, c = (w.sec(n) for n in ("A", "B", "C"))
    edge(session, a, b, effective=datetime(2019, 1, 1, tzinfo=UTC))
    edge(session, b, c)
    t = SuccessionTimeline(session)
    assert t.at(frozenset({c}), datetime(2018, 1, 1, tzinfo=UTC)) == {a}
    assert t.at(frozenset({c}), datetime(2020, 1, 1, tzinfo=UTC)) == {b}
    assert t.at(frozenset({c}), WHEN) == {c}


def test_two_distinct_originals_cannot_silently_choose_a_version(session: Session, tmp_path: Path):
    store, event, _, _, _ = event_world(session, tmp_path)
    archive_document(
        session,
        store,
        provider="D02_PRIMARY_CORPORATE_RELEASE",
        source_identifier=event.url,
        data=b"<html>closed one share amended</html>",
        mime_type="text/html",
        published_at=WHEN,
    )
    assert not apply_documentary_events(session, store, limit=LIMIT, events=(event,))[0].applied
    assert session.scalar(select(func.count()).select_from(SecuritySuccession)) == 0


def test_graph_publishes_two_classes_before_their_single_successor(session: Session):
    from pitquant.universe.sp500_anchor_graph import reconstruct
    from tests.unit.test_sp500_anchor_graph import World

    world = World(session)
    world.anchor(date(2020, 3, 31), ["A", "C", "X"])
    world.anchor(date(2020, 6, 30), ["NEW", "X"])
    for predecessor in ("A", "C"):
        edge(
            session,
            world.sec[predecessor],
            world.sec["NEW"],
            "SHARE_CLASS_CHANGE",
            datetime(2020, 5, 1, tzinfo=UTC),
        )
    report = reconstruct(session, date(2020, 4, 1), date(2020, 6, 30))
    assert report.ready == 3
    assert report.cohorts[0].members == {world.sec[name] for name in ("A", "C", "X")}
    assert report.cohorts[0].n_members == 3
    assert report.cohorts[1].members == {world.sec[name] for name in ("NEW", "X")}
    assert report.cohorts[1].n_members == 2
