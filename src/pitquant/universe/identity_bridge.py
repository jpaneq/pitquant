# ruff: noqa: E501
"""US identity bridge from SEC OFFICIAL evidence (ADR-0033): the quarterly 13(f) list and dated corporate-succession facts.

* ``bridge_name_only``: a N-30D holding identified only by name gets a CUSIP when EXACTLY ONE compatible entry of the 13F list of the
  anchor's quarter matches (exact normalised legal name + share class). Several candidates or none -> UNRESOLVED. Fuzzy similarity is never
  enough. The CUSIP is evidence for THAT quarter only.
* ``RESOLUTIONS``: six corporate identity events investigated externally. Each is applied only if the 13F lists VERIFY it (CUSIP present before
  and after; DELETED/ADDED in the stated quarter for a replacement). A security_id changing is a SUCCESSION, not an index exit + entry.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.data.providers.sec_13f_list import PARSER_VERSION as F13_VERSION
from pitquant.data.providers.sec_13f_list import quarter_end
from pitquant.db.models import (
    RawSourceArchive,
    Sec13FListEntry,
    SecurityIdentifierEvidence,
    SecuritySuccession,
    SP500Anchor,
    SP500AnchorMember,
)
from pitquant.universe.sources.spy_sec_anchors import norm_name

_CLASS_N30D = re.compile(r"\bClass\s+([A-Z])\b", re.I)
_CLASS_13F = re.compile(r"\b(?:CL|CLASS|SER|SERIES)\s+([A-Z])\b")
_NOT_COMMON = re.compile(r"\b(PFD|WT|WTS|RIGHT|RTS|UNIT|UNITS|NOTE|NOTES|DEBT|SUB)\b")


def quarter_of(d: date) -> str:
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"


def n30d_key(name: str) -> tuple[str, str | None]:
    m = _CLASS_N30D.search(name)
    base = _CLASS_N30D.sub("", name)
    return norm_name(base), (m.group(1).upper() if m else None)


@dataclass
class Bridge:
    security_id: str
    name: str
    quarter: str
    status: str  # RESOLVED | UNRESOLVED_MULTIPLE | UNRESOLVED_NONE
    cusip: str | None = None
    candidates: list[str] = field(default_factory=list)
    linked_to: str | None = None


def candidates_for(session: Session, name: str, quarter: str) -> list[Sec13FListEntry]:
    base, cls = n30d_key(name)
    out = []
    for e in session.scalars(
        select(Sec13FListEntry).where(
            Sec13FListEntry.quarter == quarter, Sec13FListEntry.parser_version == F13_VERSION
        )
    ):
        if _NOT_COMMON.search(e.issuer_description) or norm_name(e.issuer_name) != base:
            continue
        m = _CLASS_13F.search(e.issuer_description)
        if (cls is None and m is None) or (cls is not None and m is not None and m.group(1) == cls):
            out.append(e)
    return out


def _archive_for(session: Session, e: Sec13FListEntry) -> RawSourceArchive:
    return session.get_one(RawSourceArchive, e.archive_id)


def add_cusip_evidence(session: Session, sid: str, e: Sec13FListEntry, note: str) -> None:
    exists = session.scalars(
        select(SecurityIdentifierEvidence).where(
            SecurityIdentifierEvidence.security_id == sid,
            SecurityIdentifierEvidence.value == e.cusip,
            SecurityIdentifierEvidence.source_kind == "SEC_13F_LIST",
            SecurityIdentifierEvidence.observed_on == quarter_end(e.quarter),
        )
    ).first()
    if exists:
        return
    arch = _archive_for(session, e)
    session.add(
        SecurityIdentifierEvidence(security_id=sid, id_type="CUSIP", value=e.cusip, kind="OFFICIAL", observed_on=quarter_end(e.quarter), source_kind="SEC_13F_LIST", source_url=arch.source_identifier, archive_id=arch.archive_id,
                                   source_sha256=e.raw_source_hash, excerpt=f"{e.issuer_name} {e.issuer_description} ({e.quarter}); {note}"[:600], parser_version=F13_VERSION)
    )  # fmt: skip


def security_by_cusip(session: Session, cusip: str) -> str | None:
    """The security carrying an OFFICIAL CUSIP. Evidence read from the SEC 13F list is only a fallback: after a name change the old and the
    new security legitimately share a CUSIP there, and the one identified by the anchors' own filing wins."""
    base = select(SecurityIdentifierEvidence.security_id).where(
        SecurityIdentifierEvidence.id_type == "CUSIP",
        SecurityIdentifierEvidence.value == cusip,
        SecurityIdentifierEvidence.kind == "OFFICIAL",
    )
    first = {
        s
        for (s,) in session.execute(
            base.where(SecurityIdentifierEvidence.source_kind != "SEC_13F_LIST")
        )
    }
    if len(first) == 1:
        return next(iter(first))
    ids = {s for (s,) in session.execute(base)}
    return next(iter(ids)) if len(ids) == 1 else None


def bridge_name_only(session: Session) -> list[Bridge]:
    """One result per name-only security (N-30D anchors). Resolved only when the quarter's 13F list gives exactly one compatible CUSIP
    in EVERY anchor quarter where the security appears (the same CUSIP each time)."""
    rows = session.execute(
        select(SP500AnchorMember.security_id, SP500AnchorMember.issuer_name, SP500Anchor.as_of_date)
        .join(SP500Anchor, SP500Anchor.anchor_id == SP500AnchorMember.anchor_id)
        .where(SP500AnchorMember.identity_basis == "NAME_ONLY")
    ).all()
    by_sid: dict[str, list[tuple[str, date]]] = {}
    for sid_, nm, d in rows:
        if sid_:
            by_sid.setdefault(sid_, []).append((nm, d))
    out: list[Bridge] = []
    for sid, occ in sorted(by_sid.items()):
        picks: dict[str, Sec13FListEntry] = {}
        status, cands = "RESOLVED", []
        for nm, d in sorted(occ, key=lambda x: x[1]):
            q = quarter_of(d)
            c = candidates_for(session, nm, q)
            cands += [f"{q}:{x.cusip}" for x in c]
            if len(c) > 1:
                status = "UNRESOLVED_MULTIPLE"
                break
            if not c:
                status = "UNRESOLVED_NONE"
                break
            picks[q] = c[0]
        if status == "RESOLVED" and len({e.cusip for e in picks.values()}) != 1:
            status = "UNRESOLVED_MULTIPLE"
        b = Bridge(
            sid,
            occ[0][0],
            quarter_of(min(d for _, d in occ)),
            status,
            next(iter(picks.values())).cusip if status == "RESOLVED" else None,
            cands,
        )
        if status == "RESOLVED":
            for e in picks.values():
                add_cusip_evidence(
                    session,
                    sid,
                    e,
                    "N-30D name matched to the quarter's 13F list: exact normalised legal name + share class, unique",
                )
            other = security_by_cusip_other(session, b.cusip or "", sid)
            if other:
                b.linked_to = other
                link_same_security(
                    session, sid, other, "SEC_13F_LIST", next(iter(picks.values())).raw_source_hash
                )
        out.append(b)
    session.flush()
    return out


def security_by_cusip_other(session: Session, cusip: str, not_sid: str) -> str | None:
    ids = {
        s
        for (s,) in session.execute(
            select(SecurityIdentifierEvidence.security_id).where(
                SecurityIdentifierEvidence.id_type == "CUSIP",
                SecurityIdentifierEvidence.value == cusip,
                SecurityIdentifierEvidence.kind == "OFFICIAL",
            )
        )
        if s != not_sid
    }
    return next(iter(ids)) if len(ids) == 1 else None


def link_same_security(
    session: Session,
    pred: str,
    succ: str,
    source: str,
    source_hash: str | None,
    *,
    event_type: str = "SAME_SECURITY_IDENTITY_LINK",
    effective: datetime | None = None,
    ratio: float | None = None,
    note: str = "",
) -> None:
    if session.scalars(
        select(SecuritySuccession).where(
            SecuritySuccession.security_predecessor_id == pred,
            SecuritySuccession.security_successor_id == succ,
            SecuritySuccession.event_type == event_type,
        )
    ).first():
        return
    session.add(
        SecuritySuccession(
            security_predecessor_id=pred,
            security_successor_id=succ,
            effective_at=effective,
            event_type=event_type,
            exchange_ratio=ratio,
            membership_continuity=True,
            source=source,
            source_hash=source_hash,
            note=note[:400] or None,
        )
    )


# ───────────────────────────────────────────── the six investigated resolutions
@dataclass(frozen=True)
class Resolution:
    key: str
    event_type: Literal["NAME_CHANGE_SAME_SECURITY", "SECURITY_REPLACEMENT_SUCCESSOR"]
    effective: datetime
    old_cusip: str
    new_cusip: str
    ratio: float | None
    verify_before: str  # 13F quarter where the OLD cusip is listed
    verify_after: str  # 13F quarter where the NEW cusip is listed
    replacement_quarter: str | None  # quarter where old is DELETED and new ADDED (replacements)
    note: str
    old_name_only: str | None = None  # N-30D name of a name-only predecessor (name changes)
    old_isin: str | None = None
    new_isin: str | None = None


def NY_0400(y: int, m: int, d: int) -> datetime:
    return datetime(y, m, d, 8, 0, tzinfo=UTC)


RESOLUTIONS: tuple[Resolution, ...] = (
    Resolution(
        "DISCOVERY_A",
        "NAME_CHANGE_SAME_SECURITY",
        datetime(2018, 3, 6, tzinfo=UTC),
        "25470F104",
        "25470F104",
        None,
        "2018Q1",
        "2019Q2",
        None,
        "Discovery Communications, Inc. -> Discovery, Inc. (CIK 1437107): same CUSIP Series A before and after",
        old_name_only="Discovery Communications, Inc. Class A",
    ),
    Resolution(
        "DISCOVERY_C",
        "NAME_CHANGE_SAME_SECURITY",
        datetime(2018, 3, 6, tzinfo=UTC),
        "25470F302",
        "25470F302",
        None,
        "2018Q1",
        "2019Q2",
        None,
        "Discovery Communications, Inc. -> Discovery, Inc. (CIK 1437107): same CUSIP Series C before and after",
        old_name_only="Discovery Communications, Inc. Class C",
    ),
    Resolution(
        "KLA",
        "NAME_CHANGE_SAME_SECURITY",
        datetime(2019, 7, 15, tzinfo=UTC),
        "482480100",
        "482480100",
        None,
        "2019Q2",
        "2019Q3",
        None,
        "KLA-Tencor Corporation -> KLA Corporation (CIK 319201, KLAC): corporate name only",
        old_name_only="KLA-Tencor Corp.",
    ),
    Resolution(
        "AON",
        "SECURITY_REPLACEMENT_SUCCESSOR",
        NY_0400(2020, 4, 1),
        "G0408V102",
        "G0403H108",
        1.0,
        "2020Q1",
        "2020Q3",
        "2020Q2",
        "Aon plc (UK) -> Aon plc (Ireland): scheme of arrangement, 1:1, successor issuer, ticker AON continues",
        old_isin="GB00B5BT0K07",
        new_isin="IE00BLP1HW54",
    ),
    Resolution(
        "SEAGATE",
        "SECURITY_REPLACEMENT_SUCCESSOR",
        datetime(2021, 5, 18, 8, 0, tzinfo=UTC),
        "G7945M107",
        "G7997R103",
        1.0,
        "2021Q1",
        "2021Q3",
        "2021Q2",
        "Seagate Technology plc -> Seagate Technology Holdings plc: scheme of arrangement, 1:1, successor issuer",
        old_isin="IE00B58JVZ52",
        new_isin="IE00BKVD2N49",
    ),
    Resolution(
        "APACHE_APA",
        "SECURITY_REPLACEMENT_SUCCESSOR",
        datetime(2021, 3, 1, 5, 0, tzinfo=UTC),
        "037411105",
        "03743Q108",
        1.0,
        "2020Q2",
        "2021Q2",
        "2021Q1",
        "Apache Corporation -> APA Corporation: holding-company reorganisation, shares convert automatically, ticker APA continues",
    ),
    Resolution(
        "JACOBS",
        "SECURITY_REPLACEMENT_SUCCESSOR",
        datetime(2022, 8, 29, 4, 0, tzinfo=UTC),
        "469814107",
        "46982L108",
        1.0,
        "2022Q2",
        "2022Q3",
        "2022Q3",
        "Jacobs Engineering Group -> Jacobs Solutions: holding-company reorganisation, 1:1, successor issuer, ticker J continues",
    ),
)


def _entry(session: Session, quarter: str, cusip: str) -> Sec13FListEntry | None:
    return session.scalars(
        select(Sec13FListEntry).where(
            Sec13FListEntry.quarter == quarter,
            Sec13FListEntry.cusip == cusip,
            Sec13FListEntry.parser_version == F13_VERSION,
        )
    ).first()


def _find_security(
    session: Session, cusip: str, isin: str | None, name_only: str | None
) -> str | None:
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
    if name_only:
        ids = {
            s
            for (s,) in session.execute(
                select(SP500AnchorMember.security_id).where(
                    SP500AnchorMember.issuer_name == name_only,
                    SP500AnchorMember.identity_basis == "NAME_ONLY",
                    SP500AnchorMember.security_id.is_not(None),
                )
            )
        }
        if len(ids) == 1:
            return next(iter(ids))
    return None


@dataclass
class ResolutionResult:
    key: str
    applied: bool
    reason: str


def apply_resolutions(
    session: Session, items: tuple[Resolution, ...] = RESOLUTIONS
) -> list[ResolutionResult]:
    out: list[ResolutionResult] = []
    for r in items:
        e_old, e_new = (
            _entry(session, r.verify_before, r.old_cusip),
            _entry(session, r.verify_after, r.new_cusip),
        )
        if e_old is None or e_new is None:
            out.append(
                ResolutionResult(
                    r.key,
                    False,
                    f"13F verification failed: {r.old_cusip}@{r.verify_before} or {r.new_cusip}@{r.verify_after} not listed",
                )
            )
            continue
        if r.replacement_quarter:
            d_old, a_new = (
                _entry(session, r.replacement_quarter, r.old_cusip),
                _entry(session, r.replacement_quarter, r.new_cusip),
            )
            if not (
                d_old
                and d_old.status_added_deleted == "DELETED"
                and a_new
                and a_new.status_added_deleted == "ADDED"
            ):
                out.append(
                    ResolutionResult(
                        r.key,
                        False,
                        f"13F {r.replacement_quarter} does not show {r.old_cusip} DELETED and {r.new_cusip} ADDED",
                    )
                )
                continue
        new_sid = _find_security(session, r.new_cusip, r.new_isin, None)
        old_sid = (
            _find_security(session, r.old_cusip, r.old_isin, r.old_name_only)
            if r.event_type == "SECURITY_REPLACEMENT_SUCCESSOR"
            else _find_security(session, "-", None, r.old_name_only)
        )
        if not new_sid or not old_sid or new_sid == old_sid:
            out.append(
                ResolutionResult(
                    r.key,
                    False,
                    f"securities not found in the anchors (old {old_sid}, new {new_sid})",
                )
            )
            continue
        add_cusip_evidence(session, old_sid, e_old, r.note)
        add_cusip_evidence(session, new_sid, e_new, r.note)
        link_same_security(
            session,
            old_sid,
            new_sid,
            "SEC_13F_LIST+SEC_CORPORATE_EVENT",
            e_new.raw_source_hash,
            event_type=r.event_type,
            effective=r.effective,
            ratio=r.ratio,
            note=r.note,
        )
        out.append(ResolutionResult(r.key, True, "verified against the SEC 13F lists and applied"))
    session.flush()
    return out


def succession_map(session: Session) -> dict[str, str]:
    """predecessor -> FINAL successor over every succession that keeps the index membership (chains collapsed)."""
    direct = {
        x.security_predecessor_id: x.security_successor_id
        for x in session.scalars(select(SecuritySuccession))
        if x.membership_continuity
    }
    out: dict[str, str] = {}
    for p in direct:
        cur, seen = p, {p}
        while cur in direct and direct[cur] not in seen:
            cur = direct[cur]
            seen.add(cur)
        out[p] = cur
    return out
