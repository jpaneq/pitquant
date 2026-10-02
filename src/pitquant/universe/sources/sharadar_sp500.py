"""SharadarSP500MembershipProvider — technical CANDIDATE for S&P 500 history (ADR-0021).

Not canonical: the licensed S&P DJI file stays the canonical target (D-02) until a later
ADR. Confidence is PROVISIONAL_RESEARCH_SOURCE; the candidate label is reported by
``candidate_status`` (``ADAPTER_CONTRACT_TESTED`` on fixtures, ``CANONICAL_CANDIDATE`` only
after the contract suite passes on REAL data).

Input: the SHARADAR SP500 table (date, action, ticker, name, contraticker, contraname,
note; actions ``current`` / ``historical`` / ``added`` / ``removed``) and TICKERS for
identity (permaticker, by ticker AND date: tickers are reused).

Reconstruction (same discipline as the BME history):
* the ``current`` rows anchor the membership on their date; walking the ``added`` /
  ``removed`` rows BACKWARDS gives the membership at ``coverage_start``; every step is
  checked (undoing an add must remove a member, undoing a removal must re-add a
  non-member) and the size must stay in ``expected_size``;
* every ``historical`` snapshot present in the payload must equal the reconstruction on its
  date (no survivorship: removed and delisted members stay in the history);
* a removal and an addition on the same date that resolve to the SAME permaticker are a
  TICKER_CHANGE, never a turnover;
* identity: permaticker from TICKERS; unresolvable → IDENTITY_UNRESOLVED (never guessed);
* the SP500 ``date`` is the EFFECTIVE date of the change (official docs: «the effective date
  of the change») and ``historical`` rows are «historical quarterly snapshots» (evidence in
  docs/ADAPTER_FIELD_EVIDENCE.md); the vendor's accuracy is still UNVERIFIED until
  cross-checked with official S&P DJI announcements (``cross_check_announcements`` fails
  closed).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy.orm import Session

from pitquant.core.errors import DataQualityError
from pitquant.core.hashing import content_hash
from pitquant.data.archive import sha256_hex
from pitquant.market.providers.sharadar import TickerMaster, parse_table
from pitquant.universe.events import (
    EventSource,
    EventType,
    IndexEventRecord,
    MembershipSequenceError,
    SourceConfidence,
    SP500MembershipProvider,
)

INDEX = "SP500"
SOURCE = "SHARADAR_SP500"


@dataclass(frozen=True)
class OfficialAnnouncement:
    """A dated change from an archived official S&P DJI announcement."""

    ticker: str
    action: str  # added | removed
    effective_date: date
    source_sha256: str


@dataclass
class SP500Reconstruction:
    anchor_date: date
    initial: frozenset[str]
    checked_historical_dates: list[date] = field(default_factory=list)
    ticker_changes: list[tuple[str, str, date]] = field(default_factory=list)
    unresolved_identity: list[str] = field(default_factory=list)


class SharadarSP500MembershipProvider(SP500MembershipProvider):
    def __init__(
        self,
        sp500_payload: bytes,
        tickers: TickerMaster,
        *,
        coverage_start: date,
        expected_size: tuple[int, int] = (495, 510),
        archive_id: str | None = None,
    ) -> None:
        self.payload = sp500_payload
        self.tickers = tickers
        self.coverage_start = coverage_start
        self.expected_size = expected_size
        self.archive_id = archive_id

    @property
    def membership_source(self) -> str:
        return SOURCE

    @property
    def confidence(self) -> SourceConfidence:
        return SourceConfidence.PROVISIONAL_RESEARCH_SOURCE

    def load(self, session: Session, index_code: str = INDEX) -> EventSource:
        src, _ = self.reconstruct(index_code)
        return src

    def _key(self, ticker: str, on: date, rec: SP500Reconstruction) -> tuple[str, bool]:
        try:
            return f"SHARADAR:{self.tickers.resolve_recent(ticker, on)}", True
        except DataQualityError:
            rec.unresolved_identity.append(f"{ticker}@{on}")
            return f"{SOURCE}:{ticker}:{on.isoformat()}", False

    def reconstruct(self, index_code: str = INDEX) -> tuple[EventSource, SP500Reconstruction]:
        rows = parse_table("sp500", self.payload)
        current = [r for r in rows if r["action"] == "current"]
        if not current:
            raise MembershipSequenceError("SP500 payload has no 'current' rows to anchor")
        anchor_dates = {date.fromisoformat(r["date"][:10]) for r in current}
        if len(anchor_dates) != 1:
            raise MembershipSequenceError(f"'current' rows on several dates {anchor_dates}")
        anchor = anchor_dates.pop()
        members = {r["ticker"].upper() for r in current}
        hist: dict[date, set[str]] = defaultdict(set)
        changes: dict[date, tuple[set[str], set[str]]] = defaultdict(lambda: (set(), set()))
        for r in rows:
            d = date.fromisoformat(r["date"][:10])
            t = r["ticker"].upper()
            if r["action"] == "historical":
                hist[d].add(t)
            elif r["action"] == "added":
                changes[d][0].add(t)
            elif r["action"] == "removed":
                changes[d][1].add(t)
            elif r["action"] != "current":
                raise DataQualityError(f"SP500: unknown action {r['action']!r}")
        if any(d > anchor for d in changes):
            raise MembershipSequenceError("changes after the 'current' anchor date")
        # walk backwards: membership AFTER the changes of each date
        state: dict[date, frozenset[str]] = {anchor: frozenset(members)}
        cur = set(members)
        for d in sorted(changes, reverse=True):
            adds, dels = changes[d]
            state[d] = frozenset(cur)
            if not adds <= cur:
                raise MembershipSequenceError(
                    f"{d}: undoing additions of non-members {sorted(adds - cur)}"
                )
            if dels & cur:
                raise MembershipSequenceError(
                    f"{d}: undoing removals of members {sorted(dels & cur)}"
                )
            cur = (cur - adds) | dels
            if d > self.coverage_start and not (
                self.expected_size[0] <= len(cur) <= self.expected_size[1]
            ):
                raise MembershipSequenceError(
                    f"size {len(cur)} before {d} outside {self.expected_size}"
                )
        rec = SP500Reconstruction(anchor, frozenset())

        def members_on(day: date) -> frozenset[str]:
            later = [d for d in sorted(changes) if d > day]
            m = set(members)
            for d in sorted(later, reverse=True):
                adds, dels = changes[d]
                m = (m - adds) | dels
            return frozenset(m)

        for d, snap in sorted(hist.items()):
            got = members_on(d)
            if got != snap:
                raise MembershipSequenceError(
                    f"historical snapshot {d} disagrees with the event history: "
                    f"missing {sorted(snap - got)[:10]}, extra {sorted(got - snap)[:10]}"
                )
            rec.checked_historical_dates.append(d)
        initial = members_on(self.coverage_start)
        rec.initial = initial
        events: list[IndexEventRecord] = []
        for t in sorted(initial):
            key, ok = self._key(t, self.coverage_start, rec)
            events.append(
                IndexEventRecord(
                    index_code,
                    EventType.INITIAL_SNAPSHOT,
                    self.coverage_start,
                    f"init:{t}",
                    key,
                    t,
                    reason="reconstructed from current + changes",
                    identity_resolved=ok,
                )
            )
        for d in sorted(x for x in changes if x > self.coverage_start):
            adds, dels = changes[d]
            add_keys = {t: self._key(t, d, rec) for t in adds}
            del_keys = {t: self._key(t, d - timedelta(days=1), rec) for t in dels}
            same = {
                (o, n)
                for o, (ko, oko) in del_keys.items()
                for n, (kn, okn) in add_keys.items()
                if oko and okn and ko == kn
            }
            for o, n in sorted(same):
                rec.ticker_changes.append((o, n, d))
                events.append(
                    IndexEventRecord(
                        index_code,
                        EventType.TICKER_CHANGE,
                        d,
                        f"{d}:chg:{o}>{n}",
                        del_keys[o][0],
                        o,
                        new_ticker=n,
                        reason="same permaticker removed/added",
                    )
                )
            for t, (k, ok) in sorted(del_keys.items()):
                if any(t == o for o, _ in same):
                    continue
                events.append(
                    IndexEventRecord(
                        index_code,
                        EventType.INDEX_DELETE,
                        d,
                        f"{d}:del:{t}",
                        k,
                        t,
                        reason="SHARADAR removed",
                        identity_resolved=ok,
                    )
                )
            for t, (k, ok) in sorted(add_keys.items()):
                if any(t == n for _, n in same):
                    continue
                events.append(
                    IndexEventRecord(
                        index_code,
                        EventType.INDEX_ADD,
                        d,
                        f"{d}:add:{t}",
                        k,
                        t,
                        reason="SHARADAR added",
                        identity_resolved=ok,
                    )
                )
        src = EventSource(
            SOURCE,
            self.confidence,
            events,
            content_hash([sha256_hex(self.payload)]),
            self.archive_id,
            warnings=tuple(f"identity unresolved: {x}" for x in rec.unresolved_identity),
        )
        return src, rec


def cross_check_announcements(
    src: EventSource, official: Sequence[OfficialAnnouncement]
) -> list[str]:
    """Compare vendor changes with archived official announcements. Any discrepancy
    (missing event, different effective date) raises: fail closed."""
    kind = {"added": EventType.INDEX_ADD, "removed": EventType.INDEX_DELETE}
    problems = []
    for a in official:
        hits = [
            e
            for e in src.events
            if e.ticker == a.ticker.upper()
            and (e.event_type is kind[a.action] or e.event_type is EventType.TICKER_CHANGE)
        ]
        if not any(e.effective_date == a.effective_date for e in hits):
            got = sorted({str(e.effective_date) for e in hits})
            problems.append(f"{a.ticker} {a.action} official {a.effective_date}, vendor {got}")
    if problems:
        raise MembershipSequenceError("SP500 vendor vs official: " + "; ".join(problems))
    return [f"{a.ticker} {a.action} {a.effective_date}: agrees" for a in official]


def candidate_status(contract_passed_on: str | None) -> str:
    """``REAL_DATA`` → CANONICAL_CANDIDATE; ``FIXTURE`` → ADAPTER_CONTRACT_TESTED."""
    if contract_passed_on == "REAL_DATA":
        return "CANONICAL_CANDIDATE"
    if contract_passed_on == "FIXTURE":
        return "ADAPTER_CONTRACT_TESTED"
    return "NOT_TESTED"
