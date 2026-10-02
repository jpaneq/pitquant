# ruff: noqa: E501
"""Tiingo D-05 candidate evaluation (ADR-0024): ingestion of one symbol, coverage discovery from
the vendor's public ``supported_tickers`` list (no token, no quota) and the 7 explicit criteria.

``TIINGO_D05_CANDIDATE`` is true ONLY if every criterion is PASS; an unmeasured criterion is
UNKNOWN (counts as not passed). It never means CANONICAL.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import Session

from pitquant.data.archive import ArchiveStore, archive_document
from pitquant.market.ca_compare import Comparison, compare_with_official
from pitquant.market.normalized import CorporateAction
from pitquant.market.pipeline import record_ca_ingestion, store_batch
from pitquant.market.providers.tiingo import (
    PROVIDER,
    AdjustmentReport,
    TiingoEODMarketDataProvider,
    adjustment_report,
)
from pitquant.market.validation import SeriesReport, validate_series

RECENT_DAYS = 10  # an endDate this close to the listing date = still trading


# ───────────────────────────────────── ingestion of one symbol ───────────────────────────
@dataclass
class SymbolIngest:
    ticker: str
    sha256: str
    series: SeriesReport
    adjustment: AdjustmentReport
    bars_inserted: int
    actions_vendor: list[CorporateAction]
    comparisons: list[Comparison] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def ingest_symbol(
    session: Session,
    store: ArchiveStore,
    provider: TiingoEODMarketDataProvider,
    *,
    ticker: str,
    security_id: str,
    start: date,
    end: date | None = None,
    official: Sequence[CorporateAction] = (),
) -> SymbolIngest:
    body, url = provider.download(ticker, start, end)
    row = archive_document(
        session, store, provider=PROVIDER, source_identifier=url, data=body,
        mime_type="application/json", parser_version="tiingo-eod-1",
        notes=f"startDate={start}; token in header, not archived",
    )  # fmt: skip
    batch = provider.normalize(ticker, body)
    actions = list(batch.actions)
    batch.actions = []  # vendor events are compared, never stored in place of official ones
    rep = store_batch(session, batch, key_to_security={ticker: security_id}, market="US")
    first = batch.bars[0].session_date if batch.bars else start
    last = batch.bars[-1].session_date if batch.bars else start
    comps = compare_with_official(
        [o for o in official if (o.anchor_date or date.min) >= first],
        actions,
    )
    record_ca_ingestion(
        session, security_id=security_id, provider=PROVIDER, period_start=first, period_end=last,
        completed=False, events_found=len(actions), source_hash=row.sha256,
        detail="VENDOR tier, not accepted (D-05): never verified",
    )  # fmt: skip
    return SymbolIngest(
        ticker,
        row.sha256,
        validate_series(batch.bars, "XNYS"),
        adjustment_report(body),
        rep.bars_inserted,
        actions,
        comps,
        batch.warnings,
    )


# ───────────────────────────────────── coverage discovery ────────────────────────────────
class CoverageStatus(StrEnum):
    ACTIVE_COVERED = "ACTIVE_COVERED"
    DELISTED_COVERED = "DELISTED_COVERED"
    PARTIAL_PERIOD = "PARTIAL_PERIOD"
    TICKER_RECYCLED_SUSPECT = "TICKER_RECYCLED_SUSPECT"  # listed, but never in the period
    MISSING = "MISSING"


@dataclass(frozen=True)
class UniverseRow:
    security_id: str
    historical_ticker: str
    period_start: date
    period_end: date | None


@dataclass
class CoverageRow:
    security_id: str
    historical_ticker: str
    period: str
    tiingo_ticker: str | None
    start_date: date | None
    end_date: date | None
    is_active: bool | None
    status: CoverageStatus
    reason: str


def load_supported(csv_bytes: bytes) -> dict[str, list[dict[str, Any]]]:
    """ticker -> rows (a ticker can appear more than once: recycled across companies)."""
    out: dict[str, list[dict[str, Any]]] = {}
    for r in csv.DictReader(io.StringIO(csv_bytes.decode("utf-8"))):
        try:
            sd = date.fromisoformat(r["startDate"]) if r["startDate"] else None
            ed = date.fromisoformat(r["endDate"]) if r["endDate"] else None
        except ValueError:
            continue
        out.setdefault(r["ticker"].upper(), []).append(
            {"exchange": r["exchange"], "asset": r["assetType"], "start": sd, "end": ed}
        )
    return out


def coverage_rows(
    universe: Iterable[UniverseRow], supported: dict[str, list[dict[str, Any]]], asof: date
) -> list[CoverageRow]:
    rows: list[CoverageRow] = []
    for u in universe:
        per = f"{u.period_start}..{u.period_end or ''}"
        cands = supported.get(u.historical_ticker.upper(), [])
        if not cands:
            rows.append(CoverageRow(u.security_id, u.historical_ticker, per, None, None, None, None,
                                    CoverageStatus.MISSING, "ticker absent from Tiingo supported list"))  # fmt: skip
            continue
        p_end = u.period_end or asof
        best = None
        for c in cands:
            if c["start"] and c["end"] and c["start"] <= p_end and c["end"] >= u.period_start:
                best = c
                break
        if best is None:
            c = cands[0]
            rows.append(CoverageRow(u.security_id, u.historical_ticker, per, u.historical_ticker, c["start"],
                                    c["end"], None, CoverageStatus.TICKER_RECYCLED_SUSPECT,
                                    "ticker listed but its price range never overlaps the period"))  # fmt: skip
            continue
        active = best["end"] >= asof - timedelta(days=RECENT_DAYS)
        full = best["start"] <= u.period_start and best["end"] >= p_end - timedelta(
            days=RECENT_DAYS
        )
        if full:
            st = CoverageStatus.ACTIVE_COVERED if active else CoverageStatus.DELISTED_COVERED
            why = "range covers the whole period"
        else:
            st, why = CoverageStatus.PARTIAL_PERIOD, "range overlaps but does not cover the period"
        rows.append(CoverageRow(u.security_id, u.historical_ticker, per, u.historical_ticker, best["start"],
                                best["end"], active, st, why))  # fmt: skip
    return rows


# ───────────────────────────────────── D-05 criteria ─────────────────────────────────────
class Criterion(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


@dataclass
class D05Evaluation:
    criteria: dict[str, tuple[Criterion, str]]

    @property
    def candidate(self) -> bool:
        return all(c is Criterion.PASS for c, _ in self.criteria.values())


def evaluate_d05(
    *,
    series: Sequence[SeriesReport],
    comparisons: Sequence[Comparison],
    identity_reproducible: bool,
    coverage: Sequence[CoverageRow] | None,
    provenance_complete: bool | None,
    min_first_bar: date = date(2011, 1, 3),
    min_former_coverage: float = 0.95,
) -> D05Evaluation:
    c: dict[str, tuple[Criterion, str]] = {}
    if not series:
        c["1 history 2011+"] = (Criterion.UNKNOWN, "no real Tiingo series ingested (no key)")
        c["2 raw OHLCV consistent"] = (Criterion.UNKNOWN, "no real series")
        c["3 sessions aligned"] = (Criterion.UNKNOWN, "no real series")
    else:
        ok = all(s.first_date is not None and s.first_date <= min_first_bar for s in series)
        c["1 history 2011+"] = (Criterion.PASS if ok else Criterion.FAIL,
                                "; ".join(f"{s.first_date}..{s.last_date} {s.n_bars} bars" for s in series))  # fmt: skip
        bad = sum(len(s.impossible) + len(s.duplicates) + s.out_of_order for s in series)
        c["2 raw OHLCV consistent"] = (
            Criterion.PASS if bad == 0 else Criterion.FAIL,
            f"{bad} anomalies",
        )
        gaps = sum(s.n_missing + len(s.non_session) for s in series)
        c["3 sessions aligned"] = (Criterion.PASS if gaps == 0 else Criterion.FAIL,
                                   f"{gaps} missing/non-session days")  # fmt: skip
    if not comparisons:
        c["4 corporate actions vs ground truth"] = (Criterion.UNKNOWN, "no comparison available")
    else:
        from pitquant.market.ca_compare import Agreement

        bad_c = [x for x in comparisons if x.status is not Agreement.MATCH]
        c["4 corporate actions vs ground truth"] = (
            Criterion.PASS if not bad_c else Criterion.FAIL,
            f"{len(comparisons) - len(bad_c)}/{len(comparisons)} match official",
        )
    if coverage is None:
        c["5 identity/ticker mapping reproducible"] = (
            Criterion.UNKNOWN,
            "AAPL/MSFT identified (CIK + OFFICIAL CUSIP) but historical ticker->security mapping "
            "needs the S&P universe (D-02)",
        )
    else:
        c["5 identity/ticker mapping reproducible"] = (
            Criterion.PASS if identity_reproducible else Criterion.FAIL,
            "mapping run over the historical universe",
        )
    if coverage is None:
        c["6 former/delisted coverage"] = (Criterion.UNKNOWN, "no historical S&P universe (D-02)")
    else:
        former = [r for r in coverage if r.is_active is False or r.status is CoverageStatus.MISSING]
        good = [r for r in former if r.status is CoverageStatus.DELISTED_COVERED]
        rate = len(good) / len(former) if former else 0.0
        c["6 former/delisted coverage"] = (
            Criterion.PASS if former and rate >= min_former_coverage else Criterion.FAIL,
            f"{len(good)}/{len(former)} former constituents covered ({rate:.0%})",
        )
    c["7 raw provenance complete"] = (
        Criterion.UNKNOWN if provenance_complete is None
        else Criterion.PASS if provenance_complete else Criterion.FAIL,
        "archived raw responses with SHA-256, token not archived",
    )  # fmt: skip
    return D05Evaluation(c)


# ───────────────────────── deterministic D-05 sample + per-security coverage ─────────────────
import hashlib  # noqa: E402

SAMPLE_SEED = "PITQUANT_D05_SAMPLE_V1"
ACTIVE_THRESHOLD = 0.98  # fixed research thresholds: never relaxed to make Tiingo pass
FORMER_THRESHOLD = 0.95


def deterministic_sample(candidates: Iterable[str], k: int, *, salt: str = "") -> list[str]:
    """First ``k`` candidates ordered by SHA-256(seed | salt | candidate). No cherry-picking: the
    seed is fixed; a category with fewer than ``k`` candidates is returned whole."""
    seed = hashlib.sha256(SAMPLE_SEED.encode()).hexdigest()
    ranked = sorted(
        set(candidates), key=lambda c: hashlib.sha256(f"{seed}|{salt}|{c}".encode()).hexdigest()
    )
    return ranked[:k]


@dataclass
class SecurityCoverage:
    ticker: str
    category: str  # ACTIVE | FORMER | CHANGED | FIXED
    membership_start: date
    membership_end: date | None
    price_start: date | None
    price_end: date | None
    expected_sessions: int
    observed_sessions: int
    missing_sessions: int
    noncalendar_rows: int
    duplicate_rows: int
    invalid_ohlc: int
    documented_exceptions: int = 0  # suspensions / halts / IPO / delisting with a document

    @property
    def coverage(self) -> float:
        return (
            1.0
            if self.expected_sessions == 0
            else (self.observed_sessions + self.documented_exceptions) / self.expected_sessions
        )


def security_coverage_row(
    ticker: str,
    category: str,
    bars: Sequence[Any],
    membership_start: date,
    membership_end: date | None,
    asof: date,
    exchange: str = "XNYS",
    documented_missing: frozenset[date] = frozenset(),
) -> SecurityCoverage:
    """``bars``: objects with session_date/open/high/low/close/volume. Missing sessions are NOT
    errors by themselves; only a documented reason (``documented_missing``) excuses them."""
    from pitquant.data.calendars.market_calendar import get_calendar
    from pitquant.market.validation import calendar_status

    cal = get_calendar(exchange)
    end = min(membership_end or asof, asof)
    expected = [
        d
        for d in cal.sessions(max(membership_start, cal.first_session), min(end, cal.last_session))
    ]
    seen: dict[date, int] = {}
    invalid = noncal = 0
    for b in bars:
        seen[b.session_date] = seen.get(b.session_date, 0) + 1
        if calendar_status(cal, b.session_date) == "non_session":
            noncal += 1
        o, h, lo, c, v = b.open, b.high, b.low, b.close, b.volume
        bad = (
            (v is not None and v < 0)
            or not (lo <= c <= h)
            or (o is not None and not (lo <= o <= h))
        )
        invalid += int(bad)
    inside = {d for d in seen if d in set(expected)}
    missing = [d for d in expected if d not in seen]
    excused = sum(1 for d in missing if d in documented_missing)
    dates = sorted(seen)
    return SecurityCoverage(
        ticker, category, membership_start, membership_end,
        dates[0] if dates else None, dates[-1] if dates else None,
        len(expected), len(inside), len(missing), noncal, sum(1 for n in seen.values() if n > 1), invalid, excused,
    )  # fmt: skip


@dataclass
class SampleVerdict:
    active_coverage: float | None
    former_coverage: float | None
    systematic_temporal_issues: int
    invalid_ohlc: int
    ground_truth_unexplained: int | None
    mapping_reproducible: bool | None
    provenance_complete: bool | None
    candidate: bool
    reasons: list[str]


def evaluate_sample(
    rows: Sequence[SecurityCoverage],
    *,
    ground_truth_unexplained: int | None,
    mapping_reproducible: bool | None,
    provenance_complete: bool | None,
) -> SampleVerdict:
    """TIINGO_D05_CANDIDATE: >= 98 % of the ACTIVE sample covered during membership, >= 95 % of the
    FORMER/DELISTED sample, no systematic temporal problems, consistent OHLCV, 100 % of the
    ground-truth corporate actions without unexplained contradiction, reproducible mapping and
    complete provenance. A missing measurement is a failure, never a pass."""

    def share(cat: set[str]) -> float | None:
        sel = [r for r in rows if r.category in cat]
        if not sel:
            return None
        return sum(1 for r in sel if r.coverage >= 0.98) / len(sel)

    act, frm = share({"ACTIVE", "FIXED"}), share({"FORMER", "CHANGED"})
    sys_issues = sum(1 for r in rows if r.noncalendar_rows or r.duplicate_rows)
    inv = sum(r.invalid_ohlc for r in rows)
    reasons = []
    if act is None or act < ACTIVE_THRESHOLD:
        reasons.append(f"active coverage {act} < {ACTIVE_THRESHOLD}")
    if frm is None or frm < FORMER_THRESHOLD:
        reasons.append(f"former/delisted coverage {frm} < {FORMER_THRESHOLD}")
    if sys_issues:
        reasons.append(f"{sys_issues} securities with duplicate or non-calendar rows")
    if inv:
        reasons.append(f"{inv} invalid OHLC rows")
    if ground_truth_unexplained != 0:
        reasons.append(f"ground-truth contradictions unexplained: {ground_truth_unexplained}")
    if not mapping_reproducible:
        reasons.append("ticker mapping reproducibility not demonstrated")
    if not provenance_complete:
        reasons.append("provenance not demonstrated complete")
    return SampleVerdict(
        act,
        frm,
        sys_issues,
        inv,
        ground_truth_unexplained,
        mapping_reproducible,
        provenance_complete,
        not reasons,
        reasons,
    )
