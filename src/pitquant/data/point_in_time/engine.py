"""Point-in-time core: the guard and bitemporal as-of resolution (ADR-0001).

Two independent layers protect every computation:

1. **Filtering** (`as_of_view`, `facts_as_of`): only records with ``available_at <= as_of``
   are ever returned to feature engines.
2. **Assertion** (`PITGuard`): when a snapshot is frozen, every input's ``available_at`` is
   re-checked. If filtering has a bug, the pipeline fails instead of silently leaking.
"""

from __future__ import annotations

from collections.abc import Hashable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, NamedTuple, Protocol

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from pitquant.core.errors import LookAheadError
from pitquant.core.timeutils import require_aware
from pitquant.db.models import FundamentalFact, Security


class HasAvailability(Protocol):
    @property
    def available_at(self) -> datetime: ...


@dataclass(frozen=True)
class PITRecord:
    """A generic bitemporal record."""

    key: Hashable  # e.g. (security_id, concept)
    period_end: date
    available_at: datetime
    value: Any
    revision_id: int = 0
    source_ref: str | None = None

    def __post_init__(self) -> None:
        require_aware(self.available_at, "available_at")


def as_of_view[R: PITRecord](
    records: Iterable[R], as_of: datetime
) -> dict[tuple[Hashable, date], R]:
    """For each (key, period_end) keep the latest revision known at ``as_of``.

    Ordering is by ``available_at`` then ``revision_id``: a revision published later
    supersedes an earlier one; a revision not yet published is invisible.
    """
    as_of = require_aware(as_of, "as_of")
    best: dict[tuple[Hashable, date], R] = {}
    for r in records:
        if require_aware(r.available_at) > as_of:
            continue
        k = (r.key, r.period_end)
        cur = best.get(k)
        if cur is None or (r.available_at, r.revision_id) > (cur.available_at, cur.revision_id):
            best[k] = r
    return best


@dataclass
class PITGuard:
    """Asserts that no input of a computation was unknowable at ``as_of``."""

    as_of: datetime
    context: str = ""
    _checked: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.as_of = require_aware(self.as_of, "as_of")

    def check(self, name: str, available_at: datetime) -> None:
        ts = require_aware(available_at, f"{name}.available_at")
        self._checked += 1
        if ts > self.as_of:
            raise LookAheadError(
                f"[{self.context}] '{name}' available_at={ts.isoformat()} "
                f"> as_of={self.as_of.isoformat()}"
            )

    def check_all(self, items: Iterable[tuple[str, datetime]]) -> None:
        offenders: list[str] = []
        for name, ts in items:
            ts = require_aware(ts, f"{name}.available_at")
            self._checked += 1
            if ts > self.as_of:
                offenders.append(f"{name}@{ts.isoformat()}")
        if offenders:
            raise LookAheadError(
                f"[{self.context}] {len(offenders)} input(s) after as_of="
                f"{self.as_of.isoformat()}: {', '.join(sorted(offenders)[:20])}"
            )

    @property
    def n_checked(self) -> int:
        return self._checked


class FactKey(NamedTuple):
    """Identity of an economic fact. Different filings reporting it are VERSIONS of it."""

    concept: str
    period_start: date | None
    period_end: date
    unit: str
    taxonomy: str


def _version_order(f: FundamentalFact) -> tuple[datetime, datetime, int, str]:
    accepted = f.accepted_at or f.available_at
    return (f.available_at, accepted, f.revision_id, f.fact_id)


def facts_as_of(
    session: Session,
    security_id: str | None,
    as_of: datetime,
    concepts: Sequence[str] | None = None,
    *,
    issuer_id: str | None = None,
    ingested_before: datetime | None = None,
) -> dict[FactKey, FundamentalFact]:
    """The version of each fact that was actually available at ``as_of``.

    A later filing (restatement, amendment, comparative column) is a NEW version with a
    later ``available_at``; it can never displace what a snapshot at ``as_of`` saw.
    ``ingested_before`` pins the system's own knowledge (data_version) so a reconstruction
    is reproducible even after new rows are ingested.

    Fundamentals belong to the ISSUER (ADR-0020): for a ``security_id`` the facts filed by
    its issuer (``securities.issuer_id``) are included; ``issuer_id`` queries an issuer
    directly.
    """
    as_of = require_aware(as_of, "as_of")
    if security_id is None and issuer_id is None:
        raise ValueError("facts_as_of needs a security_id or an issuer_id")
    if security_id is not None and issuer_id is None:
        sec = session.get(Security, security_id)
        issuer_id = sec.issuer_id if sec is not None else None
    subject = []
    if security_id is not None:
        subject.append(FundamentalFact.security_id == security_id)
    if issuer_id is not None:
        subject.append(FundamentalFact.issuer_id == issuer_id)
    stmt = select(FundamentalFact).where(
        or_(*subject),
        FundamentalFact.available_at <= as_of,
    )
    if concepts:
        stmt = stmt.where(FundamentalFact.concept.in_(list(concepts)))
    if ingested_before is not None:
        stmt = stmt.where(FundamentalFact.ingested_at <= require_aware(ingested_before))
    best: dict[FactKey, FundamentalFact] = {}
    for f in session.scalars(stmt):
        k = FactKey(f.concept, f.period_start, f.period_end, f.unit, f.taxonomy)
        cur = best.get(k)
        if cur is None or _version_order(f) > _version_order(cur):
            best[k] = f
    guard = PITGuard(as_of, context=f"facts_as_of:{security_id or issuer_id}")
    guard.check_all((f"{k.concept}:{k.period_end}", f.available_at) for k, f in best.items())
    return best


def latest_for_period(
    facts: dict[FactKey, FundamentalFact], concept: str, period_end: date
) -> FundamentalFact | None:
    """Convenience lookup ignoring period_start/unit when they are unambiguous."""
    hits = [f for k, f in facts.items() if k.concept == concept and k.period_end == period_end]
    if len(hits) > 1:
        raise ValueError(f"{concept}@{period_end} ambiguous: {len(hits)} facts (durations/units)")
    return hits[0] if hits else None
