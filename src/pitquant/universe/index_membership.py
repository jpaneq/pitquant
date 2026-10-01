"""Point-in-time index universes (ADR-0007).

``universe(index, as_of)`` returns ONLY securities effectively in the index at ``as_of``
and never exposes information about their future exit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from pitquant.core.errors import OverlappingIntervalError
from pitquant.core.intervals import overlaps as _overlaps
from pitquant.core.timeutils import require_aware
from pitquant.db.models import IndexMembership


@dataclass(frozen=True)
class UniverseMember:
    security_id: str
    index_code: str
    inclusion_date: date
    inclusion_reason: str | None
    # exclusion fields intentionally absent: they are future information as of as_of.


@dataclass(frozen=True)
class UniverseExclusion:
    """A point-in-time universe filter decision, recorded with its reason (§93)."""

    security_id: str
    reason: str


class IndexUniverse:
    def __init__(self, session: Session) -> None:
        self.s = session

    def add_membership(
        self,
        *,
        security_id: str,
        index_code: str,
        inclusion_date: date,
        exclusion_date: date | None = None,
        inclusion_reason: str | None = None,
        exclusion_reason: str | None = None,
        announced_at: datetime | None = None,
        ticker_at_inclusion: str | None = None,
        source_id: int | None = None,
    ) -> IndexMembership:
        if exclusion_date is not None and exclusion_date <= inclusion_date:
            raise OverlappingIntervalError("exclusion_date must be after inclusion_date")
        if announced_at is not None:
            require_aware(announced_at, "announced_at")
        existing = self.s.scalars(
            select(IndexMembership).where(
                IndexMembership.security_id == security_id,
                IndexMembership.index_code == index_code,
            )
        ).all()
        for row in existing:
            if _overlaps(row.inclusion_date, row.exclusion_date, inclusion_date, exclusion_date):
                raise OverlappingIntervalError(
                    f"{security_id} already in {index_code} during "
                    f"[{row.inclusion_date}, {row.exclusion_date})"
                )
        m = IndexMembership(
            security_id=security_id,
            index_code=index_code,
            inclusion_date=inclusion_date,
            exclusion_date=exclusion_date,
            inclusion_reason=inclusion_reason,
            exclusion_reason=exclusion_reason,
            announced_at=announced_at,
            ticker_at_inclusion=ticker_at_inclusion,
            source_id=source_id,
        )
        self.s.add(m)
        self.s.flush()
        return m

    def record_exclusion(
        self, security_id: str, index_code: str, exclusion_date: date, reason: str
    ) -> None:
        row = self.s.scalars(
            select(IndexMembership).where(
                IndexMembership.security_id == security_id,
                IndexMembership.index_code == index_code,
                IndexMembership.exclusion_date.is_(None),
            )
        ).one()
        if exclusion_date <= row.inclusion_date:
            raise OverlappingIntervalError("exclusion must be after inclusion")
        row.exclusion_date = exclusion_date
        row.exclusion_reason = reason
        self.s.flush()

    def universe(self, index_code: str, as_of: date) -> list[UniverseMember]:
        """Members effective at ``as_of``: inclusion_date <= as_of < exclusion_date."""
        rows = self.s.scalars(
            select(IndexMembership)
            .where(
                IndexMembership.index_code == index_code,
                IndexMembership.inclusion_date <= as_of,
                or_(
                    IndexMembership.exclusion_date.is_(None),
                    IndexMembership.exclusion_date > as_of,
                ),
            )
            .order_by(IndexMembership.security_id)
        ).all()
        return [
            UniverseMember(
                security_id=r.security_id,
                index_code=r.index_code,
                inclusion_date=r.inclusion_date,
                inclusion_reason=r.inclusion_reason,
            )
            for r in rows
        ]

    def universe_ids(self, index_code: str, as_of: date) -> list[str]:
        return [m.security_id for m in self.universe(index_code, as_of)]
