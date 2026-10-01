"""Point-in-time index universes (ADR-0007, ADR-0013).

``universe(index, as_of)`` reads the intervals of ONE membership build (the active one by
default, or a pinned ``build_id`` for reproducibility) and never exposes information about
a member's future exit.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from pitquant.core.errors import PITQuantError
from pitquant.core.timeutils import require_aware
from pitquant.db.models import IndexEvent, IndexMembership, MembershipBuild


class NoMembershipBuildError(PITQuantError, LookupError):
    """No successful membership build exists for the index."""


class IdentityUnresolvedError(PITQuantError):
    """A backtest universe contains members whose security identity is not proven."""


class ArchivalPeriodError(PITQuantError):
    """The date is before the V1 canonical period (ARCHIVAL / NON_CANONICAL_FOR_V1)."""


@dataclass(frozen=True)
class UniverseMember:
    security_id: str
    index_code: str
    effective_from: date
    inclusion_reason: str | None
    source_event_id: str
    source_confidence: str
    identity_status: str = "RESOLVED"
    membership_id: int | None = None
    isin: str | None = None
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
                identity_status=r.identity_status,
                membership_id=r.id,
            )
            for r in rows
        ]

    def backtest_universe(
        self,
        index_code: str,
        as_of: date,
        build_id: str | None = None,
        *,
        canonical_start: date | None = None,
    ) -> list[UniverseMember]:
        """Universe for a backtest observation. Fails closed: if ANY member's identity is
        unresolved the date cannot be backtested (dropping members silently would be a
        survivorship-style bias).

        A code-space member (``IDENTITY_UNRESOLVED`` in the build) is accepted only through
        the latest identity-resolution run of that build (ADR-0020): its segment at
        ``as_of`` must be EXACT_OFFICIAL_IDENTIFIER or MULTI_SOURCE_CONFIRMED, and the
        returned ``security_id`` is the PROVEN security (ISIN owner), not the code lineage.
        ``canonical_start``: dates before it are ARCHIVAL / NON_CANONICAL_FOR_V1.
        """
        from pitquant.security_master.identity import BACKTESTABLE, IdentityResolutionStatus
        from pitquant.security_master.identity_store import latest_run, segment_at

        if canonical_start is not None and as_of < canonical_start:
            raise ArchivalPeriodError(
                f"{index_code}@{as_of}: before the V1 canonical period ({canonical_start})"
            )
        bid = self._build_id(index_code, build_id)
        members = self.universe(index_code, as_of, bid)
        run = latest_run(self.s, bid)
        out: list[UniverseMember] = []
        bad: list[str] = []
        for m in members:
            if m.identity_status == "RESOLVED":
                out.append(m)
                continue
            seg = (
                segment_at(self.s, run.run_id, m.membership_id, as_of)
                if run is not None and m.membership_id is not None
                else None
            )
            ok = (
                seg is not None
                and seg.security_id is not None
                and IdentityResolutionStatus(seg.status) in BACKTESTABLE
            )
            if not ok or seg is None or seg.security_id is None:
                bad.append(f"{m.security_id}({seg.status if seg else 'no segment'})")
                continue
            out.append(
                replace(m, security_id=seg.security_id, identity_status=seg.status, isin=seg.isin)
            )
        if bad:
            raise IdentityUnresolvedError(
                f"{index_code}@{as_of}: {len(bad)} member(s) without a proven identity "
                f"(e.g. {bad[0]}); resolve identity before backtesting"
            )
        if len({m.security_id for m in out}) != len(out):
            raise IdentityUnresolvedError(f"{index_code}@{as_of}: two members map to one security")
        return out

    def is_eligible_for_final_validation(self, build_id: str) -> bool:
        return bool(self.s.get_one(MembershipBuild, build_id).eligible_for_final_model_validation)

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
