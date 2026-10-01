"""IBEX 35 membership from OFFICIAL BME documents only (D-03, ADR-0017).

The BME «Composición histórica – IBEX 35» lists every change since 1991 but not the
initial composition. The current composition (BME quote page, observed on a date, with the
ISIN shown on each official ficha) anchors the history: walking the complete change list
BACKWARDS from it yields the membership at ``coverage_start``; the rows are then replayed
forwards as events.

Guarantees and limits:
* every intermediate step is checked (undoing an inclusion must remove a present code,
  undoing an exclusion must re-add an absent one) and the size must stay within
  ``expected_size`` — any inconsistency raises;
* membership is exact in CODE space; identity is not: codes are tickers, not securities.
  Every interval stays IDENTITY_UNRESOLVED. The current ISINs are recorded as identifiers
  valid FROM the observation date only (current identity ≠ historical identity; e.g. FER
  changed ISIN from ES to NL);
* rows whose type cannot be proven are loaded as UNRESOLVED_EVENT_TYPE turnover (see
  ``classify_rows``) and listed in the coverage report.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from itertools import pairwise

from pitquant.core.hashing import content_hash
from pitquant.universe.events import (
    EventSource,
    MembershipSequenceError,
    SourceConfidence,
)
from pitquant.universe.sources.bme import (
    INDEX,
    SOURCE,
    BMEHistoryRow,
    RowStyle,
    classify_rows,
)


@dataclass(frozen=True)
class CurrentComposition:
    observed_on: date
    constituents: tuple[tuple[str, str], ...]  # (ticker, ISIN) as shown by BME on that date
    archive_sha256: str


@dataclass
class ReconstructionReport:
    coverage_start: date
    snapshot_date: date
    initial_codes: tuple[str, ...]
    sizes: dict[str, int] = field(default_factory=dict)
    unresolved_events: list[str] = field(default_factory=list)
    order_anomalies: list[str] = field(default_factory=list)


def _changes(r: BMEHistoryRow) -> tuple[set[str], set[str]]:
    adds = set(r.additions) | {n for _, n in r.ticker_changes}
    dels = set(r.deletions) | {o for o, _ in r.ticker_changes}
    return adds, dels


def membership_before(
    rows: Sequence[BMEHistoryRow],
    current: CurrentComposition,
    on: date,
    expected_size: tuple[int, int],
) -> tuple[set[str], dict[str, int]]:
    """Codes that were members on ``on`` (after that day's rows), walking back from the
    current composition. Raises on any inconsistency."""
    members = {t for t, _ in current.constituents}
    if len(members) != len(current.constituents):
        raise MembershipSequenceError("duplicate tickers in the current composition")
    later = [r for r in rows if r.effective_date > on]
    if any(r.effective_date > current.observed_on for r in rows):
        raise MembershipSequenceError("history contains rows after the observed composition")
    sizes: dict[str, int] = {}
    for r in sorted(later, key=lambda r: (r.effective_date, r.review_number or 0), reverse=True):
        adds, dels = _changes(r)
        if not adds <= members:
            raise MembershipSequenceError(
                f"row {r.review_number} {r.effective_date}: undoing inclusion of non-members "
                f"{sorted(adds - members)}"
            )
        if dels & members:
            raise MembershipSequenceError(
                f"row {r.review_number} {r.effective_date}: undoing exclusion of current "
                f"members {sorted(dels & members)}"
            )
        members = (members - adds) | dels
        sizes[f"before {r.effective_date.isoformat()} (row {r.review_number})"] = len(members)
        if not expected_size[0] <= len(members) <= expected_size[1]:
            raise MembershipSequenceError(
                f"size {len(members)} before row {r.review_number} outside {expected_size}"
            )
    return members, sizes


def events_from_official_documents(
    rows: Sequence[BMEHistoryRow],
    current: CurrentComposition,
    coverage_start: date,
    history_sha256: str,
    expected_size: tuple[int, int],
) -> tuple[EventSource, ReconstructionReport]:
    initial, sizes = membership_before(rows, current, coverage_start, expected_size)
    rep = ReconstructionReport(coverage_start, current.observed_on, tuple(sorted(initial)), sizes)
    by_number = sorted((r for r in rows if r.review_number), key=lambda r: r.review_number or 0)
    for a, b in pairwise(by_number):
        if b.effective_date < a.effective_date:
            rep.order_anomalies.append(
                f"row {b.review_number} ({b.effective_date}) precedes row {a.review_number} "
                f"({a.effective_date}) in time"
            )
    seed = BMEHistoryRow(
        coverage_start,
        tuple(sorted(initial)),
        (),
        RowStyle.INITIAL,
        f"reconstructed:{coverage_start.isoformat()}",
        "membership derived from the observed composition and the complete change list",
    )
    forward = [r for r in rows if r.effective_date > coverage_start]
    res = classify_rows([seed, *forward], (), INDEX, unproven_as_unresolved_turnover=True)
    rep.unresolved_events = res.unresolved_events
    src = EventSource(
        SOURCE,
        # The change history is official and complete, but the ANCHOR (current composition)
        # is a transcription of JS-rendered official pages whose raw bytes cannot be
        # archived — same structure as the S&P snapshot reconstruction: provisional.
        SourceConfidence.PROVISIONAL_RESEARCH_SOURCE,
        res.events,
        content_hash([history_sha256, current.archive_sha256]),
        warnings=tuple(res.warnings),
    )
    return src, rep
