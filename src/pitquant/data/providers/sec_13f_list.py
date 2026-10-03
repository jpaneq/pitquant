# ruff: noqa: E501
"""SEC «Official List of Section 13(f) Securities» (ADR-0033): OFFICIAL SECURITY IDENTIFIER REFERENCE, never membership.

The SEC publishes it quarterly as a PDF. Every line: ``CUSIP(6) (2) (check) [status] ISSUER NAME  ISSUER DESCRIPTION``. A CUSIP is evidence
for THAT quarter only. Calls/puts (description CALL / PUT) are not securities of the issuer and are dropped.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import date

from pypdf import PdfReader

PARSER_VERSION = "sec-13f-list-1"
URLS = (
    "https://www.sec.gov/files/investment/13flist{year}q{q}.pdf",
    "https://www.sec.gov/divisions/investment/13f/13flist{year}q{q}.pdf",
)
_LINE = re.compile(r"^([0-9A-Z]{6})\s([0-9A-Z]{2})\s([0-9A-Z])\s+(?:\*\s+)?(.+?)\s*$")
_TAIL = re.compile(r"\s+(ADDED|DELETED)\s*$")
_DESC = re.compile(
    r"\s((?:COM|COMMON|ORD|ORDINARY|SHS|SHARES|SPONSORED|SPON|ADR|CL|CLASS|NEW|NEW|SER|SERIES|A|B|C|K|NON-VTG|VTG|VOTING|LTD|PLC|NV|SA|UNIT|UNITS|CAP|STK|STOCK|SUB|VTG|REIT|TR|TRUST|PFD|WT|WTS|RIGHT|RTS|DEPOSITARY|RECEIPT)(?:\s+(?:COM|COMMON|ORD|ORDINARY|SHS|SHARES|SPONSORED|SPON|ADR|CL|CLASS|NEW|SER|SERIES|A|B|C|K|NON-VTG|VTG|VOTING|LTD|PLC|NV|SA|UNIT|UNITS|CAP|STK|STOCK|SUB|REIT|TR|TRUST|PFD|WT|WTS|ADS|[0-9]+(?:\.[0-9]+)?))*)$"
)


@dataclass(frozen=True)
class Entry13F:
    quarter: str
    cusip: str
    issuer_name: str
    issuer_description: str
    status: str | None
    text: str  # issuer name + description as printed


def quarter_end(quarter: str) -> date:
    y, q = int(quarter[:4]), int(quarter[-1])
    return {1: date(y, 3, 31), 2: date(y, 6, 30), 3: date(y, 9, 30), 4: date(y, 12, 31)}[q]


def parse_13f_text(text: str, quarter: str) -> list[Entry13F]:
    out: list[Entry13F] = []
    for raw in text.splitlines():
        m = _LINE.match(raw.strip())
        if not m:
            continue
        a, b, c, rest = m.groups()
        tm = _TAIL.search(rest)
        st = tm.group(1) if tm else None
        rest = _TAIL.sub("", rest)
        if rest.endswith((" CALL", " PUT")) or rest in ("CALL", "PUT"):
            continue
        cusip = f"{a}{b}{c}"
        dm = _DESC.search(" " + rest)
        desc = dm.group(1).strip() if dm else ""
        name = rest[: len(rest) - len(desc)].strip() if desc else rest.strip()
        status = st
        out.append(Entry13F(quarter, cusip, name, desc, status, rest.strip()))
    return out


def parse_13f_pdf(data: bytes, quarter: str) -> list[Entry13F]:
    rd = PdfReader(io.BytesIO(data))
    out: list[Entry13F] = []
    for pg in rd.pages:
        out += parse_13f_text(pg.extract_text() or "", quarter)
    return out


def quarters(first: str, last: str) -> list[str]:
    out: list[str] = []
    y, q = int(first[:4]), int(first[-1])
    while f"{y}Q{q}" <= last:
        out.append(f"{y}Q{q}")
        y, q = (y + 1, 1) if q == 4 else (y, q + 1)
    return out


def ingest_quarters(session, client, store, wanted: list[str]) -> dict[str, int]:  # type: ignore[no-untyped-def]
    """Fetch (first working URL), archive the raw PDF, parse and persist the entries of every quarter not stored yet. Idempotent."""
    from sqlalchemy import select

    from pitquant.core.errors import DataQualityError
    from pitquant.data.archive import archive_document
    from pitquant.data.providers.sec_edgar.client import SECFetchError
    from pitquant.db.models import Sec13FListEntry

    done = {
        q
        for (q,) in session.execute(
            select(Sec13FListEntry.quarter)
            .where(Sec13FListEntry.parser_version == PARSER_VERSION)
            .distinct()
        )
    }
    counts: dict[str, int] = {}
    for qt in wanted:
        if qt in done:
            counts[qt] = -1
            continue
        data: bytes | None = None
        url = ""
        for tpl in URLS:
            u = tpl.format(year=qt[:4], q=qt[-1])
            try:
                data, url = client.get(u).body, u
                break
            except SECFetchError:
                continue
        if data is None:
            raise DataQualityError(f"13F list {qt}: not available at the known SEC locations")
        arch = archive_document(
            session,
            store,
            provider="SEC_13F_LIST",
            source_identifier=url,
            data=data,
            mime_type="application/pdf",
            parser_version=PARSER_VERSION,
            notes=f"Official List of Section 13(f) Securities {qt}",
        )
        rows = parse_13f_pdf(data, qt)
        if len(rows) < 5000:
            raise DataQualityError(f"13F list {qt}: only {len(rows)} lines parsed")
        session.add_all(
            Sec13FListEntry(
                quarter=qt,
                cusip=r.cusip,
                issuer_name=r.issuer_name[:200],
                issuer_description=r.issuer_description[:100],
                status_added_deleted=r.status,
                raw_source_hash=arch.sha256,
                archive_id=arch.archive_id,
                parser_version=PARSER_VERSION,
            )
            for r in rows
        )
        session.flush()
        counts[qt] = len(rows)
    return counts
