"""Resolve preregistered implementation defaults and synthetic smoke before any real fit."""

from __future__ import annotations

import importlib.metadata
import json
import platform
from pathlib import Path

import numpy as np
import xgboost

from pitquant.research.ranker_adapters import XGBRankerAdapter
from pitquant.research.ranking_preregistration import EXPERIMENT, digest, encoded, write_once

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    plan = json.loads((ROOT / "docs" / (EXPERIMENT + "_MANIFEST.json")).read_bytes())
    params = {
        **plan["contracts"]["models"]["L2R_M4"]["params"],
        "objective": "rank:ndcg",
        "booster": "gbtree",
        "gamma": 0.0,
        "base_score": 0.5,
        "boost_from_average": 0,
        "colsample_bylevel": 1.0,
        "colsample_bynode": 1.0,
        "max_delta_step": 0.0,
        "max_leaves": 0,
        "num_parallel_tree": 1,
        "sampling_method": "uniform",
        "monotone_constraints": "()",
        "interaction_constraints": "",
        "validate_parameters": True,
        "verbosity": 0,
        "disable_default_eval_metric": True,
    }
    params.update(plan["contracts"]["grid"][0])
    rng = np.random.default_rng(20261009)
    x = rng.normal(size=(60, 4))
    qid = np.repeat(np.arange(6, dtype=np.int64), 10)
    y = np.tile(np.arange(10, dtype=float), 6)
    x[:, 0] += y
    adapter = XGBRankerAdapter(params)
    adapter.fit(x, y, qid)
    scores = adapter.predict(x, qid)
    destination = ROOT / "data/research/equity-ranking-v0/synthetic-smoke"
    adapter.serialize(destination)
    loaded = XGBRankerAdapter.load(destination)
    again = XGBRankerAdapter(params)
    again.fit(x, y, qid)
    if not np.array_equal(scores, loaded.predict(x, qid)) or not np.array_equal(
        scores, again.predict(x, qid)
    ):
        raise ValueError("synthetic serialization/determinism failure")
    common = {k: v for k, v in params.items() if k not in plan["contracts"]["grid"][0]}
    completion = {
        "status": "PREREGISTRATION_IMPLEMENTATION_COMPLETION",
        "experiment_id": EXPERIMENT,
        "preregistration_sha256": plan["manifest_sha256"],
        "parameters_fixed": common,
        "grid": plan["contracts"]["grid"],
        "resolved_defaults": {
            "gamma": 0.0,
            "base_score": 0.5,
            "boost_from_average": 0,
            "note": (
                "Explicit constant initial score disables automatic intercept estimation; "
                "ranking translation-invariant. Other unspecified tree defaults mirror "
                "upstream 3.1.3, no new grid."
            ),
        },
        "sources": [
            "https://raw.githubusercontent.com/dmlc/xgboost/v3.1.3/src/tree/param.h",
            "https://raw.githubusercontent.com/dmlc/xgboost/v3.1.3/src/objective/lambdarank_obj.cc",
            "https://xgboost.readthedocs.io/en/release_3.1.0/parameter.html",
        ],
        "missing": "native NaN",
        "synthetic_smoke": {
            "fit": True,
            "predict": True,
            "qid": True,
            "grades_0_9": True,
            "serialization_reload": True,
            "deterministic_exact": True,
            "real_outcomes": 0,
        },
        "synthetic_booster_config": adapter.metadata()["booster_config"],
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "xgboost": importlib.metadata.version("xgboost"),
            "scikit-learn": importlib.metadata.version("scikit-learn"),
            "numpy": importlib.metadata.version("numpy"),
            "build_info": xgboost.build_info(),
        },
        "real_fits_before_completion": 0,
        "holdout_outcomes_accessed": 0,
        "oot_outcomes_accessed": 0,
    }
    completion["sha256"] = digest(completion)
    write_once(
        ROOT / "docs" / (EXPERIMENT + "_IMPLEMENTATION_COMPLETION.json"), encoded(completion)
    )
    print("Synthetic smoke and implementation completion frozen", completion["sha256"])


if __name__ == "__main__":
    main()
