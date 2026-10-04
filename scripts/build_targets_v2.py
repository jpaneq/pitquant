# ruff: noqa: E501
"""Rebuild the research targets on the COMPARABLE return basis (ADR-0049). Idempotent; append-only. PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db python scripts/build_targets_v2.py"""

import json
import os
import warnings

from pitquant.db.session import make_engine, make_session_factory
from pitquant.research.targets_v2 import build_targets_v2

warnings.filterwarnings("ignore")
with make_session_factory(make_engine(os.environ["PITQUANT_DATABASE_URL"]))() as s:
    r = build_targets_v2(s)
    s.commit()
print(json.dumps(r, indent=1, default=str))
