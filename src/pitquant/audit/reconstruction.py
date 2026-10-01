"""Auditable point-in-time reconstruction (D-01..D-03 completion criterion).

For a historical instant T and a pinned ``DataVersion`` the report states:
1. which securities were really in the universe,
2. which ticker each one had at T,
3. which fundamentals were really published at T,
4. the filing/event each datum comes from,
5. when it became available,
and carries a hash. Re-running with the same DataVersion reproduces the same hash (7);
later filings, restatements or provider corrections do not alter it (6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.core.hashing import content_hash
from pitquant.core.timeutils import require_aware, utc_now
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.data.point_in_time.engine import facts_as_of
from pitquant.db.models import IndexEvent, MembershipBuild
from pitquant.security_master.service import SecurityMaster
from pitquant.universe.index_membership import IndexUniverse


@dataclass(frozen=True)
class DataVersion:
    """Pins the system's knowledge: rows ingested after ``ingested_before`` and membership
    builds other than ``membership_builds`` are invisible to the reconstruction."""

    ingested_before: datetime
    membership_builds: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ingested_before": self.ingested_before,
            "membership_builds": dict(sorted(self.membership_builds.items())),
        }


def current_data_version(session: Session, index_codes: list[str]) -> DataVersion:
    u = IndexUniverse(session)
    return DataVersion(utc_now(), {c: u.active_build(c).build_id for c in index_codes})


def reconstruct(
    session: Session,
    as_of: datetime,
    index_code: str,
    exchange: str,
    data_version: DataVersion,
    concepts: list[str] | None = None,
) -> dict[str, Any]:
    as_of = require_aware(as_of, "as_of")
    cal = get_calendar(exchange)
    local_day: date = pd.Timestamp(as_of).tz_convert(cal.tz).date()
    build_id = data_version.membership_builds[index_code]
    build = session.get_one(MembershipBuild, build_id)
    if build.built_at > data_version.ingested_before:
        raise ValueError("pinned build is newer than the data_version cutoff")
    sm = SecurityMaster(session)
    members = []
    fundamentals: dict[str, list[dict[str, Any]]] = {}
    for m in IndexUniverse(session).universe(index_code, local_day, build_id):
        ev = session.get_one(IndexEvent, m.source_event_id)
        members.append(
            {
                "security_id": m.security_id,
                "ticker_at_T": sm.ticker_as_of(m.security_id, local_day),
                "member_since": m.effective_from,
                "entry_event": {
                    "event_id": ev.event_id,
                    "type": ev.event_type,
                    "source_event_id": ev.source_event_id,
                    "announced_at": ev.announced_at,
                    "reason": ev.reason,
                },
            }
        )
        facts = facts_as_of(
            session, m.security_id, as_of, concepts, ingested_before=data_version.ingested_before
        )
        fundamentals[m.security_id] = sorted(
            (
                {
                    "taxonomy": k.taxonomy,
                    "concept": k.concept,
                    "unit": k.unit,
                    "period_start": k.period_start,
                    "period_end": k.period_end,
                    "value": f.value,
                    "accession_number": f.accession_number,
                    "form": f.form,
                    "filed_date": f.filed_date,
                    "accepted_at": f.accepted_at,
                    "available_at": f.available_at,
                    "is_amendment": f.is_amendment,
                    "source_document": f.source_document,
                    "fact_id": f.fact_id,
                }
                for k, f in facts.items()
            ),
            key=lambda r: (r["concept"], r["period_end"], str(r["period_start"]), r["unit"]),
        )
    body = {
        "as_of": as_of,
        "index_code": index_code,
        "data_version": data_version.as_dict(),
        "membership_build": {
            "build_id": build.build_id,
            "source": build.membership_source,
            "confidence": build.source_confidence,
            "raw_source_hash": build.raw_source_hash,
            "events_hash": build.events_hash,
        },
        "members": sorted(members, key=lambda r: str(r["security_id"])),
        "fundamentals": fundamentals,
    }
    return {**body, "report_hash": content_hash(body)}


def latest_build_ids(session: Session, index_code: str) -> list[str]:
    return list(
        session.scalars(
            select(MembershipBuild.build_id)
            .where(MembershipBuild.index_code == index_code)
            .order_by(MembershipBuild.built_at)
        )
    )
