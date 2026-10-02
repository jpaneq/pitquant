"""IdentityResolutionEngine (ADR-0020): which SECURITY did a membership interval refer to?

Index sources (BME history) prove membership in CODE space. Identity needs a dated
identifier. Evidence combined here:

* ANCV semiannual snapshots (``security_identity_snapshots``): ISIN, issuer legal name,
  ANCV label (``ENG/AC 1,50``), issue date. A snapshot proves the ISIN was active on its
  reference date — never a start or end date;
* the BME membership interval and the code it had on each date (ticker periods bounded to
  membership);
* official identifier observations (BME current composition, CNMV queries).

The ISIN is the anchor. The ANCV label is only a way to FIND candidates (it is not the
exchange ticker: Redeia is ``REDEIA/AC`` while its BME code is RED). Rules, testable:

MULTI_SOURCE_CONFIRMED — a run of snapshots STRICTLY inside the interval where
  * at least one snapshot has exactly one ordinary-share line (``AC``; CFI ``E*`` when
    present) whose label equals the BME code of that date (the anchor), and
  * every other snapshot of the run contains the same ISIN (any label), and
  * ISIN changes inside the interval are explained by an ANCV issue date of the new ISIN
    between the two snapshots and the same issuer legal name (nominal change: same
    security); otherwise the window between the snapshots is PROVISIONAL;
  * the edges between the interval bounds and the first/last snapshot inherit the status
    only if a snapshot outside the interval shows the same ISIN (or, after the last ANCV
    snapshot, the BME current composition gives the same ISIN); otherwise PROVISIONAL.
EXACT_OFFICIAL_IDENTIFIER — an official document states this code ↔ ISIN on a date in
  the segment (``OfficialIdentifier.exact``).
PROVISIONAL — candidate ISIN(s) from bracketing snapshots only, a single source, or an
  unexplained window.
UNRESOLVED — no evidence.

A ticker alone is never sufficient: a label match always needs the ISIN to be unique
among ordinary shares on that date, and the GAM label reused by another issuer in 2023
cannot leak into a 2013–2017 interval because only snapshots inside the interval anchor.
"""

from __future__ import annotations

import re
import unicodedata
from bisect import bisect_left, bisect_right
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import StrEnum

ENGINE_VERSION = "identity-engine-2"  # 2: only EXACT official documents break label ties


class IdentityResolutionStatus(StrEnum):
    EXACT_OFFICIAL_IDENTIFIER = "EXACT_OFFICIAL_IDENTIFIER"
    MULTI_SOURCE_CONFIRMED = "MULTI_SOURCE_CONFIRMED"
    PROVISIONAL = "PROVISIONAL"
    UNRESOLVED = "UNRESOLVED"


BACKTESTABLE = {
    IdentityResolutionStatus.EXACT_OFFICIAL_IDENTIFIER,
    IdentityResolutionStatus.MULTI_SOURCE_CONFIRMED,
}


class PeriodClass(StrEnum):
    V1_CANONICAL = "V1_CANONICAL"
    ARCHIVAL = "ARCHIVAL_NON_CANONICAL_FOR_V1"


@dataclass(frozen=True)
class SnapshotLine:
    reference_date: date
    isin: str
    issuer_legal_name: str
    instrument_name: str
    cfi: str | None = None
    issue_date: date | None = None

    @property
    def label(self) -> str:
        return self.instrument_name.split("/", 1)[0].strip()

    @property
    def share_kind(self) -> str:
        rest = self.instrument_name.split("/", 1)[1] if "/" in self.instrument_name else ""
        return rest.split()[0] if rest.split() else ""

    @property
    def is_ordinary_share(self) -> bool:
        return self.share_kind == "AC" and (self.cfi is None or self.cfi.startswith("E"))


@dataclass(frozen=True)
class CodePeriod:
    code: str
    start: date
    end: date | None  # exclusive


@dataclass(frozen=True)
class MembershipSpan:
    key: str  # index_membership.id (as text) or a test label
    effective_from: date
    effective_to: date | None
    codes: tuple[CodePeriod, ...]

    def code_at(self, d: date) -> str | None:
        for p in self.codes:
            if p.start <= d and (p.end is None or d < p.end):
                return p.code
        return None


@dataclass(frozen=True)
class OfficialIdentifier:
    """A dated code ↔ ISIN statement. ``exact`` only for an archived official document
    stating it verbatim; a transcription of a JS-rendered page is not exact."""

    code: str
    isin: str
    observed_on: date
    source: str
    source_hash: str
    exact: bool


@dataclass
class Segment:
    start: date
    end: date | None
    status: IdentityResolutionStatus
    isin: str | None
    evidence: list[str] = field(default_factory=list)
    candidates: tuple[str, ...] = ()


def normalize_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9]+", " ", s).strip()


class SnapshotIndex:
    """ANCV lines by reference date, with label and ISIN lookups."""

    def __init__(self, lines: Iterable[SnapshotLine]) -> None:
        self.by_date: dict[date, list[SnapshotLine]] = defaultdict(list)
        for ln in lines:
            self.by_date[ln.reference_date].append(ln)
        self.dates = sorted(self.by_date)
        self._isin: dict[date, dict[str, SnapshotLine]] = {
            d: {ln.isin: ln for ln in ls} for d, ls in self.by_date.items()
        }

    def label_candidates(self, d: date, code: str) -> list[SnapshotLine]:
        return [ln for ln in self.by_date[d] if ln.is_ordinary_share and ln.label == code]

    def line(self, d: date, isin: str) -> SnapshotLine | None:
        return self._isin[d].get(isin)

    def issuer_ordinary_isins(self, d: date, issuer_name: str) -> set[str]:
        n = normalize_name(issuer_name)
        return {
            ln.isin
            for ln in self.by_date[d]
            if ln.is_ordinary_share and normalize_name(ln.issuer_legal_name) == n
        }

    def latest_line(self, isin: str) -> SnapshotLine | None:
        for d in reversed(self.dates):
            if (ln := self._isin[d].get(isin)) is not None:
                return ln
        return None

    def before(self, d: date) -> date | None:
        """Last snapshot date <= d."""
        i = bisect_right(self.dates, d)
        return self.dates[i - 1] if i else None

    def after(self, d: date) -> date | None:
        """First snapshot date >= d."""
        i = bisect_left(self.dates, d)
        return self.dates[i] if i < len(self.dates) else None


@dataclass
class _Point:
    d: date
    isin: str | None
    how: str  # anchor | continuity | ambiguous | none
    candidates: tuple[str, ...] = ()


def _day(d: date) -> date:
    return d + timedelta(days=1)


class IdentityResolutionEngine:
    def __init__(
        self,
        snapshots: SnapshotIndex,
        official: Sequence[OfficialIdentifier] = (),
        *,
        horizon: date,
    ) -> None:
        self.ix = snapshots
        self.official = official
        self.horizon = horizon  # end of knowledge for open intervals (e.g. observation day)

    # ── per-date evidence ─────────────────────────────────────────────────────
    def _points(self, span: MembershipSpan, dates: list[date]) -> list[_Point]:
        pts: list[_Point] = []
        for d in dates:
            code = span.code_at(d)
            cands = self.ix.label_candidates(d, code) if code else []
            isins = tuple(sorted({c.isin for c in cands}))
            if len(isins) == 1:
                pts.append(_Point(d, isins[0], "anchor", isins))
                continue
            if len(isins) > 1:
                # only an EXACT official document may break a tie (ADR-0020); a transcription
                # of a rendered page is a single provisional source and cannot
                pick = [
                    o.isin
                    for o in self.official
                    if o.exact and o.code == code and o.isin in isins and o.observed_on >= d
                ]
                if len(set(pick)) == 1:
                    pts.append(_Point(d, pick[0], "anchor+official", isins))
                else:
                    pts.append(_Point(d, None, "ambiguous", isins))
                continue
            pts.append(_Point(d, None, "none"))
        # continuity: a snapshot without a label match still carries a known ISIN
        known = [p.isin for p in pts if p.isin]
        for p in pts:
            if p.isin is None and p.how == "none":
                present = [i for i in dict.fromkeys(known) if self.ix.line(p.d, i)]
                if len(present) == 1:
                    lab = self.ix.line(p.d, present[0])
                    p.isin, p.how = present[0], f"continuity(label {lab.label if lab else '?'})"
        return pts

    def _same_security(self, a: str, da: date, b: str, db: date) -> str | None:
        """ISIN a (last seen da) -> b (first seen db) is a nominal/ISIN change of ONE
        security when ANCV dates b's issue in (da, db], a is gone at db and the issuer
        legal name is unchanged. Returns the switch date evidence or None."""
        lb, la = self.ix.line(db, b), self.ix.line(da, a)
        if lb is None or la is None or lb.issue_date is None:
            return None
        if not (da < lb.issue_date <= db) or self.ix.line(db, a) is not None:
            return None
        if normalize_name(la.issuer_legal_name) != normalize_name(lb.issuer_legal_name):
            return None
        return lb.issue_date.isoformat()

    def resolve(self, span: MembershipSpan) -> list[Segment]:
        f = span.effective_from
        t = span.effective_to or _day(self.horizon)
        inside = [d for d in self.ix.dates if f <= d < t]
        if not inside:
            return [self._bracket_only(span, f, t)]
        pts = self._points(span, inside)
        segs: list[Segment] = []
        M = IdentityResolutionStatus.MULTI_SOURCE_CONFIRMED
        P = IdentityResolutionStatus.PROVISIONAL
        # runs of identical ISIN
        runs: list[tuple[str | None, list[_Point]]] = []
        for p in pts:
            if runs and runs[-1][0] == p.isin:
                runs[-1][1].append(p)
            else:
                runs.append((p.isin, [p]))
        anchored = {i for i, ps in runs if i and any(q.how.startswith("anchor") for q in ps)}
        cursor, prev = f, None  # prev: (isin, last date) of the previous confirmed run
        for isin, ps in runs:
            first, last = ps[0].d, ps[-1].d
            ev = [f"{q.d}:{q.how}:{q.isin or '|'.join(q.candidates) or '-'}" for q in ps]
            if isin is None or isin not in anchored:
                cands = tuple(
                    sorted({c for q in ps for c in q.candidates} | ({isin} if isin else set()))
                )
                st = P if cands else IdentityResolutionStatus.UNRESOLVED
                segs.append(Segment(cursor, _day(last), st, None, ev, cands))
                cursor, prev = _day(last), None
                continue
            start = first
            if cursor < first:
                switch = self._same_security(prev[0], prev[1], isin, first) if prev else None
                if cursor == f and not segs:
                    segs.append(self._leading_edge(span, f, first, isin))
                elif switch is not None and prev is not None:
                    start = date.fromisoformat(switch)
                    segs[-1].end = start
                    segs[-1].evidence.append(
                        f"ISIN change {prev[0]}->{isin} (same issuer) at ANCV issue date {switch}"
                    )
                else:
                    gap_c = tuple(x for x in ((prev[0] if prev else None), isin) if x)
                    segs.append(
                        Segment(
                            cursor, first, P, None, ["unexplained window between snapshots"], gap_c
                        )
                    )
            segs.append(Segment(start, _day(last), M, isin, ev))
            cursor, prev = _day(last), (isin, last)
        if cursor < t:
            segs.append(self._trailing_edge(span, cursor, t, prev))
        segs = [x for x in segs if x.end is None or x.end > x.start]
        if span.effective_to is None and segs and segs[-1].end is not None and segs[-1].end >= t:
            segs[-1].end = None
        return _merge(self._apply_official(span, segs))

    # ── edges ─────────────────────────────────────────────────────────────────
    def _leading_edge(self, span: MembershipSpan, f: date, first: date, isin: str) -> Segment:
        d0 = self.ix.before(f)
        P, M = IdentityResolutionStatus.PROVISIONAL, IdentityResolutionStatus.MULTI_SOURCE_CONFIRMED
        if d0 is not None and self.ix.line(d0, isin) is not None:
            ln = self.ix.line(first, isin)
            if ln is not None and ln.issue_date is not None and ln.issue_date > f:
                return Segment(
                    f, first, P, None, [f"ISIN {isin} issued {ln.issue_date} after {f}"], (isin,)
                )
            return Segment(f, first, M, isin, [f"{d0}: same ISIN before the interval"])
        if d0 is not None:
            # Newly listed between d0 and the first snapshot: accepted only if the BME code was
            # not an ANCV label of any ordinary share at d0 and the ISIN was issued by f.
            code = span.code_at(f)
            ln = self.ix.line(first, isin)
            free = code is not None and not self.ix.label_candidates(d0, code)
            if free and ln is not None and ln.issue_date is not None and ln.issue_date <= f:
                return Segment(
                    f,
                    first,
                    M,
                    isin,
                    [f"{d0}: label {code} unused; {isin} issued {ln.issue_date} (new listing)"],
                )
        why = "no snapshot before the interval" if d0 is None else f"{d0}: ISIN absent"
        return Segment(f, first, P, None, [f"leading edge: {why}"], (isin,))

    def _trailing_edge(
        self, span: MembershipSpan, start: date, t: date, prev: tuple[str, date] | None
    ) -> Segment:
        P, M = IdentityResolutionStatus.PROVISIONAL, IdentityResolutionStatus.MULTI_SOURCE_CONFIRMED
        if prev is None:
            return Segment(start, t, P, None, ["trailing edge after an unresolved run"])
        isin, dl = prev
        dn = self.ix.after(t) if span.effective_to is not None else None
        if dn is not None:
            if self.ix.line(dn, isin) is not None:
                return Segment(start, t, M, isin, [f"{dn}: same ISIN after the interval"])
            last = self.ix.line(dl, isin)
            new = self.ix.issuer_ordinary_isins(dn, last.issuer_legal_name) if last else set()
            later = {
                i
                for i in new - {isin}
                if (ln := self.ix.line(dn, i)) is not None
                and ln.issue_date is not None
                and ln.issue_date >= t
            }
            if last is not None and not (new - {isin} - later):
                return Segment(
                    start,
                    t,
                    M,
                    isin,
                    [f"{dn}: ISIN retired, no new ordinary ISIN of {last.issuer_legal_name}"],
                )
            return Segment(
                start,
                t,
                P,
                None,
                [f"{dn}: ISIN gone and issuer has new ISIN(s) {sorted(new)}"],
                (isin,),
            )
        code = span.code_at(min(t, self.horizon) - timedelta(days=1)) or span.code_at(self.horizon)
        obs = [o for o in self.official if o.code == code and o.observed_on >= start]
        if obs and all(o.isin == isin for o in obs):
            return Segment(
                start, t, M, isin, [f"{o.observed_on}: {o.source} gives {o.isin}" for o in obs]
            )
        return Segment(
            start, t, P, None, ["after the last ANCV snapshot: no corroboration"], (isin,)
        )

    def _bracket_only(self, span: MembershipSpan, f: date, t: date) -> Segment:
        cands: set[str] = set()
        ev = []
        for d in (self.ix.before(f), self.ix.after(t)):
            if d is None:
                continue
            code = span.code_at(f) if d <= f else span.code_at(t - timedelta(days=1))
            got = {c.isin for c in self.ix.label_candidates(d, code)} if code else set()
            cands |= got
            ev.append(f"{d}: bracket {code} -> {sorted(got)}")
        st = IdentityResolutionStatus.PROVISIONAL if cands else IdentityResolutionStatus.UNRESOLVED
        return Segment(f, span.effective_to, st, None, ev or ["no snapshot"], tuple(sorted(cands)))

    def _apply_official(self, span: MembershipSpan, segs: list[Segment]) -> list[Segment]:
        for o in self.official:
            if not o.exact:
                continue
            for s in segs:
                inside = s.start <= o.observed_on and (s.end is None or o.observed_on < s.end)
                if inside and s.isin == o.isin and span.code_at(o.observed_on) == o.code:
                    s.status = IdentityResolutionStatus.EXACT_OFFICIAL_IDENTIFIER
                    s.evidence.append(f"{o.observed_on}: {o.source} ({o.source_hash[:12]})")
        return segs


def _merge(segs: list[Segment]) -> list[Segment]:
    out: list[Segment] = []
    for s in segs:
        if (
            out
            and out[-1].status == s.status
            and out[-1].isin == s.isin
            and out[-1].end == s.start
            and s.isin
        ):
            out[-1].end = s.end
            out[-1].evidence += s.evidence
        else:
            out.append(s)
    return out


# ───────────────────────── membership events (the 7 BME rows) ─────────────────────────


class RowOutcome(StrEnum):
    TICKER_CHANGE = "TICKER_CHANGE"
    SECURITY_REPLACEMENT = "SECURITY_REPLACEMENT"
    INDEX_TURNOVER = "INDEX_TURNOVER"  # INDEX_DELETE of old + INDEX_ADD of new, proven
    CORPORATE_REORGANIZATION = "CORPORATE_REORGANIZATION"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class RowResolution:
    row_ref: str
    old_code: str
    new_code: str
    effective_date: date
    outcome: RowOutcome
    evidence: tuple[str, ...]
    isin_before: str | None = None
    isin_after: str | None = None


def resolve_code_row(
    ix: SnapshotIndex, row_ref: str, old: str, new: str, effective: date, *, max_years: int = 4
) -> RowResolution:
    """Classify an «old -> new» BME row by ISIN continuity (no inference by name).

    The ISIN of ``old`` is taken from the LAST snapshot before the effective date where the
    ANCV label equals ``old`` uniquely; the ISIN of ``new`` from the FIRST snapshot on/after
    it where the label equals ``new`` uniquely (ANCV relabels on its own schedule, e.g.
    Criteria -> CaixaBank was relabelled before the BME code changed), both within
    ``max_years``. Same ISIN, present in EVERY snapshot in between -> TICKER_CHANGE (one
    security). Different ISINs with the old one still active after -> INDEX_TURNOVER.
    Anything else stays UNRESOLVED."""
    lo = date(effective.year - max_years, effective.month, 1)
    hi = date(effective.year + max_years, effective.month, 1)
    before_dates = [d for d in ix.dates if lo <= d < effective]
    after_dates = [d for d in ix.dates if effective <= d <= hi]
    if not before_dates or not after_dates:
        return RowResolution(
            row_ref,
            old,
            new,
            effective,
            RowOutcome.UNRESOLVED,
            ("no ANCV snapshot on both sides of the effective date",),
        )
    db = next((d for d in reversed(before_dates) if ix.label_candidates(d, old)), None)
    da = next((d for d in after_dates if ix.label_candidates(d, new)), None)
    if db is None or da is None:
        return RowResolution(
            row_ref,
            old,
            new,
            effective,
            RowOutcome.UNRESOLVED,
            (f"label {old} before / {new} after not found within {max_years}y",),
        )
    before = {c.isin for c in ix.label_candidates(db, old)}
    after = {c.isin for c in ix.label_candidates(da, new)}
    ev = [f"{db}: label {old} -> {sorted(before)}", f"{da}: label {new} -> {sorted(after)}"]
    if len(before) != 1 or len(after) != 1:
        return RowResolution(
            row_ref,
            old,
            new,
            effective,
            RowOutcome.UNRESOLVED,
            (*ev, "label match not unique on both sides"),
        )
    (a,), (b,) = before, after
    between = [d for d in ix.dates if db < d < da]
    if a == b:
        gaps = [d for d in between if ix.line(d, a) is None]
        if gaps:
            return RowResolution(
                row_ref,
                old,
                new,
                effective,
                RowOutcome.UNRESOLVED,
                (*ev, f"{a} absent at {gaps}: continuity not proven"),
                a,
                b,
            )
        for d in between:
            ln = ix.line(d, a)
            if ln is not None:
                ev.append(f"{d}: {a} present as {ln.instrument_name!r}")
        la, lb = ix.line(db, a), ix.line(da, b)
        if (
            la
            and lb
            and normalize_name(la.issuer_legal_name) != normalize_name(lb.issuer_legal_name)
        ):
            ev.append(f"issuer legal name {la.issuer_legal_name!r} -> {lb.issuer_legal_name!r}")
        return RowResolution(
            row_ref,
            old,
            new,
            effective,
            RowOutcome.TICKER_CHANGE,
            (*ev, f"same ISIN {a} on both sides, continuous"),
            a,
            b,
        )
    if ix.line(da, a) is not None:
        return RowResolution(
            row_ref,
            old,
            new,
            effective,
            RowOutcome.INDEX_TURNOVER,
            (*ev, f"{a} still active at {da}: different securities"),
            a,
            b,
        )
    return RowResolution(
        row_ref,
        old,
        new,
        effective,
        RowOutcome.UNRESOLVED,
        (*ev, f"{a} retired and {b} new: replacement not proven by ANCV alone"),
        a,
        b,
    )


def date_level_backtestability(
    resolved: Mapping[str, list[Segment]],
    spans: Mapping[str, MembershipSpan],
    dates: Sequence[date],
) -> dict[str, object]:
    """Share of ``dates`` on which EVERY member has a backtestable segment — the fail-closed
    rule of ``backtest_universe``. Identity QA only: no returns or metrics are computed."""
    ok = 0
    blockers: dict[str, int] = defaultdict(int)
    for d in dates:
        bad = []
        for k, sp in spans.items():
            if not (sp.effective_from <= d and (sp.effective_to is None or d < sp.effective_to)):
                continue
            seg = next(
                (s for s in resolved[k] if s.start <= d and (s.end is None or d < s.end)), None
            )
            if seg is None or seg.status not in BACKTESTABLE:
                bad.append(sp.code_at(d) or k)
        if bad:
            for b in bad:
                blockers[b] += 1
        else:
            ok += 1
    return {
        "dates_total": len(dates),
        "dates_backtestable": ok,
        "date_coverage_percentage": round(100.0 * ok / len(dates), 1) if dates else 0.0,
        "date_blockers": dict(sorted(blockers.items(), key=lambda kv: -kv[1])),
    }


def coverage_metrics(
    resolved: Mapping[str, list[Segment]],
    spans: Mapping[str, MembershipSpan],
    canonical_start: date,
) -> dict[str, object]:
    """Interval-level metrics over the canonical period (intervals touching it). An interval
    counts as resolved only if EVERY canonical-period segment is backtestable."""
    total = exact = multi = prov = unres = 0
    for key, segs in resolved.items():
        sp = spans[key]
        if sp.effective_to is not None and sp.effective_to <= canonical_start:
            continue
        canon = [s for s in segs if s.end is None or s.end > canonical_start]
        total += 1
        sts = {s.status for s in canon}
        if sts <= BACKTESTABLE:
            if IdentityResolutionStatus.MULTI_SOURCE_CONFIRMED in sts:
                multi += 1
            else:
                exact += 1
        elif IdentityResolutionStatus.UNRESOLVED in sts and not (sts & BACKTESTABLE):
            unres += 1
        else:
            prov += 1
    pct = round(100.0 * (exact + multi) / total, 1) if total else 0.0
    return {
        "intervals_total": total,
        "resolved_exact": exact,
        "resolved_multi_source": multi,
        "provisional": prov,
        "unresolved": unres,
        "coverage_percentage": pct,
    }
