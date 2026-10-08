#!/usr/bin/env python3
"""Replay the frozen availability audit into separate intermediate revisions."""

from __future__ import annotations

import argparse
import importlib.util
import shutil
from pathlib import Path

from pitquant.research import us_coverage_scale as A
from pitquant.research import us_targeted_closure as T

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "data/research/us-targeted-closure-v1"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("storage", "sec5", "aliases"))
    args = parser.parse_args()
    dest = WORK / args.stage
    dest.mkdir(parents=True, exist_ok=True)
    for filename in (
        "FIRST_ML_COVERAGE_AUDIT.json",
        "FIRST_ML_FOLD_AUDIT.json",
        "D02_MEMBERSHIP_SOURCE_MANIFEST.json",
    ):
        shutil.copy2(ROOT / "docs" / filename, dest / filename)
    spec = importlib.util.spec_from_file_location(
        "scale_audit", ROOT / "scripts/audit_us_research_scale.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.WORK, module.DOCS = WORK, dest
    if args.stage in ("sec5", "aliases"):
        A.CORE_TAGS = A.CORE_TAGS | {
            "ProfitLoss",
            "NetIncomeLossAttributableToNoncontrollingInterest",
        }
        A.core_fundamentals = T.core_fundamentals
    module.main()


if __name__ == "__main__":
    main()
