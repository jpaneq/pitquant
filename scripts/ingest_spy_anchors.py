# ruff: noqa: E501
"""Ingest the SEC-filed SPY anchors (ADR-0032). Needs PITQUANT_SEC_USER_AGENT in the environment (never persisted).

    PITQUANT_SEC_USER_AGENT="..." PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db python scripts/ingest_spy_anchors.py [--extend]

Core chain 2017-09-30 → 2022-09-30 (the 12 NPORT-P and 4 N-30D accessions declared by the owner, CHECKED against EDGAR, plus the
remaining N-30D / NPORT-P of those years found in the EDGAR submissions). ``--extend`` attempts 2010-09 → 2017-03 N-30D (only
meaningful once 2017-10 → 2022-09 is complete). Core discrepancies abort atomically; extension discrepancies are reported per target and never admitted. Nothing after 2022-09-30 is ingested.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.data.archive import ArchiveStore  # noqa: E402
from pitquant.data.providers.sec_edgar.client import SECClient, UrllibTransport  # noqa: E402
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402
from pitquant.universe.sp500_anchor_ingest import (  # noqa: E402
    AnchorTarget,
    AnchorVerificationError,
    IngestReport,
    declared_targets,
    discover_filings,
    discovered_targets,
    fetch_and_archive,
    ingest,
    parse_anchor,
    persist_anchors,
    resolve_targets,
    schedule_period,
)

# September 2010 bounds January 2011. The 2013 accession is pinned to
# distinguish the genuine filing from the misdated 2014 submission.
EXTENSION = [
    AnchorTarget(
        date(y, m, 30 if m == 9 else 31),
        "N-30D",
        "0001193125-13-457894" if (y, m) == (2013, 9) else None,
    )
    for y in range(2010, 2018)
    for m in (3, 9)
    if date(2010, 9, 30) <= date(y, m, 30 if m == 9 else 31) < date(2017, 9, 30)
]


def extend_anchors(
    session: Session, client: SECClient, store: ArchiveStore
) -> tuple[IngestReport, list[str]]:
    """Core ingestion remains atomic. Extension targets fail closed individually.

    Missing/conflicting filings are reported; only independently verified documents
    are admitted. In particular, the 2014 metadata anomaly is never corrected here.
    """
    found = discover_filings(client)
    ok, errors = resolve_targets(found, EXTENSION)
    parsed = []
    for _, filing in ok:
        docs = fetch_and_archive(session, client, store, filing)
        try:
            if schedule_period(docs.primary) is None:
                raise AnchorVerificationError(f"{filing.accession}: schedule date not extracted")
            parsed.append(parse_anchor(docs, filing))
        except AnchorVerificationError as exc:
            errors.append(str(exc))
    return persist_anchors(session, parsed), errors


def main(extend: bool) -> int:
    ua = os.environ.get("PITQUANT_SEC_USER_AGENT", "")
    if "@" not in ua:
        print("PITQUANT_SEC_USER_AGENT (with a contact e-mail) is required", file=sys.stderr)
        return 2
    cfg = get_settings()
    targets: list[AnchorTarget] = declared_targets() + discovered_targets()
    client = SECClient(UrllibTransport(), ua)
    with make_session_factory(make_engine(cfg.database.url))() as s:
        rep, _ = ingest(s, client, ArchiveStore(ROOT / cfg.archive.root), targets)
        extension_report, errors = (
            extend_anchors(s, client, ArchiveStore(ROOT / cfg.archive.root))
            if extend
            else (None, [])
        )
        s.commit()
    print(json.dumps({"extension_errors": errors,
                      "extension_identity_conflicts": extension_report.identity_conflicts if extension_report else [],
                      "extension_created_securities": extension_report.created_securities if extension_report else 0, "extension_created_anchors": extension_report.created_anchors if extension_report else [], "created_anchors": rep.created_anchors, "skipped_existing": rep.skipped_existing, "created_securities": rep.created_securities, "reused_securities": rep.reused_securities,
                      "identity_conflicts": rep.identity_conflicts, "crosschecks": [{k: v for k, v in c.items() if not k.startswith("_")} for c in rep.crosschecks], "sec_requests": client.requests_made}, indent=2))  # fmt: skip
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main("--extend" in sys.argv))
