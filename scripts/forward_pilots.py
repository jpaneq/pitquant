"""Train once / generate real forward forecasts / review without opening trades."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

# Set before importing numerical libraries. Never change the user's environment files.
for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[name] = "2"

from pitquant.config.settings import get_settings  # noqa: E402
from pitquant.db.session import make_engine, make_session_factory  # noqa: E402
from pitquant.forward.service import run_cycle  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", action="store_true", help="Initial V1 fit, once per market")
    parser.add_argument(
        "--candidate",
        action="store_true",
        help="Monthly challenger; requires mature forward labels",
    )
    parser.add_argument(
        "--replay",
        action="store_true",
        help="Chronological replay of permitted 12/24-month segments",
    )
    args = parser.parse_args()
    cfg = get_settings()
    factory = make_session_factory(make_engine(cfg.database.url))
    with factory() as session:
        result = run_cycle(
            session,
            Path("data/forward-pilots-v1"),
            train=args.train,
            candidate=args.candidate,
            cfg=cfg,
        )
        if args.replay:
            from pitquant.core.timeutils import utc_now
            from pitquant.forward.replay import replay_window

            result["replays"] = [
                replay_window(session, m, h, utc_now(), Path("data/forward-pilots-v1/replay"))
                for m in ("EQUITY", "BTC")
                for h in (12, 24)
            ]
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
