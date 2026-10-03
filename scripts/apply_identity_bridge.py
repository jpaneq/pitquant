# ruff: noqa: E501
"""Apply the SEC-evidence identity bridge (ADR-0033): 13F-list CUSIPs for name-only N-30D securities + the six verified successions. Idempotent."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402
from pitquant.universe.identity_bridge import apply_resolutions, bridge_name_only  # noqa: E402


def main() -> int:
    with make_session_factory(make_engine(get_settings().database.url))() as s:
        res = apply_resolutions(s)
        br = bridge_name_only(s)
        s.commit()
    print(
        json.dumps(
            {
                "resolutions": [r.__dict__ for r in res],
                "name_only_total": len(br),
                "bridge": dict(Counter(b.status for b in br)),
                "linked_to_existing_cusip_security": sum(1 for b in br if b.linked_to),
                "unresolved": [
                    {"name": b.name, "status": b.status, "cands": b.candidates[:3]}
                    for b in br
                    if b.status != "RESOLVED"
                ],
            },
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
