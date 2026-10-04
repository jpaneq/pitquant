# ruff: noqa: E501
"""Build the RUN 3 research dataset (features + ranks + targets) into the database. Idempotent (existing rows are skipped). Usage: PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db python scripts/build_research_dataset.py"""

import json
import os
import warnings

from pitquant.db.session import make_engine, make_session_factory
from pitquant.research.dataset_v1 import build_research_dataset

warnings.filterwarnings("ignore")
with make_session_factory(make_engine(os.environ["PITQUANT_DATABASE_URL"]))() as s:
    r = build_research_dataset(s)
    s.commit()
print(json.dumps({k: v for k, v in r.items() if k != "_cohorts"}, indent=1, default=str))
