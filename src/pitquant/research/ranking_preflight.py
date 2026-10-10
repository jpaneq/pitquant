"""PITQuant-owned cohort/trainability checks, performed before any real estimator fit."""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np

from pitquant.research import equity_baseline as E
from pitquant.research import equity_v1 as V
from pitquant.research import first_ml_contract as C


def audit_inputs(rows: list[dict[str, Any]], contracts: dict[str, Any]) -> dict[str, Any]:
    findings = []
    blocks = []
    for f in contracts["cohorts"]:
        train = [r for r in rows if r["month"] in f["TRAIN"]["monthly_rows"]]
        test = [r for r in rows if r["month"] in f["TEST"]["monthly_rows"]]
        for role, selected in [("TRAIN", train), ("TEST", test)]:
            if (
                dict(sorted(Counter(r["month"] for r in selected).items()))
                != f[role]["monthly_rows"]
            ):
                raise ValueError("preflight complete month contract mismatch")
            for r in selected:
                E.assert_row(r, role, f["fit_at"])
        inners = V.inner_folds({"TRAIN": train, "TEST": test, "fit_at": f["fit_at"]})
        declared = contracts["inner_cv"]["geometry"][f"F{f['fold']}"]
        if len(inners) != len(declared):
            raise ValueError("preflight inner geometry mismatch")
        for i, (inner, geometry) in enumerate(zip(inners, declared, strict=True)):
            for role, key in [("train", "TRAIN"), ("validation", "VALIDATION")]:
                group = inner[role]
                if sorted({r["month"] for r in group}) != geometry[key]:
                    raise ValueError("inner month mismatch")
                if len(group) != sum(f["TRAIN"]["monthly_rows"][m] for m in geometry[key]):
                    raise ValueError("inner row loss")
            x = E.matrix(inner["train"], C.M4.features)
            missing = [n for j, n in enumerate(C.M4.features) if np.isnan(x[:, j]).all()]
            block = {
                "fold": f"F{f['fold']}",
                "inner_index": i,
                "train_months": geometry["TRAIN"],
                "validation_months": geometry["VALIDATION"],
                "train_rows": len(inner["train"]),
                "validation_rows": len(inner["validation"]),
                "all_missing_features": missing,
            }
            blocks.append(block)
            if missing:
                findings.append(
                    {
                        **block,
                        "rule": "all-missing TRAIN feature fails",
                        "reasons": {
                            n: dict(
                                Counter(r["features"][n]["missing_reason"] for r in inner["train"])
                            )
                            for n in missing
                        },
                    }
                )
    return {
        "status": "BLOCKED_FROZEN_ALL_MISSING_TRAIN_FEATURE" if findings else "PASSED",
        "findings": findings,
        "blocks": blocks,
        "inner_blocks": len(blocks),
        "models_fitted_on_real_data": 0,
        "outer_predictions": 0,
        "ranking_metrics_computed": 0,
        "holdout_outcomes_accessed": 0,
        "oot_outcomes_accessed": 0,
    }


def require_trainable(rows: list[dict[str, Any]], contracts: dict[str, Any]) -> None:
    audit = audit_inputs(rows, contracts)
    if audit["findings"]:
        raise ValueError(
            "frozen all-missing TRAIN feature contract blocks real fits; human review required"
        )
