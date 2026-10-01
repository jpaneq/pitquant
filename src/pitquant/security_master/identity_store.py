"""Persistence for the IdentityResolutionEngine (ADR-0020).

* reads ANCV evidence from ``security_identity_snapshots``;
* builds one ``MembershipSpan`` per ``index_membership`` interval, with the codes the BME
  history proves for it (ticker history bounded to membership);
* stores a run + its segments (append-only) and registers the PROVEN ISINs on securities.

Security choice for a proven ISIN: the security that already owns it (a re-entry after a
gap maps back to the same security — one ISIN never gets two security_ids); otherwise the
membership's own security. Identifier validity is the union of the proven segments, never
the snapshot date stretched to a listing date.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.core.hashing import content_hash
from pitquant.db.models import (
    IdentifierHistory,
    IdentityResolutionRun,
    IndexMembership,
    Issuer,
    MembershipIdentitySegment,
    RawSourceArchive,
    Security,
    SecurityIdentitySnapshot,
    TickerHistory,
)
from pitquant.security_master.identity import (
    BACKTESTABLE,
    ENGINE_VERSION,
    CodePeriod,
    IdentityResolutionEngine,
    MembershipSpan,
    OfficialIdentifier,
    PeriodClass,
    Segment,
    SnapshotIndex,
    SnapshotLine,
    coverage_metrics,
)
from pitquant.security_master.service import SecurityMaster


def load_snapshot_index(session: Session, source: str = "CNMV_ANCV") -> SnapshotIndex:
    rows = session.scalars(
        select(SecurityIdentitySnapshot).where(SecurityIdentitySnapshot.source == source)
    )
    return SnapshotIndex(
        SnapshotLine(
            r.reference_date, r.isin, r.issuer_legal_name, r.instrument_name, r.cfi, r.issue_date
        )
        for r in rows
    )


def snapshots_hash(session: Session, provider: str = "CNMV_ANCV") -> str:
    """Hash of the archived distributions the evidence comes from (content addressed)."""
    shas = sorted(
        session.scalars(
            select(RawSourceArchive.sha256).where(RawSourceArchive.provider == provider)
        )
    )
    return content_hash(shas)


def spans_for_build(session: Session, build_id: str) -> dict[int, MembershipSpan]:
    out: dict[int, MembershipSpan] = {}
    for iv in session.scalars(select(IndexMembership).where(IndexMembership.build_id == build_id)):
        tick = session.scalars(
            select(TickerHistory)
            .where(TickerHistory.security_id == iv.security_id)
            .order_by(TickerHistory.valid_from)
        ).all()
        codes = tuple(
            CodePeriod(t.ticker, t.valid_from, t.valid_to)
            for t in tick
            if t.valid_from < (iv.effective_to or date.max)
            and (t.valid_to is None or t.valid_to > iv.effective_from)
        )
        out[iv.id] = MembershipSpan(str(iv.id), iv.effective_from, iv.effective_to, codes)
    return out


def _split_at(seg: Segment, cut: date) -> list[Segment]:
    if seg.start < cut and (seg.end is None or seg.end > cut):
        a = Segment(seg.start, cut, seg.status, seg.isin, list(seg.evidence), seg.candidates)
        b = Segment(cut, seg.end, seg.status, seg.isin, list(seg.evidence), seg.candidates)
        return [a, b]
    return [seg]


@dataclass
class IdentityRunResult:
    run: IdentityResolutionRun
    segments: dict[int, list[Segment]]
    spans: dict[int, MembershipSpan]
    metrics: dict[str, object]
    metrics_pre: dict[str, object]


def _owner_of(session: Session, isin: str) -> str | None:
    owners = set(
        session.scalars(
            select(IdentifierHistory.security_id).where(
                IdentifierHistory.id_type == "ISIN", IdentifierHistory.value == isin
            )
        )
    )
    if len(owners) > 1:
        raise ValueError(f"ISIN {isin} already owned by several securities {owners}")
    return owners.pop() if owners else None


def _issuer_for(session: Session, sec: Security, legal_name: str, linked: str | None = None) -> str:
    """The security's issuer. ``linked``: issuer proven by an official CIF ↔ ISIN document
    (ANCV query by NIF); otherwise a new issuer named after the ANCV legal name."""
    if sec.issuer_id is not None and linked is not None and sec.issuer_id != linked:
        raise ValueError(f"security {sec.security_id}: issuer {sec.issuer_id} != CIF link {linked}")
    if sec.issuer_id is None and linked is not None:
        sec.issuer_id = linked
    if sec.issuer_id is None:
        iss = Issuer(name=legal_name, country="ES")
        session.add(iss)
        session.flush()
        sec.issuer_id = iss.issuer_id
    return sec.issuer_id


def run_identity_resolution(
    session: Session,
    *,
    index_code: str,
    build_id: str,
    engine: IdentityResolutionEngine,
    canonical_start: date,
    inputs_hash: str,
    official: Sequence[OfficialIdentifier] = (),
    issuer_links: Mapping[str, str] | None = None,
) -> IdentityRunResult:
    """``issuer_links``: ISIN -> issuer_id proven by an official CIF <-> ISIN document."""
    issuer_links = issuer_links or {}
    spans = spans_for_build(session, build_id)
    raw = {k: engine.resolve(sp) for k, sp in spans.items()}
    metrics = coverage_metrics(
        {str(k): v for k, v in raw.items()}, {str(k): v for k, v in spans.items()}, canonical_start
    )
    pre_spans = {str(k): sp for k, sp in spans.items() if sp.effective_from < canonical_start}
    metrics_pre = coverage_metrics(
        {k: [s for s in raw[int(k)] if s.start < canonical_start] for k in pre_spans},
        pre_spans,
        date.min,
    )
    run = IdentityResolutionRun(
        index_code=index_code,
        build_id=build_id,
        engine_version=ENGINE_VERSION,
        inputs_hash=content_hash(
            [inputs_hash, *(f"{o.code}:{o.isin}:{o.source_hash}" for o in official)]
        ),
        canonical_start=canonical_start,
        metrics={"canonical": metrics, "pre_canonical": metrics_pre},
    )
    session.add(run)
    session.flush()
    sm = SecurityMaster(session)
    proven: dict[tuple[str, str], list[tuple[date, date | None]]] = defaultdict(list)
    for mid, segs in raw.items():
        iv = session.get_one(IndexMembership, mid)
        for seg in [x for s in segs for x in _split_at(s, canonical_start)]:
            sid: str | None = None
            issuer_id: str | None = None
            if seg.status in BACKTESTABLE and seg.isin:
                sid = _owner_of(session, seg.isin) or iv.security_id
                sec = session.get_one(Security, sid)
                last = engine.ix.latest_line(seg.isin)
                issuer_id = _issuer_for(
                    session,
                    sec,
                    last.issuer_legal_name if last else sec.name,
                    issuer_links.get(seg.isin),
                )
                proven[(sid, seg.isin)].append((seg.start, seg.end))
            session.add(
                MembershipIdentitySegment(
                    run_id=run.run_id,
                    membership_id=mid,
                    segment_from=seg.start,
                    segment_to=seg.end,
                    status=seg.status.value,
                    period_class=(
                        PeriodClass.V1_CANONICAL
                        if seg.start >= canonical_start
                        else PeriodClass.ARCHIVAL
                    ).value,
                    isin=seg.isin,
                    security_id=sid,
                    issuer_id=issuer_id,
                    evidence=[*seg.evidence, *(f"candidate:{c}" for c in seg.candidates)],
                )
            )
            session.flush()
    for (sid, isin), ranges in proven.items():
        for a, b in _union(ranges):
            have = session.scalars(
                select(IdentifierHistory).where(
                    IdentifierHistory.security_id == sid,
                    IdentifierHistory.id_type == "ISIN",
                    IdentifierHistory.value == isin,
                )
            ).all()
            if any(
                h.valid_from <= a and (h.valid_to is None or (b is not None and h.valid_to >= b))
                for h in have
            ):
                continue
            sm.add_identifier(sid, "ISIN", isin, a, b)
    session.flush()
    return IdentityRunResult(run, raw, spans, metrics, metrics_pre)


def _union(ranges: list[tuple[date, date | None]]) -> list[tuple[date, date | None]]:
    out: list[tuple[date, date | None]] = []
    for a, b in sorted(ranges, key=lambda r: r[0]):
        if out and (out[-1][1] is None or out[-1][1] >= a):
            pa, pb = out[-1]
            out[-1] = (pa, None if pb is None or b is None else max(pb, b))
        else:
            out.append((a, b))
    return out


def latest_run(session: Session, build_id: str) -> IdentityResolutionRun | None:
    return session.scalars(
        select(IdentityResolutionRun)
        .where(IdentityResolutionRun.build_id == build_id)
        .order_by(IdentityResolutionRun.created_at.desc(), IdentityResolutionRun.run_id.desc())
    ).first()


def segment_at(
    session: Session, run_id: str, membership_id: int, as_of: date
) -> MembershipIdentitySegment | None:
    for s in session.scalars(
        select(MembershipIdentitySegment).where(
            MembershipIdentitySegment.run_id == run_id,
            MembershipIdentitySegment.membership_id == membership_id,
        )
    ):
        if s.segment_from <= as_of and (s.segment_to is None or as_of < s.segment_to):
            return s
    return None
