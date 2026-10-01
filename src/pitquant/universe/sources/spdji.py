"""S&P 500 membership sources (D-02).

* ``SPDJILicensedFileProvider`` — CANONICAL: official/licensed S&P DJI history, mapped
  to the normalized change-file layout below by a thin adapter.
* ``SPDJIAnnouncementReconstructionProvider`` — PROVISIONAL_RESEARCH_SOURCE: rebuilds
  history from a known constituent snapshot plus official S&P DJI announcements. Results
  that depend on it are never reported as a definitive backtest.

Wikipedia, Kaggle or community repositories are NOT accepted here; load them with
``CROSSCHECK_ONLY`` confidence and use ``events.cross_check`` for QA.

Normalized change file (CSV, UTF-8, one row per event)::

    event_id,effective_date,announced_at,action,ticker,new_ticker,identifier,reason
    E1,2015-07-01,2015-06-22T21:15:00+00:00,ADD,XYZ,,CUSIP:123456789,replaces ABC
    action ∈ {INITIAL, ADD, DELETE, TICKER_CHANGE}
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.orm import Session

from pitquant.core.errors import ProviderContractError
from pitquant.core.hashing import content_hash
from pitquant.data.archive import ArchiveStore, archive_document
from pitquant.universe.events import (
    EventSource,
    EventType,
    IndexEventRecord,
    MembershipSequenceError,
    SourceConfidence,
    SP500MembershipProvider,
)

INDEX = "SP500"
PARSER_VERSION = "spdji-normalized-1"
_ACTIONS = {
    "INITIAL": EventType.INITIAL_SNAPSHOT,
    "ADD": EventType.INDEX_ADD,
    "DELETE": EventType.INDEX_DELETE,
    "TICKER_CHANGE": EventType.TICKER_CHANGE,
}


def _dt(s: str) -> datetime | None:
    s = s.strip()
    if not s:
        return None
    d = datetime.fromisoformat(s)
    if d.tzinfo is None:
        raise ProviderContractError(f"announced_at {s!r} must carry a UTC offset")
    return d


def _key(identifier: str, ticker: str) -> str:
    if not identifier.strip():
        raise ProviderContractError(
            f"{ticker}: an identifier (CUSIP/ISIN/permanent id) is required"
        )
    return identifier.strip()


def parse_normalized_change_file(data: bytes, index_code: str = INDEX) -> list[IndexEventRecord]:
    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
    out: list[IndexEventRecord] = []
    for r in rows:
        action = r["action"].strip().upper()
        if action not in _ACTIONS:
            raise ProviderContractError(f"{r['event_id']}: unknown action {action}")
        if action != "TICKER_CHANGE" and not r.get("reason", "").strip() and action != "INITIAL":
            raise ProviderContractError(f"{r['event_id']}: every entry/exit needs a cause")
        out.append(
            IndexEventRecord(
                index_code=index_code,
                event_type=_ACTIONS[action],
                effective_date=date.fromisoformat(r["effective_date"].strip()),
                source_event_id=r["event_id"].strip(),
                security_key=_key(r["identifier"], r["ticker"]),
                ticker=r["ticker"].strip().upper() or None,
                new_ticker=(r.get("new_ticker") or "").strip().upper() or None,
                identifier=r["identifier"].strip(),
                announced_at=_dt(r.get("announced_at", "")),
                reason=(r.get("reason") or "").strip() or None,
            )
        )
    return out


@dataclass
class SPDJILicensedFileProvider(SP500MembershipProvider):
    """CANONICAL source: the licensed S&P DJI history file (already in normalized layout)."""

    data: bytes
    source_identifier: str
    store: ArchiveStore

    @property
    def membership_source(self) -> str:
        return "SPDJI_LICENSED"

    @property
    def confidence(self) -> SourceConfidence:
        return SourceConfidence.CANONICAL

    def load(self, session: Session, index_code: str = INDEX) -> EventSource:
        arch = archive_document(
            session,
            self.store,
            provider=self.membership_source,
            source_identifier=self.source_identifier,
            data=self.data,
            mime_type="text/csv",
            parser_version=PARSER_VERSION,
        )
        return EventSource(
            self.membership_source,
            self.confidence,
            parse_normalized_change_file(self.data, index_code),
            arch.sha256,
            arch.archive_id,
        )


@dataclass(frozen=True)
class Announcement:
    announcement_id: str
    announced_at: datetime
    effective_date: date
    action: str  # ADD | DELETE
    ticker: str
    identifier: str
    reason: str
    source_url: str


def parse_announcements(data: bytes) -> list[Announcement]:
    out = []
    for r in csv.DictReader(io.StringIO(data.decode("utf-8"))):
        ann = _dt(r["announced_at"])
        if ann is None:
            raise ProviderContractError(f"{r['announcement_id']}: announced_at required")
        if not r["source_url"].strip():
            raise ProviderContractError(f"{r['announcement_id']}: official source required")
        out.append(
            Announcement(
                r["announcement_id"].strip(),
                ann,
                date.fromisoformat(r["effective_date"].strip()),
                r["action"].strip().upper(),
                r["ticker"].strip().upper(),
                r["identifier"].strip(),
                r["reason"].strip(),
                r["source_url"].strip(),
            )
        )
    return out


def ticker_observations(
    snapshot_date: date,
    snapshot: Sequence[tuple[str, str]],
    announcements: Sequence[Announcement],
) -> tuple[tuple[str, str, date], ...]:
    """Tickers actually stated by a source on a date: the snapshot (on its date) and each
    announcement (on the day it was announced)."""
    obs = {ident: (tick, snapshot_date) for tick, ident in snapshot}
    for a in sorted(announcements, key=lambda x: x.announced_at, reverse=True):
        d = a.announced_at.date()
        if a.identifier not in obs or d < obs[a.identifier][1]:
            obs[a.identifier] = (a.ticker, d)
    return tuple(sorted((k, t, d) for k, (t, d) in obs.items()))


def reconstruct_from_snapshot(
    snapshot_date: date,
    snapshot: Sequence[tuple[str, str]],  # (ticker, identifier) members ON snapshot_date
    announcements: Sequence[Announcement],
    coverage_start: date,
    index_code: str = INDEX,
) -> list[IndexEventRecord]:
    """Walk announcements backwards from the snapshot to ``coverage_start`` to obtain the
    initial membership, then emit the announcements forward as events.

    Fails loudly on any inconsistency (deleting a non-member, adding a member) instead of
    silently patching the history.
    """
    members = {ident: tick for tick, ident in snapshot}
    if len(members) != len(snapshot):
        raise MembershipSequenceError("duplicate identifiers in snapshot")
    in_range = sorted(
        (a for a in announcements if a.effective_date > coverage_start),
        key=lambda a: (a.effective_date, a.action != "DELETE", a.announcement_id),
    )
    for a in reversed([a for a in in_range if a.effective_date <= snapshot_date]):
        if a.action == "ADD":
            if a.identifier not in members:
                raise MembershipSequenceError(
                    f"{a.announcement_id}: undoing ADD of non-member {a.ticker}"
                )
            del members[a.identifier]
        elif a.action == "DELETE":
            if a.identifier in members:
                raise MembershipSequenceError(
                    f"{a.announcement_id}: undoing DELETE of member {a.ticker}"
                )
            members[a.identifier] = a.ticker
        else:
            raise ProviderContractError(f"{a.announcement_id}: unsupported action {a.action}")
    # Membership at coverage_start is derived, but neither the ticker nor the identity at
    # that date is observed: the snapshot's (modern) ticker is NOT projected backwards and
    # the interval stays IDENTITY_UNRESOLVED until a dated official source proves it.
    events = [
        IndexEventRecord(
            index_code,
            EventType.INITIAL_SNAPSHOT,
            coverage_start,
            f"initial:{ident}",
            ident,
            None,
            identifier=ident,
            reason=(
                f"derived from snapshot {snapshot_date} by reversing announcements; "
                f"identifier {ident} observed later ({tick}), identity at {coverage_start} "
                "not proven"
            ),
            identity_resolved=False,
        )
        for ident, tick in sorted(members.items())
    ]
    for a in in_range:
        events.append(
            IndexEventRecord(
                index_code,
                EventType.INDEX_ADD if a.action == "ADD" else EventType.INDEX_DELETE,
                a.effective_date,
                a.announcement_id,
                a.identifier,
                a.ticker,
                identifier=a.identifier,
                announced_at=a.announced_at,
                reason=f"{a.reason} [{a.source_url}]",
            )
        )
    return events


@dataclass
class SPDJIAnnouncementReconstructionProvider(SP500MembershipProvider):
    """PROVISIONAL_RESEARCH_SOURCE — never the basis of a definitive backtest."""

    snapshot_date: date
    snapshot_csv: bytes  # ticker,identifier
    announcements_csv: bytes
    coverage_start: date
    store: ArchiveStore

    @property
    def membership_source(self) -> str:
        return "SPDJI_ANNOUNCEMENT_RECONSTRUCTION"

    @property
    def confidence(self) -> SourceConfidence:
        return SourceConfidence.PROVISIONAL_RESEARCH_SOURCE

    def load(self, session: Session, index_code: str = INDEX) -> EventSource:
        a1 = archive_document(
            session,
            self.store,
            provider=self.membership_source,
            source_identifier=f"snapshot:{self.snapshot_date}",
            data=self.snapshot_csv,
            mime_type="text/csv",
            parser_version=PARSER_VERSION,
        )
        a2 = archive_document(
            session,
            self.store,
            provider=self.membership_source,
            source_identifier="announcements",
            data=self.announcements_csv,
            mime_type="text/csv",
            parser_version=PARSER_VERSION,
        )
        snap = [
            (r["ticker"].strip().upper(), r["identifier"].strip())
            for r in csv.DictReader(io.StringIO(self.snapshot_csv.decode("utf-8")))
        ]
        anns = parse_announcements(self.announcements_csv)
        events = reconstruct_from_snapshot(
            self.snapshot_date, snap, anns, self.coverage_start, index_code
        )
        return EventSource(
            self.membership_source,
            self.confidence,
            events,
            content_hash([a1.sha256, a2.sha256]),
            a2.archive_id,
            ticker_observations=ticker_observations(self.snapshot_date, snap, anns),
        )
