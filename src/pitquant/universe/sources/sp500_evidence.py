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

PARSER_VERSION = "sp500-evidence-8"


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
_RENAMED = r"(?:,\s*to be renamed\s+[^,():;]{1,40},)?"  # «Westar Energy Inc. (NYSE: WR), to be renamed Evergy, will replace …»
_REPLACE = re.compile(
    rf"{_NAME}{_TICK}{_RENAMED}\s+will replace\s+{_NAME}{_TICK}\s+in the S&P 500(?!\s+(?:GICS|Barra|Pure|Growth|Value))"
)
_TIMING = re.compile(
    rf"(?P<tba>(?:after the close of trading|prior to the open of trading|effective)?\s*on a date to be announced)|"
    rf"(?P<after>after the (?:market )?close of trading(?: on)?)\s*{_DATE}|"
    rf"(?P<before>(?:effective )?(?:prior to|before|at) the open(?:ing)? (?:of trading )?(?:on trading )?on)\s*{_DATE}|"
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
    n = re.sub(r"^.*?PRNewswire\s*/\s*--\s*", "", n.strip())  # release dateline
    n = re.sub(r"^.*?\bannounced on [A-Z][a-z]+\.? \d{1,2}\s*,\s*", "", n)
    n = re.sub(r"^.*\bwill replace\s+", "", n)
    n = re.sub(r"^.*\bconstituents?\s+", "", n)
    return re.sub(r"^(?:and|,)\s+", "", n).strip()


_MULTI_TICK = re.compile(
    r"([A-Z0-9][^():;]{1,90}?)\s*\(\s*([A-Za-z][A-Za-z /]{1,18})\s*:\s*([A-Z][A-Za-z0-9.\-]{0,9}(?:\s*[;/]\s*[A-Z][A-Za-z0-9.\-]{0,9})+)\s*\)"
)
_CORP_SUFFIX = {
    "inc",
    "corp",
    "corporation",
    "co",
    "company",
    "ltd",
    "limited",
    "plc",
    "holdings",
    "group",
    "the",
    "and",
}


def _expand_multi_tickers(text: str) -> str:
    """«Fox Corp. (NASD: FOXAV; FOXBV)» / «Under Armour Inc. (NYSE:UA/UAA)» (several share-class tickers of ONE company) become
    «Fox Corp. (NASD: FOXAV) and Fox Corp. (NASD: FOXBV)» so every ticker is its own enumerated leg; the company name is repeated, so the
    class of each ticker is NOT inferred here (the identity layer matches by the set of classes)."""

    def rep(m: re.Match[str]) -> str:
        name, ex = m.group(1).strip(), m.group(2)
        ticks = re.split(r"\s*[;/]\s*", m.group(3).strip())
        return " and ".join(f"{name} ({ex}: {t})" for t in ticks)

    return _MULTI_TICK.sub(rep, text)


def name_key(name: str) -> str:
    """Normalised company name for exact lookups across releases (corporate suffixes dropped, no fuzzy matching)."""
    words = re.sub(r"[^a-z0-9& ]+", " ", name.lower()).split()
    return " ".join(w for w in words if w not in _CORP_SUFFIX)


def collect_name_tickers(text: str) -> list[tuple[str, str]]:
    """(name_key, ticker) pairs «Company Inc. (EXCH: T)» of ONE release text, for resolving a removed company that a later release names
    WITHOUT a ticker. Only the pairs are returned; the caller decides which releases may be used (never later than the release it helps)."""
    text = _expand_multi_tickers(re.sub(r"\s+", " ", text))
    return [
        (name_key(_clean_name(n)), t.upper())
        for n, t in _TICK_NAME.findall(text)
        if name_key(_clean_name(n))
    ]


def _group_companies(items: list[tuple[str, str]]) -> list[list[tuple[str, str]]]:
    """Consecutive (name, ticker) entries of the SAME company (several share classes) form one group."""
    groups: list[list[tuple[str, str]]] = []
    for name, tk in items:
        if groups and name_key(_clean_name(groups[-1][-1][0])) == name_key(_clean_name(name)):
            groups[-1].append((name, tk))
        else:
            groups.append([(name, tk)])
    return groups


def _list_clauses(text: str) -> list[tuple[str, str, str, str, int, int]]:
    """«A (T) and B (T) will replace C (T) and D (T) in the S&P 500 [respectively]»: N subject COMPANIES and N object companies pair
    POSITIONALLY. A company with several share-class tickers (``_expand_multi_tickers``) is ONE company: classes pair 1:1 when both
    sides list the same number of them; otherwise each ticker becomes its own add-only / remove-only leg with the clause date (the
    set of classes moves together; which class replaces which is not stated). (add_name, add_t, rem_name, rem_t, start, end)"""
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
        if len(objs) < 2:
            continue  # single pairs are handled by the main pattern
        ogroups = _group_companies(objs)
        n = len(ogroups)
        head_start = max(0, pm.start() - 140 * len(objs))
        subs = [
            (m.group(1), m.group(2), m.start())
            for m in _TICK_NAME.finditer(text, head_start, pm.start())
        ]
        sgroups = _group_companies([(a, b) for a, b, _ in subs])
        if len(sgroups) < n:
            continue
        sgroups = sgroups[-n:]
        flat = [x for g in sgroups for x in g]
        start = next(st for (a_, b_, st) in subs if (a_, b_) == flat[0])
        for sg, og in zip(sgroups, ogroups, strict=True):
            if len(sg) == len(og):
                pairs = [(sa, ra) for sa, ra in zip(sg, og, strict=True)]
                for (an, at), (rn, rt) in pairs:
                    out.append(
                        (_clean_name(an), at.upper(), _clean_name(rn), rt.upper(), start, qm.end())
                    )
            else:
                for an, at in sg:
                    out.append((_clean_name(an), at.upper(), "", "", start, qm.end()))
                for rn, rt in og:
                    out.append(("", "", _clean_name(rn), rt.upper(), start, qm.end()))
    return out


_CONSTITUENTS = re.compile(r"constituents?\s", re.I)


def _subjects_before(text: str, verb_start: int) -> list[tuple[str, str, int]]:
    """Companies enumerated between the nearest preceding «constituents» marker and the verb. The whole
    enumeration is taken (never just as many as the object list has) so unequal lists are detected."""
    window_start = max(0, verb_start - 900)
    marks = list(_CONSTITUENTS.finditer(text, window_start, verb_start))
    if not marks:
        return []
    start = marks[-1].end()
    return [
        (m.group(1), m.group(2), m.start()) for m in _TICK_NAME.finditer(text, start, verb_start)
    ]


_MOVE = re.compile(
    r"will (?:all )?move to the S&P 500,?\s+(?:replacing|switching places with)\s+(?:S&P (?:MidCap 400|SmallCap 600|500) constituents?\s+)?"
)


def _move_clauses(text: str) -> list[tuple[str, str, str, str, int, int]]:
    """«S&P MidCap 400 constituents A (T), B (T) and C (T) will move to the S&P 500, replacing|switching
    places with D (T), E (T) and F (T) [respectively]»: N subjects, the FIRST N tickers after the verb
    pair positionally (the quarterly-rebalance form, ADR-0031)."""
    out: list[tuple[str, str, str, str, int, int]] = []
    for mm in _MOVE.finditer(text):
        seg = text[mm.end() : mm.end() + 700]
        cut = [
            k
            for k in (
                re.search(
                    r"all of which|respectively|will move to|is acquiring|are acquiring|will be (?:added|removed)",
                    seg,
                ),
            )
            if k
        ]
        seg = seg[: cut[0].start()] if cut else seg
        objs = _TICK_NAME.findall(seg)
        subs = _subjects_before(text, mm.start())
        n = min(len(subs), len(objs))
        if n == 0:
            continue
        if len(subs) != len(objs):
            continue  # unequal lists: positional pairing would be a guess
        subs = subs[-n:]
        for (an, at, _), (rn, rt) in zip(subs, objs[:n], strict=True):
            out.append(
                (
                    _clean_name(an),
                    at.upper(),
                    _clean_name(rn),
                    rt.upper(),
                    subs[0][2],
                    mm.end() + len(seg),
                )
            )
    return out


_SWITCH = re.compile(r"will switch places with")


def _switch_clauses(text: str) -> list[tuple[str, str, str, str, int, int]]:
    """«S&P MidCap 400 constituents A (T) and B (T) will switch places with C (T) and D (T) respectively in the
    S&P 500»: only when the clause itself ends in the S&P 500 (never MidCap/SmallCap)."""
    out: list[tuple[str, str, str, str, int, int]] = []
    for mm in _SWITCH.finditer(text):
        qm = _LIST_END.search(text, mm.end(), mm.end() + 420)
        if qm is None or "in the S&P" in text[mm.end() : qm.start()]:
            continue
        objs = _TICK_NAME.findall(text[mm.end() : qm.start()])
        if not objs:
            continue
        subs = _subjects_before(text, mm.start())
        if len(subs) != len(objs):
            continue
        for (an, at, _), (rn, rt) in zip(subs, objs, strict=True):
            out.append(
                (_clean_name(an), at.upper(), _clean_name(rn), rt.upper(), subs[0][2], qm.end())
            )
    return out


_ADD_TIMED = re.compile(rf"{_NAME}{_TICK}\s+(?:will be|was) added to the S&P 500{_NOT_500}")
_REMOVED = re.compile(r"(both of )?which will be removed from the S&P 500")


def _timing_after(
    text: str, pos: int, announced: date, horizon: int = 220
) -> tuple[Timing, date | None]:
    tail = text[pos : pos + horizon]
    for tm in _TIMING.finditer(tail):
        if tm.group("tba"):
            return Timing.TBA, None
        dm = _mk_date(tm.groups(), announced)
        if dm is None:
            continue
        timing = (
            Timing.AFTER_CLOSE if tm.group("after")
            else Timing.BEFORE_OPEN if tm.group("before")
            else Timing.EFFECTIVE_ON_DATE
        )  # fmt: skip
        return timing, dm
    return Timing.UNKNOWN, None


def _timed_adds_removes(
    text: str, announced: date, name_tickers: dict[str, set[str]] | None = None
) -> list[ParsedChange]:
    """Two-sided changes whose legs have DIFFERENT dates: «A (T) will be added to the S&P 500 prior to the open on
    D1 … B (T), which will be removed from the S&P 500 effective prior to the open on D2». Each leg is its own
    change (an add-only and a remove-only): the 501-member interval between them is real (ADR-0031)."""
    out: list[ParsedChange] = []
    for m in _ADD_TIMED.finditer(text):
        timing, stated = _timing_after(text, m.end(), announced)
        if timing is Timing.UNKNOWN:
            continue
        group = [(m.group(1), m.group(2))]
        pos = m.start()
        while True:  # «A (T) and B (T) will be added»: walk back over the enumeration
            prev = [x for x in _TICK_NAME.finditer(text, max(0, pos - 160), pos)]
            if not prev or not re.fullmatch(r"\s*(?:,\s*)?(?:and\s+)?", text[prev[-1].end() : pos]):
                break
            group.insert(0, (prev[-1].group(1), prev[-1].group(2)))
            pos = prev[-1].start()
        for name, tk in group:
            out.append(ParsedChange(tk.upper(), _clean_name(name), "", "", timing, stated, None, "UNSPECIFIED",
                                    text[max(0, m.start() - 20) : m.end() + 200][:420],
                                    ["add leg with its own date; the removal leg is a separate change"]))  # fmt: skip
    for m in _REMOVED.finditer(text):
        before = text[max(0, m.start() - 320) : m.start()]
        timing, stated = _timing_after(text, m.end(), announced)
        if timing is Timing.UNKNOWN:
            continue
        ticks = _enumerated_ticks_before(before)
        if ticks:
            # the ticker(s) sit RIGHT before «, which will be removed»: «B (T), which …» or «A (T) and B (T), both of which …»
            for name, tk in ticks:
                out.append(ParsedChange("", "", tk.upper(), _clean_name(name), timing, stated, None, "UNSPECIFIED",
                                        text[max(0, m.start() - 160) : m.end() + 160][:420],
                                        ["removal leg with its own date; the add leg is a separate change"]))  # fmt: skip
            continue
        # «… , replacing HollyFrontier, which will be removed …»: the removed company is named WITHOUT a ticker. v3 took the nearest
        # earlier ticker (the ADDED company's): never. The ticker must come from an exact-name mention in the SAME release or in an EARLIER
        # official release (``name_tickers``), and it must be unique.
        rm = re.search(r"replacing\s+([A-Z][^():;,]{1,60}?)\s*,?\s*$", before)
        if rm is None:
            continue
        rname = _clean_name(rm.group(1))
        cands = {
            t.upper()
            for n, t in _TICK_NAME.findall(text)
            if name_key(_clean_name(n)) == name_key(rname)
        }
        src = "the same release"
        if not cands and name_tickers:
            cands = set(name_tickers.get(name_key(rname), set()))
            src = "an earlier official S&P release (exact company name)"
        if len(cands) != 1:
            continue
        out.append(ParsedChange("", "", next(iter(cands)), rname, timing, stated, None, "UNSPECIFIED",
                                text[max(0, m.start() - 160) : m.end() + 160][:420],
                                [f"removal leg with its own date; removed company named without ticker, ticker from {src}"]))  # fmt: skip
    return out


def _enumerated_ticks_before(before: str) -> list[tuple[str, str]]:
    """The «A (T) and B (T)» enumeration that ends exactly at the end of ``before`` (separators: «, », « and », « both of »)."""
    ms = list(_TICK_NAME.finditer(before))
    if not ms or not re.fullmatch(r"\s*,?\s*", before[ms[-1].end() :]):
        return []
    last = ms[-1]
    group = [(last.group(1), last.group(2))]
    pos = last.start()
    while True:
        prev = list(_TICK_NAME.finditer(before, 0, pos))
        if not prev or not re.fullmatch(
            r"\s*(?:,\s*)?(?:and\s+)?(?:both of\s+)?", before[prev[-1].end() : pos]
        ):
            break
        group.insert(0, (prev[-1].group(1), prev[-1].group(2)))
        pos = prev[-1].start()
    return group


_NAME_ONLY = re.compile(
    rf"{_NAME}{_TICK}\s+will replace\s+([A-Z][^():;,]{{1,60}}?)\s+in the S&P 500{_NOT_500}"
)


def _name_only_clauses(text: str) -> list[tuple[str, str, str, str, int, int]]:
    """«Verisk (T) will replace Joy Global in the S&P 500»: the removed company is named only; its ticker
    must appear once, earlier in the SAME release as «Joy Global Inc. (NYSE: JOY)». Otherwise no clause."""
    out: list[tuple[str, str, str, str, int, int]] = []
    for m in _NAME_ONLY.finditer(text):
        rname = re.sub(r"\s+", " ", m.group(3)).strip()
        rname = re.sub(r"['’]s$", "", rname)
        rname = re.sub(r"[ ,]+(?:Inc|Corp|Co|Ltd|plc|Group)\.?$", "", rname).strip()
        mentions = [
            (_clean_name(n), t.upper())
            for n, t in _TICK_NAME.findall(text[: m.start()])
            if name_key(_clean_name(n)) == name_key(rname)
        ]
        found = {t for _, t in mentions}
        if len(found) != 1:
            continue
        out.append(
            (m.group(1).strip(), m.group(2), mentions[0][0], next(iter(found)), m.start(), m.end())
        )
    return out


def _summary_backed_pairs(text: str) -> list[tuple[str, str, str, str, int, int]]:
    """An index-less prose pair needs BOTH exact names in a dated S&P 500 summary.

    Some releases state the destination index only in their summary (FBHS/CVC, 2016).
    Never infer it from the title, a nearby other-index clause, or a GICS description.
    """
    pair = re.compile(rf"{_NAME}{_TICK}\s+will replace\s+{_NAME}{_TICK}")
    sector = r"Consumer|Energy|Financials|Health|Industrials|Information|Materials|Real|Utilities|Telecommunication|Communication"
    rows = []
    for hm in _HEADER.finditer(text):
        tail = text[hm.end() :]
        end = re.search(r"S&P (?:MIDCAP |SMALLCAP )?\d+ INDEX", tail, re.I)
        table = tail[: end.start()] if end else tail[:1400]
        adds = re.findall(rf"ADDED\s+(.+?)\s+(?:{sector})\b", table)
        removes = re.findall(rf"DELETED\s+(.+?)\s+(?:{sector})\b", table)
        if len(adds) == len(removes) == 1:
            rows.append((name_key(adds[0]), name_key(removes[0])))
    out = []
    for m in pair.finditer(text):
        an, at, rn, rt = m.groups()
        an, rn = _clean_name(an), _clean_name(rn)
        if (name_key(an), name_key(rn)) in rows:
            out.append((an, at, rn, rt, m.start(), m.end()))
    return out


def _with_rename(m: re.Match[str]) -> str:
    """The added name, with the S&P statement «, to be renamed Evergy,» kept (it links the old and new name of ONE company)."""
    ren = re.search(r"to be renamed\s+([^,():;]{1,40}),", m.group(0))
    base = _clean_name(m.group(1))
    return f"{base} (to be renamed {ren.group(1).strip()})" if ren else base


_ADD_THEN_REPLACE = re.compile(
    rf"{_NAME}{_TICK}\s+will be added to the S&P 500{_NOT_500}[^.]{{0,100}}\.\s+(?:[A-Z][\w&'\-]*\s+){{1,4}}will replace\s+{_NAME}{_TICK}\s*\."
)


def _added_then_replace(text: str) -> list[tuple[str, str, str, str, int, int]]:
    """«Tesla Inc. (NASD:TSLA) will be added to the S&P 500. Tesla will replace Apartment Investment and Management Co. (NYSE:AIV).»: the
    second sentence names the added company only by its short name and carries NO «in the S&P 500»; the first sentence fixes that it is the
    S&P 500 and the ticker. The date comes from the same intro/summary machinery as any other clause."""
    out: list[tuple[str, str, str, str, int, int]] = []
    for m in _ADD_THEN_REPLACE.finditer(text):
        if _TIMING.search(m.group(0)):
            continue  # the add sentence carries its own date: the legs have different dates (timed adds/removes)
        out.append(
            (
                _clean_name(m.group(1)),
                m.group(2).upper(),
                _clean_name(m.group(3)),
                m.group(4).upper(),
                m.start(),
                m.end(),
            )
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


def parse_release(
    text: str, announced: date, name_tickers: dict[str, set[str]] | None = None
) -> list[ParsedChange]:
    """Every «X (EXCH: A) will replace Y (EXCH: B) in the S&P 500» clause of ONE release, with
    the nearest timing phrase after it and, cross-checking, the date of the «S&P 500 INDEX –»
    summary header. Clauses about other indices are ignored."""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"S&\s+P", "S&P", text)  # «S& P 500» typography in some releases
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)  # «( NASD : CSGP )»
    text = _expand_multi_tickers(text)  # «(NYSE:UA/UAA)», «(NASD: FOXAV; FOXBV)»
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
        (_with_rename(m), m.group(2), m.group(3).strip(), m.group(4), m.start(), m.end())
        for m in _REPLACE.finditer(text)
    ]
    seen_pairs = {(c[1].upper(), c[3].upper()) for c in clauses}
    clauses += [c for c in _list_clauses(text) if (c[1], c[3]) not in seen_pairs]
    seen_pairs |= {(c[1], c[3]) for c in clauses}
    for extra in (
        _move_clauses(text),
        _switch_clauses(text),
        _name_only_clauses(text),
        _summary_backed_pairs(text),
        _added_then_replace(text),
    ):
        clauses += [c for c in extra if (c[1].upper(), c[3].upper()) not in seen_pairs]
        seen_pairs |= {(c[1].upper(), c[3].upper()) for c in clauses}
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
            ad = table.get((add_t, "Addition")) if add_t else table.get((rem_t, "Deletion"))
            if ad is not None and (
                not rem_t or not add_t or table.get((rem_t, "Deletion"), ad) == ad
            ):
                timing, stated = Timing.BEFORE_OPEN, ad
                notes.append("date from the release's effective-date summary table")
        if (
            timing is Timing.UNKNOWN
        ):  # intro: «will make the following changes … effective prior to the open …»
            intro = text[max(0, c_start - 3000) : c_start]
            for im in _TIMING.finditer(intro):
                ctx = intro[max(0, im.start() - 420) : im.start()]
                if (
                    re.search(r"following (?:index )?(?:changes|adjustments)", ctx) is not None
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
    timed = _timed_adds_removes(text, announced, name_tickers)
    known_add = {c.added_ticker for c in timed if c.added_ticker and c.timing is not Timing.UNKNOWN}
    out = [
        c
        for c in out
        if not (c.added_ticker in known_add and not c.removed_ticker and c.timing is Timing.UNKNOWN)
    ]
    have_a = {x.added_ticker for x in out if x.added_ticker}
    have_r = {x.removed_ticker for x in out if x.removed_ticker}
    for c in timed:
        if (c.added_ticker and c.added_ticker in have_a) or (
            c.removed_ticker and c.removed_ticker in have_r
        ):
            continue
        out.append(c)
        have_a.add(c.added_ticker)
        have_r.add(c.removed_ticker)
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
