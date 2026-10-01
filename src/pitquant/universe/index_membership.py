"""Point-in-time index universes (ADR-0007, ADR-0013).

``universe(index, as_of)`` reads the intervals of ONE membership build (the active one by
default, or a pinned ``build_id`` for reproducibility) and never exposes information about
a member's future exit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from pitquant.core.errors import PITQuantError
from pitquant.core.timeutils import require_aware
from pitquant.db.models import IndexEvent, IndexMembership, MembershipBuild


class NoMembershipBuildError(PITQuantError, LookupError):
    """No successful membership build exists for the index."""


@dataclass(frozen=True)
class UniverseMember:
    security_id: str
    index_code: str
    effective_from: date
    inclusion_reason: str | None
    source_event_id: str
    source_confidence: str
    # exclusion fields intentionally absent: they are future information as of as_of.


@dataclass(frozen=True)
class AnnouncedChange:
    """A change already ANNOUNCED at as_of but not yet EFFECTIVE (for event-driven use)."""

    event_type: str
    security_id: str | None
    ticker: str | None
    announced_at: datetime
    effective_date: date


class IndexUniverse:
    def __init__(self, session: Session) -> None:
        self.s = session

    def active_build(self, index_code: str) -> MembershipBuild:
        b = self.s.scalars(
            select(MembershipBuild)
            .where(MembershipBuild.index_code == index_code, MembershipBuild.status == "ok")
            .order_by(MembershipBuild.built_at.desc(), MembershipBuild.build_id.desc())
        ).first()
        if b is None:
            raise NoMembershipBuildError(f"no successful membership build for {index_code}")
        return b

    def _build_id(self, index_code: str, build_id: str | None) -> str:
        if build_id is None:
            return self.active_build(index_code).build_id
        b = self.s.get(MembershipBuild, build_id)
        if b is None or b.index_code != index_code or b.status != "ok":
            raise NoMembershipBuildError(f"build {build_id} not usable for {index_code}")
        return build_id

    def universe(
        self, index_code: str, as_of: date, build_id: str | None = None
    ) -> list[UniverseMember]:
        """Members effective at ``as_of``: effective_from <= as_of < effective_to."""
        bid = self._build_id(index_code, build_id)
        rows = self.s.scalars(
            select(IndexMembership)
            .where(
                IndexMembership.build_id == bid,
                IndexMembership.index_code == index_code,
                IndexMembership.effective_from <= as_of,
                or_(IndexMembership.effective_to.is_(None), IndexMembership.effective_to > as_of),
            )
            .order_by(IndexMembership.security_id)
        ).all()
        return [
            UniverseMember(
                security_id=r.security_id,
                index_code=r.index_code,
                effective_from=r.effective_from,
                inclusion_reason=r.inclusion_reason,
                source_event_id=r.source_event_id,
                source_confidence=r.source_confidence,
            )
            for r in rows
        ]

    def universe_ids(self, index_code: str, as_of: date, build_id: str | None = None) -> list[str]:
        return [m.security_id for m in self.universe(index_code, as_of, build_id)]

    def announced_changes(
        self, index_code: str, as_of: datetime, build_id: str | None = None
    ) -> list[AnnouncedChange]:
        """Events known at ``as_of`` (announced_at <= as_of) whose effective date is later."""
        as_of = require_aware(as_of, "as_of")
        b = self.s.get_one(MembershipBuild, self._build_id(index_code, build_id))
        rows = self.s.scalars(
            select(IndexEvent).where(
                IndexEvent.index_code == index_code,
                IndexEvent.membership_source == b.membership_source,
                IndexEvent.raw_source_hash == b.raw_source_hash,
                IndexEvent.announced_at.is_not(None),
                IndexEvent.announced_at <= as_of,
                IndexEvent.effective_date > as_of.date(),
            )
        ).all()
        return [
            AnnouncedChange(r.event_type, r.security_id, r.ticker, r.announced_at, r.effective_date)
            for r in rows
            if r.announced_at is not None
        ]

    def source_status(self, index_code: str, build_id: str | None = None) -> str:
        """CANONICAL / PROVISIONAL_RESEARCH_SOURCE / SYNTHETIC of the build a run relies on.
        Backtests over a non-CANONICAL universe must be labelled non-definitive."""
        return self.s.get_one(
            MembershipBuild, self._build_id(index_code, build_id)
        ).source_confidence
