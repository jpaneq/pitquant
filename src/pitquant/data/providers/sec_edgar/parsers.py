"""Parsers for SEC EDGAR documents. Pure functions over bytes (no network)."""

from __future__ import annotations

import json
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from pitquant.core.errors import DataQualityError

ET_TZ = ZoneInfo("America/New_York")
PARSER_VERSION = "sec-edgar-1"


def accession_nodash(acc: str) -> str:
    return acc.replace("-", "")


def cik10(cik: str | int) -> str:
    return f"{int(cik):010d}"


# ───────────────────────────── submissions ─────────────────────────────


@dataclass(frozen=True)
class SubmissionFiling:
    accession_number: str
    form: str
    filing_date: date
    report_date: date | None
    acceptance_raw: str | None  # cross-check only; the HEADER is authoritative
    primary_document: str | None


def _opt_date(s: str | None) -> date | None:
    return date.fromisoformat(s) if s else None


def parse_submissions(data: bytes) -> tuple[list[SubmissionFiling], list[str]]:
    """Return filings from a submissions document plus names of older paginated files."""
    doc = json.loads(data)
    block = doc["filings"]["recent"] if "filings" in doc else doc
    n = len(block["accessionNumber"])
    out = []
    for i in range(n):
        out.append(
            SubmissionFiling(
                accession_number=block["accessionNumber"][i],
                form=block["form"][i],
                filing_date=date.fromisoformat(block["filingDate"][i]),
                report_date=_opt_date((block.get("reportDate") or [None] * n)[i]),
                acceptance_raw=(block.get("acceptanceDateTime") or [None] * n)[i],
                primary_document=(block.get("primaryDocument") or [None] * n)[i],
            )
        )
    files = [f["name"] for f in doc.get("filings", {}).get("files", [])]
    return out, files


# ───────────────────────────── header ─────────────────────────────

_ACCEPT = re.compile(rb"<ACCEPTANCE-DATETIME>\s*(\d{14})")
_ACC_NO = re.compile(rb"<ACCESSION-NUMBER>\s*([\d-]+)")


def parse_acceptance_datetime(header: bytes, expected_accession: str | None = None) -> datetime:
    """ACCEPTANCE-DATETIME from an EDGAR header (YYYYMMDDHHMMSS, US/Eastern wall time)."""
    m = _ACCEPT.search(header)
    if not m:
        raise DataQualityError("ACCEPTANCE-DATETIME not found in EDGAR header")
    if expected_accession is not None:
        a = _ACC_NO.search(header)
        if a and a.group(1).decode() != expected_accession:
            raise DataQualityError(
                f"header accession {a.group(1).decode()} != expected {expected_accession}"
            )
    raw = m.group(1).decode()
    local = datetime.strptime(raw, "%Y%m%d%H%M%S").replace(tzinfo=ET_TZ)
    return local.astimezone(ZoneInfo("UTC"))


def acceptance_raw_consistent(
    raw: str | None, header_utc: datetime, tol_s: int = 120
) -> bool | None:
    """Cross-check the submissions field against the header WITHOUT assuming its zone:
    consistent if it matches either as UTC or as Eastern wall time. None if absent."""
    if not raw:
        return None
    try:
        naive = datetime.fromisoformat(raw.replace("Z", "")).replace(tzinfo=None)
    except ValueError:
        return False
    as_utc = naive.replace(tzinfo=ZoneInfo("UTC"))
    as_et = naive.replace(tzinfo=ET_TZ)
    return any(abs((c - header_utc).total_seconds()) <= tol_s for c in (as_utc, as_et))


# ───────────────────────────── companyfacts ─────────────────────────────


@dataclass(frozen=True)
class CompanyFact:
    taxonomy: str
    concept: str
    unit: str
    start: date | None
    end: date
    value: float
    accession_number: str
    form: str
    filed: date
    fy: int | None
    fp: str | None


def parse_companyfacts(data: bytes) -> list[CompanyFact]:
    doc = json.loads(data)
    out: list[CompanyFact] = []
    for taxonomy, concepts in doc.get("facts", {}).items():
        for concept, body in concepts.items():
            for unit, rows in body.get("units", {}).items():
                for r in rows:
                    out.append(
                        CompanyFact(
                            taxonomy=taxonomy,
                            concept=concept,
                            unit=unit,
                            start=_opt_date(r.get("start")),
                            end=date.fromisoformat(r["end"]),
                            value=float(r["val"]),
                            accession_number=r["accn"],
                            form=r.get("form", ""),
                            filed=date.fromisoformat(r["filed"]),
                            fy=r.get("fy"),
                            fp=r.get("fp"),
                        )
                    )
    return out


# ───────────────────────────── filing index / XBRL instance ─────────────────────────────

_LINKBASE = re.compile(r"_(cal|def|lab|pre)\.xml$", re.I)


def pick_xbrl_instance(index_json: bytes) -> str | None:
    """Choose the XBRL instance document from a filing directory listing."""
    items: list[str] = [str(i["name"]) for i in json.loads(index_json)["directory"]["item"]]
    htm = [n for n in items if n.lower().endswith("_htm.xml")]  # extracted inline XBRL
    if htm:
        return sorted(htm)[0]
    xml = [
        n
        for n in items
        if n.lower().endswith(".xml")
        and not _LINKBASE.search(n)
        and n.lower() != "filingsummary.xml"
    ]
    return sorted(xml)[0] if xml else None


InstanceKey = tuple[str, str, date | None, date, str]  # (taxonomy, concept, start, end, unit)


def _taxonomy(ns: str) -> str | None:
    if "fasb.org/us-gaap" in ns:
        return "us-gaap"
    if "xbrl.sec.gov/dei" in ns:
        return "dei"
    if "fasb.org/srt" in ns:
        return "srt"
    if "xbrl.ifrs.org" in ns:
        return "ifrs-full"
    return None


def _local(tag: str) -> tuple[str, str]:
    ns, _, local = tag[1:].partition("}") if tag.startswith("{") else ("", "", tag)
    return ns, local


def parse_xbrl_instance(data: bytes) -> dict[InstanceKey, float]:
    """Non-dimensional numeric facts of an XBRL instance, keyed like companyfacts.

    Used to VALIDATE companyfacts values against the filing they claim to come from.
    """
    root = ET.fromstring(data)
    xbrli = "{http://www.xbrl.org/2003/instance}"
    contexts: dict[str, tuple[date | None, date]] = {}
    for ctx in root.iter(f"{xbrli}context"):
        if (
            ctx.find(".//{http://xbrl.org/2006/xbrldi}explicitMember") is not None
            or ctx.find(".//{http://xbrl.org/2006/xbrldi}typedMember") is not None
        ):
            continue  # dimensional: not comparable with companyfacts
        p = ctx.find(f"{xbrli}period")
        if p is None:
            continue
        inst = p.find(f"{xbrli}instant")
        if inst is not None and inst.text:
            contexts[ctx.attrib["id"]] = (None, date.fromisoformat(inst.text.strip()))
            continue
        s, e = p.find(f"{xbrli}startDate"), p.find(f"{xbrli}endDate")
        if s is not None and e is not None and s.text and e.text:
            contexts[ctx.attrib["id"]] = (
                date.fromisoformat(s.text.strip()),
                date.fromisoformat(e.text.strip()),
            )
    units: dict[str, str] = {}
    for u in root.iter(f"{xbrli}unit"):
        measures = [m.text.split(":")[-1] for m in u.iter(f"{xbrli}measure") if m.text]
        if u.find(f"{xbrli}divide") is not None and len(measures) == 2:
            units[u.attrib["id"]] = f"{measures[0]}/{measures[1]}"
        elif measures:
            units[u.attrib["id"]] = measures[0]
    out: dict[InstanceKey, float] = {}
    precision: dict[InstanceKey, float] = {}
    for el in root:
        ctx_id, unit_id = el.attrib.get("contextRef"), el.attrib.get("unitRef")
        if not ctx_id or not unit_id or ctx_id not in contexts or el.text is None:
            continue
        ns, concept = _local(el.tag)
        taxonomy = _taxonomy(ns)
        if taxonomy is None:
            continue
        try:
            val = float(el.text.strip())
        except ValueError:
            continue
        start, end = contexts[ctx_id]
        key = (taxonomy, concept, start, end, units.get(unit_id, unit_id))
        dec = _decimals(el.attrib.get("decimals"))
        if key not in out:
            out[key], precision[key] = val, dec
            continue
        # XBRL allows the same fact reported more than once at different precision
        # (e.g. 25808000000 @ -6 in a statement and 25800000000 @ -8 in a note). They must
        # agree once rounded to the coarser precision; keep the most precise value.
        prev, prev_dec = out[key], precision[key]
        if math.isnan(prev):
            continue
        coarse = min(dec, prev_dec)
        if not math.isinf(coarse) and _round(prev, coarse) != _round(val, coarse):
            out[key] = math.nan  # inconsistent duplicates: nothing can be validated
        elif math.isinf(coarse) and prev != val:
            out[key] = math.nan
        elif dec > prev_dec:
            out[key], precision[key] = val, dec
    return out


def _decimals(raw: str | None) -> float:
    if raw is None or raw.strip().upper() == "INF":
        return math.inf
    return float(int(raw))


def _round(v: float, decimals: float) -> float:
    return round(v, int(decimals))
