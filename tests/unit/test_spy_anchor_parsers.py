# ruff: noqa: E501
"""SEC-filed SPY anchors (ADR-0032): NPORT-P / N-30D parsing, identity bootstrap, cross-check, fail-closed verification,
idempotency and immutability. Every document here is a SYNTHETIC FIXTURE (SYN issuers, fake CUSIPs/accessions)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from pitquant.core.errors import ImmutableRecordError
from pitquant.data.archive import ArchiveStore
from pitquant.data.providers.sec_edgar.client import HttpResponse, SECClient
from pitquant.db.models import (
    Security,
    SecurityIdentifierEvidence,
    SP500Anchor,
    SP500AnchorCrossCheck,
    SP500AnchorMember,
)
from pitquant.universe.sources.spy_sec_anchors import (
    HoldingClass,
    isin_valid,
    norm_name,
    parse_n30d_schedule,
    parse_nport,
    parse_submission_header,
)
from pitquant.universe.sp500_anchor_ingest import (
    AnchorTarget,
    AnchorVerificationError,
    Discovered,
    discover_filings,
    ingest,
    resolve_targets,
)

NS = 'xmlns="http://www.sec.gov/edgar/nport"'


def inv(
    name: str,
    cusip: str | None,
    isin: str | None,
    shares: float,
    value: float,
    cat: str = "EC",
    units: str = "NS",
    lei: str = "SYNLEI00000000000001",
) -> str:
    ids = f'<identifiers><isin value="{isin}"/></identifiers>' if isin else ""
    cu = f"<cusip>{cusip}</cusip>" if cusip is not None else ""
    return f"<invstOrSec><name>{name}</name><lei>{lei}</lei><title>{name}</title>{cu}{ids}<balance>{shares}</balance><units>{units}</units><curCd>USD</curCd><valUSD>{value}</valUSD><pctVal>0.1</pctVal><assetCat>{cat}</assetCat></invstOrSec>"


def nport_xml(period: str, holdings: list[str], cik: str = "0000884394") -> bytes:
    return (
        f'<?xml version="1.0"?><edgarSubmission {NS}><headerData><submissionType>NPORT-P</submissionType></headerData><formData><genInfo><regName>SYN FIXTURE TRUST</regName>'
        f"<regFileNumber>811-06125</regFileNumber><regCik>{cik}</regCik><repPdDate>{period}</repPdDate></genInfo><fundInfo><netAssets>1000000000</netAssets></fundInfo>"
        f"<invstOrSecs>{''.join(holdings)}</invstOrSecs></formData></edgarSubmission>"
    ).encode()


def n30d_html(rows: list[tuple[str, int, int]], dup_last: bool = False) -> bytes:
    body = "".join(
        f"<tr><td>{n}</td><td>&nbsp;</td><td>{s:,}</td><td>$</td><td>{v:,}</td></tr>"
        for n, s, v in rows
    )
    if dup_last:
        n, s, v = rows[-1]
        body += f"<tr><td>{n}</td><td>{s:,}</td><td>{v:,}</td></tr>"
    return f"<html><body><table><tr><td>Common Stocks</td></tr>{body}<tr><td>Total Investments</td><td>1,000</td><td>9,999,999</td></tr></table></body></html>".encode()


def header(
    form: str, acc: str, period: str, cik: str = "0000884394", accepted: str = "20221128205055"
) -> str:
    p = period.replace("-", "")
    return f"<SEC-HEADER>{acc}.hdr.sgml : 20221128\nACCESSION NUMBER:\t\t{acc}\nCONFORMED SUBMISSION TYPE:\t{form}\nCONFORMED PERIOD OF REPORT:\t{p}\nFILED AS OF DATE:\t\t20221128\n<ACCEPTANCE-DATETIME>{accepted}\nFILER:\n\tCOMPANY DATA:\n\t\tCENTRAL INDEX KEY:\t\t{cik}\n</SEC-HEADER>"


class FakeSec:
    def __init__(self, routes: dict[str, bytes]):
        self.routes = routes

    def get(self, url: str, headers: dict[str, str]) -> HttpResponse:
        if url in self.routes:
            return HttpResponse(200, self.routes[url], "text/plain")
        return HttpResponse(404, b"", "text/plain")


def build_sec(filings: list[tuple[str, str, str, bytes]]) -> SECClient:
    """filings: (form, accession, period, primary document). Routes mimic EDGAR submissions, index.json, primary doc and the complete submission."""
    recent = {
        "form": [],
        "accessionNumber": [],
        "reportDate": [],
        "acceptanceDateTime": [],
        "filingDate": [],
    }
    routes: dict[str, bytes] = {}
    for form, acc, period, doc in filings:
        recent["form"].append(form)
        recent["accessionNumber"].append(acc)
        recent["reportDate"].append(period)
        recent["acceptanceDateTime"].append("2022-11-28T20:50:55.000Z")
        recent["filingDate"].append("2022-11-28")
        nd = acc.replace("-", "")
        base = f"https://www.sec.gov/Archives/edgar/data/884394/{nd}/"
        pname = "primary_doc.xml" if form == "NPORT-P" else "d1n30d.htm"
        routes[base + "index.json"] = json.dumps(
            {
                "directory": {
                    "item": [{"name": pname}, {"name": f"{acc}-index.html"}, {"name": f"{acc}.txt"}]
                }
            }
        ).encode()
        routes[base + pname] = doc
        routes[base + f"{acc}.txt"] = header(form, acc, period).encode()
    routes["https://data.sec.gov/submissions/CIK0000884394.json"] = json.dumps(
        {"filings": {"recent": recent, "files": []}}
    ).encode()
    return SECClient(FakeSec(routes), "PITQuant tests test@example.org", sleep=lambda _s: None)


# ───────────────────────────────────────────── parsers
def test_nport_parser_reads_identifiers_and_never_builds_them() -> None:
    n = parse_nport(
        nport_xml(
            "2022-09-30", [inv("SYN ALPHA CORP", "SYN000001", "US0000000019", 1000, 50_000_000)]
        )
    )
    h = n.holdings[0]
    assert (n.period, n.reg_cik, n.form) == (date(2022, 9, 30), "0000884394", "NPORT-P")
    assert (
        h.cusip == "SYN000001" and h.isin == "US0000000019" and h.ticker is None
    )  # no ticker in NPORT: not invented
    assert h.klass is HoldingClass.INDEX_EQUITY_CANDIDATE


def test_isin_fallback_when_the_filing_has_the_placeholder_cusip() -> None:
    n = parse_nport(
        nport_xml("2022-09-30", [inv("SYN IRISH PLC", "000000000", "IE00B4BNMY34", 10, 5_000_000)])
    )
    h = n.holdings[0]
    assert (
        h.cusip is None
        and h.isin == "IE00B4BNMY34"
        and h.klass is HoldingClass.INDEX_EQUITY_CANDIDATE
        and isin_valid(h.isin)
    )
    bad = parse_nport(nport_xml("2022-09-30", [inv("SYN NOID", "000000000", None, 10, 5_000_000)]))
    assert (
        bad.holdings[0].klass is HoldingClass.UNRESOLVED
    )  # neither a CUSIP nor an ISIN: never assumed to be a member


def test_non_equity_stub_and_rights_lines_never_become_members() -> None:
    n = parse_nport(
        nport_xml(
            "2022-09-30",
            [
                inv("SYN CASH FUND", None, None, 1, 4_000_000, cat="STIV"),
                inv(
                    "SYN STUB CORP", "SYN000002", "US0000000027", 1.0, 16.7
                ),  # 1 share left after the index deletion
                inv("SYN RIGHTS", "SYN000003", "US0000000035", 500, 9_000_000),
                inv("SYN REAL CORP", "SYN000004", "US0000000043", 500, 9_000_000),
            ],
        )
    )
    k = {h.issuer_name: h.klass for h in n.holdings}
    assert k["SYN CASH FUND"] is HoldingClass.NON_EQUITY
    assert k["SYN STUB CORP"] is HoldingClass.TRANSIENT_CORPORATE_ACTION
    assert k["SYN RIGHTS"] is HoldingClass.TRANSIENT_CORPORATE_ACTION
    assert k["SYN REAL CORP"] is HoldingClass.INDEX_EQUITY_CANDIDATE


def test_duplicate_cusip_lines_are_merged_and_reported() -> None:
    n = parse_nport(
        nport_xml(
            "2022-09-30",
            [
                inv("SYN A", "SYN000001", "US0000000019", 100, 5_000_000),
                inv("SYN A", "SYN000001", "US0000000019", 50, 2_500_000),
            ],
        )
    )
    assert len(n.holdings) == 1 and n.duplicates_merged == 1 and n.holdings[0].shares == 150


def test_schedule_of_investments_parser_skips_headings_totals_and_page_break_repeats() -> None:
    rows = [("SYN Alpha, Inc.(a)", 1000, 5_000_000), ("SYN Beta Corp. REIT", 2000, 7_000_000)]
    s = parse_n30d_schedule(n30d_html(rows, dup_last=True))
    assert [h.name for h in s] == [
        "SYN Alpha, Inc.",
        "SYN Beta Corp.",
    ]  # footnote and REIT marker stripped, Total skipped, repeat dropped
    assert len(parse_n30d_schedule(n30d_html(rows, dup_last=True), dedupe=False)) == 3
    assert norm_name("SYN Alpha, Inc. Class A") != norm_name(
        "SYN Alpha, Inc. Class C"
    )  # the class designator is kept


def test_submission_header_states_form_period_filer_and_acceptance() -> None:
    h = parse_submission_header(header("NPORT-P", "0001-22-1", "2022-09-30"))
    assert (h.form, h.period, h.filer_cik, h.accepted_at) == (
        "NPORT-P",
        date(2022, 9, 30),
        "0000884394",
        datetime(2022, 11, 28, 20, 50, 55, tzinfo=UTC),
    )


# ───────────────────────────────────────────── verification (fail closed)
def test_declared_accession_must_match_form_and_period_or_nothing_is_ingested() -> None:
    found = [Discovered("NPORT-P", "0001-22-1", date(2022, 9, 30), "x", "2022-11-28")]
    ok, bad = resolve_targets(found, [AnchorTarget(date(2022, 9, 30), "NPORT-P", "0001-22-1")])
    assert ok and not bad
    _, bad = resolve_targets(
        found, [AnchorTarget(date(2022, 6, 30), "NPORT-P", "0001-22-1")]
    )  # right accession, wrong period
    assert bad and "EDGAR says" in bad[0]
    _, bad = resolve_targets(found, [AnchorTarget(date(2022, 9, 30), "NPORT-P", "9999-99-9")])
    assert bad and "not in the EDGAR submissions" in bad[0]


def test_filing_whose_own_header_disagrees_is_rejected(session: Session, tmp_path: Path) -> None:
    client = build_sec(
        [
            (
                "NPORT-P",
                "0001-22-1",
                "2022-09-30",
                nport_xml(
                    "2022-09-30", [inv("SYN A", "SYN000001", "US0000000019", 100, 5_000_000)]
                ),
            )
        ]
    )
    routes = client.transport.routes  # type: ignore[attr-defined]
    routes[next(u for u in routes if u.endswith("0001-22-1.txt"))] = header(
        "NPORT-P", "0001-22-1", "2022-09-30", cik="0000111111"
    ).encode()
    with pytest.raises(AnchorVerificationError, match="filer CIK"):
        ingest(
            session,
            client,
            ArchiveStore(tmp_path),
            [AnchorTarget(date(2022, 9, 30), "NPORT-P", "0001-22-1")],
        )
    assert session.scalars(select(SP500Anchor)).first() is None


# ───────────────────────────────────────────── ingestion, identity, cross-check
def two_filings() -> list[tuple[str, str, str, bytes]]:
    nport = nport_xml(
        "2022-09-30",
        [
            inv("SYN ALPHA CORP", "SYN000001", "US0000000019", 1000, 50_000_000),
            inv("SYN BETA CORP", "SYN000002", "US0000000027", 2000, 60_000_000),
            inv(
                "SYN BETA CORP", "SYN000003", "US0000000035", 500, 15_000_000
            ),  # SAME NAME, different CUSIP: a different security
            inv("SYN STUB", "SYN000009", "US0000000092", 1, 20),
        ],
    )
    n30d = n30d_html(
        [
            ("SYN Alpha, Inc.", 1010, 50_500_000),
            ("SYN Beta Corp.", 2020, 60_600_000),
            ("SYN Beta Corp. Class C", 505, 15_150_000),
            ("SYN Extra Corp.", 100, 8_000_000),
        ]
    )
    return [
        ("NPORT-P", "0001-22-1", "2022-09-30", nport),
        ("N-30D", "0002-22-2", "2022-09-30", n30d),
    ]


def test_ingestion_identity_crosscheck_and_idempotency(session: Session, tmp_path: Path) -> None:
    client = build_sec(two_filings())
    targets = [
        AnchorTarget(date(2022, 9, 30), "NPORT-P", "0001-22-1"),
        AnchorTarget(date(2022, 9, 30), "N-30D", "0002-22-2"),
    ]
    rep, _ = ingest(session, client, ArchiveStore(tmp_path), targets)
    anchors = {a.form: a for a in session.scalars(select(SP500Anchor))}
    a, b = anchors["NPORT-P"], anchors["N-30D"]
    # two clocks, never merged; evidence is never OFFICIAL_SPDJI
    assert a.as_of_date == date(2022, 9, 30) and a.source_available_at == datetime(
        2022, 11, 28, 20, 50, 55, tzinfo=UTC
    )
    assert (
        a.evidence_kind == "SEC_FILED_INDEX_REPLICATION_ANCHOR"
        and a.evidence_tier == "SEC_NPORT_IDENTIFIED_ANCHOR"
        and b.evidence_tier == "SEC_SCHEDULE_ANCHOR"
    )
    assert (a.member_count, a.excluded_count, a.unresolved_count) == (
        3,
        1,
        0,
    )  # the 1-share stub is excluded
    # same name, two CUSIPs -> two securities; each CUSIP is OFFICIAL evidence
    betas = [
        m
        for m in session.scalars(
            select(SP500AnchorMember).where(SP500AnchorMember.anchor_id == a.anchor_id)
        )
        if m.issuer_name == "SYN BETA CORP"
    ]
    assert len({m.security_id for m in betas}) == 2
    assert (
        session.scalars(
            select(SecurityIdentifierEvidence).where(
                SecurityIdentifierEvidence.value == "SYN000001"
            )
        )
        .first()
        .kind
        == "OFFICIAL"
    )  # type: ignore[union-attr]
    # schedule lines are linked to the NPORT securities by (price, shares) of the SAME date, incl. the class-qualified name
    sched = {
        m.issuer_name: m
        for m in session.scalars(
            select(SP500AnchorMember).where(SP500AnchorMember.anchor_id == b.anchor_id)
        )
    }
    assert (
        sched["SYN Alpha, Inc."].identity_basis == "SHARES_VALUE"
        and sched["SYN Beta Corp. Class C"].identity_basis == "SHARES_VALUE"
    )
    assert sched["SYN Extra Corp."].identity_basis == "NAME_ONLY"
    cc = session.scalars(select(SP500AnchorCrossCheck)).one()
    assert (
        cc.metrics["nport_equities"] == 3
        and cc.metrics["matched"] == 3
        and cc.metrics["schedule_only"] == 1
        and cc.metrics["nport_only"] == 0
    )
    n_sec = len(session.scalars(select(Security)).all())
    rep2, _ = ingest(session, client, ArchiveStore(tmp_path), targets)  # re-run: idempotent
    assert (
        len(rep2.created_anchors) == 0
        and len(rep2.skipped_existing) == 2
        and len(session.scalars(select(Security)).all()) == n_sec
    )
    assert rep.created_securities >= 4


def test_anchors_are_append_only(session: Session, tmp_path: Path) -> None:
    ingest(
        session,
        build_sec(two_filings()),
        ArchiveStore(tmp_path),
        [AnchorTarget(date(2022, 9, 30), "NPORT-P", "0001-22-1")],
    )
    a = session.scalars(select(SP500Anchor)).one()
    a.member_count = 999
    with pytest.raises(ImmutableRecordError):
        session.flush()
    session.rollback()
    with pytest.raises(ImmutableRecordError):
        session.execute(update(SP500AnchorMember).values(shares=1))
        session.flush()


def test_discovery_lists_only_nport_and_n30d_of_the_spy_trust() -> None:
    client = build_sec(two_filings())
    assert {(d.form, d.period) for d in discover_filings(client)} == {
        ("NPORT-P", date(2022, 9, 30)),
        ("N-30D", date(2022, 9, 30)),
    }
