# ruff: noqa: E501
"""Ingest the SEC-filed SPY anchors (ADR-0032). Needs PITQUANT_SEC_USER_AGENT in the environment (never persisted).

    PITQUANT_SEC_USER_AGENT="..." PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db python scripts/ingest_spy_anchors.py [--extend]

Core chain 2017-09-30 → 2022-09-30 (the 12 NPORT-P and 4 N-30D accessions declared by the owner, CHECKED against EDGAR, plus the
remaining N-30D / NPORT-P of those years found in the EDGAR submissions). ``--extend`` adds 2014-09 → 2017-03 N-30D (only
meaningful once 2017-10 → 2022-09 is complete). Any discrepancy aborts BEFORE anything is stored. Nothing after 2022-09-30 is ingested.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.data.archive import ArchiveStore  # noqa: E402
from pitquant.data.providers.sec_edgar.client import SECClient, UrllibTransport  # noqa: E402
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402
from pitquant.universe.sp500_anchor_ingest import (  # noqa: E402
    AnchorTarget,
    declared_targets,
    discovered_targets,
    ingest,
)

EXTENSION = [
    date(2014, 9, 30),
    date(2015, 3, 31),
    date(2015, 9, 30),
    date(2016, 3, 31),
    date(2016, 9, 30),
    date(2017, 3, 31),
]


def main(extend: bool) -> int:
    ua = os.environ.get("PITQUANT_SEC_USER_AGENT", "")
    if "@" not in ua:
        print("PITQUANT_SEC_USER_AGENT (with a contact e-mail) is required", file=sys.stderr)
        return 2
    cfg = get_settings()
    targets: list[AnchorTarget] = declared_targets() + discovered_targets()
    if extend:
        targets += [AnchorTarget(d, "N-30D") for d in EXTENSION]
    client = SECClient(UrllibTransport(), ua)
    with make_session_factory(make_engine(cfg.database.url))() as s:
        rep, _ = ingest(s, client, ArchiveStore(ROOT / cfg.archive.root), targets)
        s.commit()
    print(json.dumps({"created_anchors": rep.created_anchors, "skipped_existing": rep.skipped_existing, "created_securities": rep.created_securities, "reused_securities": rep.reused_securities,
                      "identity_conflicts": rep.identity_conflicts, "crosschecks": [{k: v for k, v in c.items() if not k.startswith("_")} for c in rep.crosschecks], "sec_requests": client.requests_made}, indent=2))  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--extend" in sys.argv))
