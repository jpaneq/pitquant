"""BTC_DERIVATIVES_ARCHIVER. Public original collection; no broker, prediction trade or tuning."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pitquant.btc.archive import (  # noqa: E402
    activate_forward,
    baseline_experiment,
    collect,
    forward_cycle,
)
from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.data.archive import ArchiveStore  # noqa: E402
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discover", action="store_true")
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--readiness-only", action="store_true")
    parser.add_argument(
        "--evaluate-only",
        action="store_true",
        help="refresh the archive, then check matured predictions and print the analysis",
    )
    args = parser.parse_args()
    cfg = get_settings()
    with make_session_factory(make_engine(cfg.database.url))() as session:
        if args.readiness_only:
            report = baseline_experiment(session)
            session.commit()
        elif args.evaluate_only:
            from pitquant.btc.evaluation import analysis, evaluate_due
            from pitquant.core.timeutils import utc_now

            collect(session, ArchiveStore(ROOT / cfg.archive.root))  # fetch the target bars first
            report = {
                "run": evaluate_due(session, utc_now()),
                "analysis": analysis(session, utc_now()),
            }
            session.commit()
        else:
            report = collect(session, ArchiveStore(ROOT / cfg.archive.root), discover=args.discover)
            if args.activate:
                activate_forward(session)
                session.commit()
            report["forward"] = forward_cycle(session)
            (ROOT / "data/btc_collection.json").write_text(
                json.dumps(report, indent=2, default=str) + "\n"
            )
        print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
