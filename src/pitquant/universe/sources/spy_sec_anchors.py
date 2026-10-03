# ruff: noqa: E501
"""Historical S&P 500 reference anchors from SEC filings of the SPDR S&P 500 ETF Trust (ADR-0032).

* Tier A ``SEC_NPORT_IDENTIFIED_ANCHOR``: NPORT-P ``primary_doc.xml``, Part C holdings with CUSIP (+ ISIN / LEI).
* Tier B ``SEC_SCHEDULE_ANCHOR``: the Schedule of Investments of an N-30D shareholder report (names + shares + value;
  NO identifiers, so identity there is name-based and labelled so).

These are SEC-FILED INDEX-REPLICATION compositions, NEVER OFFICIAL_SPDJI. ``as_of_date`` (the state described) and
``source_available_at`` (SEC acceptance, weeks later) are different clocks: the anchor is REFERENCE truth about a past
state and must never feed a feature or any information set at ``decision_at``.

Pure parsing: bytes in, records out. Nothing is guessed: a CUSIP is read, never rebuilt from a ticker; an ISIN is only
read (a derived ISIN would have to be labelled DERIVED).
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import StrEnum
from html.parser import HTMLParser

from pitquant.core.errors import DataQualityError

PARSER_VERSION = "spy-sec-anchors-1"
SPY_CIK = "0000884394"
SPY_FILE_NUMBER = "811-06125"
NPORT_NS = "{http://www.sec.gov/edgar/nport}"
TIER_A = "SEC_NPORT_IDENTIFIED_ANCHOR"
TIER_B = "SEC_SCHEDULE_ANCHOR"
TIER_C = "MULTI_SOURCE_CURRENT_ANCHOR"
EVIDENCE_KIND = "SEC_FILED_INDEX_REPLICATION_ANCHOR"
# SPY keeps stub positions of stocks that left the index or were spun off (e.g. 1 share of Vontier after its removal, USD 14k of
# Embecta). Across all 2019-2022 NPORT anchors the smallest genuine member is worth > USD 12M and every stub is < USD 20k.
MIN_MEMBER_VALUE_USD = 1_000_000.0


class HoldingClass(StrEnum):
    INDEX_EQUITY_CANDIDATE = "INDEX_EQUITY_CANDIDATE"
    NON_EQUITY = "NON_EQUITY"
    TRANSIENT_CORPORATE_ACTION = "TRANSIENT_CORPORATE_ACTION"
    UNRESOLVED = "UNRESOLVED"


@dataclass
class Holding:
    position: int
    issuer_name: str
    title: str | None
    cusip: str | None
    isin: str | None
    ticker: str | None
    other_id: str | None
    lei: str | None
    shares: float | None
    units: str | None
    currency: str | None
    value_usd: float | None
    pct_net_assets: float | None
    asset_cat: str | None
    klass: HoldingClass = HoldingClass.UNRESOLVED
    reason: str = ""
    notes: list[str] = field(default_factory=list)


@dataclass
class FilingHeader:
    form: str
    accession: str
    period: date
    filer_cik: str
    accepted_at: datetime
    filing_date: date


# ───────────────────────────────────────────── complete submission header
def parse_submission_header(txt: bytes | str) -> FilingHeader:
    """From the SGML header of the COMPLETE SUBMISSION (.txt): the filing's own statement of form, period and filer."""
    t = txt.decode("utf-8", "replace") if isinstance(txt, bytes) else txt
    head = t[:6000]

    def field_(name: str) -> str:
        m = re.search(rf"^{re.escape(name)}:\s*(.+)$", head, re.M)
        if not m:
            raise DataQualityError(f"submission header: {name} not found")
        return m.group(1).strip()

    acc = field_("ACCESSION NUMBER")
    form = field_("CONFORMED SUBMISSION TYPE")
    period = field_("CONFORMED PERIOD OF REPORT")
    cik = re.search(r"FILER:.*?CENTRAL INDEX KEY:\s*(\d+)", head, re.S)
    acc_dt = re.search(r"<ACCEPTANCE-DATETIME>\s*(\d{14})", head)
    filed = field_("FILED AS OF DATE")
    if not cik or not acc_dt:
        raise DataQualityError("submission header: filer CIK or acceptance time missing")
    return FilingHeader(
        form,
        acc,
        date(int(period[:4]), int(period[4:6]), int(period[6:8])),
        cik.group(1).zfill(10),
        datetime.strptime(acc_dt.group(1), "%Y%m%d%H%M%S").replace(tzinfo=UTC),
        date(int(filed[:4]), int(filed[4:6]), int(filed[6:8])),
    )


# ───────────────────────────────────────────── NPORT-P
_TRANSIENT = re.compile(
    r"\b(rights?|warrants?|when[- ]issued|contingent value|cvr|tender|subscription)\b", re.I
)


def _f(x: str | None) -> float | None:
    try:
        return float(x) if x not in (None, "") else None
    except ValueError:
        return None


def _t(e: ET.Element, tag: str) -> str | None:
    c = e.find(NPORT_NS + tag)
    return c.text.strip() if c is not None and c.text and c.text.strip() else None


def isin_valid(isin: str | None) -> bool:
    """ISO 6166 shape + Luhn check digit (an ISIN is read from the filing, never constructed)."""
    if not isin or not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}\d", isin):
        return False
    digits = "".join(str(int(c, 36)) for c in isin)
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            d = d - 9 if d > 9 else d
        total += d
    return total % 10 == 0


def classify_nport(h: Holding) -> None:
    """Explicit classification; anything ambiguous is UNRESOLVED (never assumed to be an index member)."""
    if h.asset_cat != "EC":
        h.klass, h.reason = (
            HoldingClass.NON_EQUITY,
            f"asset category {h.asset_cat!r} is not common equity",
        )
    elif h.units != "NS":
        h.klass, h.reason = HoldingClass.NON_EQUITY, f"units {h.units!r} are not a share balance"
    elif _TRANSIENT.search(f"{h.issuer_name} {h.title or ''}"):
        h.klass, h.reason = (
            HoldingClass.TRANSIENT_CORPORATE_ACTION,
            "rights/warrants/when-issued/CVR line",
        )
    elif (not h.cusip or len(h.cusip) != 9 or h.cusip == "000000000") and not isin_valid(h.isin):
        h.klass, h.reason = (
            HoldingClass.UNRESOLVED,
            "equity with neither a usable CUSIP nor a valid ISIN",
        )
    elif h.value_usd is not None and h.value_usd < MIN_MEMBER_VALUE_USD:
        h.klass, h.reason = (
            HoldingClass.TRANSIENT_CORPORATE_ACTION,
            f"residual stub position (USD {h.value_usd:,.0f} < {MIN_MEMBER_VALUE_USD:,.0f}): not an index weight",
        )
    elif h.currency not in (None, "USD"):
        h.klass, h.reason = HoldingClass.UNRESOLVED, f"non-USD line ({h.currency})"
    elif not h.shares or h.shares <= 0:
        h.klass, h.reason = HoldingClass.UNRESOLVED, "no positive share balance"
    else:
        if h.cusip == "000000000":
            h.cusip = (
                None  # the SEC placeholder for «no CUSIP» (non-US domicile): identity is the ISIN
            )
        basis = "CUSIP" if h.cusip else "ISIN (no CUSIP in the filing)"
        h.klass, h.reason = (
            HoldingClass.INDEX_EQUITY_CANDIDATE,
            f"common equity, {basis}, share balance",
        )


@dataclass
class NPortFiling:
    form: str
    reg_cik: str
    file_number: str | None
    period: date
    net_assets: float | None
    holdings: list[Holding]
    duplicates_merged: int = 0


def parse_nport(xml: bytes) -> NPortFiling:
    root = ET.fromstring(xml)
    form = (root.findtext(f"{NPORT_NS}headerData/{NPORT_NS}submissionType") or "").strip()
    gi = root.find(f"{NPORT_NS}formData/{NPORT_NS}genInfo")
    if gi is None:
        raise DataQualityError("NPORT: genInfo missing")
    period_s = _t(gi, "repPdDate")
    reg_cik = _t(gi, "regCik")
    if not period_s or not reg_cik:
        raise DataQualityError("NPORT: report period or registrant CIK missing")
    fi = root.find(f"{NPORT_NS}formData/{NPORT_NS}fundInfo")
    net = _f(_t(fi, "netAssets")) if fi is not None else None
    out: list[Holding] = []
    seen: dict[str, Holding] = {}
    merged = 0
    for i, inv in enumerate(
        root.iterfind(f"{NPORT_NS}formData/{NPORT_NS}invstOrSecs/{NPORT_NS}invstOrSec"), 1
    ):
        ids = inv.find(f"{NPORT_NS}identifiers")
        isin = ticker = other = None
        if ids is not None:
            e = ids.find(f"{NPORT_NS}isin")
            isin = e.get("value") if e is not None else None
            e = ids.find(f"{NPORT_NS}ticker")
            ticker = e.get("value") if e is not None else None
            e = ids.find(f"{NPORT_NS}other")
            other = e.get("value") if e is not None else None
        cusip = _t(inv, "cusip")
        h = Holding(
            i,
            _t(inv, "name") or "",
            _t(inv, "title"),
            cusip.upper() if cusip else None,
            isin,
            ticker,
            other,
            _t(inv, "lei"),
            _f(_t(inv, "balance")),
            _t(inv, "units"),
            _t(inv, "curCd"),
            _f(_t(inv, "valUSD")),
            _f(_t(inv, "pctVal")),
            _t(inv, "assetCat"),
        )
        classify_nport(h)
        key = h.cusip or h.isin
        if key and key in seen and h.klass is HoldingClass.INDEX_EQUITY_CANDIDATE:
            first = seen[key]
            first.shares = (first.shares or 0.0) + (h.shares or 0.0)
            first.value_usd = (first.value_usd or 0.0) + (h.value_usd or 0.0)
            first.notes.append(f"duplicate CUSIP line at position {i} merged")
            merged += 1
            continue
        if key and h.klass is HoldingClass.INDEX_EQUITY_CANDIDATE:
            seen[key] = h
        out.append(h)
    return NPortFiling(
        form,
        reg_cik.zfill(10),
        gi.findtext(f"{NPORT_NS}regFileNumber"),
        date.fromisoformat(period_s),
        net,
        out,
        merged,
    )


# ───────────────────────────────────────────── N-30D schedule
class _Rows(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._row.append(
                re.sub(r"\s+", " ", html.unescape("".join(self._cell)).replace("\xa0", " ")).strip()
            )
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append([c for c in self._row if c])
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


_NUM = re.compile(r"^\(?\$?\s?[\d,]+(?:\.\d+)?\)?$")


def _num(s: str) -> float | None:
    s2 = s.replace("$", "").replace(",", "").replace("(", "").replace(")", "").strip()
    try:
        return float(s2)
    except ValueError:
        return None


_FOOT = re.compile(r"\s*\((?:[a-z]|\d)\)\s*$|\s*\(\w{1,2}\)\s*")


def clean_schedule_name(raw: str) -> str:
    n = _FOOT.sub(" ", raw)
    n = re.sub(r"\s+REIT\s*$", "", n.strip())
    return re.sub(r"\s+", " ", n).strip()


@dataclass
class ScheduleHolding:
    position: int
    name: str
    shares: float
    value_usd: float
    raw_name: str


def parse_n30d_schedule(doc: bytes, dedupe: bool = True) -> list[ScheduleHolding]:
    """Rows «name | shares | [$] value» of the Schedule of Investments. Section headings, subtotals and notes are
    skipped by shape (a holding needs a non-numeric name and two numeric cells, shares being a whole number)."""
    p = _Rows()
    p.feed(doc.decode("utf-8", "replace"))
    out: list[ScheduleHolding] = []
    for cells in p.rows:
        if len(cells) < 3:
            continue
        name = cells[0]
        if _NUM.match(name) or re.match(
            r"(?i)total|net assets|liabilities|short-term|investment", name
        ):
            continue
        nums = [c for c in cells[1:] if _NUM.match(c)]
        if len(nums) != 2 or any(c not in nums and c != "$" for c in cells[1:]):
            continue
        shares, value = _num(nums[0]), _num(nums[1])
        if shares is None or value is None or shares != int(shares) or shares <= 0 or value <= 0:
            continue
        out.append(ScheduleHolding(len(out) + 1, clean_schedule_name(name), shares, value, name))
    if not dedupe:
        return out
    seen: set[tuple[str, float, float]] = set()
    kept: list[ScheduleHolding] = []
    for h in (
        out
    ):  # a page break can repeat rows verbatim; a real portfolio never has two identical lines
        k = (h.name, h.shares, h.value_usd)
        if k not in seen:
            seen.add(k)
            kept.append(ScheduleHolding(len(kept) + 1, h.name, h.shares, h.value_usd, h.raw_name))
    return kept


# ───────────────────────────────────────────── names
_SUFFIX = re.compile(
    r"\b(inc|incorporated|corp|corporation|co|company|plc|ltd|limited|llc|lp|nv|sa|ag|se|holdings?|group|the|de|ordinary|shares?|common|stock)\b"
)


def norm_name(s: str) -> str:
    """Comparison key for company names: lowercase, ``&`` kept as «and», punctuation and corporate suffixes removed.
    The class designator («class a»/«cl b») is KEPT: Alphabet A and C are different securities."""
    t = s.lower().replace("&", " and ")
    t = re.sub(r"\bcl(?:ass)?\.?\s+([a-z])\b", r"class \1", t)
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    t = _SUFFIX.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()
