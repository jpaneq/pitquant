# ruff: noqa: E501
"""Ingest the SEC Official List of Section 13(f) Securities (ADR-0033). PITQUANT_SEC_USER_AGENT required (never persisted).

python scripts/ingest_13f_lists.py [FIRST LAST | --anchor-quarters]      # default 2017Q3 2022Q3
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.data.archive import ArchiveStore  # noqa: E402
from pitquant.data.providers.sec_13f_list import ingest_quarters, quarters  # noqa: E402
from pitquant.data.providers.sec_edgar.client import SECClient, UrllibTransport  # noqa: E402
from pitquant.db.models import SP500Anchor  # noqa: E402
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402
from pitquant.universe.identity_bridge import quarter_of  # noqa: E402
from pitquant.universe.sp500_anchor_graph import pre_holdout_limit  # noqa: E402


def main() -> int:
    ua = os.environ.get("PITQUANT_SEC_USER_AGENT", "")
    if "@" not in ua:
        print("PITQUANT_SEC_USER_AGENT is required", file=sys.stderr)
        return 2
    first, last = (sys.argv[1], sys.argv[2]) if len(sys.argv) == 3 else ("2017Q3", "2022Q3")
    cfg = get_settings()
    with make_session_factory(make_engine(cfg.database.url))() as s:
        wanted = (
            sorted(
                {
                    quarter_of(d)
                    for d in s.scalars(
                        select(SP500Anchor.as_of_date).where(
                            SP500Anchor.status == "VERIFIED",
                            SP500Anchor.as_of_date <= pre_holdout_limit(cfg),
                        )
                    )
                }
            )
            if "--anchor-quarters" in sys.argv
            else quarters(first, last)
        )
        counts = ingest_quarters(
            s,
            SECClient(UrllibTransport(timeout_s=180), ua),
            ArchiveStore(ROOT / cfg.archive.root),
            wanted,
        )
        s.commit()
    print(json.dumps(counts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
