"""Reproducible investigation of EDGAR timestamp semantics (ADR-0019).

For each selected accession, fetch and ARCHIVE (raw_source_archive) every independent
representation of "when was this filing accepted", then compare them WITHOUT parsing
assumptions:

* H  header ``.hdr.sgml``   ``<ACCEPTANCE-DATETIME>YYYYMMDDHHMMSS`` (no zone in the field)
* I  filing index page      ``-index.htm`` "Accepted" (no zone in the field)
* S  submissions JSON       ``acceptanceDateTime`` (ISO with a ``Z`` suffix)
* A  company Atom feed      ``<updated>`` — carries an EXPLICIT UTC offset
* L  HTTP ``Last-Modified`` of the complete submission ``.txt`` — RFC 7231, GMT by spec

A is SEC's own rendering of the same instant WITH an explicit offset (the zone proof); L is
GMT by spec but a weak clock (files are rewritten). The independent corroboration is the
filingDate rollover at the 17:30 Eastern cutoff. The test of each
hypothesis is arithmetic on raw values, recorded in ``docs/edgar_time_investigation.json``.

Needs PITQUANT_SEC_USER_AGENT (contact e-mail). Usage:
    python scripts/edgar_time_investigation.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.data.archive import ArchiveStore, archive_document  # noqa: E402
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402

ET = ZoneInfo("America/New_York")
PROVIDER = "SEC_EDGAR_TIME_INVESTIGATION"
FIXTURES = ROOT / "tests" / "fixtures" / "sec_real"

# (cik, accession, form, why) — chosen from ingested filings by header time (see ADR-0019)
CASES = [
    ("320193", "0000320193-18-000007", "10-Q", "winter, pre-open (08:01 ET?)"),
    ("320193", "0000320193-25-000073", "10-Q", "summer, pre-open (06:00 ET?)"),
    ("320193", "0000320193-18-000145", "10-K", "Monday after DST end, pre-open"),
    ("789019", "0001564590-18-019062", "10-K", "summer, in session (11:03 ET?)"),
    ("789019", "0001193125-12-026864", "10-Q/A", "winter, in session (15:04 ET?)"),
    ("789019", "0001193125-11-015947", "10-Q", "winter, ~16:00 ET"),
    ("789019", "0000950170-23-035122", "10-K", "summer, ~16:00 ET"),
    ("789019", "0001193125-14-289961", "10-K", "summer, 17:16 ET, before 17:30 cutoff"),
    ("320193", "0000320193-20-000010", "10-Q", "winter, 18:02 ET, after 17:30 cutoff"),
    ("320193", "0000320193-19-000119", "10-K", "summer, 18:12 ET, after 17:30 cutoff"),
]


def get(url: str, ua: str, method: str = "GET") -> tuple[bytes, dict[str, str]]:
    req = urllib.request.Request(url, headers={"User-Agent": ua}, method=method)
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read() if method == "GET" else b""
        hdrs = {k: v for k, v in r.headers.items()}
    time.sleep(0.2)
    return body, hdrs


def main() -> int:
    ua = os.environ.get("PITQUANT_SEC_USER_AGENT", "")
    if "@" not in ua:
        print("set PITQUANT_SEC_USER_AGENT with a contact e-mail", file=sys.stderr)
        return 2
    s = get_settings()
    store = ArchiveStore(ROOT / s.archive.root)
    factory = make_session_factory(make_engine(s.database.url))
    FIXTURES.mkdir(parents=True, exist_ok=True)
    out = []
    with factory() as ses:

        def keep(url: str, body: bytes, mime: str, name: str | None = None) -> str:
            row = archive_document(
                ses,
                store,
                provider=PROVIDER,
                source_identifier=url,
                data=body,
                mime_type=mime,
                parser_version="edgar-time-investigation-1",
            )
            if name:
                (FIXTURES / name).write_bytes(body)
            return row.sha256

        subs: dict[str, dict[str, str]] = {}
        atom: dict[str, str] = {}
        for cik in sorted({c for c, *_ in CASES}):
            url = f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"
            body, _ = get(url, ua)
            keep(url, body, "application/json")
            recent = json.loads(body)["filings"]["recent"]
            for i, acc in enumerate(recent["accessionNumber"]):
                subs[acc] = {k: recent[k][i] for k in ("acceptanceDateTime", "filingDate", "form")}
            for form in ("10-K", "10-Q", "10-Q/A"):
                aurl = (
                    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
                    f"&CIK={cik}&type={form}&dateb=&owner=include&count=100&output=atom"
                )
                abody, _ = get(aurl, ua)
                keep(aurl, abody, "application/atom+xml", f"atom_{cik}_{form.replace('/', '')}.xml")
                for m in re.finditer(rb"<entry>.*?</entry>", abody, flags=re.S):
                    e = m.group(0)
                    acc_m = re.search(rb"<accession-number>([\d-]+)</accession-number>", e)
                    upd = re.search(rb"<updated>([^<]+)</updated>", e)
                    if acc_m and upd:
                        atom[acc_m.group(1).decode()] = upd.group(1).decode()
        for cik, acc, form, why in CASES:
            nd = acc.replace("-", "")
            base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{nd}/"
            hdr, _ = get(base + f"{acc}.hdr.sgml", ua)
            keep(base + f"{acc}.hdr.sgml", hdr, "text/plain", f"{acc}.hdr.sgml")
            idx, _ = get(base + f"{acc}-index.htm", ua)
            keep(base + f"{acc}-index.htm", idx, "text/html", f"{acc}-index.htm")
            _, head = get(base + f"{acc}.txt", ua, method="HEAD")
            h = re.search(rb"<ACCEPTANCE-DATETIME>\s*(\d{14})", hdr)
            ia = re.search(rb"Accepted</div>\s*<div class=\"info\">([^<]+)<", idx)
            out.append(
                {
                    "case": why,
                    "cik": cik,
                    "accession": acc,
                    "form": form,
                    "H_header_raw": h.group(1).decode() if h else None,
                    "I_index_accepted_raw": ia.group(1).decode().strip() if ia else None,
                    "S_submissions_raw": subs.get(acc, {}).get("acceptanceDateTime"),
                    "S_filingDate_raw": subs.get(acc, {}).get("filingDate"),
                    "A_atom_updated_raw": atom.get(acc),
                    "L_last_modified_raw": head.get("Last-Modified"),
                }
            )
        ses.commit()
    for r in out:
        r.update(evaluate(r))
    (ROOT / "docs" / "edgar_time_investigation.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    for r in out:
        print(json.dumps(r))
    return 0


def evaluate(r: dict[str, str | None]) -> dict[str, object]:
    """Arithmetic only: express every source as an absolute instant under each hypothesis
    and report the differences (seconds) against the explicit-offset Atom clock."""
    res: dict[str, object] = {}
    if not r["A_atom_updated_raw"] or not r["H_header_raw"]:
        res["verdict"] = "INCOMPLETE"
        return res
    atom = datetime.fromisoformat(r["A_atom_updated_raw"])  # explicit offset
    naive_h = datetime.strptime(r["H_header_raw"], "%Y%m%d%H%M%S")  # noqa: DTZ007 (hypotheses)
    h_et = naive_h.replace(tzinfo=ET)
    h_utc = naive_h.replace(tzinfo=UTC)
    res["header_as_ET_minus_atom_s"] = (h_et - atom).total_seconds()
    res["header_as_UTC_minus_atom_s"] = (h_utc - atom).total_seconds()
    res["atom_utc_offset"] = atom.strftime("%z")
    if r["S_submissions_raw"]:
        s = datetime.fromisoformat(r["S_submissions_raw"].replace("Z", "+00:00"))
        res["submissions_as_UTC_minus_atom_s"] = (s - atom).total_seconds()
        res["submissions_as_ET_minus_atom_s"] = (
            s.replace(tzinfo=None).replace(tzinfo=ET) - atom
        ).total_seconds()
    if r["L_last_modified_raw"]:
        lm = parsedate_to_datetime(r["L_last_modified_raw"])
        res["last_modified_minus_header_as_ET_s"] = (lm - h_et).total_seconds()
        res["last_modified_minus_header_as_UTC_s"] = (lm - h_utc).total_seconds()
    if r["I_index_accepted_raw"]:
        i = datetime.strptime(r["I_index_accepted_raw"], "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007
        res["index_equals_header_wall_clock"] = i == naive_h
    return res


if __name__ == "__main__":
    raise SystemExit(main())
