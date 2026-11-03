"""Read-only audit of archived rule decisions; never create orders or tune rules."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pitquant.config.settings import get_settings
from pitquant.db.session import make_engine, make_session_factory
from pitquant.positions.audit import audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    cfg = get_settings()
    with make_session_factory(make_engine(cfg.database.url))() as s:
        result = audit(s, cfg)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
