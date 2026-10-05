# ruff: noqa: E501
"""Bounded evidence ingestion for ADR-0056; no targets, prices or outcomes read."""

from __future__ import annotations

import csv
import io
import json
import os
from datetime import UTC, date, datetime
from pathlib import Path

import httpx

from pitquant.data.archive import ArchiveStore, archive_document
from pitquant.db.session import make_engine, make_session_factory
from pitquant.research.membership_evidence import UA_EFFECTIVE, VERSION, historical_states

ROOT = Path(__file__).resolve().parent.parent
SOURCES = {
    "clenow_original": (
        "https://raw.githubusercontent.com/fja05680/sp500/master/S%26P%20500%20Historical%20Components%20%26%20Changes.csv",
        "clenow.csv",
        "CLENOW_TRADING_EVOLVED_1996_2019",
        "text/csv",
    ),
    "clenow_updated": (
        "https://raw.githubusercontent.com/fja05680/sp500/master/S%26P%20500%20Historical%20Components%20%26%20Changes%20%28Updated%29.csv",
        "clenow-updated.csv",
        "FJA_CLENOW_PLUS_WIKIPEDIA_POST2019",
        "text/csv",
    ),
    "clenow_provenance": (
        "https://raw.githubusercontent.com/fja05680/sp500/master/README.md",
        "clenow-readme.md",
        "FJA_DOCUMENTATION",
        "text/plain",
    ),
    "wikipedia_history": (
        "https://media.githubusercontent.com/media/leosmigel/analyzingalpha/master/2019-09-18-sp500-historical-components-and-changes/2021-09-24-sp500-history.csv",
        "2021-09-24-sp500-history.csv",
        "WIKIPEDIA_SELECTED_CHANGES",
        "text/csv",
    ),
    "wikipedia_provenance": (
        "https://media.githubusercontent.com/media/leosmigel/analyzingalpha/master/2019-09-18-sp500-historical-components-and-changes/2021-09-24-sp500-companies-and-historical-components.ipynb",
        "2021-09-24-sp500-companies-and-historical-components.ipynb",
        "LEOS_WIKIPEDIA_PARSER",
        "application/json",
    ),
}


def main() -> None:
    cache = Path(os.environ.get("PITQUANT_D02_SOURCE_CACHE", "/tmp/pitquant-evidence-tiers"))
    store = ArchiveStore(ROOT / "data/archive")
    session = make_session_factory(make_engine(os.environ["PITQUANT_DATABASE_URL"]))()
    manifest = {
        "evidence_version": VERSION,
        "sources": {},
        "research_attempts": [],
        "independence_note": "Pre-2019 original history is Clenow's book companion file; Wikipedia changes are a separate editorial reconstruction. Post-2019 updated FJA history shares Wikipedia upstream and is never counted as an independent second Wikipedia source.",
    }
    manifest_path = ROOT / "docs/D02_MEMBERSHIP_SOURCE_MANIFEST.json"
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text())
        manifest["research_attempts"] = previous.get("research_attempts", [])
    raw_sources = {}
    for key, (url, filename, upstream, mime) in SOURCES.items():
        path = cache / filename
        raw = (
            path.read_bytes()
            if path.exists()
            else httpx.get(url, timeout=20, follow_redirects=True).raise_for_status().content
        )
        archive = archive_document(
            session,
            store,
            provider="D02_HISTORICAL_REFERENCE",
            source_identifier=url,
            data=raw,
            mime_type=mime,
            parser_version=VERSION,
        )
        manifest["sources"][key] = {
            "source_url": url,
            "publisher": "FJA / Clenow"
            if key.startswith("clenow")
            else "Wikipedia via Analyzing Alpha",
            "document_id": filename,
            "accession": None,
            "retrieved_at": archive.retrieved_at.isoformat(),
            "sha256": archive.sha256,
            "archive_id": archive.archive_id,
            "raw_document": archive.storage_uri,
            "evidence_type": "HISTORICAL_MEMBERSHIP_REFERENCE"
            if mime == "text/csv"
            else "UPSTREAM_PROVENANCE",
            "effective_date": None,
            "resolver_version": VERSION,
            "upstream": upstream,
        }
        raw_sources[key] = raw
    states = historical_states(raw_sources["clenow_original"], until=date(2019, 9, 30))
    prior = frozenset()
    ua_additions = []
    for day, members in states:
        if "UA" in members and "UA" not in prior:
            ua_additions.append(day)
        prior = members
    wiki = [
        r
        for r in csv.DictReader(io.StringIO(raw_sources["wikipedia_history"].decode()))
        if r["ticker"] == "UA" and r["name"] == "Under Armour (Class C)" and r["action"] == "added"
    ]
    assert UA_EFFECTIVE in ua_additions
    assert any(
        datetime.strptime(r["date"], "%B %d, %Y").replace(tzinfo=UTC).date() == UA_EFFECTIVE
        for r in wiki
    )
    assert "Trading Evolved" in raw_sources["clenow_provenance"].decode()
    assert "wikipedia.org" in raw_sources["wikipedia_provenance"].decode()
    matrix = json.loads((ROOT / "docs/D02_UNDER_ARMOUR_EVIDENCE_MATRIX.json").read_text())
    primaries = []
    for entry in matrix["matrix"]:
        source = {**entry, "sha256": entry.get("sha256") or entry.get("hash")}
        store.get(source["sha256"])
        primaries.append(source)
    manifest["under_armour"] = {
        "security_id": "ea33aaa6-2990-475f-b03d-3852d591c274",
        "share_class": "C",
        "effective_date": str(UA_EFFECTIVE),
        "event": "ADD",
        "evidence_tier": "CORROBORATED_HISTORICAL",
        "primary_identity_supported": True,
        "primary_sources": primaries,
        "membership_sources": [
            {
                **manifest["sources"][k],
                "effective_date": str(UA_EFFECTIVE),
                "event": "ADD",
                "security_class": "C",
                "parsed_fact": "Class C added 2016-04-08",
            }
            for k in ("clenow_original", "wikipedia_history")
        ],
        "ticker_note": "Historical reconstruction symbols may be normalized; SEC dated ticker aliases govern UA.C/UA/UAA, never a merge of Class A and Class C.",
        "official_direct": False,
        "additional_sp_search_stopped": True,
    }
    session.commit()
    (ROOT / "docs/D02_MEMBERSHIP_SOURCE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    main()
