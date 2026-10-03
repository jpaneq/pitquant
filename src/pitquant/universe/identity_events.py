# ruff: noqa: E501
"""SEC 8-K corporate identity events (ADR-0034): name / ticker / identifier changes and successor issuers.

Each event is applied only after (1) the 8-K is fetched, archived (SHA-256) and its own header says form 8-K + the declared accession, (2) the
8-K text contains the declared company names, and (3) the SEC 13(f) lists show the declared CUSIPs in the declared quarters. A security change
that keeps the index slot is a SUCCESSION/identity link (``membership_continuity``), never an exit + entry. Name/ticker/legal-change dates are
kept apart (the legal name change and the ticker change can differ by days); the date of a CUSIP transition is PARTIAL unless a source states it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.data.archive import ArchiveStore, archive_document
from pitquant.data.providers.sec_edgar.client import SECClient
from pitquant.db.models import SecurityTickerAlias, SP500AnchorMember
from pitquant.universe.identity_bridge import (
    ResolutionResult,
    _entry,
    add_cusip_evidence,
    link_same_security,
    security_by_cusip,
)
from pitquant.universe.sources.spy_sec_anchors import parse_submission_header


@dataclass(frozen=True)
class Alias:
    ticker: str
    valid_from: date | None
    valid_to: date | None


@dataclass(frozen=True)
class CorporateEvent:
    key: str
    event_type: str
    accession: str
    cik: int
    phrases: tuple[str, ...]  # must appear in the 8-K text
    effective: datetime
    old_name_only: str | None
    old_cusip: str
    new_cusip: str
    new_isin: str | None
    verify: tuple[tuple[str, str], ...]  # (13F quarter, cusip) that must be listed
    ratio: float | None
    aliases_old: tuple[Alias, ...]
    aliases_new: tuple[Alias, ...]
    note: str
    cusip_transition_bounds: str = "PARTIAL"  # EXACT only if a source states the date


EVENTS: tuple[CorporateEvent, ...] = (
    CorporateEvent(
        "PRICELINE_BOOKING",
        "NAME_TICKER_IDENTIFIER_CHANGE_SAME_SECURITY",
        "0001075531-18-000008",
        1075531,
        ("Booking Holdings",),
        datetime(2018, 2, 21, tzinfo=UTC),
        "Priceline Group, Inc.",
        "741503403",
        "09857L108",
        None,
        (("2017Q4", "741503403"), ("2018Q2", "09857L108")),
        None,
        (Alias("PCLN", None, date(2018, 2, 26)),),
        (Alias("BKNG", date(2018, 2, 27), None),),
        "The Priceline Group Inc. -> Booking Holdings Inc.: legal name change 2018-02-21; ticker PCLN -> BKNG effective 2018-02-27; CUSIP 741503403 -> 09857L108 (existing certificates stay valid): the SAME security",
        "PARTIAL",
    ),
    CorporateEvent(
        "COACH_TAPESTRY",
        "NAME_TICKER_CHANGE_SAME_SECURITY",
        "0001157523-17-002666",
        1116132,
        ("Tapestry",),
        datetime(2017, 10, 31, tzinfo=UTC),
        "Coach, Inc.",
        "189754104",
        "876030107",
        None,
        (("2017Q3", "189754104"), ("2018Q1", "876030107")),
        None,
        (Alias("COH", None, date(2017, 10, 30)),),
        (Alias("TPR", date(2017, 10, 31), None),),
        "Coach, Inc. -> Tapestry, Inc., ticker COH -> TPR effective 2017-10-31: the SAME security; the exact date of the CUSIP transition 189754104 -> 876030107 is not stated (PARTIAL)",
        "PARTIAL",
    ),
    CorporateEvent(
        "PRAXAIR_LINDE",
        "SECURITY_REPLACEMENT_SUCCESSOR",
        "0001193125-18-313073",
        1707925,
        ("Linde plc",),
        datetime(2018, 10, 31, tzinfo=UTC),
        "Praxair, Inc.",
        "74005P104",
        "G5494J103",
        "IE00BZ12WP82",
        (("2018Q3", "74005P104"), ("2019Q2", "G5494J103")),
        1.0,
        (Alias("PX", None, date(2018, 10, 30)),),
        (Alias("LIN", date(2018, 10, 31), None),),
        "Praxair Inc. and Linde AG combine under Linde plc: each Praxair share -> 1 ordinary share of Linde plc, Linde plc successor issuer; PX suspended after the 2018-10-30 close, LIN from 2018-10-31",
        "EXACT",
    ),
)


def _find(
    session: Session, *, cusip: str | None = None, isin: str | None = None, name: str | None = None
) -> str | None:
    if cusip:
        sid = security_by_cusip(session, cusip)
        if sid:
            return sid
    if isin:
        ids = {
            s
            for (s,) in session.execute(
                select(SP500AnchorMember.security_id).where(
                    SP500AnchorMember.isin == isin, SP500AnchorMember.security_id.is_not(None)
                )
            )
        }
        if len(ids) == 1:
            return next(iter(ids))
    if name:
        ids = {
            s
            for (s,) in session.execute(
                select(SP500AnchorMember.security_id).where(
                    SP500AnchorMember.issuer_name == name,
                    SP500AnchorMember.identity_basis == "NAME_ONLY",
                    SP500AnchorMember.security_id.is_not(None),
                )
            )
        }
        if len(ids) == 1:
            return next(iter(ids))
    return None


@dataclass
class Fetched:
    sha: str
    archive_id: str
    text: str
    form: str


def fetch_8k(
    session: Session, client: SECClient, store: ArchiveStore, cik: int, accession: str
) -> Fetched:
    nd = accession.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{nd}/"
    idx = client.get(base + "index.json").body
    items = [x["name"] for x in json.loads(idx)["directory"]["item"]]
    prim = next(
        n for n in items if n.lower().endswith((".htm", ".html")) and "index" not in n.lower()
    )
    docs = {
        "index.json": idx,
        prim: client.get(base + prim).body,
        f"{accession}.txt": client.get(base + f"{accession}.txt").body,
    }
    rows = []
    for name, data in docs.items():
        mime = (
            "application/json"
            if name.endswith(".json")
            else "text/html"
            if name.endswith((".htm", ".html"))
            else "text/plain"
        )
        rows.append(
            archive_document(
                session,
                store,
                provider="SEC_8K",
                source_identifier=base + name,
                data=data,
                mime_type=mime,
                parser_version="identity-events-1",
                notes=f"8-K {accession}",
            )
        )
    hdr = parse_submission_header(docs[f"{accession}.txt"])
    if hdr.accession != accession:
        raise ValueError(f"{accession}: header accession {hdr.accession}")
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", docs[prim].decode("utf-8", "replace")))
    full = rows[1]
    return Fetched(full.sha256, full.archive_id, text, hdr.form)


def apply_events(
    session: Session,
    client: SECClient | None,
    store: ArchiveStore | None,
    items: tuple[CorporateEvent, ...] = EVENTS,
    *,
    fetched: dict[str, Fetched] | None = None,
) -> list[ResolutionResult]:
    out: list[ResolutionResult] = []
    for ev in items:
        try:
            f = (fetched or {}).get(ev.accession)
            if f is None:
                assert client is not None and store is not None, (
                    "client and store are required to fetch an 8-K"
                )
                f = fetch_8k(session, client, store, ev.cik, ev.accession)
        except Exception as e:
            out.append(
                ResolutionResult(
                    ev.key, False, f"8-K {ev.accession} not retrievable/verifiable: {e}"
                )
            )
            continue
        if f.form != "8-K" or not all(p in f.text for p in ev.phrases):
            out.append(
                ResolutionResult(
                    ev.key, False, f"8-K {ev.accession} is form {f.form} or lacks {ev.phrases}"
                )
            )
            continue
        ents = [_entry(session, q, c) for q, c in ev.verify]
        if any(e is None for e in ents):
            out.append(
                ResolutionResult(
                    ev.key,
                    False,
                    "13F verification failed: "
                    + ", ".join(
                        f"{q}:{c}" for (q, c), e in zip(ev.verify, ents, strict=True) if e is None
                    ),
                )
            )
            continue
        old = _find(session, cusip=None, name=ev.old_name_only) or _find(
            session, cusip=ev.old_cusip
        )
        new = _find(session, cusip=ev.new_cusip, isin=ev.new_isin)
        if not old or not new or old == new:
            out.append(
                ResolutionResult(
                    ev.key, False, f"securities not found in the anchors (old {old}, new {new})"
                )
            )
            continue
        for ent in ents:
            if ent is not None:
                add_cusip_evidence(session, old if ent.cusip == ev.old_cusip else new, ent, ev.note)
        link_same_security(
            session,
            old,
            new,
            f"SEC_8K:{ev.accession}+SEC_13F_LIST",
            f.sha,
            event_type=ev.event_type,
            effective=ev.effective,
            ratio=ev.ratio,
            note=ev.note + f"; CUSIP transition date: {ev.cusip_transition_bounds}",
        )
        have = {(x.security_id, x.ticker) for x in session.scalars(select(SecurityTickerAlias))}
        for owner, aliases in (
            (old if ev.event_type == "SECURITY_REPLACEMENT_SUCCESSOR" else new, ev.aliases_old),
            (new, ev.aliases_new),
        ):
            for a in aliases:
                if (owner, a.ticker) not in have:
                    session.add(
                        SecurityTickerAlias(
                            security_id=owner,
                            ticker=a.ticker,
                            valid_from=a.valid_from,
                            valid_to=a.valid_to,
                            bounds="EXACT" if (a.valid_from or a.valid_to) else "PARTIAL",
                            source=f"SEC_8K:{ev.accession}",
                            source_hash=f.sha,
                            confidence="HIGH",
                            note=ev.note[:300],
                        )
                    )
        out.append(
            ResolutionResult(ev.key, True, f"8-K {ev.accession} archived/verified; 13F {ev.verify}")
        )
    session.flush()
    return out
