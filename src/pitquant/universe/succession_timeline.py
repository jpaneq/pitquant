"""Materialise legal securities from reconciliation lineages at a decision instant.

The graph may reconcile a continuous index slot with its final successor. Consumers must
receive the predecessor before a replacement, including multiple classes before a merger.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.core.errors import DataQualityError
from pitquant.core.timeutils import require_aware
from pitquant.db.models import SecuritySuccession

REPLACEMENTS = {"SECURITY_REPLACEMENT_SUCCESSOR", "SHARE_CLASS_CHANGE"}


class SuccessionTimeline:
    def __init__(self, session: Session) -> None:
        rows = list(
            session.scalars(
                select(SecuritySuccession).where(SecuritySuccession.membership_continuity.is_(True))
            )
        )
        same = {
            r.security_predecessor_id: r.security_successor_id
            for r in rows
            if r.event_type not in REPLACEMENTS
        }

        def canonical(sid: str) -> str:
            seen: set[str] = set()
            while sid in same:
                if sid in seen:
                    raise DataQualityError("cycle in same-security identity links")
                seen.add(sid)
                sid = same[sid]
            return sid

        self.incoming: dict[str, list[tuple[str, datetime | None, str]]] = {}
        for row in rows:
            if row.event_type in REPLACEMENTS:
                pred, succ = (
                    canonical(row.security_predecessor_id),
                    canonical(row.security_successor_id),
                )
                edge = (pred, row.effective_at, row.event_type)
                if edge not in self.incoming.setdefault(succ, []):
                    self.incoming[succ].append(edge)

    def at(self, members: frozenset[str], decision_at: datetime) -> frozenset[str]:
        require_aware(decision_at, "decision_at")

        def expand(sid: str, seen: frozenset[str]) -> set[str]:
            if sid in seen:
                raise DataQualityError("cycle in replacement lineage")
            edges = self.incoming.get(sid, [])
            if any(effective is None for _, effective, _ in edges):
                raise DataQualityError(f"replacement date unknown for {sid}")
            if len({effective for _, effective, _ in edges}) > 1:
                raise DataQualityError(f"conflicting replacement dates for {sid}")
            if len(edges) > 1 and any(kind != "SHARE_CLASS_CHANGE" for _, _, kind in edges):
                raise DataQualityError(
                    f"multiple predecessors without class-conversion proof for {sid}"
                )
            pending = [
                (pred, effective, kind)
                for pred, effective, kind in edges
                if effective is not None and decision_at < effective
            ]
            if not pending:
                return {sid}
            result: set[str] = set()
            for pred, _, _ in pending:
                result |= expand(pred, seen | {sid})
            return result

        return frozenset(s for member in members for s in expand(member, frozenset()))
