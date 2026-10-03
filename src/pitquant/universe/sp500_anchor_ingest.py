# ruff: noqa: E501
"""Ingestion of SEC-filed SPY anchors (ADR-0032): discovery in EDGAR submissions, fail-closed verification, archive,
parse, identity bootstrap by CUSIP/ISIN (never by ticker) and persistence. Idempotent. The network is injected
(``SECClient``) so tests replay fixtures."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.core.errors import DataQualityError
from pitquant.data.archive import ArchiveStore, archive_document
from pitquant.data.providers.sec_edgar.client import SECClient
from pitquant.db.models import (
    RawSourceArchive,
    Security,
    SecurityIdentifierEvidence,
    SP500Anchor,
    SP500AnchorCrossCheck,
    SP500AnchorMember,
)
from pitquant.universe.sources.spy_sec_anchors import (
    EVIDENCE_KIND,
    MIN_MEMBER_VALUE_USD,
    PARSER_VERSION,
    SPY_CIK,
    TIER_A,
    TIER_B,
    FilingHeader,
    HoldingClass,
    parse_n30d_schedule,
    parse_nport,
    parse_submission_header,
)
from pitquant.universe.sources.spy_sec_anchors import norm_name as nn

PROVIDER = "SEC_SPY_ANCHOR"
ARCH = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{name}"
SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"


class AnchorVerificationError(DataQualityError):
    """A filing is not what it was declared to be (form / period / filer): nothing is ingested."""


@dataclass(frozen=True)
class AnchorTarget:
    period: date
    form: str  # NPORT-P | N-30D
    accession: str | None = None  # None = the single filing of that form/period found in EDGAR


# Accessions declared by the owner; every one is CHECKED against EDGAR (the prompt is not an authority).
NPORT_DECLARED = {
    date(2019, 12, 31): "0001752724-20-042737",
    date(2020, 3, 31): "0001752724-20-111515",
    date(2020, 6, 30): "0001752724-20-177260",
    date(2020, 9, 30): "0001752724-20-236128",
    date(2020, 12, 31): "0001752724-21-043869",
    date(2021, 3, 31): "0001752724-21-119080",
    date(2021, 6, 30): "0001752724-21-189808",
    date(2021, 9, 30): "0001752724-21-258706",
    date(2021, 12, 31): "0001752724-22-048845",
    date(2022, 3, 31): "0001752724-22-127611",
    date(2022, 6, 30): "0001752724-22-196968",
    date(2022, 9, 30): "0001752724-22-271183",
}
N30D_DECLARED = {
    date(2017, 9, 30): "0001193125-17-355427",
    date(2019, 3, 31): "0001193125-19-156288",
    date(2019, 9, 30): "0001193125-19-302203",
    date(2020, 3, 31): "0001193125-20-156851",
}


def declared_targets() -> list[AnchorTarget]:
    t = [AnchorTarget(d, "NPORT-P", a) for d, a in NPORT_DECLARED.items()]
    t += [AnchorTarget(d, "N-30D", a) for d, a in N30D_DECLARED.items()]
    return t


def discovered_targets(
    core_start: date = date(2017, 9, 30), last: date = date(2022, 9, 30)
) -> list[AnchorTarget]:
    """The rest of the 2017-09 → 2022-09 chain, found in EDGAR (no accession taken on trust)."""
    return [
        AnchorTarget(d, "N-30D")
        for d in (
            date(2018, 3, 31),
            date(2018, 9, 30),
            date(2020, 9, 30),
            date(2021, 3, 31),
            date(2021, 9, 30),
            date(2022, 3, 31),
            date(2022, 9, 30),
        )
    ] + [AnchorTarget(date(2019, 9, 30), "NPORT-P")]


@dataclass
class Discovered:
    form: str
    accession: str
    period: date
    accepted_at: str
    filing_date: str


def discover_filings(client: SECClient) -> list[Discovered]:
    """Every NPORT-P / N-30D of the SPDR S&P 500 ETF Trust listed in the EDGAR submissions API (recent + archive pages)."""
    base = json.loads(client.get(SUBMISSIONS.format(cik=SPY_CIK)).body)
    blocks = [base["filings"]["recent"]]
    for f in base["filings"].get("files", []):
        blocks.append(json.loads(client.get(f"https://data.sec.gov/submissions/{f['name']}").body))
    out: list[Discovered] = []
    for b in blocks:
        for form, acc, rd, at, fd in zip(
            b["form"],
            b["accessionNumber"],
            b["reportDate"],
            b["acceptanceDateTime"],
            b["filingDate"],
            strict=True,
        ):
            if form in ("NPORT-P", "N-30D") and rd:
                out.append(Discovered(form, acc, date.fromisoformat(rd), at, fd))
    return out


def resolve_targets(
    found: list[Discovered], targets: list[AnchorTarget]
) -> tuple[list[tuple[AnchorTarget, Discovered]], list[str]]:
    """Match each target to EDGAR. A declared accession must match form AND period; otherwise it is a DISCREPANCY."""
    ok: list[tuple[AnchorTarget, Discovered]] = []
    bad: list[str] = []
    for t in targets:
        same = [f for f in found if f.form == t.form and f.period == t.period]
        if t.accession:
            hit = next((f for f in found if f.accession == t.accession), None)
            if hit is None:
                bad.append(
                    f"{t.form} {t.period}: declared accession {t.accession} not in the EDGAR submissions of CIK {SPY_CIK}"
                )
            elif hit.form != t.form or hit.period != t.period:
                bad.append(
                    f"{t.accession}: declared {t.form} {t.period} but EDGAR says {hit.form} period {hit.period}"
                )
            else:
                ok.append((t, hit))
        elif len(same) == 1:
            ok.append((t, same[0]))
        else:
            bad.append(
                f"{t.form} {t.period}: {len(same)} candidate filings in EDGAR (need exactly 1)"
            )
    return ok, bad


@dataclass
class FilingDocs:
    header: FilingHeader
    primary_name: str
    primary: bytes
    archive_rows: list[RawSourceArchive] = field(default_factory=list)


def fetch_and_archive(
    session: Session, client: SECClient, store: ArchiveStore, d: Discovered
) -> FilingDocs:
    acc_nd = d.accession.replace("-", "")
    base = ARCH.format(cik=int(SPY_CIK), acc=acc_nd, name="")
    idx_url = base + "index.json"
    idx = client.get(idx_url).body
    items = [x["name"] for x in json.loads(idx)["directory"]["item"]]
    primary_name = (
        "primary_doc.xml"
        if d.form == "NPORT-P"
        else next(
            n for n in items if n.lower().endswith((".htm", ".html")) and "index" not in n.lower()
        )
    )
    txt_name = f"{d.accession}.txt"
    docs: dict[str, bytes] = {"index.json": idx}
    for name in (primary_name, txt_name):
        docs[name] = client.get(base + name).body
    rows = []
    for name, data in docs.items():
        mime = (
            "application/json"
            if name.endswith(".json")
            else "application/xml"
            if name.endswith(".xml")
            else "text/html"
            if name.endswith((".htm", ".html"))
            else "text/plain"
        )
        rows.append(archive_document(session, store, provider=PROVIDER, source_identifier=base + name, data=data, mime_type=mime, parser_version=PARSER_VERSION,
                                     notes=f"{d.form} {d.period} accession {d.accession} accepted {d.accepted_at}"))  # fmt: skip
    return FilingDocs(
        parse_submission_header(docs[txt_name]), primary_name, docs[primary_name], rows
    )


def verify(docs: FilingDocs, d: Discovered) -> None:
    h = docs.header
    problems = []
    if h.filer_cik != SPY_CIK:
        problems.append(f"filer CIK {h.filer_cik} != {SPY_CIK}")
    if h.form != d.form:
        problems.append(f"form {h.form} != {d.form}")
    if h.period != d.period:
        problems.append(f"period {h.period} != {d.period}")
    if h.accession != d.accession:
        problems.append(f"accession {h.accession} != {d.accession}")
    if problems:
        raise AnchorVerificationError(f"{d.accession}: " + "; ".join(problems))


@dataclass
class ParsedAnchor:
    d: Discovered
    docs: FilingDocs
    tier: str
    holdings: list[dict[str, Any]]  # unified rows
    notes: list[str] = field(default_factory=list)


def parse_anchor(docs: FilingDocs, d: Discovered) -> ParsedAnchor:
    verify(docs, d)
    notes: list[str] = []
    rows: list[dict[str, Any]] = []
    if d.form == "NPORT-P":
        n = parse_nport(docs.primary)
        if n.reg_cik != SPY_CIK or n.period != d.period or n.form != "NPORT-P":
            raise AnchorVerificationError(
                f"{d.accession}: NPORT document says {n.form} {n.reg_cik} {n.period}"
            )
        for h in n.holdings:
            rows.append(dict(position=h.position, name=h.issuer_name, title=h.title, cusip=h.cusip, isin=h.isin, lei=h.lei, shares=h.shares,
                             value=h.value_usd, pct=h.pct_net_assets, klass=h.klass.value, reason=h.reason))  # fmt: skip
        if n.duplicates_merged:
            notes.append(f"{n.duplicates_merged} duplicate-CUSIP lines merged")
        tier = TIER_A
    else:
        raw_n = len(parse_n30d_schedule(docs.primary, dedupe=False))
        sched = parse_n30d_schedule(docs.primary)
        if raw_n != len(sched):
            notes.append(
                f"{raw_n - len(sched)} verbatim-duplicate schedule rows dropped (page-break repetition)"
            )
        for s in sched:
            rows.append(dict(position=s.position, name=s.name, title=None, cusip=None, isin=None, lei=None, shares=s.shares, value=s.value_usd,
                             pct=None, klass=(HoldingClass.INDEX_EQUITY_CANDIDATE if s.value_usd >= MIN_MEMBER_VALUE_USD else HoldingClass.TRANSIENT_CORPORATE_ACTION).value, reason="schedule line: name + shares + value (no identifiers)"))  # fmt: skip
        tier = TIER_B
    return ParsedAnchor(d, docs, tier, rows, notes)


# ─────────────────────────────────────────────── identity bootstrap + persistence
@dataclass
class IngestReport:
    created_anchors: list[str] = field(default_factory=list)
    skipped_existing: list[str] = field(default_factory=list)
    created_securities: int = 0
    reused_securities: int = 0
    identity_conflicts: list[str] = field(default_factory=list)
    crosschecks: list[dict[str, Any]] = field(default_factory=list)


def _known_by_identifier(session: Session) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for sid, t, v in session.execute(
        select(
            SecurityIdentifierEvidence.security_id,
            SecurityIdentifierEvidence.id_type,
            SecurityIdentifierEvidence.value,
        ).where(
            SecurityIdentifierEvidence.kind == "OFFICIAL",
            SecurityIdentifierEvidence.id_type.in_(("CUSIP", "ISIN")),
        )
    ):
        out.setdefault((t, v), sid)
    return out


def _name_index(session: Session) -> dict[str, set[str]]:
    idx: dict[str, set[str]] = {}
    for sid, name, title in session.execute(
        select(
            SP500AnchorMember.security_id, SP500AnchorMember.issuer_name, SP500AnchorMember.title
        ).where(SP500AnchorMember.security_id.is_not(None))
    ):
        for n in (name, title):
            if n and sid:
                idx.setdefault(nn(n), set()).add(sid)
    return idx


def _new_security(session: Session, name: str, isin: str | None, rep: IngestReport) -> str:
    s = Security(
        name=name[:300], exchange="XNYS", currency="USD", country=isin[:2] if isin else "US"
    )
    session.add(s)
    session.flush()
    rep.created_securities += 1
    return s.security_id


def _evidence(
    session: Session,
    sid: str,
    id_type: str,
    value: str,
    d: ParsedAnchor,
    arch: RawSourceArchive,
    name: str,
) -> None:
    session.add(
        SecurityIdentifierEvidence(
            security_id=sid,
            id_type=id_type,
            value=value,
            kind="OFFICIAL",
            observed_on=d.d.period,
            source_kind="SEC_NPORT_P_HOLDING",
            source_url=arch.source_identifier,
            archive_id=arch.archive_id,
            source_sha256=arch.sha256,
            excerpt=f"{name}: {id_type} {value} held by SPDR S&P 500 ETF Trust at {d.d.period} ({d.d.accession})"[
                :600
            ],
            parser_version=PARSER_VERSION,
        )
    )


def persist_anchors(session: Session, parsed: list[ParsedAnchor]) -> IngestReport:
    rep = IngestReport()
    have = {
        a.accession
        for a in session.scalars(
            select(SP500Anchor).where(SP500Anchor.parser_version == PARSER_VERSION)
        )
    }
    todo = [
        p
        for p in sorted(parsed, key=lambda p: (p.tier != TIER_A, p.d.period))
        if p.d.accession not in have
    ]
    rep.skipped_existing = sorted(p.d.accession for p in parsed if p.d.accession in have)
    by_id = _known_by_identifier(session)
    names = _name_index(session)
    persisted: dict[
        str, list[dict[str, Any]]
    ] = {}  # (period, form) -> resolved rows, for cross-checks
    # 1. NPORT: identity by CUSIP, else ISIN. Never by ticker or by name.
    for p in [x for x in todo if x.tier == TIER_A]:
        main = next(
            r for r in p.docs.archive_rows if r.source_identifier.endswith(p.docs.primary_name)
        )
        for r in p.holdings:
            if r["klass"] != HoldingClass.INDEX_EQUITY_CANDIDATE.value:
                r["sid"], r["basis"], r["status"] = (
                    None,
                    "NONE",
                    "EXCLUDED" if r["klass"] != HoldingClass.UNRESOLVED.value else "UNRESOLVED",
                )
                continue
            c, i = r["cusip"], r["isin"]
            by_c = by_id.get(("CUSIP", c)) if c else None
            by_i = by_id.get(("ISIN", i)) if i else None
            if by_c and by_i and by_c != by_i:
                rep.identity_conflicts.append(
                    f"{p.d.period} {r['name']}: CUSIP {c} -> {by_c} but ISIN {i} -> {by_i}"
                )
            sid = by_c or by_i
            if sid is None:
                sid = _new_security(session, r["name"], i, rep)
            else:
                rep.reused_securities += 1
            for t, v in (("CUSIP", c), ("ISIN", i)):
                if v:
                    by_id.setdefault((t, v), sid)
                    _evidence(session, sid, t, v, p, main, r["name"])
            r["sid"], r["basis"], r["status"] = sid, "CUSIP" if c else "ISIN", "RESOLVED"
            for n in (r["name"], r["title"]):
                if n:
                    names.setdefault(nn(n), set()).add(sid)
        persisted[f"{p.d.period}"] = p.holdings
    # NPORT anchors already persisted: their rows come from the database (for same-date cross-checks)
    for a in session.scalars(
        select(SP500Anchor).where(
            SP500Anchor.parser_version == PARSER_VERSION, SP500Anchor.form == "NPORT-P"
        )
    ):
        if str(a.as_of_date) not in persisted:
            persisted[str(a.as_of_date)] = [
                dict(name=m.issuer_name, shares=m.shares, value=m.value_usd, sid=m.security_id)
                for m in session.scalars(
                    select(SP500AnchorMember).where(
                        SP500AnchorMember.anchor_id == a.anchor_id,
                        SP500AnchorMember.status == "RESOLVED",
                    )
                )
            ]
    # 2. N-30D. A same-date NPORT is the SAME portfolio seen twice: the price per share (value/shares) is identical and the share
    #    balance within a few percent. A MUTUAL-UNIQUE (price, shares) match links the schedule line to the NPORT CUSIP; the link
    #    is then learned by name. Other lines go through the name index (unique only) and finally become NAME_ONLY.
    nport_members: dict[date, set[str]] = {}
    for key_, rows_ in persisted.items():
        nport_members[date.fromisoformat(key_)] = {h["sid"] for h in rows_ if h.get("sid")}
    learned: dict[str, set[str]] = {}
    pair_stats: dict[str, dict[str, Any]] = {}
    for p in [x for x in todo if x.tier == TIER_B]:
        ref = [
            h
            for h in persisted.get(str(p.d.period), [])
            if h.get("sid") and h.get("shares") and h.get("value")
        ]
        if not ref:
            continue
        cand_s: dict[int, list[int]] = {}
        cand_n: dict[int, list[int]] = {}
        for si, r in enumerate(p.holdings):
            if r["klass"] != HoldingClass.INDEX_EQUITY_CANDIDATE.value:
                continue
            ps = r["value"] / r["shares"]
            for ni, h in enumerate(ref):
                if (
                    abs(ps - h["value"] / h["shares"]) <= 0.011
                    and 0.95 <= r["shares"] / h["shares"] <= 1.05
                ):
                    cand_s.setdefault(si, []).append(ni)
                    cand_n.setdefault(ni, []).append(si)
        for si, nis in cand_s.items():
            if len(nis) == 1 and len(cand_n[nis[0]]) == 1:
                r, h = p.holdings[si], ref[nis[0]]
                r["sid"], r["basis"], r["status"] = h["sid"], "SHARES_VALUE", "RESOLVED"
                learned.setdefault(nn(r["name"]), set()).add(h["sid"])
        pair_stats[str(p.d.period)] = {"ref": ref}
    for k, v in learned.items():
        names.setdefault(k, set()).update(v)
    name_only: dict[str, str] = {}
    for sid_, nm in session.execute(
        select(SP500AnchorMember.security_id, SP500AnchorMember.issuer_name).where(
            SP500AnchorMember.identity_basis == "NAME_ONLY"
        )
    ):
        if sid_:
            name_only[nn(nm)] = sid_
    for p in sorted([x for x in todo if x.tier == TIER_B], key=lambda x: x.d.period):
        for r in p.holdings:
            if r["klass"] != HoldingClass.INDEX_EQUITY_CANDIDATE.value:
                r["sid"], r["basis"], r["status"] = None, "NONE", "EXCLUDED"
                continue
            if "sid" in r:
                continue
            key = nn(r["name"])
            ids = names.get(key, set())
            if len(ids) == 1:
                r["sid"], r["basis"], r["status"] = next(iter(ids)), "NAME_MATCH", "RESOLVED"
            elif len(ids) > 1:
                # the same name can belong to several securities over time (re-domiciliation, reverse split, new share class):
                # keep the candidates held in the NEAREST FOLLOWING NPORT anchor; unique -> NAME_TEMPORAL, otherwise unresolved
                later = sorted(d_ for d_ in nport_members if d_ >= p.d.period)
                narrowed = ids & nport_members[later[0]] if later else set()
                if len(narrowed) == 1:
                    r["sid"], r["basis"], r["status"] = (
                        next(iter(narrowed)),
                        "NAME_TEMPORAL",
                        "RESOLVED",
                    )
                else:
                    r["sid"], r["basis"], r["status"] = None, "NONE", "UNRESOLVED"
                    r["reason"] = (
                        f"name matches {len(ids)} securities (multi-class / re-domiciled issuer): ambiguous"
                    )
            else:
                sid = name_only.get(key)
                if sid is None:
                    sid = _new_security(session, r["name"], None, rep)
                    name_only[key] = sid
                    names.setdefault(key, set()).add(sid)
                r["sid"], r["basis"], r["status"] = sid, "NAME_ONLY", "RESOLVED"
        ref_rows: list[dict[str, Any]] | None = pair_stats.get(str(p.d.period), {}).get("ref")
        if ref_rows is not None:
            ref = ref_rows
            ns = {h["sid"] for h in ref}
            ss = {r["sid"] for r in p.holdings if r.get("sid")}
            rep.crosschecks.append(
                dict(anchor_date=str(p.d.period), nport_equities=len(ns), schedule_equities=sum(1 for r in p.holdings if r["klass"] == HoldingClass.INDEX_EQUITY_CANDIDATE.value), matched=len(ns & ss), nport_only=len(ns - ss), schedule_only=len(ss - ns),
                     identity_unresolved=sum(1 for r in p.holdings if r["klass"] == HoldingClass.INDEX_EQUITY_CANDIDATE.value and not r.get("sid")),
                     _nport_only=sorted(h["name"] for h in ref if h["sid"] in ns - ss)[:60], _schedule_only=sorted(r["name"] for r in p.holdings if r.get("sid") in ss - ns)[:60]))  # fmt: skip
    # 3. rows
    for p in todo:
        main = next(
            r for r in p.docs.archive_rows if r.source_identifier.endswith(p.docs.primary_name)
        )
        cands = [r for r in p.holdings if r["klass"] == HoldingClass.INDEX_EQUITY_CANDIDATE.value]
        resolved = [r for r in cands if r.get("sid")]
        anchor = SP500Anchor(
            as_of_date=p.d.period,
            source_type="SEC_NPORT_P" if p.d.form == "NPORT-P" else "SEC_N30D",
            evidence_kind=EVIDENCE_KIND,
            evidence_tier=p.tier,
            form=p.d.form,
            accession=p.d.accession,
            filer_cik=p.docs.header.filer_cik,
            source_available_at=p.docs.header.accepted_at,
            archive_id=main.archive_id,
            source_sha256=main.sha256,
            member_count=len(cands),
            resolved_count=len(resolved),
            unresolved_count=len(p.holdings)
            - len(resolved)
            - sum(1 for r in p.holdings if r["status"] == "EXCLUDED"),
            excluded_count=sum(1 for r in p.holdings if r.get("status") == "EXCLUDED"),
            status="VERIFIED"
            if not [c for c in rep.identity_conflicts if c.startswith(str(p.d.period))]
            else "IDENTITY_CONFLICT",
            notes=[
                *p.notes,
                f"identity basis: {'CUSIP/ISIN (OFFICIAL, read from the filing)' if p.tier == TIER_A else 'same-date NPORT (shares,value) link, else unique name match, else name-only'}",
            ],
            parser_version=PARSER_VERSION,
        )
        session.add(anchor)
        session.flush()
        for r in p.holdings:
            session.add(
                SP500AnchorMember(
                    anchor_id=anchor.anchor_id, security_id=r.get("sid"), cusip=r["cusip"], isin=r["isin"], ticker_as_reported=None, issuer_name=r["name"][:300],
                    title=(r["title"] or None), lei=r["lei"], source_position=r["position"], shares=r["shares"], value_usd=r["value"], pct_net_assets=r["pct"],
                    classification=r["klass"], identity_basis=r.get("basis", "NONE"), status=r.get("status", "UNRESOLVED") if r["klass"] == HoldingClass.INDEX_EQUITY_CANDIDATE.value else r.get("status", "EXCLUDED"),
                )
            )  # fmt: skip
        rep.created_anchors.append(f"{p.d.period} {p.d.form} {p.d.accession}")
    session.flush()
    # cross-check rows (needs both anchors persisted)
    anchor_ids = {
        (a.as_of_date, a.form): a.anchor_id
        for a in session.scalars(
            select(SP500Anchor).where(SP500Anchor.parser_version == PARSER_VERSION)
        )
    }
    for c in rep.crosschecks:
        d_ = date.fromisoformat(c["anchor_date"])
        a_id, b_id = anchor_ids.get((d_, "NPORT-P")), anchor_ids.get((d_, "N-30D"))
        if a_id and b_id:
            met = {k: v for k, v in c.items() if not k.startswith("_")}
            session.add(
                SP500AnchorCrossCheck(
                    anchor_a_id=a_id,
                    anchor_b_id=b_id,
                    metrics=met,
                    details=[
                        {"nport_only": c["_nport_only"], "schedule_only": c["_schedule_only"]}
                    ],
                )
            )
    session.flush()
    return rep


def ingest(
    session: Session, client: SECClient, store: ArchiveStore, targets: list[AnchorTarget]
) -> tuple[IngestReport, list[str]]:
    found = discover_filings(client)
    ok, bad = resolve_targets(found, targets)
    if bad:
        raise AnchorVerificationError("; ".join(bad))
    parsed = []
    for _t, d in ok:
        parsed.append(parse_anchor(fetch_and_archive(session, client, store, d), d))
    return persist_anchors(session, parsed), bad
