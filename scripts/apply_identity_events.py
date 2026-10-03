# ruff: noqa: E501
"""Apply the SEC 8-K identity events (Priceline->Booking, Coach->Tapestry, Praxair->Linde), ADR-0034. PITQUANT_SEC_USER_AGENT required."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.data.archive import ArchiveStore  # noqa: E402
from pitquant.data.providers.sec_edgar.client import SECClient, UrllibTransport  # noqa: E402
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402
from pitquant.universe.identity_events import apply_events  # noqa: E402


def main() -> int:
    ua = os.environ.get("PITQUANT_SEC_USER_AGENT", "")
    if "@" not in ua:
        print("PITQUANT_SEC_USER_AGENT is required", file=sys.stderr)
        return 2
    cfg = get_settings()
    with make_session_factory(make_engine(cfg.database.url))() as s:
        res = apply_events(
            s, SECClient(UrllibTransport(timeout_s=120), ua), ArchiveStore(ROOT / cfg.archive.root)
        )
        s.commit()
    print(json.dumps([r.__dict__ for r in res], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
