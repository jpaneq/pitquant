"""Event-sourced index membership (D-02, D-03, ADR-0013).

Membership is NEVER loaded as intervals from a provider. Providers emit an event stream
(adds, deletes, ticker changes, reviews); this module validates the stream and derives the
intervals into an immutable ``MembershipBuild``. Every interval points to the event that
caused its start and its end.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.core.errors import PITQuantError, ProviderContractError
from pitquant.core.hashing import content_hash
from pitquant.core.timeutils import require_aware
from pitquant.db.models import IndexEvent, IndexMembership, MembershipBuild, ProviderKey
from pitquant.security_master.service import SecurityMaster


class EventType(StrEnum):
    INDEX_ADD = "INDEX_ADD"
    INDEX_DELETE = "INDEX_DELETE"
    TICKER_CHANGE = "TICKER_CHANGE"
    ORDINARY_REVIEW = "ORDINARY_REVIEW"
    EXTRAORDINARY_REVIEW = "EXTRAORDINARY_REVIEW"
    INITIAL_SNAPSHOT = "INITIAL_SNAPSHOT"


class SourceConfidence(StrEnum):
    CANONICAL = "CANONICAL"  # official / licensed history
    PROVISIONAL_RESEARCH_SOURCE = "PROVISIONAL_RESEARCH_SOURCE"  # reconstruction, unverified
    SYNTHETIC = "SYNTHETIC"
    CROSSCHECK_ONLY = "CROSSCHECK_ONLY"  # Wikipedia, Kaggle, community repos: QA only


class IdentityStatus(StrEnum):
    """Kept separate from membership: a source can prove that "the company quoted as XYZ"
    was a member while not proving WHICH security that was. Same ticker != same security."""

    RESOLVED = "RESOLVED"
    IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"


BUILDABLE = {
    SourceConfidence.CANONICAL,
    SourceConfidence.PROVISIONAL_RESEARCH_SOURCE,
    SourceConfidence.SYNTHETIC,
}

MEMBERSHIP_EVENTS = {EventType.INDEX_ADD, EventType.INDEX_DELETE, EventType.INITIAL_SNAPSHOT}


class MembershipSequenceError(PITQuantError):
    """The event stream is internally inconsistent (e.g. deleting a non-member)."""


class UnresolvedSourceEventError(PITQuantError):
    """A source row cannot be classified reliably and no authoritative resolution exists."""


@dataclass(frozen=True)
class IndexEventRecord:
    """Provider-neutral event. ``security_key`` identifies the security within the source
    (provider key, ISIN, or a lineage key assigned by the parser)."""

    index_code: str
    event_type: EventType
    effective_date: date
    source_event_id: str
    security_key: str | None = None
    ticker: str | None = None
    new_ticker: str | None = None
    identifier: str | None = None
    announced_at: datetime | None = None
    reason: str | None = None
    parent_source_event_id: str | None = None
    # False when the source proves membership but not the security's identity (no ISIN /
    # CUSIP / permanent id). Such intervals are built but flagged IDENTITY_UNRESOLVED.
    identity_resolved: bool = True

    @property
    def identity_status(self) -> IdentityStatus:
        return (
            IdentityStatus.RESOLVED
            if self.identity_resolved
            else IdentityStatus.IDENTITY_UNRESOLVED
        )

    def __post_init__(self) -> None:
        if self.announced_at is not None:
            require_aware(self.announced_at, "announced_at")
        if self.event_type in MEMBERSHIP_EVENTS and not self.security_key:
            raise ProviderContractError(
                f"{self.source_event_id}: membership event without security"
            )
        if self.event_type is EventType.TICKER_CHANGE and not (self.ticker and self.new_ticker):
            raise ProviderContractError(f"{self.source_event_id}: ticker change needs old and new")


@dataclass(frozen=True)
class EventSource:
    """What a provider hands over: events + the exact source bytes they came from."""

    membership_source: str
    confidence: SourceConfidence
    events: Sequence[IndexEventRecord]
    raw_source_hash: str  # SHA-256 of the archived source document(s)
    archive_id: str | None = None
    warnings: tuple[str, ...] = ()
    # (security_key, ticker, observed_on): tickers the source states on a date for keys
    # whose events carry no ticker (e.g. a constituent snapshot). Registered from that date
    # only — never projected backwards.
    ticker_observations: tuple[tuple[str, str, date], ...] = ()


class IndexEventProvider(ABC):
    @property
    @abstractmethod
    def membership_source(self) -> str: ...

    @property
    @abstractmethod
    def confidence(self) -> SourceConfidence: ...

    @abstractmethod
    def load(self, session: Session, index_code: str) -> EventSource:
        """Fetch/parse, archive the raw source, and return the event stream."""


class SP500MembershipProvider(IndexEventProvider, ABC):
    """Marker interface: any S&P 500 history source (licensed or reconstructed)."""


# ───────────────────────────── persistence ─────────────────────────────


@dataclass
class BuildReport:
    build_id: str
    status: str
    n_events: int
    n_intervals: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    size_by_event_date: dict[str, int] = field(default_factory=dict)
    n_identity_unresolved: int = 0
    eligible_for_final_model_validation: bool = False


def events_hash(events: Sequence[IndexEventRecord]) -> str:
    return content_hash([e.__dict__ for e in sorted(events, key=lambda e: e.source_event_id)])


def persist_events(
    session: Session, src: EventSource, security_ids: dict[str, str]
) -> dict[str, IndexEvent]:
    """Append events (idempotent on (source, source_event_id, raw_source_hash))."""
    out: dict[str, IndexEvent] = {}
    parents: dict[str, str] = {}
    ordered = sorted(
        src.events, key=lambda e: (e.parent_source_event_id is not None, e.effective_date)
    )
    for e in ordered:
        existing = session.scalars(
            select(IndexEvent).where(
                IndexEvent.membership_source == src.membership_source,
                IndexEvent.source_event_id == e.source_event_id,
                IndexEvent.raw_source_hash == src.raw_source_hash,
            )
        ).first()
        if existing is None:
            existing = IndexEvent(
                index_code=e.index_code,
                event_type=e.event_type.value,
                parent_event_id=parents.get(e.parent_source_event_id or ""),
                security_id=security_ids.get(e.security_key or ""),
                ticker=e.ticker,
                new_ticker=e.new_ticker,
                identifier=e.identifier,
                effective_date=e.effective_date,
                announced_at=e.announced_at,
                reason=e.reason,
                membership_source=src.membership_source,
                source_event_id=e.source_event_id,
                source_confidence=src.confidence.value,
                raw_source_hash=src.raw_source_hash,
                archive_id=src.archive_id,
                identity_status=e.identity_status.value,
            )
            session.add(existing)
            session.flush()
        parents[e.source_event_id] = existing.event_id
        out[e.source_event_id] = existing
    return out


_ORDER = {
    EventType.ORDINARY_REVIEW: 0,
    EventType.EXTRAORDINARY_REVIEW: 0,
    EventType.INITIAL_SNAPSHOT: 1,
    EventType.INDEX_DELETE: 2,  # deletions before additions on the same date
    EventType.TICKER_CHANGE: 3,
    EventType.INDEX_ADD: 4,
}


def build_membership(
    session: Session,
    src: EventSource,
    security_ids: dict[str, str],
    *,
    expected_size: tuple[int, int] | None = None,
    allow_failed: bool = False,
) -> BuildReport:
    """Validate the event stream and derive an immutable membership build.

    Checks: no add of a current member, no delete of a non-member, no ticker change for
    an unknown member, every interval starts and ends with a sourced event, and (when
    configured) the index size stays within ``expected_size`` after every event date.
    """
    if src.confidence not in BUILDABLE:
        raise ProviderContractError(
            f"{src.membership_source} is {src.confidence}: usable only for cross-checks/QA"
        )
    missing = {
        e.security_key for e in src.events if e.security_key and e.security_key not in security_ids
    }
    if missing:
        raise ProviderContractError(
            f"events reference unregistered securities: {sorted(missing)[:5]}"
        )
    stored = persist_events(session, src, security_ids)
    events = sorted(
        src.events, key=lambda e: (e.effective_date, _ORDER[e.event_type], e.source_event_id)
    )
    index_codes = {e.index_code for e in events}
    if len(index_codes) != 1:
        raise MembershipSequenceError(f"one index per build, got {index_codes}")
    index_code = index_codes.pop()

    build = MembershipBuild(
        index_code=index_code,
        membership_source=src.membership_source,
        source_confidence=src.confidence.value,
        raw_source_hash=src.raw_source_hash,
        events_hash=events_hash(src.events),
        n_events=len(src.events),
        status="pending",
        report={},
    )
    errors: list[str] = []
    warnings: list[str] = []
    open_: dict[str, tuple[IndexEventRecord, str | None]] = {}  # sec_id -> (start event, ticker)
    intervals: list[dict[str, Any]] = []
    sizes: dict[str, int] = {}
    by_date: dict[date, list[IndexEventRecord]] = defaultdict(list)
    for e in events:
        by_date[e.effective_date].append(e)

    for d in sorted(by_date):
        for e in by_date[d]:
            sid = security_ids.get(e.security_key or "")
            if e.event_type in MEMBERSHIP_EVENTS and sid is None:
                errors.append(f"{e.source_event_id}: no security for {e.security_key}")
                continue
            if e.event_type in (EventType.INDEX_ADD, EventType.INITIAL_SNAPSHOT):
                assert sid is not None  # narrowed above; kept for the type checker
                if sid in open_:
                    errors.append(
                        f"{e.source_event_id}: {e.ticker} added on {d} but already a member"
                    )
                    continue
                open_[sid] = (e, e.ticker)
            elif e.event_type is EventType.INDEX_DELETE:
                assert sid is not None  # narrowed above; kept for the type checker
                if sid not in open_:
                    errors.append(
                        f"{e.source_event_id}: {e.ticker} deleted on {d} but not a member"
                    )
                    continue
                start, ticker = open_.pop(sid)
                if d <= start.effective_date:
                    errors.append(f"{e.source_event_id}: empty interval for {ticker} on {d}")
                    continue
                intervals.append({"sid": sid, "start": start, "end": e, "ticker": ticker})
            elif e.event_type is EventType.TICKER_CHANGE:
                target = sid or next((s for s, (_, t) in open_.items() if t == e.ticker), None)
                if target is None or target not in open_:
                    errors.append(
                        f"{e.source_event_id}: ticker change {e.ticker}->{e.new_ticker} "
                        "for a security that is not a current member"
                    )
                    continue
                start, _ = open_[target]
                open_[target] = (start, e.new_ticker)  # membership continues, ticker changes
        n = len(open_)
        sizes[d.isoformat()] = n
        if expected_size and not (expected_size[0] <= n <= expected_size[1]):
            errors.append(f"size {n} outside {expected_size} after events of {d}")

    for sid, (start, ticker) in open_.items():
        intervals.append({"sid": sid, "start": start, "end": None, "ticker": ticker})

    n_unresolved = sum(1 for iv in intervals if not iv["start"].identity_resolved)
    if n_unresolved:
        warnings.append(
            f"{n_unresolved} interval(s) IDENTITY_UNRESOLVED: membership known, security not "
            "proven — excluded from backtests until resolved"
        )
    build.status = "failed" if errors else "ok"
    build.eligible_for_final_model_validation = (
        not errors and src.confidence is SourceConfidence.CANONICAL and n_unresolved == 0
    )
    build.report = {
        "errors": errors[:200],
        "warnings": warnings,
        "n_intervals": len(intervals),
        "n_identity_unresolved": n_unresolved,
    }
    session.add(build)
    session.flush()
    if errors and not allow_failed:
        raise MembershipSequenceError(f"{len(errors)} error(s); first: {errors[0]}")
    if not errors:
        for iv in intervals:
            first: IndexEventRecord = iv["start"]
            end: IndexEventRecord | None = iv["end"]
            session.add(
                IndexMembership(
                    build_id=build.build_id,
                    security_id=iv["sid"],
                    index_code=index_code,
                    ticker_at_inclusion=first.ticker,
                    effective_from=first.effective_date,
                    effective_to=end.effective_date if end else None,
                    inclusion_reason=first.reason or first.event_type.value,
                    exclusion_reason=(end.reason or end.event_type.value) if end else None,
                    announced_at=first.announced_at,
                    membership_source=src.membership_source,
                    source_event_id=stored[first.source_event_id].event_id,
                    exclusion_event_id=stored[end.source_event_id].event_id if end else None,
                    source_confidence=src.confidence.value,
                    raw_source_hash=src.raw_source_hash,
                    identity_status=first.identity_status.value,
                )
            )
        session.flush()
    return BuildReport(
        build.build_id,
        build.status,
        len(events),
        len(intervals),
        errors,
        warnings,
        sizes,
        n_unresolved,
        build.eligible_for_final_model_validation,
    )


def apply_ticker_changes(
    session: Session, src: EventSource, security_ids: dict[str, str], exchange: str
) -> int:
    """Mirror TICKER_CHANGE events into ticker_history (same security_id, two rows)."""
    sm = SecurityMaster(session)
    n = 0
    for e in sorted(src.events, key=lambda x: x.effective_date):
        if e.event_type is not EventType.TICKER_CHANGE:
            continue
        day_before = e.effective_date - timedelta(days=1)
        sid = security_ids.get(e.security_key or "") or sm.resolve(
            e.ticker or "", exchange, day_before
        )
        if sm.ticker_as_of(sid, e.effective_date) == (e.new_ticker or "").upper():
            continue  # already applied (idempotent)
        sm.change_ticker(sid, exchange, e.new_ticker or "", e.effective_date)
        n += 1
    return n


def provider_key_map(session: Session, source_id: int) -> dict[str, str]:
    rows = session.scalars(select(ProviderKey).where(ProviderKey.source_id == source_id)).all()
    return {r.provider_key: r.security_id for r in rows}


# ───────────────────────────── QA cross-check ─────────────────────────────


@dataclass(frozen=True)
class Discrepancy:
    on: date
    only_in_canonical: frozenset[str]
    only_in_crosscheck: frozenset[str]


def cross_check(
    canonical: dict[date, set[str]], crosscheck: dict[date, set[str]]
) -> list[Discrepancy]:
    """Compare tickers per date against a CROSSCHECK_ONLY source (never ingested)."""
    out = []
    for d in sorted(set(canonical) & set(crosscheck)):
        a, b = canonical[d], crosscheck[d]
        if a != b:
            out.append(Discrepancy(d, frozenset(a - b), frozenset(b - a)))
    return out
