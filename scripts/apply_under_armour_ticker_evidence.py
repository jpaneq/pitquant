"""Replay reviewed UA share-class aliases from hash-verified SEC/OCC originals.

Only appends identity aliases. Never emits membership events, joins classes,
changes issuer assignments, or remaps research prices. No network access.
"""

from __future__ import annotations

import html
import io
import json
import os
import re
from datetime import date
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import select

from pitquant.data.archive import ArchiveStore
from pitquant.db.models import RawSourceArchive, SecurityIdentifierEvidence, SecurityTickerAlias
from pitquant.db.session import make_engine, make_session_factory

VERSION = "d02-under-armour-ticker-evidence-v1"


def alias_specs(annual: str, occ: str) -> list[tuple[str, str, date | None, date | None, str]]:
    annual = " ".join(annual.translate(str.maketrans({"“": '"', "”": '"'})).split())
    occ = " ".join(occ.split())
    required = (
        'Our Class A Common Stock was listed on the NYSE under the symbol "UA" '
        'until December 6, 2016 and under the symbol "UAA" since December 7, 2016.',
        'Our Class C Common Stock was listed on the NYSE under the symbol "UA.C" '
        "since its initial issuance on April 8, 2016 and until December 6, 2016 "
        'and under the symbol "UA" since December 7, 2016.',
    )
    if not all(s in annual for s in required):
        raise ValueError("Exact class-specific annual ticker assertions missing")
    if not all(
        s in occ
        for s in (
            "UA: 904311107",
            "UA.C: 904311206",
            "Class A Common Shares",
            "Class C Common Shares",
        )
    ):
        raise ValueError("Official OCC class/CUSIP assertions missing")
    return [
        ("904311107", "UA", None, date(2016, 12, 6), "PARTIAL"),
        ("904311107", "UAA", date(2016, 12, 7), None, "EXACT"),
        ("904311206", "UA.C", date(2016, 4, 8), date(2016, 12, 6), "EXACT"),
        ("904311206", "UA", date(2016, 12, 7), None, "EXACT"),
    ]


def main() -> None:
    manifest = json.loads(Path("docs/D02_UNDER_ARMOUR_EVIDENCE_MATRIX.json").read_text())
    annual = next(m for m in manifest["matrix"] if m["source"] == "SEC 2016 10-K")
    occ = next(m for m in manifest["matrix"] if m["source"].startswith("OCC notice"))
    store = ArchiveStore(Path("data/archive"))
    with make_session_factory(make_engine(os.environ["PITQUANT_DATABASE_URL"]))() as session:
        for source in (annual, occ):
            archive = session.get_one(RawSourceArchive, source["archive_id"])
            if archive.sha256 != source["sha256"] or archive.source_identifier != source["url"]:
                raise ValueError("Manifest/archive identity mismatch")
        body = store.get(annual["sha256"]).decode("utf-8", "replace")
        annual_text = html.unescape(re.sub(r"<[^>]+>", " ", body))
        occ_text = "\n".join(
            p.extract_text() for p in PdfReader(io.BytesIO(store.get(occ["sha256"]))).pages
        )
        specs = alias_specs(annual_text, occ_text)
        owners = {}
        for cusip in ("904311107", "904311206"):
            ids = set(
                session.scalars(
                    select(SecurityIdentifierEvidence.security_id).where(
                        SecurityIdentifierEvidence.id_type == "CUSIP",
                        SecurityIdentifierEvidence.value == cusip,
                        SecurityIdentifierEvidence.kind == "OFFICIAL",
                    )
                )
            )
            if len(ids) != 1:
                raise ValueError("Class-specific CUSIP does not identify exactly one security")
            owners[cusip] = next(iter(ids))
        if owners["904311107"] == owners["904311206"]:
            raise ValueError("Class A and C must remain distinct securities")
        existing = {
            (a.security_id, a.ticker, a.valid_from, a.valid_to, a.source_hash)
            for a in session.scalars(select(SecurityTickerAlias))
        }
        rows = []
        for cusip, ticker, start, end, bounds in specs:
            sid = owners[cusip]
            key = (sid, ticker, start, end, annual["sha256"])
            if key not in existing:
                session.add(
                    SecurityTickerAlias(
                        security_id=sid,
                        ticker=ticker,
                        valid_from=start,
                        valid_to=end,
                        bounds=bounds,
                        source="SEC_10K:0001336917-17-000017+OCC38727",
                        source_hash=annual["sha256"],
                        confidence="HIGH",
                        note="Class-specific SEC ticker history + OCC CUSIP; "
                        "NOT index membership evidence. Class A UA start remains PARTIAL.",
                    )
                )
                existing.add(key)
            rows.append(
                dict(
                    security_id=sid,
                    cusip=cusip,
                    ticker=ticker,
                    valid_from=str(start) if start else None,
                    valid_to=str(end) if end else None,
                    bounds=bounds,
                )
            )
        session.commit()
    Path("docs/D02_UNDER_ARMOUR_TICKER_EVIDENCE.json").write_text(
        json.dumps(
            dict(
                version=VERSION,
                sources=[annual, occ],
                aliases=rows,
                index_effective_date=None,
                membership_event_created=False,
            ),
            indent=2,
        )
        + "\n"
    )
    print("Verified four class-specific aliases; no index membership event created.")


if __name__ == "__main__":
    main()
