"""SEC EDGAR FIXTURES for a fictional issuer (CIK 0000999999, "FIXTURE CORP").

Document SHAPES follow EDGAR (submissions JSON, companyfacts JSON, .hdr.sgml headers,
index.json, XBRL instance). Every value, date and accession is invented for testing and
must never be read as real filing data.

Timeline (US/Eastern):
  A  10-K   FY2023   filed 2024-02-20, accepted 16:15:02 (after close)
  B  10-Q   Q1-2024  filed 2024-05-01, accepted 10:15:00 (intraday)
  C  10-Q/A Q1-2024  filed 2024-06-10, accepted 12:00:00 (amendment: Q1-2024 revenue 30 -> 28)
  D  10-K   FY2024   filed 2025-02-18, accepted 07:00:00 (pre-market; restates FY2023 100 -> 95)
  X  orphan accession cited by companyfacts but absent from submissions
  P  10-K   FY2009   filed 2010-03-01 (before XBRL coverage start)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from pitquant.data.providers.sec_edgar.client import HttpResponse

CIK = "999999"
A, B, C, D = (
    "0000999999-24-000010",
    "0000999999-24-000020",
    "0000999999-24-000030",
    "0000999999-25-000010",
)
X, P = "0000999999-24-000099", "0000999999-10-000001"

FILINGS = [  # accession, form, filed, report, accepted (ET wall), submissions acceptance
    (A, "10-K", "2024-02-20", "2023-12-31", "20240220161502", "2024-02-20T16:15:02.000Z"),
    (B, "10-Q", "2024-05-01", "2024-03-31", "20240501101500", "2024-05-01T10:15:00.000Z"),
    (C, "10-Q/A", "2024-06-10", "2024-03-31", "20240610120000", "2024-06-10T12:00:00.000Z"),
    (D, "10-K", "2025-02-18", "2024-12-31", "20250218070000", "2025-02-18T09:00:00.000Z"),
    (P, "10-K", "2010-03-01", "2009-12-31", "20100301120000", "2010-03-01T12:00:00.000Z"),
]

FY23 = ("2023-01-01", "2023-12-31")
FY24 = ("2024-01-01", "2024-12-31")
Q1_24 = ("2024-01-01", "2024-03-31")
Q1_23 = ("2023-01-01", "2023-03-31")

# (concept, unit, start, end, val, accn, form, filed)
FACTS = [
    ("Revenues", "USD", *FY23, 100.0, A, "10-K", "2024-02-20"),
    ("Revenues", "USD", "2022-01-01", "2022-12-31", 90.0, A, "10-K", "2024-02-20"),
    ("Revenues", "USD", *Q1_24, 30.0, B, "10-Q", "2024-05-01"),
    ("Revenues", "USD", *Q1_23, 25.0, B, "10-Q", "2024-05-01"),
    ("NetIncomeLoss", "USD", *Q1_24, 5.0, B, "10-Q", "2024-05-01"),  # instance says 6 -> reject
    ("Revenues", "USD", *Q1_24, 28.0, C, "10-Q/A", "2024-06-10"),
    ("Revenues", "USD", *FY24, 120.0, D, "10-K", "2025-02-18"),
    ("Revenues", "USD", *FY23, 95.0, D, "10-K", "2025-02-18"),  # restated comparative
    ("Revenues", "USD", *FY23, 101.0, X, "10-K", "2024-03-01"),  # orphan accession
    ("Revenues", "USD", "2009-01-01", "2009-12-31", 50.0, P, "10-K", "2010-03-01"),
]

INSTANCE_FACTS = {  # accession -> [(concept, start, end, value)]
    A: [("Revenues", *FY23, 100.0)],
    B: [("Revenues", *Q1_24, 30.0), ("NetIncomeLoss", *Q1_24, 6.0)],
    D: [("Revenues", *FY24, 120.0), ("Revenues", *FY23, 95.0)],
}


def submissions_json() -> bytes:
    cols: dict[str, list[str]] = {
        k: []
        for k in (
            "accessionNumber",
            "form",
            "filingDate",
            "reportDate",
            "acceptanceDateTime",
            "primaryDocument",
        )
    }
    for acc, form, filed, rep, _hdr, sub in FILINGS:
        cols["accessionNumber"].append(acc)
        cols["form"].append(form)
        cols["filingDate"].append(filed)
        cols["reportDate"].append(rep)
        cols["acceptanceDateTime"].append(sub)
        cols["primaryDocument"].append(f"fix-{acc[-6:]}.htm")
    return json.dumps(
        {"cik": CIK, "name": "FIXTURE CORP", "filings": {"recent": cols, "files": []}}
    ).encode()


def companyfacts_json(facts: list[tuple] | None = None) -> bytes:  # type: ignore[type-arg]
    units: dict[str, dict[str, list[dict[str, object]]]] = {}
    for concept, unit, start, end, val, accn, form, filed in facts or FACTS:
        units.setdefault(concept, {}).setdefault(unit, []).append(
            {
                "start": start,
                "end": end,
                "val": val,
                "accn": accn,
                "fy": int(end[:4]),
                "fp": "FY" if form.startswith("10-K") else "Q1",
                "form": form,
                "filed": filed,
            }
        )
    return json.dumps(
        {
            "cik": int(CIK),
            "entityName": "FIXTURE CORP",
            "facts": {"us-gaap": {c: {"units": u} for c, u in units.items()}},
        }
    ).encode()


def header(acc: str) -> bytes:
    stamp = next(h for a, *_r, h, _s in FILINGS if a == acc)
    return (
        f"<SEC-HEADER>\n<ACCESSION-NUMBER>{acc}\n<TYPE>10-K\n"
        f"<ACCEPTANCE-DATETIME>{stamp}\n</SEC-HEADER>\n"
    ).encode()


def index_json(acc: str) -> bytes:
    items = [
        {"name": f"fix-{acc[-6:]}.htm"},
        {"name": "FilingSummary.xml"},
        {"name": f"fix-{acc[-6:]}_pre.xml"},
    ]
    if acc in INSTANCE_FACTS:
        items.append({"name": f"fix-{acc[-6:]}_htm.xml"})
    return json.dumps({"directory": {"item": items}}).encode()


def instance_xml(acc: str) -> bytes:
    ctx, facts = [], []
    for i, (concept, start, end, val) in enumerate(INSTANCE_FACTS[acc]):
        ctx.append(
            f'<xbrli:context id="c{i}"><xbrli:entity><xbrli:identifier '
            f'scheme="http://www.sec.gov/CIK">{CIK}</xbrli:identifier></xbrli:entity>'
            f"<xbrli:period><xbrli:startDate>{start}</xbrli:startDate>"
            f"<xbrli:endDate>{end}</xbrli:endDate></xbrli:period></xbrli:context>"
        )
        facts.append(
            f'<us-gaap:{concept} contextRef="c{i}" unitRef="usd" decimals="-6">'
            f"{val}</us-gaap:{concept}>"
        )
    return (
        '<?xml version="1.0"?><xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" '
        'xmlns:iso4217="http://www.xbrl.org/2003/iso4217" '
        'xmlns:us-gaap="http://fasb.org/us-gaap/2023">'
        '<xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>'
        + "".join(ctx)
        + "".join(facts)
        + "</xbrli:xbrl>"
    ).encode()


@dataclass
class FakeSEC:
    """Offline transport serving the fixtures. ``visible`` limits which filings exist yet,
    so tests can ingest history in stages (the world as it looked at different times)."""

    visible: set[str] = field(default_factory=lambda: {A, B, C, D, X, P})
    calls: list[tuple[str, dict[str, str]]] = field(default_factory=list)
    fail_once: set[str] = field(default_factory=set)

    def get(self, url: str, headers: dict[str, str]) -> HttpResponse:
        self.calls.append((url, headers))
        if url in self.fail_once:
            self.fail_once.discard(url)
            return HttpResponse(503, b"", "text/plain")
        if url.endswith(f"CIK{int(CIK):010d}.json") and "submissions" in url:
            keep = [f for f in FILINGS if f[0] in self.visible]
            saved = FILINGS[:]
            FILINGS[:] = keep
            try:
                return HttpResponse(200, submissions_json(), "application/json")
            finally:
                FILINGS[:] = saved
        if "companyfacts" in url:
            facts = [f for f in FACTS if f[5] in self.visible]
            return HttpResponse(200, companyfacts_json(facts), "application/json")
        for acc in self.visible:
            nd = acc.replace("-", "")
            if f"/{nd}/" in url:
                if url.endswith(".hdr.sgml"):
                    return HttpResponse(200, header(acc), "text/plain")
                if url.endswith("index.json"):
                    return HttpResponse(200, index_json(acc), "application/json")
                if url.endswith("_htm.xml"):
                    return HttpResponse(200, instance_xml(acc), "application/xml")
        return HttpResponse(404, b"", "text/plain")
