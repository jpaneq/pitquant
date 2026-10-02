# ruff: noqa: E501
"""S&P 500 membership EVIDENCE (D-02 candidate, ADR-0025): official announcements → events.

* Tier 1 ``OFFICIAL_SPDJI``: releases on press.spglobal.com (S&P Global's own archive).
* Tier 2 ``OFFICIAL_REPUBLISHED``: PRNewswire copies (Wayback ``id_`` captures) of S&P releases.
* Tier 3 ``DISCOVERY_ONLY``: community CSV rows. They only say WHERE to look; they never
  become membership.

Temporal model: a release states a change date and a TIMING («after the close of trading on»,
«prior to the open of trading on»). ``effective_at`` is the OPEN of the first NYSE session at
which the change is in force (real calendar, never +1 calendar day): after the close of Monday
2011-01-03 → open of 2011-01-04; after the close of Friday 2011-04-01 → Monday 2011-04-04.
A universe «at the start of session s» contains a ticker iff ``effective_at(add) <= open(s)`` and
not ``effective_at(remove) <= open(s)``. A release with a date «to be announced» proves intent,
NOT a date (``TBA``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum

from pitquant.core.errors import DataQualityError
from pitquant.data.calendars.market_calendar import get_calendar

PARSER_VERSION = "sp500-evidence-2"


class Timing(StrEnum):
    AFTER_CLOSE = "AFTER_CLOSE"
    BEFORE_OPEN = "BEFORE_OPEN"
    EFFECTIVE_ON_DATE = "EFFECTIVE_ON_DATE"
    TBA = "TBA"
    UNKNOWN = "UNKNOWN"


class SourceTier(StrEnum):
    OFFICIAL_SPDJI = "OFFICIAL_SPDJI"
    OFFICIAL_REPUBLISHED = "OFFICIAL_REPUBLISHED"
    DISCOVERY_ONLY = "DISCOVERY_ONLY"


class EventStatus(StrEnum):
    OFFICIAL_CONFIRMED = "OFFICIAL_CONFIRMED"
    OFFICIAL_REPUBLISHED_CONFIRMED = "OFFICIAL_REPUBLISHED_CONFIRMED"
    DISCOVERY_ONLY = "DISCOVERY_ONLY"
    DATE_TBA = "DATE_TBA"
    CONFLICT = "CONFLICT"
    UNRESOLVED = "UNRESOLVED"


CANONICAL_STATUSES = {EventStatus.OFFICIAL_CONFIRMED, EventStatus.OFFICIAL_REPUBLISHED_CONFIRMED}


def effective_at(timing: Timing, stated: date | None, exchange: str = "XNYS") -> datetime | None:
    """Open of the first session in which the change is in force (UTC)."""
    if timing in (Timing.TBA, Timing.UNKNOWN) or stated is None:
        return None
    cal = get_calendar(exchange)
    if timing is Timing.AFTER_CLOSE:
        if not cal.is_session(stated):
            raise DataQualityError(f"after-close change on {stated}: not a {exchange} session")
        return cal.session_open(cal.next_session(stated))
    if timing is Timing.BEFORE_OPEN:
        if not cal.is_session(stated):
            raise DataQualityError(f"before-open change on {stated}: not a {exchange} session")
        return cal.session_open(stated)
    return cal.session_open(cal.session_on_or_after(stated))  # EFFECTIVE_ON_DATE


def effective_session(timing: Timing, stated: date | None, exchange: str = "XNYS") -> date | None:
    e = effective_at(timing, stated, exchange)
    if e is None:
        return None
    cal = get_calendar(exchange)
    return cal.session_on_or_after(e.astimezone(UTC).date())


# ───────────────────────────────────────── parsing ───────────────────────────────────────
_MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}  # fmt: skip
_WD = {d: i for i, d in enumerate(("mon", "tue", "wed", "thu", "fri", "sat", "sun"))}
_DATE = (
    r"(?:(Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day,?\s+)?"
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})(?:,?\s+(\d{4}))?"
)
_TICK = r"\((?:[A-Za-z][A-Za-z /]{1,18})\s*:\s*([A-Z][A-Za-z0-9.\-]{0,9})\s*\)"
_NAME = r"([A-Z0-9][^():;]{1,90}?)\s*"
_REPLACE = re.compile(
    rf"{_NAME}{_TICK}\s+will replace\s+{_NAME}{_TICK}\s+in the S&P 500(?!\s+(?:GICS|Barra|Pure|Growth|Value))"
)
_TIMING = re.compile(
    rf"(?P<tba>(?:after the close of trading|prior to the open of trading|effective)?\s*on a date to be announced)|"
    rf"(?P<after>after the (?:market )?close of trading(?: on)?)\s*{_DATE}|"
    rf"(?P<before>(?:effective )?prior to the open(?:ing)? (?:of trading )?(?:on trading )?on)\s*{_DATE}|"
    rf"(?P<eff>effective (?:on )?)\s*{_DATE}",
    re.I,
)
_HEADER = re.compile(rf"S&P 500 INDEX\s*[–-]\s*(?:{_DATE}|TBA)", re.I)
_REASONS = (
    ("BANKRUPTCY", r"bankruptcy|chapter 11"),
    ("SPINOFF", r"spinning off|spin-off|spin off"),
    ("MERGER_OR_ACQUISITION", r"acquir|merg|buyout|take[- ]private"),
    ("NO_LONGER_REPRESENTATIVE", r"no longer (?:representative|eligible)|ranked near"),
)


@dataclass
class ParsedChange:
    added_ticker: str
    added_name: str
    removed_ticker: str
    removed_name: str
    timing: Timing
    stated_change_date: date | None
    header_date: date | None
    reason_class: str
    excerpt: str
    notes: list[str] = field(default_factory=list)


def _quad(g: tuple[str | None, ...]) -> tuple[str | None, ...]:
    """The date groups (weekday, month, day, year) of whichever alternative matched."""
    for i in range(0, len(g) - 3):
        mon = g[i + 1]
        if mon is not None and g[i + 2] is not None and mon[:3].lower() in _MONTHS:
            return g[i : i + 4]
    return (None, None, None, None)


def _mk_date(g: tuple[str | None, ...], announced: date) -> date | None:
    wd, mon, day, year = _quad(g)
    if mon is None or day is None:
        return None
    m, d = _MONTHS[mon[:3].lower()], int(day)
    years = [int(year)] if year else [announced.year, announced.year + 1]
    for y in years:
        try:
            cand = date(y, m, d)
        except ValueError:
            continue
        in_window = year or announced - timedelta(days=3) <= cand <= announced + timedelta(days=200)
        if in_window and (wd is None or cand.weekday() == _WD[wd[:3].lower()]):
            return cand
    return None


_TICK_NAME = re.compile(rf"([A-Z0-9][^():;]{{1,90}}?)\s*{_TICK}")
_NOT_500 = r"(?!\s+(?:GICS|Barra|Pure|Growth|Value))"
_LIST_END = re.compile(rf"in the S&P 500{_NOT_500}")


_TABLE = re.compile(
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},\s+\d{4})\s+S&P 500\s+"
    r"(Addition|Deletion)\s+.+?\s+([A-Z][A-Z0-9.\-]{0,6})\s+"
    r"(?:Communication|Consumer|Energy|Financials|Health|Industrials|Information|Materials|Real|Utilities)"
)


def _summary_table(text: str, announced: date) -> dict[tuple[str, str], date]:
    """Modern releases end with «Effective Date | Index | Action | Company | Ticker» rows:
    {(ticker, 'Addition'|'Deletion'): date}, timing «prior to the open … on the effective date»."""
    if "prior to the open of trading on the effective date" not in text:
        return {}
    out: dict[tuple[str, str], date] = {}
    for m in _TABLE.finditer(text):
        dm = re.match(r"([A-Za-z]+)\.?\s+(\d{1,2}),\s+(\d{4})", m.group(1))
        d = _mk_date((None, *dm.groups()), announced) if dm else None
        if d is not None:
            out[(m.group(3).upper(), m.group(2))] = d
    return out


def _clean_name(n: str) -> str:
    n = re.sub(r"^.*\bconstituents?\s+", "", n.strip())
    return re.sub(r"^(?:and|,)\s+", "", n).strip()


def _list_clauses(text: str) -> list[tuple[str, str, str, str, int, int]]:
    """«A (T) and B (T) will replace C (T) and D (T) in the S&P 500 [respectively]»: N subjects
    and N objects pair POSITIONALLY. (add_name, add_t, rem_name, rem_t, clause_start, clause_end)"""
    out: list[tuple[str, str, str, str, int, int]] = []
    for pm in re.finditer(r"will replace", text):
        p = pm.end()
        qm = _LIST_END.search(text, p, p + 420)
        if qm is None:
            continue
        mid = text[p : qm.start()]
        if "in the S&P" in mid:
            continue
        objs = _TICK_NAME.findall(mid)
        n = len(objs)
        if n < 2:
            continue  # single pairs are handled by the main pattern
        head_start = max(0, pm.start() - 140 * n)
        subs = [
            (m.group(1), m.group(2), m.start())
            for m in _TICK_NAME.finditer(text, head_start, pm.start())
        ]
        if len(subs) < n:
            continue
        subs = subs[-n:]
        for (an, at, _), (rn, rt) in zip(subs, objs, strict=True):
            out.append(
                (_clean_name(an), at.upper(), _clean_name(rn), rt.upper(), subs[0][2], qm.end())
            )
    return out


_ADD_ONLY = re.compile(
    rf"{_NAME}{_TICK}\s+(?:was|will be) added to the S&P 500{_NOT_500}(?:\s+(?:on|effective)\s*{_DATE})?"
)


def _added_only(text: str, announced: date) -> list[ParsedChange]:
    """Spin-off / temporary additions without a simultaneous deletion (never 1 add = 1 delete)."""
    out: list[ParsedChange] = []
    for m in _ADD_ONLY.finditer(text):
        name, tick = m.group(1).strip(), m.group(2).upper()
        stated = _mk_date(m.groups(), announced)
        was = "was added" in text[m.start() : m.end()]
        tail = text[m.end() : m.end() + 300]
        reason = (
            "SPINOFF" if re.search(r"spun off|spinning off|spin-off", tail, re.I) else "UNSPECIFIED"
        )
        timing = Timing.EFFECTIVE_ON_DATE if stated is not None else Timing.UNKNOWN
        notes = ["addition without a simultaneous deletion"]
        if was and stated is None:
            notes.append("past-tense addition without a date")
        out.append(ParsedChange(tick, _clean_name(name), "", "", timing, stated, None, reason,
                                text[max(0, m.start() - 20) : m.end() + 200][:420], notes))  # fmt: skip
    return out


def parse_release(text: str, announced: date) -> list[ParsedChange]:
    """Every «X (EXCH: A) will replace Y (EXCH: B) in the S&P 500» clause of ONE release, with
    the nearest timing phrase after it and, cross-checking, the date of the «S&P 500 INDEX –»
    summary header. Clauses about other indices are ignored."""
    text = re.sub(r"\s+", " ", text)
    header: date | None = None
    hms = list(_HEADER.finditer(text))
    hm = hms[0] if len(hms) == 1 else None  # several headers = several dates: no cross-check
    hdr_tba = False
    table = _summary_table(text, announced)
    if hm:
        header = _mk_date(hm.groups(), announced)
        hdr_tba = header is None
    out: list[ParsedChange] = []
    clauses: list[tuple[str, str, str, str, int, int]] = [
        (m.group(1).strip(), m.group(2), m.group(3).strip(), m.group(4), m.start(), m.end())
        for m in _REPLACE.finditer(text)
    ]
    seen_pairs = {(c[1].upper(), c[3].upper()) for c in clauses}
    clauses += [c for c in _list_clauses(text) if (c[1], c[3]) not in seen_pairs]
    for add_name, add_t, rem_name, rem_t, c_start, c_end in clauses:
        add_t, rem_t = add_t.upper(), rem_t.upper()
        tail = text[c_end : c_end + 700]
        timing, stated = Timing.UNKNOWN, None
        notes: list[str] = []
        # the first timing phrase after the clause (chained sentences share ONE phrase at the
        # end); the «S&P 500 INDEX –» summary header is the cross-check
        for tm in _TIMING.finditer(tail):
            if tm.group("tba"):
                timing = Timing.TBA
                break
            dm = _mk_date(tm.groups(), announced)
            if dm is None:
                continue
            stated = dm
            timing = (
                Timing.AFTER_CLOSE if tm.group("after")
                else Timing.BEFORE_OPEN if tm.group("before")
                else Timing.EFFECTIVE_ON_DATE
            )  # fmt: skip
            break
        if (
            timing is Timing.UNKNOWN
        ):  # «will make the following changes … after the close on D:» form
            head = text[max(0, c_start - 400) : c_start]
            last = None
            for hm2 in _TIMING.finditer(head):
                if len(head) - hm2.end() < 60:
                    last = hm2
            if last is not None:
                if last.group("tba"):
                    timing = Timing.TBA
                elif (dm2 := _mk_date(last.groups(), announced)) is not None:
                    stated = dm2
                    timing = (
                        Timing.AFTER_CLOSE if last.group("after")
                        else Timing.BEFORE_OPEN if last.group("before")
                        else Timing.EFFECTIVE_ON_DATE
                    )  # fmt: skip
        if timing is Timing.UNKNOWN:
            ad = table.get((add_t, "Addition"))
            if ad is not None and table.get((rem_t, "Deletion"), ad) == ad:
                timing, stated = Timing.BEFORE_OPEN, ad
                notes.append("date from the release's effective-date summary table")
        if (
            timing is Timing.UNKNOWN
        ):  # intro: «will make the following changes … effective prior to the open …»
            intro = text[max(0, c_start - 3000) : c_start]
            for im in _TIMING.finditer(intro):
                ctx = intro[max(0, im.start() - 160) : im.start()]
                if (
                    "following changes" in ctx
                    and (dm3 := _mk_date(im.groups(), announced)) is not None
                ):
                    stated = dm3
                    timing = (
                        Timing.AFTER_CLOSE
                        if im.group("after")
                        else Timing.BEFORE_OPEN
                        if im.group("before")
                        else Timing.EFFECTIVE_ON_DATE
                    )
        if timing is Timing.UNKNOWN and hdr_tba:
            timing = Timing.TBA
        if header is not None and stated is not None and header != stated:
            notes.append(f"summary header date {header} != prose date {stated}")
        reason = "UNSPECIFIED"
        for label, rx in _REASONS:
            if re.search(rx, tail[:400], re.I):
                reason = label
                break
        out.append(
            ParsedChange(
                add_t.upper(),
                add_name,
                rem_t.upper(),
                rem_name,
                timing,
                stated,
                header,
                reason,
                text[max(0, c_start - 20) : c_end + 160][:420],
                notes,
            )
        )
    out += [
        c
        for c in _added_only(text, announced)
        if c.added_ticker not in {x.added_ticker for x in out}
    ]
    return out


# ───────────────────────────────────────── discovery ─────────────────────────────────────
@dataclass(frozen=True)
class DiscoveryRow:
    row_date: date
    added: tuple[str, ...]
    removed: tuple[str, ...]


def _tk(x: object) -> str:
    """'RVTY (PREVIOUSLY PKI)' -> 'RVTY' (discovery noise; the old ticker is not evidence)."""
    return str(x).split(" (")[0].strip().upper()


def parse_discovery_csv(data: bytes, since: date) -> list[DiscoveryRow]:
    """``date,added_tickers,removed_tickers`` with Python-list cells. Discovery ONLY."""
    import ast
    import csv
    import io

    out: list[DiscoveryRow] = []
    for r in csv.DictReader(io.StringIO(data.decode("utf-8"))):
        d = date.fromisoformat(r["date"])
        if d < since:
            continue
        add = tuple(
            _tk(x) for x in (ast.literal_eval(r["added_tickers"]) if r["added_tickers"] else [])
        )
        rem = tuple(
            _tk(x) for x in (ast.literal_eval(r["removed_tickers"]) if r["removed_tickers"] else [])
        )
        out.append(DiscoveryRow(d, add, rem))
    # the community file may split one change over several rows of the same date (an addition in
    # one row, the matching deletion in another): merge by date so a pair is judged as a pair
    merged: dict[date, tuple[list[str], list[str]]] = {}
    for row in out:
        ma, mb = merged.setdefault(row.row_date, ([], []))
        ma += [t for t in row.added if t not in ma]
        mb += [t for t in row.removed if t not in mb]
    return [DiscoveryRow(d, tuple(ma), tuple(mb)) for d, (ma, mb) in sorted(merged.items())]


# ───────────────────────────────────────── matching ──────────────────────────────────────
@dataclass(frozen=True)
class Announcement:
    """One parsed clause with its document context."""

    tier: SourceTier
    url: str
    sha256: str
    announced_on: date
    change: ParsedChange


@dataclass
class EventResult:
    row: DiscoveryRow
    added: str | None
    removed: str | None
    status: EventStatus
    reason: str
    announcement: Announcement | None = None
    effective_session: date | None = None


def match_discovery(rows: list[DiscoveryRow], anns: list[Announcement]) -> list[EventResult]:
    """Per discovery row and per (added, removed) pair found in the evidence. Never edits the
    official data to fit the discovery row: a date mismatch is a CONFLICT."""
    out: list[EventResult] = []
    for row in rows:
        used_add: set[str] = set()
        used_rem: set[str] = set()
        cands = [
            a for a in anns
            if (a.change.added_ticker in row.added or (a.change.removed_ticker != '' and a.change.removed_ticker in row.removed))
            and abs((a.announced_on - row.row_date).days) <= 120
        ]  # fmt: skip

        # prefer: both tickers match, a concrete date, tier 1 over tier 2, latest announcement
        def rank(a: Announcement, row: DiscoveryRow = row) -> tuple[int, int, int, date]:
            both = int(
                a.change.added_ticker in row.added and a.change.removed_ticker in row.removed
            )
            concrete = int(a.change.stated_change_date is not None)
            tier = int(a.tier is SourceTier.OFFICIAL_SPDJI)
            return (both, concrete, tier, a.announced_on)

        for a in sorted(cands, key=rank, reverse=True):
            c = a.change
            if c.added_ticker in used_add or (
                c.removed_ticker != "" and c.removed_ticker in used_rem
            ):
                continue
            both = c.added_ticker in row.added and (
                c.removed_ticker == "" or c.removed_ticker in row.removed
            )
            used_add.add(c.added_ticker)
            if c.removed_ticker:
                used_rem.add(c.removed_ticker)
            if c.timing is Timing.TBA:
                out.append(EventResult(row, c.added_ticker, c.removed_ticker or None, EventStatus.DATE_TBA,
                                       "release states a date to be announced", a))  # fmt: skip
                continue
            try:
                eff = effective_session(c.timing, c.stated_change_date)
            except DataQualityError as e:
                out.append(
                    EventResult(
                        row, c.added_ticker, c.removed_ticker, EventStatus.UNRESOLVED, str(e), a
                    )
                )
                continue
            if eff is None:
                out.append(EventResult(row, c.added_ticker, c.removed_ticker or None, EventStatus.UNRESOLVED,
                                       "no resolvable date/timing in the release", a))  # fmt: skip
            elif eff != row.row_date:
                out.append(EventResult(row, c.added_ticker, c.removed_ticker or None, EventStatus.CONFLICT,
                                       f"official effective session {eff} != discovery date {row.row_date}", a, eff))  # fmt: skip
            else:
                st = (EventStatus.OFFICIAL_CONFIRMED if a.tier is SourceTier.OFFICIAL_SPDJI
                      else EventStatus.OFFICIAL_REPUBLISHED_CONFIRMED)  # fmt: skip
                out.append(
                    EventResult(
                        row,
                        c.added_ticker,
                        c.removed_ticker or None,
                        st,
                        "official evidence matches"
                        if both
                        else "official pair confirms the discovery side on the same session; discovery lacks the counterpart",
                        a,
                        eff,
                    )
                )
        for t in row.added:
            if t not in used_add:
                out.append(
                    EventResult(
                        row,
                        t,
                        None,
                        EventStatus.DISCOVERY_ONLY,
                        "no official evidence found for this addition",
                    )
                )
        for t in row.removed:
            if t not in used_rem:
                out.append(
                    EventResult(
                        row,
                        None,
                        t,
                        EventStatus.DISCOVERY_ONLY,
                        "no official evidence found for this removal",
                    )
                )
    claimed = {
        (
            r.announcement.change.added_ticker,
            r.announcement.change.removed_ticker,
            r.announcement.url,
        )
        for r in out
        if r.announcement is not None
    }
    pairs_done = {(a, b) for a, b, _ in claimed}
    for a in anns:
        c = a.change
        if (c.added_ticker, c.removed_ticker, a.url) in claimed or (
            c.added_ticker,
            c.removed_ticker,
        ) in pairs_done:
            continue
        try:
            eff = effective_session(c.timing, c.stated_change_date)
        except DataQualityError:
            eff = None
        if eff is None or eff < date(2011, 1, 1) or c.timing is Timing.TBA:
            continue  # TBA / unresolvable releases are not events by themselves
        st = (
            EventStatus.OFFICIAL_CONFIRMED
            if a.tier is SourceTier.OFFICIAL_SPDJI
            else EventStatus.OFFICIAL_REPUBLISHED_CONFIRMED
        )
        out.append(
            EventResult(
                DiscoveryRow(eff, (), ()),
                c.added_ticker or None,
                c.removed_ticker or None,
                st,
                "official announcement without a discovery row (discovery list incomplete)",
                a,
                eff,
            )
        )
        pairs_done.add((c.added_ticker, c.removed_ticker))
    return out


# ───────────────────────────────────────── replay ────────────────────────────────────────
@dataclass(frozen=True)
class ReplayEvent:
    effective_session: date
    added: str | None
    removed: str | None


def undo_events(current: set[str], events: list[ReplayEvent]) -> set[str]:
    """Walk backwards from the anchor applying every event in reverse."""
    s = set(current)
    for e in sorted(events, key=lambda x: x.effective_session, reverse=True):
        if e.added is not None:
            if e.added not in s:
                raise DataQualityError(f"undo {e.effective_session}: {e.added} not in the set")
            s.discard(e.added)
        if e.removed is not None:
            if e.removed in s:
                raise DataQualityError(
                    f"undo {e.effective_session}: {e.removed} already in the set"
                )
            s.add(e.removed)
    return s


def replay_events(start: set[str], events: list[ReplayEvent]) -> set[str]:
    s = set(start)
    for e in sorted(events, key=lambda x: x.effective_session):
        if e.removed is not None:
            if e.removed not in s:
                raise DataQualityError(f"replay {e.effective_session}: {e.removed} not in the set")
            s.discard(e.removed)
        if e.added is not None:
            if e.added in s:
                raise DataQualityError(
                    f"replay {e.effective_session}: {e.added} already in the set"
                )
            s.add(e.added)
    return s


def members_at_open(base: set[str], events: list[ReplayEvent], session: date) -> set[str]:
    """Membership at the START of ``session``: events effective on or before it applied."""
    return replay_events(base, [e for e in events if e.effective_session <= session])
