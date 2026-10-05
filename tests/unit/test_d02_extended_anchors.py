"""DEV extension must preserve discrepancies, classes and the sealed split.

SEC routes and instruments are synthetic; no live network is used in tests.
"""

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from scripts import ingest_spy_anchors as cli
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pitquant.data.archive import ArchiveStore
from pitquant.db.models import RawSourceArchive, SP500Anchor
from pitquant.research import first_ml as FM
from pitquant.research import first_ml_contract as C
from pitquant.research.membership_bridge import legal_name_key
from pitquant.universe.sources.sp500_renames import RenameStatement
from pitquant.universe.sources.spy_sec_anchors import FilingHeader
from pitquant.universe.sp500_anchor_graph import AnchorNode, Leg, Resolver
from pitquant.universe.sp500_anchor_ingest import (
    AnchorVerificationError,
    Discovered,
    FilingDocs,
    parse_anchor,
    schedule_period,
)
from tests.unit.test_first_ml_readiness import months
from tests.unit.test_spy_anchor_parsers import build_sec, n30d_html


def dated_doc(period: str) -> bytes:
    return (
        b"<p>Schedule of Investments</p><p>"
        + period.encode()
        + b"</p>"
        + n30d_html([("SYN ALPHA", 1000, 5_000_000)])
    )


def test_actual_schedule_period_overrules_neither_api_nor_header() -> None:
    doc = dated_doc("September 30, 2014")
    filing = Discovered("N-30D", "SYN", date(2013, 9, 30), "2014-12-01", "2014-12-01")
    h = FilingHeader(
        "N-30D",
        "SYN",
        filing.period,
        "0000884394",
        datetime(2014, 12, 1, tzinfo=UTC),
        date(2014, 12, 1),
    )
    assert schedule_period(doc) == date(2014, 9, 30)
    with pytest.raises(AnchorVerificationError, match="schedule period"):
        parse_anchor(FilingDocs(h, "schedule.htm", doc), filing)


def test_extension_commits_only_verified_targets_and_is_idempotent(
    session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pitquant.universe.sp500_anchor_ingest import AnchorTarget

    monkeypatch.setattr(
        cli,
        "EXTENSION",
        [AnchorTarget(date(2015, 3, 31), "N-30D"), AnchorTarget(date(2014, 9, 30), "N-30D")],
    )
    client = build_sec(
        [("N-30D", "0000000000-15-000001", "2015-03-31", dated_doc("March 31, 2015"))]
    )
    report, errors = cli.extend_anchors(session, client, ArchiveStore(tmp_path))
    assert len(report.created_anchors) == 1 and len(errors) == 1
    assert "2014-09-30: 0 candidate" in errors[0]
    again, again_errors = cli.extend_anchors(session, client, ArchiveStore(tmp_path))
    assert not again.created_anchors and again_errors == errors
    assert session.scalar(select(func.count()).select_from(SP500Anchor)) == 1
    anchor = session.scalars(select(SP500Anchor)).one()
    archive = session.get_one(RawSourceArchive, anchor.archive_id)
    assert anchor.source_sha256 == archive.sha256
    assert ArchiveStore(tmp_path).get(archive.sha256) == dated_doc("March 31, 2015")
    assert anchor.source_available_at.date() > anchor.as_of_date


def test_undated_extension_is_archived_but_never_an_anchor(
    session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pitquant.universe.sp500_anchor_ingest import AnchorTarget

    monkeypatch.setattr(cli, "EXTENSION", [AnchorTarget(date(2015, 3, 31), "N-30D")])
    client = build_sec(
        [("N-30D", "0000000000-15-000002", "2015-03-31", n30d_html([("SYN", 100, 5_000_000)]))]
    )
    report, errors = cli.extend_anchors(session, client, ArchiveStore(tmp_path))
    assert not report.created_anchors and "schedule date not extracted" in errors[0]
    assert session.scalar(select(func.count()).select_from(RawSourceArchive)) == 3
    assert session.scalar(select(func.count()).select_from(SP500Anchor)) == 0


@pytest.mark.pit
@pytest.mark.parametrize("n,expected", [(60, 0), (61, 1), (73, 2), (84, 2), (85, 3)])
def test_exact_required_continuous_months(n: int, expected: int) -> None:
    assert len(C.walk_forward_folds(months(date(2011, 1, 1), n)).folds) == expected
    assert C.REQUIRED_SECURITIES == 100 and C.MIN_FOLDS == 3


@pytest.mark.pit
def test_planner_cannot_admit_holdout_or_oot_even_if_caller_supplies_them() -> None:
    plan = C.walk_forward_folds(months(date(2011, 1, 1), 220))
    assert plan.folds and all(f.test_end < C.month_index(C.HOLDOUT[0]) for f in plan.folds)
    assert not C.walk_forward_folds(months(C.OOT_START, 100)).folds


@pytest.mark.pit
@pytest.mark.parametrize(
    "status,members",
    [
        ("NO_ANCHOR", None),
        ("BLOCKED", frozenset({"OLD"})),
        ("MEMBERSHIP_READY", frozenset({"OLD"})),
    ],
)
def test_missing_anchor_or_weak_lineage_cannot_enter_folds(
    status: str, members: frozenset[str] | None
) -> None:
    assert not FM.cohort_is_usable(status, members, {"NEW"}, {"OLD": "NEW"})
    assert FM.cohort_is_usable("MEMBERSHIP_READY", frozenset({"OTHER"}), {"NEW"}, {"OLD": "NEW"})


def node(period: date, names: dict[str, str]) -> AnchorNode:
    return AnchorNode(
        str(period),
        period,
        "SEC_SCHEDULE_ANCHOR",
        "N-30D",
        None,
        frozenset(names),
        0,
        {},
        names,
        {},
    )


def test_old_predecessor_does_not_steal_successor_addition(session: Session) -> None:
    old = node(date(2010, 9, 30), {"OLD": "SYN Legacy Corp"})
    a = node(date(2019, 3, 31), {})
    b = node(date(2019, 9, 30), {"NEW": "SYN Successor Corp"})
    rename = RenameStatement(
        "RENAME",
        "SYN Legacy Corp",
        "SYN Successor Corp",
        "OLD",
        "NEW",
        False,
        "SYN official statement",
        date(2019, 6, 3),
    )
    resolver = Resolver(session, [old, a, b], renames=[rename])
    leg = Leg(
        "SYN",
        "OFFICIAL_CONFIRMED",
        "ADD",
        "NEW",
        "SYN Legacy Corp",
        date(2019, 6, 7),
        date(2019, 6, 7),
        True,
        None,
    )
    resolver.resolve(leg, a, b, set())
    assert leg.security_id == "NEW" and leg.resolution == "RENAME_STATEMENT"
    early = Leg(
        "SYN",
        "OFFICIAL_CONFIRMED",
        "ADD",
        "NEW",
        "SYN Legacy Corp",
        date(2019, 5, 1),
        date(2019, 5, 1),
        True,
        None,
    )
    resolver.resolve(early, a, b, set())
    assert early.security_id == "OLD"  # a future rename cannot resolve this event


def test_class_a_and_c_are_never_the_same_issuer_name_key() -> None:
    assert legal_name_key("Alphabet Inc Class A") != legal_name_key("Alphabet Inc Class C")
    assert legal_name_key("Google Inc Class A") != legal_name_key("Alphabet Inc Class A")


@pytest.mark.pit
def test_conflicting_official_cusip_and_isin_never_create_verified_anchor(
    session: Session, tmp_path: Path
) -> None:
    from pitquant.db.models import Security, SecurityIdentifierEvidence
    from pitquant.universe.sp500_anchor_ingest import AnchorTarget, ingest
    from tests.unit.test_spy_anchor_parsers import inv, nport_xml

    securities = [
        Security(name="SYN A", exchange="XNYS", currency="USD"),
        Security(name="SYN B", exchange="XNYS", currency="USD"),
    ]
    session.add_all(securities)
    session.flush()
    for security, identifier_type, value in [
        (securities[0], "CUSIP", "SYN000001"),
        (securities[1], "ISIN", "US0000000019"),
    ]:
        session.add(
            SecurityIdentifierEvidence(
                security_id=security.security_id,
                id_type=identifier_type,
                value=value,
                kind="OFFICIAL",
                observed_on=date(2019, 9, 30),
                source_kind="SYN_FIXTURE",
                source_url="fixture",
                parser_version="fixture",
            )
        )
    session.flush()
    client = build_sec(
        [
            (
                "NPORT-P",
                "0000000000-20-000001",
                "2020-03-31",
                nport_xml("2020-03-31", [inv("SYN", "SYN000001", "US0000000019", 1000, 5_000_000)]),
            )
        ]
    )
    with pytest.raises(AnchorVerificationError, match="conflicting security identifiers"):
        ingest(
            session, client, ArchiveStore(tmp_path), [AnchorTarget(date(2020, 3, 31), "NPORT-P")]
        )
    assert session.scalar(select(func.count()).select_from(SP500Anchor)) == 0
