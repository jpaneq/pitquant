# ruff: noqa: E501
"""Historical anchor graph + LOCAL event reconciliation (ADR-0032). Replaces «single current anchor + undo everything».

Two consecutive anchors A < B (SEC-filed SPY compositions, state at the close of ``as_of_date``) bound a SEGMENT. Only the
membership events effective in (A, B] matter for it; an event after B can never invalidate a snapshot before B. Membership is
kept in ``security_id`` space (CUSIP / ISIN identity), so a ticker change is never an exit + an entry.

Per security X of a segment the engine builds a timeline of its events, each with an interval of possible effective sessions
[lo, hi] (exact for confirmed official events; a window for date conflicts; (announcement, B] for releases without a date; the
whole segment when nothing is known) and checks that the timeline reaches B's state starting from A's state. A cohort T (membership
at the OPEN of the first session of a month) is MEMBERSHIP_READY when no security has an uncertain interval covering T, every holding
of the two bounding anchors is resolved to a ``security_id``, and the forward replay from A and the backward replay from B agree on
every pinned security. Unconfirmed discovery-CSV legs are never trusted for dates: in STRICT mode (default) they block their segment
unless they resolve to a security the anchors already explain, or to a mere ticker alias of one security.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.config.settings import Settings, get_settings
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.db.models import (
    IndexCurrentAnchor,
    SecurityIdentifierEvidence,
    SP500Anchor,
    SP500AnchorMember,
    SP500Announcement,
    SP500MembershipEvent,
)
from pitquant.universe.sources.spy_sec_anchors import PARSER_VERSION as ANCHOR_PARSER
from pitquant.universe.sources.spy_sec_anchors import norm_name

ENGINE_VERSION = "anchor-graph-2"
CONFIRMED = {"OFFICIAL_CONFIRMED", "OFFICIAL_REPUBLISHED_CONFIRMED"}


# ───────────────────────────────────────────── anchors
@dataclass
class AnchorNode:
    anchor_id: str
    as_of: date
    tier: str
    form: str
    source_available_at: Any
    members: frozenset[str]
    unresolved_lines: int
    basis: dict[str, str]  # security_id -> identity basis in THIS anchor
    names: dict[str, str]  # security_id -> issuer name
    shares: dict[str, float]  # security_id -> shares held by the ETF (continuity hints only)
    pre_traded: list[str] = field(
        default_factory=list
    )  # Tier B: adds held ahead of their next-session effective date
    lei: dict[str, str] = field(
        default_factory=dict
    )  # security_id -> issuer LEI read from the NPORT-P


def pre_holdout_limit(settings: Settings | None = None) -> date:
    return (settings or get_settings()).validation.final_holdout.start - timedelta(days=1)


def load_anchors(
    session: Session, *, upto: date | None = None, settings: Settings | None = None
) -> list[AnchorNode]:
    """One node per as_of date (Tier A NPORT preferred over the N-30D of the same date), never after ``upto`` (default: the last
    day before the sealed holdout, so no post-holdout anchor can touch a pre-holdout reconstruction)."""
    limit = upto or pre_holdout_limit(settings)
    rows = list(
        session.scalars(
            select(SP500Anchor)
            .where(
                SP500Anchor.parser_version == ANCHOR_PARSER,
                SP500Anchor.status == "VERIFIED",
                SP500Anchor.as_of_date <= limit,
            )
            .order_by(SP500Anchor.as_of_date, SP500Anchor.evidence_tier)
        )
    )
    best: dict[date, SP500Anchor] = {}
    for a in rows:
        cur = best.get(a.as_of_date)
        if cur is None or (a.form == "NPORT-P" and cur.form != "NPORT-P"):
            best[a.as_of_date] = a
    from pitquant.universe.identity_bridge import succession_map

    canon = succession_map(
        session
    )  # predecessor -> final successor (membership-preserving successions only)

    def cn(x: str) -> str:
        return canon.get(x, x)

    out: list[AnchorNode] = []
    for d in sorted(best):
        a = best[d]
        mem = list(
            session.scalars(
                select(SP500AnchorMember).where(SP500AnchorMember.anchor_id == a.anchor_id)
            )
        )
        cands = [m for m in mem if m.classification == "INDEX_EQUITY_CANDIDATE"]
        out.append(
            AnchorNode(
                a.anchor_id, d, a.evidence_tier, a.form, a.source_available_at,
                frozenset(cn(m.security_id) for m in cands if m.security_id and m.status == "RESOLVED"),
                sum(1 for m in cands if not m.security_id or m.status != "RESOLVED") + sum(1 for m in mem if m.classification == "UNRESOLVED"),
                {cn(m.security_id): m.identity_basis for m in cands if m.security_id},
                {cn(m.security_id): m.issuer_name for m in cands if m.security_id},
                {cn(m.security_id): (m.shares or 0.0) for m in cands if m.security_id},
                lei={cn(m.security_id): m.lei for m in cands if m.security_id and m.lei and m.lei not in ("N/A", "")},
            )
        )  # fmt: skip
    return out


# ───────────────────────────────────────────── events
@dataclass
class Leg:
    event_id: str
    status: str
    kind: str  # ADD | REMOVE
    ticker: str
    name: str
    lo: date | None  # first possible effective session
    hi: date | None  # last possible effective session (None = unbounded)
    exact: bool
    discovery_date: date | None
    security_id: str | None = None
    resolution: str = "UNRESOLVED"
    reason: str = ""
    conflict_csv: date | None = (
        None  # a discovery-CSV date that disagrees with the OFFICIAL one (never widens the primary date)
    )


_PHRASE = re.compile(
    r"((?:[A-Z0-9][\w&.,'\-]*\s+){0,6}[A-Z0-9][\w&.,'\-]*)\s*\(\s*(?:[A-Za-z][A-Za-z /]{1,18})\s*:\s*([A-Z][A-Za-z0-9.\-]{0,9})\s*[;)]"
)


def scan_release_phrases(session: Session, settings: Settings) -> dict[str, set[str]]:
    """ticker -> phrases right before «(EXCH: TICKER)» in the ARCHIVED S&P releases (no network). Used only as auxiliary name
    evidence for a ticker: the phrase is matched against anchor names by whole-word containment."""
    from pathlib import Path

    from pitquant.data.archive import ArchiveStore
    from pitquant.db.models import RawSourceArchive

    store = ArchiveStore(Path(settings.archive.root))
    out: dict[str, set[str]] = {}
    seen: set[str] = set()
    for r in session.scalars(
        select(RawSourceArchive).where(RawSourceArchive.provider.like("SP_PRESS:%"))
    ):
        if r.sha256 in seen:
            continue
        seen.add(r.sha256)
        try:
            raw = store.get(r.sha256).decode("utf-8", "replace")
        except Exception:
            continue
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw))
        for m in _PHRASE.finditer(text):
            out.setdefault(m.group(2).upper(), set()).add(m.group(1).strip())
    return out


class Resolver:
    """ticker/name -> security_id, in this order: the CURRENT anchor (ticker + CUSIP, HIGH), the unique name of a release
    (MEDIUM). Never a free ticker lookup: a candidate must be PLAUSIBLE for the segment (an added security is not a member of A; a
    removed one is a member of A or was added inside the segment)."""

    def __init__(
        self,
        session: Session,
        anchors: list[AnchorNode],
        phrases: dict[str, set[str]] | None = None,
    ):
        self.phrases = phrases or {}
        self.issuer: dict[
            str, str
        ] = {}  # security_id -> issuer key (LEI when the NPORT-P gives one), over ALL anchors
        for an_ in anchors:
            for sid_, lei_ in an_.lei.items():
                self.issuer.setdefault(sid_, lei_)
        self.name_idx: dict[str, set[str]] = {}
        for a in anchors:
            for sid, nm in a.names.items():
                self.name_idx.setdefault(norm_name(nm), set()).add(sid)
        for msid, mnm in session.execute(
            select(SP500AnchorMember.security_id, SP500AnchorMember.issuer_name).where(
                SP500AnchorMember.security_id.is_not(None)
            )
        ):
            if msid:
                self.name_idx.setdefault(norm_name(mnm), set()).add(msid)
        self.ticker_names: dict[str, set[str]] = {}
        for an in session.scalars(
            select(SP500Announcement).where(SP500Announcement.parser_version == "sp500-evidence-3")
        ):
            for t, n in ((an.added_ticker, an.added_name), (an.removed_ticker, an.removed_name)):
                if t and n:
                    self.ticker_names.setdefault(t.upper(), set()).add(norm_name(n))
        cur = session.scalars(
            select(IndexCurrentAnchor)
            .where(IndexCurrentAnchor.index_code == "SP500")
            .order_by(IndexCurrentAnchor.ingested_at.desc())
        ).first()
        cus = {(t, v): s for s, t, v in session.execute(select(SecurityIdentifierEvidence.security_id, SecurityIdentifierEvidence.id_type, SecurityIdentifierEvidence.value).where(SecurityIdentifierEvidence.id_type == "CUSIP", SecurityIdentifierEvidence.kind == "OFFICIAL"))}  # fmt: skip
        self.cur_ticker: dict[str, str] = {}
        if cur:
            for m in cur.members:
                csid = cus.get(("CUSIP", m.get("cusip") or ""))
                if csid:
                    self.cur_ticker[str(m["ticker"]).upper().replace("/", ".")] = csid

    def _by_containment(self, raw: str) -> set[str]:
        """Anchor securities whose normalised name appears as WHOLE WORDS inside the phrase; only the LONGEST keys count (so
        «Apache» does not win over «Apache Corp» and junk before the name is ignored)."""
        exact = self.name_idx.get(norm_name(raw))
        if exact:
            return set(exact)
        n = " " + norm_name(raw) + " "
        hits = [k for k in self.name_idx if len(k) >= 4 and f" {k} " in n]
        if not hits:
            return set()
        best = max(len(k) for k in hits)
        out: set[str] = set()
        for k in hits:
            if len(k) == best:
                out |= self.name_idx[k]
        return out

    def candidates(self, ticker: str, name: str) -> tuple[set[str], str]:
        t = ticker.upper()
        if t in self.cur_ticker:
            return {self.cur_ticker[t]}, "CURRENT_ANCHOR_TICKER"
        raws = ({name} if name else set()) | self.phrases.get(t, set())
        out: set[str] = set()
        for raw in raws:
            out |= self._by_containment(raw)
        if not out:
            for n in self.ticker_names.get(t, set()):
                out |= self.name_idx.get(n, set())
        return out, "RELEASE_NAME"

    def resolve(
        self,
        leg: Leg,
        a: AnchorNode,
        b: AnchorNode,
        added_in_seg: set[str],
        lineage: dict[str, str] | None = None,
    ) -> None:
        cands, how = self.candidates(leg.ticker, leg.name)
        if lineage:
            cands = {lineage.get(c, c) for c in cands}
        if leg.kind == "ADD":
            ok = {c for c in cands if c not in a.members}
        else:
            ok = {c for c in cands if c in a.members or c in added_in_seg}
        pool = ok if ok else set()
        if not pool and len(cands) == 1:
            # a single candidate that is NOT plausible as a membership change (e.g. the new ticker of a rename whose old security is
            # already in A): keep it, marked, so a CSV rename pair can be recognised as ONE security
            leg.security_id, leg.resolution = next(iter(cands)), how + "+IMPLAUSIBLE"
            return
        if len(pool) == 1:
            leg.security_id, leg.resolution = next(iter(pool)), how
        elif len(pool) > 1:
            both = {c for c in pool if (c in b.members) == (leg.kind == "ADD")}
            if len(both) == 1:
                leg.security_id, leg.resolution = next(iter(both)), how + "+B_CONSISTENT"
            else:
                leg.reason = f"{len(pool)} plausible securities"
        else:
            leg.reason = "no plausible security" if cands else "name/ticker unknown to the anchors"


def _session(cal: Any, d: date | None) -> date | None:
    return cal.session_on_or_after(d) if d else None


def load_legs(session: Session, run_id: str | None = None) -> list[Leg]:
    cal = get_calendar("XNYS")
    if run_id is None:
        run_id = session.scalars(
            select(SP500MembershipEvent.run_id).order_by(SP500MembershipEvent.created_at.desc())
        ).first()
    if run_id is None:
        return []
    ann = {a.announcement_row_id: a for a in session.scalars(select(SP500Announcement))}
    legs: list[Leg] = []
    for e in session.scalars(
        select(SP500MembershipEvent).where(SP500MembershipEvent.run_id == run_id)
    ):
        official = _session(cal, e.effective_at.date()) if e.effective_at else None
        a = ann.get(e.announcement_row_id) if e.announcement_row_id else None
        ann_d = a.announcement_at.date() if a and a.announcement_at else None
        lo: date | None
        hi: date | None
        conflict_csv: date | None = None
        if e.status in CONFIRMED and official:
            lo = hi = official
            exact = True
        elif e.status == "CONFLICT" and official and e.discovery_date:
            csv = _session(cal, e.discovery_date)
            assert csv is not None
            lo, hi, exact = (
                official,
                official,
                True,
            )  # PRIMARY (official release) wins; the CSV date is only a recorded conflict
            conflict_csv = csv if csv != official else None
        elif e.status in ("DATE_TBA", "UNRESOLVED") and ann_d:
            lo, hi, exact = _session(cal, ann_d), None, False
        else:
            lo = hi = None
            exact = False
        for kind, tk, nm in (
            ("ADD", e.added_ticker, a.added_name if a else ""),
            ("REMOVE", e.removed_ticker, a.removed_name if a else ""),
        ):
            if tk:
                legs.append(
                    Leg(
                        e.event_id,
                        e.status,
                        kind,
                        tk.upper(),
                        nm or "",
                        lo,
                        hi,
                        exact,
                        e.discovery_date,
                        conflict_csv=conflict_csv,
                    )
                )
    return legs


def adjust_tier_b(anchors: list[AnchorNode], legs: list[Leg], res: Resolver) -> list[AnchorNode]:
    """An N-30D schedule is the portfolio AFTER the closing trades of its date: SPY already holds a stock that enters the index at
    the open of the NEXT session (e.g. EQT and PG&E were in the 2022-09-30 schedule, effective 2022-10-03) while the NPORT-P of the
    same date shows the index state. For a Tier B anchor the confirmed ADDs effective at the next session are removed from its
    member set (state = index membership at the close of ``as_of``). Removals are not pre-traded (Duke/Citrix were still held)."""
    cal = get_calendar("XNYS")
    out: list[AnchorNode] = []
    for a in anchors:
        if a.form == "NPORT-P":
            out.append(a)
            continue
        nxt = _next_session(cal, a.as_of)
        pre: set[str] = set()
        for leg in legs:
            if leg.kind == "ADD" and leg.exact and leg.lo == nxt:
                c, _how = res.candidates(leg.ticker, leg.name)
                hit = {x for x in c if x in a.members}
                if len(hit) == 1:
                    pre |= hit
        out.append(
            AnchorNode(
                a.anchor_id,
                a.as_of,
                a.tier,
                a.form,
                a.source_available_at,
                frozenset(a.members - pre),
                a.unresolved_lines,
                a.basis,
                a.names,
                a.shares,
                sorted(pre),
            )
        )
    return out


# ───────────────────────────────────────────── segments
@dataclass
class Delta:
    security_identifier: str
    name: str
    anchor_A_status: str
    events_status: str
    anchor_B_status: str
    expected: str
    observed: str
    difference_type: str
    window: tuple[str | None, str | None] | None = None
    hints: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {**self.__dict__, "window": list(self.window) if self.window else None}


@dataclass
class SegmentResult:
    a: AnchorNode
    b: AnchorNode
    n_confirmed_legs: int
    forward_ok: bool
    backward_ok: bool
    status: str  # VALIDATED | LOCAL_GAPS | IDENTITY_UNRESOLVED
    deltas: list[Delta]
    windows: dict[str, tuple[date, date]]  # security_id -> [lo, hi) uncertain
    segment_blocked: str | None  # reason that blocks every cohort of the segment (strict)
    legs: list[Leg]
    alias_candidates: list[dict[str, str]] = field(default_factory=list)
    pinned: dict[str, list[tuple[date, str]]] = field(
        default_factory=dict
    )  # security_id -> exact (session, ADD|REMOVE)


def _next_session(cal: Any, d: date) -> date:
    n: date = cal.next_session(d) if cal.is_session(d) else cal.session_on_or_after(d)
    return n


def _collapse_duplicates(evs: list[Leg]) -> list[Leg]:
    """The same change is reported by several rows (a discovery row and an official-only announcement, a republished release):
    consecutive legs of the SAME kind for one security are ONE event. An exact official leg wins; otherwise the widest interval."""
    out: list[Leg] = []
    for e in evs:
        if out and out[-1].kind == e.kind:
            prev = out[-1]
            if e.exact and not prev.exact:
                out[-1] = e
            elif not (prev.exact and not e.exact) and not (e.exact and prev.exact):
                lo = min(x for x in (prev.lo, e.lo) if x) if (prev.lo or e.lo) else None
                hi = max(x for x in (prev.hi, e.hi) if x) if (prev.hi or e.hi) else None
                out[-1] = Leg(
                    prev.event_id,
                    prev.status,
                    prev.kind,
                    prev.ticker,
                    prev.name,
                    lo,
                    hi,
                    False,
                    prev.discovery_date,
                    prev.security_id,
                    prev.resolution,
                )
            continue
        out.append(e)
    return out


def validate_segment(
    session: Session,
    a: AnchorNode,
    b: AnchorNode,
    legs_all: list[Leg],
    res: Resolver,
    *,
    strict: bool = True,
) -> SegmentResult:
    cal = get_calendar("XNYS")
    seg_lo, seg_hi = _next_session(cal, a.as_of), b.as_of
    cohort_ts = cal.first_sessions_of_months(seg_lo, seg_hi)
    inside = [
        leg for leg in legs_all
        if (leg.lo is not None and seg_lo <= leg.lo <= seg_hi) or (leg.lo is None and leg.discovery_date and a.as_of < leg.discovery_date <= b.as_of)
    ]  # fmt: skip
    # same ISSUER (LEI read from the filings) under a new security: a CUSIP / name / ticker change, NOT an exit + an entry
    lineage: dict[str, str] = {}
    rem_l: dict[str, list[str]] = {}
    add_l: dict[str, list[str]] = {}
    for rx in a.members - b.members:
        if a.lei.get(rx):
            rem_l.setdefault(a.lei[rx], []).append(rx)
    for ax in b.members - a.members:
        if b.lei.get(ax):
            add_l.setdefault(b.lei[ax], []).append(ax)
    alias: list[dict[str, str]] = []
    for lei_, olds in rem_l.items():
        news = add_l.get(lei_, [])
        if len(olds) == 1 and len(news) == 1:
            lineage[olds[0]] = news[0]
            alias.append(
                {
                    "security_id": news[0],
                    "tickers": f"{a.names.get(olds[0], '?')} -> {b.names.get(news[0], '?')}",
                    "evidence": f"same issuer LEI {lei_} in both NPORT-P filings (identity transition, not membership)",
                }
            )
    if lineage:
        a = AnchorNode(a.anchor_id, a.as_of, a.tier, a.form, a.source_available_at, frozenset(lineage.get(x, x) for x in a.members), a.unresolved_lines, a.basis, a.names, {lineage.get(k, k): v for k, v in a.shares.items()}, a.pre_traded, {lineage.get(k, k): v for k, v in a.lei.items()})  # fmt: skip
    added_in_seg = {s for s in b.members - a.members}
    for leg in inside:
        res.resolve(leg, a, b, added_in_seg, lineage)
    # timelines per security
    by_sec: dict[str, list[Leg]] = {}
    unresolved_confirmed: list[Leg] = []
    unconfirmed: list[Leg] = []
    for leg in inside:
        if (
            leg.status in CONFIRMED
            or leg.status == "CONFLICT"
            or leg.status in ("DATE_TBA", "UNRESOLVED")
        ):
            if leg.security_id:
                by_sec.setdefault(leg.security_id, []).append(leg)
            else:
                unresolved_confirmed.append(leg)
        else:
            unconfirmed.append(leg)
    delta_secs = a.members ^ b.members
    touched = delta_secs | set(by_sec)
    windows: dict[str, tuple[date, date]] = {}
    pinned: dict[str, list[tuple[date, str]]] = {}
    deltas: list[Delta] = []
    n_conf = sum(1 for leg in inside if leg.status in CONFIRMED)
    for sid in sorted(touched):
        in_a, in_b = sid in a.members, sid in b.members
        evs = _collapse_duplicates(
            sorted(by_sec.get(sid, []), key=lambda x: (x.lo or seg_lo, x.kind))
        )
        state, last_known, ok = in_a, seg_lo, True
        unc_lo: date | None = None
        unc_hi: date | None = None
        det_events: list[tuple[date, str]] = []
        for e in evs:
            want = e.kind == "ADD"
            if (
                state == want
            ):  # add of a member / remove of a non-member: the timeline is inconsistent
                ok = False
                break
            state = want
            if e.exact and e.lo:
                det_events.append((e.lo, e.kind))
                last_known = max(last_known, e.lo)
            else:
                lo_e = e.lo or seg_lo
                hi_e = e.hi if e.hi else seg_hi
                unc_lo = min(unc_lo, lo_e) if unc_lo else lo_e
                unc_hi = max(unc_hi, hi_e) if unc_hi else hi_e
        explained = ok and state == in_b and unc_lo is None
        if explained:
            if det_events:
                pinned[sid] = det_events
            continue
        # not explained by exact confirmed events: an uncertain interval remains
        lo = unc_lo or last_known
        hi = unc_hi or seg_hi
        if not ok:
            lo, hi = seg_lo, seg_hi
        if unc_lo is not None and state == in_b and ok:
            pass  # dated-with-uncertainty (conflict / release without date): window as computed
        windows[sid] = (lo, hi)
        if in_b and not in_a:
            dt = "MISSING_ADDITION_EVENT"
        elif in_a and not in_b:
            dt = "MISSING_REMOVAL_EVENT"
        else:
            dt = "UNEXPLAINED"
        ev_status = ",".join(f"{e.kind}:{e.status}" for e in evs) or "none"
        if any(e.status in ("DATE_TBA", "UNRESOLVED") for e in evs):
            dt = "PARSER_MISS" if False else "DATE_MISSING_IN_RELEASE"
        elif not ok:
            dt = "UNEXPLAINED"
        weak = [
            bs
            for s_, bs in list(a.basis.items()) + list(b.basis.items())
            if s_ == sid and bs in ("NAME_ONLY", "NAME_TEMPORAL")
        ]
        hints: list[str] = []
        if weak and dt.startswith("MISSING"):
            dt = "SECURITY_IDENTITY_GAP"
            hints.append(
                "one side of this change rests on a name-only identity (N-30D): it may be the same security under another name/CUSIP"
            )
        for ll in unconfirmed:
            if ll.security_id == sid:
                hints.append(
                    f"discovery CSV leg {ll.kind} {ll.ticker} {ll.discovery_date} (unconfirmed, date not trusted)"
                )
        deltas.append(
            Delta(sid, a.names.get(sid) or b.names.get(sid) or sid, "MEMBER" if in_a else "ABSENT", ev_status, "MEMBER" if in_b else "ABSENT",
                  "MEMBER" if in_b else "ABSENT", "MEMBER" if state else "ABSENT", dt, (str(lo), str(hi)), hints)
        )  # fmt: skip
    # identity-link hints: an unexplained removal and an unexplained addition of the SAME issuer under a new CUSIP/name
    rem = [d for d in deltas if d.difference_type == "MISSING_REMOVAL_EVENT"]
    add = [d for d in deltas if d.difference_type == "MISSING_ADDITION_EVENT"]
    for r_ in rem:
        for a_ in add:
            ra, rb = (
                a.shares.get(r_.security_identifier, 0.0),
                b.shares.get(a_.security_identifier, 0.0),
            )
            tr, ta = norm_name(r_.name).split(), norm_name(a_.name).split()
            same_head = (
                bool(tr and ta) and len(set(tr) & set(ta)) / len(set(tr) | set(ta)) >= 0.5
            )  # token overlap, not a shared first word
            if same_head and ra and rb and 0.5 <= rb / ra <= 2.0:
                for d_, other in ((r_, a_), (a_, r_)):
                    d_.hints.append(
                        f"possible identity link with {other.name} (name token overlap, shares ratio {rb / ra:.2f}): CUSIP/name change of ONE issuer?"
                    )
                    d_.difference_type = "SECURITY_IDENTITY_GAP"
    for lg in inside:
        if lg.conflict_csv and lg.exact and lg.security_id:
            deltas.append(Delta(lg.security_id, a.names.get(lg.security_id) or b.names.get(lg.security_id) or lg.ticker, "n/a", f"{lg.kind}:{lg.status}", "n/a", "official date", "CSV date differs", "DISCOVERY_CONFLICT", None, [f"official effective {lg.lo} vs discovery CSV {lg.conflict_csv}: the primary date stands; the CSV never widens it"]))  # fmt: skip
    # confirmed-but-unresolved legs: identity gap, the segment cannot be trusted for the dates around them
    seg_block: str | None = None
    for leg in unresolved_confirmed:
        lo, hi = leg.lo or seg_lo, leg.hi or seg_hi
        deltas.append(
            Delta(
                f"{leg.ticker}?",
                leg.name,
                "?",
                f"{leg.kind}:{leg.status}",
                "?",
                "?",
                "?",
                "SECURITY_IDENTITY_GAP",
                (str(lo), str(hi)),
                [leg.reason or "ticker/name not resolvable to an anchor security"],
            )
        )
        windows[f"{leg.ticker}?{leg.event_id}"] = (lo, max(hi, lo + timedelta(days=1)))
    # an unresolved PRIMARY add and remove of the SAME ticker inside the segment: a transient member whose identity is unknown. It is a
    # member between the two dates, so the cohorts in between cannot be reconstructed.
    for tk in {x.ticker for x in unresolved_confirmed}:
        adds = [
            x.lo
            for x in unresolved_confirmed
            if x.ticker == tk and x.kind == "ADD" and x.exact and x.lo
        ]
        rems = [
            x.lo
            for x in unresolved_confirmed
            if x.ticker == tk and x.kind == "REMOVE" and x.exact and x.lo
        ]
        if adds and rems and min(adds) < max(rems):
            windows[f"transient-primary:{tk}"] = (min(adds), max(rems))
            deltas.append(Delta(f"{tk}?", tk, "ABSENT", "ADD+REMOVE:PRIMARY", "ABSENT", "?", "?", "SECURITY_IDENTITY_GAP", (str(min(adds)), str(max(rems))), ["primary add and remove of the same ticker inside the segment; the security is in no anchor, so it has no security_id"]))  # fmt: skip
    # Unconfirmed discovery-CSV legs never give a date. Each CSV ROW is first classified against the anchors:
    #  1. both legs resolve to ONE security                       -> TICKER_ALIAS_ONLY (rename artifact of the CSV)
    #  2. a leg resolves into the LEI lineage (old or new)         -> alias of that security (rename), not membership
    #  3. a leg resolves to a security the anchors already explain -> only a hint for that security
    #  4. otherwise it is a CLAIM the anchors cannot place. It is harmless only while it can be matched to an anchor-visible,
    #     still-unexplained change (a CAPACITY ledger per direction); beyond that capacity, or when the same ticker is added AND
    #     removed inside the segment (a transient member the anchors cannot see), strict mode blocks the whole segment.
    lin_all = set(lineage) | set(lineage.values())
    lin_issuers = {res.issuer[x] for x in lin_all if x in res.issuer}
    visible_add = [
        d for d in deltas if d.anchor_A_status == "ABSENT" and d.anchor_B_status == "MEMBER"
    ]
    visible_rem = [
        d for d in deltas if d.anchor_A_status == "MEMBER" and d.anchor_B_status == "ABSENT"
    ]
    cap = {"ADD": len(visible_add), "REMOVE": len(visible_rem)}
    if unconfirmed:
        by_event: dict[str, list[Leg]] = {}
        for ll in unconfirmed:
            by_event.setdefault(ll.event_id, []).append(ll)
        tickers_added = {x.ticker for x in unconfirmed if x.kind == "ADD"}
        tickers_removed = {x.ticker for x in unconfirmed if x.kind == "REMOVE"}
        transient_tickers = tickers_added & tickers_removed
        for ls in by_event.values():
            ids = {x.security_id for x in ls if x.security_id}
            if (
                len(ls) == 2
                and all(x.security_id for x in ls)
                and len({res.issuer.get(i, i) for i in ids}) == 1
            ):
                alias.append(
                    {
                        "security_id": next(iter(ids)),
                        "tickers": "->".join(sorted({x.ticker for x in ls})),
                        "evidence": "discovery CSV pair resolves to ONE security (rename), not a membership change",
                    }
                )
                continue
            if len(ls) == 2 and any(
                x.security_id in lin_all or res.issuer.get(x.security_id or "", "") in lin_issuers
                for x in ls
                if x.security_id
            ):
                alias.append(
                    {
                        "security_id": next(x.security_id for x in ls if x.security_id in lin_all),
                        "tickers": "<->".join(x.ticker for x in ls),
                        "evidence": "discovery CSV pair touches a same-LEI lineage: ticker change of one issuer",
                    }
                )
                continue
            for x in ls:
                if x.security_id and (x.security_id in windows or x.security_id in pinned):
                    continue  # explained (or already a gap) by the anchors: the CSV leg is only a hint
                if x.security_id and x.ticker not in transient_tickers:
                    # a lone leg for a security the anchors show as a member at BOTH ends (ADD) or at NEITHER end (REMOVE) changes
                    # no membership: a ticker/class relabelling of the CSV. It would only matter with a same-ticker transient pair.
                    deltas.append(Delta(x.security_id, x.name or x.ticker, "n/a", f"{x.kind}:{x.status}", "n/a", "no change (anchors)", "no change (anchors)", "TICKER_ALIAS_ONLY", None,
                                        [f"discovery CSV {x.kind} {x.ticker} {x.discovery_date}: the anchors show no membership change for this security (ticker/class artifact); QA only"]))  # fmt: skip
                    continue
                if not x.security_id and x.ticker not in transient_tickers and cap[x.kind] > 0:
                    cap[x.kind] -= (
                        1  # matched to an anchor-visible unexplained change: a hint for that gap
                    )
                    continue
                is_trans = x.ticker in transient_tickers
                gap_type = "TRANSIENT_HOLDING" if is_trans else "SECURITY_IDENTITY_GAP"
                why = (
                    "same ticker added and removed inside the segment (transient member the anchors cannot see)"
                    if is_trans
                    else "more discovery legs than anchor-visible changes (unresolved ticker)"
                )
                win: tuple[str, str] | None = None
                if is_trans:
                    ds = [
                        lg.discovery_date
                        for lg in unconfirmed
                        if lg.ticker == x.ticker and lg.discovery_date
                    ]
                    if ds:
                        lo_t, hi_t = _session(cal, min(ds)), _session(cal, max(ds))
                        crosses = (
                            lo_t is not None
                            and hi_t is not None
                            and any(lo_t <= m < hi_t for m in cohort_ts)
                        )
                        if crosses and res.phrases.get(x.ticker) and lo_t and hi_t:
                            # DISCOVERY corroborated by a mention in an archived S&P release AND able to change a monthly decision
                            windows[f"transient:{x.ticker}"] = (lo_t, hi_t)
                            win = (str(lo_t), str(hi_t))
                monthly = (
                    "blocks only the monthly cohorts in its window"
                    if win
                    else "DISCOVERY_UNCORROBORATED: warning only for monthly research"
                )
                deltas.append(Delta(x.security_id or f"{x.ticker}?", x.name or x.ticker, "n/a", f"{x.kind}:{x.status}", "n/a", "no change (anchors)" if x.security_id else "?", "CSV claims a change", gap_type,
                                    win, [f"discovery CSV {x.kind} {x.ticker} {x.discovery_date}: unconfirmed, date not trusted; {why}; monthly: {monthly}; daily canonical: blocks the segment"]))  # fmt: skip
                seg_block = (
                    seg_block
                    or f"unconfirmed discovery leg {x.kind} {x.ticker} {x.discovery_date}: {why}"
                )
    # replay forward / backward on confirmed exact events
    exact = sorted(
        [
            (leg.lo, leg.kind, leg.security_id)
            for leg in inside
            if leg.exact and leg.security_id and leg.lo
        ],
        key=lambda x: (x[0], x[1]),
    )
    fwd = set(a.members)
    bwd = set(b.members)
    anomalies = 0
    for _d, kind, xs in exact:
        if kind == "ADD":
            anomalies += xs in fwd
            fwd.add(xs)
        else:
            anomalies += xs not in fwd
            fwd.discard(xs)
    for _d, kind, xs in reversed(exact):
        if kind == "ADD":
            anomalies += xs not in bwd
            bwd.discard(xs)
        else:
            anomalies += xs in bwd
            bwd.add(xs)
    forward_ok = fwd == set(b.members) and not unresolved_confirmed and not anomalies
    backward_ok = bwd == set(a.members) and not unresolved_confirmed and not anomalies
    if a.unresolved_lines or b.unresolved_lines:
        status = "IDENTITY_UNRESOLVED"
    elif forward_ok and backward_ok and not seg_block and not windows:
        status = "VALIDATED"
    else:
        status = "LOCAL_GAPS"
    return SegmentResult(
        a,
        b,
        n_conf,
        forward_ok,
        backward_ok,
        status,
        deltas,
        windows,
        seg_block if strict else None,
        inside,
        alias,
        pinned,
    )


# ───────────────────────────────────────────── cohorts
@dataclass
class Cohort:
    date: date  # decision_at (open of the first session of the month)
    status: str  # MEMBERSHIP_READY | BLOCKED | NO_ANCHOR
    segment: str | None
    n_members: int | None
    reasons: list[str] = field(default_factory=list)
    members: frozenset[str] | None = None
    forward_set: frozenset[str] | None = (
        None  # anchor A + every change certain to have happened by decision_at
    )
    backward_set: frozenset[str] | None = (
        None  # anchor B - every change certain to happen after decision_at
    )
    sets_equal: bool | None = None
    primary_conflicts: list[str] = field(default_factory=list)
    monthly_ambiguity: list[str] = field(default_factory=list)
    daily_ready: bool = False  # the stricter DAILY_CANONICAL standard for the same cohort


@dataclass
class GraphReport:
    anchors: list[AnchorNode]
    segments: list[SegmentResult]
    cohorts: list[Cohort]
    strict: bool  # True = DAILY_CANONICAL standard; False = MONTHLY_RESEARCH standard
    longest_run: int
    ready: int
    post_limit_events_used: int = 0
    daily_longest_run: int = 0
    daily_ready: int = 0
    weak_identity: list[str] = field(
        default_factory=list
    )  # securities in the anchors WITHOUT official CUSIP/ISIN evidence

    @property
    def standard(self) -> str:
        return "DAILY_CANONICAL" if self.strict else "MONTHLY_RESEARCH"


def sets_at(seg: SegmentResult, t: date) -> tuple[frozenset[str], frozenset[str]]:
    """(forward_set, backward_set) at the OPEN of session ``t``. Forward starts from anchor A and applies only changes CERTAIN to have
    happened by ``t`` (exact events <= t; uncertain intervals whose last possible session is <= t); backward starts from anchor B and
    undoes only changes certain to happen after ``t``. They differ exactly for a security whose uncertain interval covers ``t``."""
    fwd, bwd = set(seg.a.members), set(seg.b.members)
    for sid in set(seg.a.members) | set(seg.b.members) | set(seg.pinned) | set(seg.windows):
        in_a, in_b = sid in seg.a.members, sid in seg.b.members
        if sid in seg.pinned:
            ev = sorted(seg.pinned[sid])
            f, b = in_a, in_b
            for d, k in ev:
                if d <= t:
                    f = k == "ADD"
            for d, k in reversed(ev):
                if d > t:
                    b = k != "ADD"
        elif sid in seg.windows:
            lo, hi = seg.windows[sid]
            f = in_b if hi <= t else in_a
            b = in_a if lo > t else in_b
        else:
            f, b = in_a, in_b
        if sid in seg.windows or sid in seg.pinned or sid in seg.a.members or sid in seg.b.members:
            (fwd.add if f else fwd.discard)(sid)
            (bwd.add if b else bwd.discard)(sid)
    return frozenset(x for x in fwd if x in _ids(seg)), frozenset(x for x in bwd if x in _ids(seg))


def _ids(seg: SegmentResult) -> set[str]:
    return set(seg.a.members) | set(seg.b.members) | set(seg.pinned)


def members_at(seg: SegmentResult, t: date) -> frozenset[str] | None:
    """Membership at the OPEN of session ``t`` inside the segment, or None when a security is uncertain at ``t``."""
    f, b = sets_at(seg, t)
    covering = [w for w in seg.windows.values() if w[0] <= t < w[1]]
    return f if f == b and not covering else None


def reconstruct(
    session: Session,
    start: date,
    end: date,
    *,
    standard: str = "MONTHLY",
    strict: bool | None = None,
    settings: Settings | None = None,
    persist: bool = False,
) -> GraphReport:
    """``standard``: MONTHLY (the Research Lab gate: an uncertainty blocks a cohort only if it can change the membership at THAT
    decision_at) or DAILY (canonical: any unresolved change or unconfirmed discovery leg blocks its whole segment).
    ``strict`` (legacy): True -> DAILY, False -> MONTHLY."""
    if strict is not None:
        standard = "DAILY" if strict else "MONTHLY"
    daily = standard == "DAILY"
    cfg = settings or get_settings()
    limit = pre_holdout_limit(cfg)
    anchors = load_anchors(session, settings=cfg)
    cal = get_calendar("XNYS")
    legs = load_legs(session)
    res = Resolver(session, anchors, scan_release_phrases(session, cfg))
    anchors = adjust_tier_b(anchors, legs, res)
    segs: dict[tuple[date, date], SegmentResult] = {}
    for a, b in itertools.pairwise(anchors):
        segs[(a.as_of, b.as_of)] = validate_segment(session, a, b, legs, res, strict=True)
    cohorts: list[Cohort] = []
    for t in cal.first_sessions_of_months(start, end):
        prev = [x for x in anchors if x.as_of < t]
        nxt = [x for x in anchors if x.as_of >= t]
        if not prev or not nxt:
            cohorts.append(
                Cohort(
                    t,
                    "NO_ANCHOR",
                    None,
                    None,
                    ["no anchor on one side of this date inside the pre-holdout chain"],
                )
            )
            continue
        seg = segs[(prev[-1].as_of, nxt[0].as_of)]
        label = f"{seg.a.as_of}→{seg.b.as_of}"
        fwd, bwd = sets_at(seg, t)
        cover = [
            d
            for d in seg.deltas
            if d.window and d.window[0] and d.window[1] and d.window[0] <= str(t) < d.window[1]
        ]
        conflicts = [
            f"{d.difference_type}: {d.name}"
            for d in cover
            if d.difference_type in ("UNEXPLAINED", "DATE_CONFLICT")
        ]
        ambiguity = [f"{d.difference_type}: {d.name}" for d in cover]
        ident = bool(seg.a.unresolved_lines or seg.b.unresolved_lines)
        daily_ok = (
            not ident and seg.status == "VALIDATED" and not seg.segment_blocked and not seg.windows
        )
        monthly_reasons: list[str] = []
        if ident:
            monthly_reasons.append("anchor holdings not resolved to a security_id")
        if ambiguity:
            monthly_reasons.append(
                f"{len(ambiguity)} securities with an effective-date uncertainty covering this decision_at"
            )
        if fwd != bwd and not ambiguity:
            monthly_reasons.append(
                "forward and backward reconstructions disagree without an explained uncertainty: fail closed"
            )
        daily_reasons = list(monthly_reasons)
        if not daily_ok:
            daily_reasons.append(
                seg.segment_blocked or "daily canonical: the segment has unresolved changes"
            )
        reasons = daily_reasons if daily else monthly_reasons
        c = Cohort(
            t,
            "BLOCKED" if reasons else "MEMBERSHIP_READY",
            label,
            None if reasons else len(fwd),
            reasons,
            None if reasons else fwd,
            fwd,
            bwd,
            fwd == bwd,
            conflicts,
            ambiguity,
            daily_ok and not monthly_reasons,
        )
        cohorts.append(c)
    rep = GraphReport(anchors, list(segs.values()), cohorts, daily, _run(cohorts, lambda c: c.status == "MEMBERSHIP_READY"), sum(c.status == "MEMBERSHIP_READY" for c in cohorts),
                      sum(1 for s_ in segs.values() for leg in s_.legs if leg.lo and leg.lo > limit), _run(cohorts, lambda c: c.daily_ready), sum(c.daily_ready for c in cohorts))  # fmt: skip
    have = {
        x
        for (x,) in session.execute(
            select(SecurityIdentifierEvidence.security_id).where(
                SecurityIdentifierEvidence.kind == "OFFICIAL",
                SecurityIdentifierEvidence.id_type.in_(("CUSIP", "ISIN")),
            )
        )
    }
    from pitquant.universe.identity_bridge import succession_map

    cn = succession_map(session)
    have |= {
        cn[k] for k in cn if k in have
    }  # a successor inherits the identity evidence of its predecessor chain
    rep.weak_identity = sorted({x for a_ in anchors for x in a_.members if x not in have})
    return rep


def _run(cohorts: list[Cohort], ok: Any) -> int:
    best = run = 0
    prev_d: date | None = None
    for c in cohorts:
        if ok(c):
            run = (
                run + 1
                if prev_d
                and (c.date.year * 12 + c.date.month) - (prev_d.year * 12 + prev_d.month) == 1
                else 1
            )
            best, prev_d = max(best, run), c.date
        else:
            run, prev_d = 0, None
    return best


# ───────────────────────────────────────────── persistence + metrics
def persist_graph(session: Session, rep: GraphReport) -> dict[str, int]:
    """Append-only: one row per validated segment (per engine run) and the ticker aliases proven by the filings.
    Idempotent: a (segment, engine version, event run) already stored is not duplicated."""
    from pitquant.db.models import SecurityTickerAlias, SP500MembershipSegment

    run_id = session.scalars(
        select(SP500MembershipEvent.run_id).order_by(SP500MembershipEvent.created_at.desc())
    ).first()
    have = {
        (x.anchor_a_id, x.anchor_b_id, x.engine_version, x.run_id)
        for x in session.scalars(select(SP500MembershipSegment))
    }
    n_seg = n_alias = 0
    for sg in rep.segments:
        key = (
            sg.a.anchor_id,
            sg.b.anchor_id,
            ENGINE_VERSION + ("+strict" if rep.strict else "+lenient"),
            run_id,
        )
        if key in have:
            continue
        session.add(
            SP500MembershipSegment(
                anchor_a_id=sg.a.anchor_id, anchor_b_id=sg.b.anchor_id, run_id=run_id, engine_version=key[2], n_confirmed_events=sg.n_confirmed_legs,
                n_delta_added=sum(1 for d in sg.deltas if d.anchor_B_status == "MEMBER" and d.anchor_A_status == "ABSENT"),
                n_delta_removed=sum(1 for d in sg.deltas if d.anchor_A_status == "MEMBER" and d.anchor_B_status == "ABSENT"),
                forward_ok=sg.forward_ok, backward_ok=sg.backward_ok, status=sg.status, deltas=[d.as_dict() for d in sg.deltas],
            )
        )  # fmt: skip
        n_seg += 1
    have_alias = {
        (x.security_id, x.ticker, x.source) for x in session.scalars(select(SecurityTickerAlias))
    }
    for sg in rep.segments:
        for al in sg.alias_candidates:
            for tk in re.split(r"\s*(?:->|<->|-)\s*", al["tickers"]):
                tk = tk.strip().upper()
                if not tk or (" " in tk and len(tk) > 12):
                    continue
                key2 = (al["security_id"], tk, "ANCHOR_GRAPH")
                if key2 in have_alias:
                    continue
                session.add(SecurityTickerAlias(security_id=al["security_id"], ticker=tk[:20], valid_from=None, valid_to=None, bounds="PARTIAL", source="ANCHOR_GRAPH",
                                                source_hash=None, confidence="MEDIUM", note=al["evidence"][:300]))  # fmt: skip
                have_alias.add(key2)
                n_alias += 1
    session.flush()
    return {"segments": n_seg, "aliases": n_alias}


def graph_metrics(rep: GraphReport) -> dict[str, Any]:
    """The principal D-02 metrics (the discovery-CSV «% confirmed» is QA only)."""
    tiers: dict[str, int] = {}
    for a in rep.anchors:
        tiers[a.tier] = tiers.get(a.tier, 0) + 1
    members = sum(len(a.members) for a in rep.anchors)
    weak = len(rep.weak_identity)
    return {
        "verified_anchors": len(rep.anchors),
        "anchors_by_tier": tiers,
        "validated_segments": sum(1 for s in rep.segments if s.status == "VALIDATED"),
        "forward_validated_segments": sum(1 for s in rep.segments if s.forward_ok),
        "backward_validated_segments": sum(1 for s in rep.segments if s.backward_ok),
        "segments": len(rep.segments),
        "local_unresolved_segments": sum(1 for s in rep.segments if s.status != "VALIDATED"),
        "monthly_cohorts": len(rep.cohorts),
        "monthly_cohorts_reconstructible": rep.ready,
        "longest_continuous_period": rep.longest_run,
        "security_identity_resolution": {"anchor_members": members, "weak_identity_members": weak, "unresolved_lines": sum(a.unresolved_lines for a in rep.anchors)},
        "post_limit_events_used": rep.post_limit_events_used,
        "mode": rep.standard,
        "daily_canonical_cohorts": rep.daily_ready,
        "daily_canonical_longest_run": rep.daily_longest_run,
    }  # fmt: skip


# ───────────────────────────────────────────── gap reclassification (ADR-0033)
CATEGORIES = (
    "PRIMARY_DELTA_UNEXPLAINED", "PRIMARY_EVENT_MISSING", "MONTHLY_DATE_AMBIGUITY", "SECURITY_IDENTITY_ONLY", "TICKER_OR_NAME_CHANGE",
    "SUCCESSOR_SECURITY", "DISCOVERY_UNCORROBORATED", "DISCOVERY_CONFLICT", "TRANSIENT_EVENT_POSSIBLE", "RESOLVED",
)  # fmt: skip


def classify_gaps(rep: GraphReport) -> list[dict[str, Any]]:
    """One record per delta/alias of every segment with its ADR-0033 category and whether it can really block a monthly membership
    (``blocks_membership``) or only an identity join (``blocks_identity``). The cohorts it blocks are listed."""
    out: list[dict[str, Any]] = []
    cohort_dates = [c.date for c in rep.cohorts]
    for sg in rep.segments:
        label = f"{sg.a.as_of}→{sg.b.as_of}"
        for d in sg.deltas:
            crossing = [
                str(t)
                for t in cohort_dates
                if d.window and d.window[0] and d.window[1] and d.window[0] <= str(t) < d.window[1]
            ]
            t = d.difference_type
            if t == "TICKER_ALIAS_ONLY":
                cat, bm, bi = "TICKER_OR_NAME_CHANGE", False, False
            elif t == "DISCOVERY_CONFLICT":
                cat, bm, bi = "DISCOVERY_CONFLICT", False, False
            elif t in ("MISSING_ADDITION_EVENT", "MISSING_REMOVAL_EVENT"):
                cat, bm, bi = (
                    ("PRIMARY_EVENT_MISSING", True, False)
                    if crossing
                    else ("RESOLVED", False, False)
                )
            elif t == "DATE_MISSING_IN_RELEASE":
                cat, bm, bi = (
                    ("MONTHLY_DATE_AMBIGUITY", True, False)
                    if crossing
                    else ("RESOLVED", False, False)
                )
            elif t == "UNEXPLAINED":
                cat, bm, bi = (
                    ("PRIMARY_DELTA_UNEXPLAINED", True, False)
                    if crossing
                    else ("RESOLVED", False, False)
                )
            elif t == "TRANSIENT_HOLDING":
                cat, bm, bi = (
                    ("TRANSIENT_EVENT_POSSIBLE", True, False)
                    if crossing
                    else ("DISCOVERY_UNCORROBORATED", False, False)
                )
            elif t == "SECURITY_IDENTITY_GAP":
                if d.window:  # an anchor delta (or a primary leg) whose identity is unresolved: membership unknown until the identity is
                    cat, bm, bi = (
                        ("SECURITY_IDENTITY_ONLY", bool(crossing), True)
                        if crossing
                        else ("RESOLVED", False, False)
                    )
                else:  # a discovery-CSV leg whose ticker resolves to nothing
                    cat, bm, bi = "DISCOVERY_UNCORROBORATED", False, False
            else:
                cat, bm, bi = "PRIMARY_DELTA_UNEXPLAINED", bool(crossing), False
            out.append({"segment": label, "difference_type": t, "category": cat, "security": d.name, "events": d.events_status, "window": list(d.window) if d.window else None, "cohorts_blocked": crossing, "blocking_decision_dates": crossing, "blocks_monthly_membership": bm, "blocks_membership": bm, "blocks_identity": bi, "hints": d.hints})  # fmt: skip
        for al in sg.alias_candidates:
            kind = "SUCCESSOR_SECURITY" if "LEI" in al["evidence"] else "TICKER_OR_NAME_CHANGE"
            out.append({"segment": label, "difference_type": "ALIAS", "category": kind, "security": al["tickers"], "events": "anchor LEI / discovery pair", "window": None, "cohorts_blocked": [], "blocks_membership": False, "blocks_identity": False, "hints": [al["evidence"]]})  # fmt: skip
    return out
