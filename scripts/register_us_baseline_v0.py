# ruff: noqa: E501
"""Register the BLOCKED research experiment US_BASELINE_V0 (ADR-0031). Idempotent; never trains.

    PITQUANT_DATABASE_URL=sqlite:///data/pitquant.db python scripts/register_us_baseline_v0.py

Universe SP500, FEATURE_V0_51, horizons 6M/12M, benchmark SPY total-return PROXY, models Elastic Net and Logistic
Regression. The block reasons are the closed gates reported by ``research_readiness``; no dataset is attached
while D-02 membership is not proven.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pitquant.config.settings import get_settings
from pitquant.db.session import make_engine, make_session_factory
from pitquant.research.baselines import ELASTIC_NET, LOGISTIC
from pitquant.research.registry import (
    ExperimentSpec,
    define_experiment,
    gates_from_readiness,
)
from pitquant.research.walkforward import WalkForwardConfig
from pitquant.research_readiness import research_readiness


def main() -> int:
    cfg = get_settings()
    with make_session_factory(make_engine(cfg.database.url))() as s:
        rf = research_readiness(s, cfg)
        gates = gates_from_readiness(rf.reasons.get("FEATURE_RESEARCH_READY_US", []))
        spec = ExperimentSpec(
            "US_BASELINE_V0",
            ELASTIC_NET,
            WalkForwardConfig(purge_months=1, embargo_months=1, label_horizon_months=6),
            6,
            "SP500@FEATURE_V0_51",
            "SPY_TOTAL_RETURN_PROXY",
            horizons=(6, 12),
            extra_models=(LOGISTIC,),
        )
        ex = define_experiment(s, spec, None, gates)
        if "dataset not built" not in " ".join(ex.blocked_reasons) and ex.dataset_hash is None:
            pass
        s.commit()
        print(
            json.dumps(
                {
                    "experiment_id": ex.experiment_id,
                    "name": ex.name,
                    "status": ex.status,
                    "commit": ex.commit_sha,
                    "blocked_reasons": ex.blocked_reasons,
                    "trained": False,
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
