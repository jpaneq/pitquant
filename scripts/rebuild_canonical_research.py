"""Rebuild append-only canonical Yahoo snapshots/targets; never trains models."""

from __future__ import annotations

import argparse
import json

from pitquant.config.settings import get_settings
from pitquant.db.session import make_engine, make_session_factory
from pitquant.research.dataset_v1 import build_research_dataset
from pitquant.research.targets_v2 import build_targets_v2


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets-only", action="store_true")
    args = parser.parse_args()
    with make_session_factory(make_engine(get_settings().database.url))() as session:
        report = {}
        if not args.targets_only:
            report["features"] = build_research_dataset(session, canonical_only=True)
            session.commit()
        report["targets"] = build_targets_v2(session, canonical_only=True)
        session.commit()
        print(json.dumps(report, default=str))


if __name__ == "__main__":
    main()
