"""Outcome-free training-feature eligibility shared by every research estimator."""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np

from pitquant.research import equity_baseline as E
from pitquant.research import equity_v1 as V

CONTRACT = "TRAIN_FEATURE_AVAILABILITY_CONTRACT_V1"


def training_blocks(
    rows: list[dict[str, Any]], contracts: dict[str, Any]
) -> list[tuple[str, list[dict[str, Any]]]]:
    keys = [(r["issuer_id"], r["month"]) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate issuer-month")
    # Retain the original cohort, PIT, maturity and exact inner-geometry assertions.
    blocks = []
    for f in contracts["cohorts"]:
        train = [r for r in rows if r["month"] in f["TRAIN"]["monthly_rows"]]
        test = [r for r in rows if r["month"] in f["TEST"]["monthly_rows"]]
        for role, selected in [("TRAIN", train), ("TEST", test)]:
            if (
                dict(sorted(Counter(r["month"] for r in selected).items()))
                != f[role]["monthly_rows"]
            ):
                raise ValueError("complete outer month contract mismatch")
            for row in selected:
                E.assert_row(row, role, f["fit_at"])
        if {r["month"] for r in train} & {r["month"] for r in test}:
            raise ValueError("outer TRAIN/TEST overlap")
        fid = f"F{f['fold']}"
        blocks.append((fid + "/OUTER_TRAIN", train))
        inners = V.inner_folds({"TRAIN": train, "TEST": test, "fit_at": f["fit_at"]})
        declared = contracts["inner_cv"]["geometry"][fid]
        if len(inners) != len(declared):
            raise ValueError("inner geometry mismatch")
        for i, (inner, geometry) in enumerate(zip(inners, declared, strict=True)):
            for role, key in [("train", "TRAIN"), ("validation", "VALIDATION")]:
                if dict(sorted(Counter(r["month"] for r in inner[role]).items())) != {
                    m: f["TRAIN"]["monthly_rows"][m] for m in geometry[key]
                }:
                    raise ValueError("complete inner month contract mismatch")
            if {r["month"] for r in inner["train"]} & {r["month"] for r in inner["validation"]}:
                raise ValueError("inner TRAIN/VALIDATION overlap")
            blocks.append((f"{fid}/INNER_{i}_TRAIN", inner["train"]))
    return blocks


def audit_feature_availability(
    rows: list[dict[str, Any]], contracts: dict[str, Any], names: tuple[str, ...]
) -> dict[str, Any]:
    if not names or len(set(names)) != len(names):
        raise ValueError("empty or duplicate feature contract")
    cells = []
    for block, selected in training_blocks(rows, contracts):
        x = E.matrix(selected, names)
        if np.isinf(x).any():
            raise ValueError("infinite predictor is not legitimate missingness")
        for j, name in enumerate(names):
            n = int(np.isfinite(x[:, j]).sum())
            cells.append(
                {
                    "block": block,
                    "feature": name,
                    "row_count": len(selected),
                    "issuer_count": len({r["issuer_id"] for r in selected}),
                    "finite_count": n,
                    "missing_count": len(selected) - n,
                    "coverage_pct": 100.0 * n / len(selected),
                    "missing_reasons": dict(
                        Counter(
                            r["features"][name]["missing_reason"]
                            for r in selected
                            if r["features"][name]["value"] is None
                        )
                    ),
                }
            )
    removed = [n for n in names if any(c["feature"] == n and not c["finite_count"] for c in cells)]
    return {
        "contract_id": CONTRACT,
        "rule": "at least one finite observed value in EVERY inner and outer TRAIN block",
        "coverage_thresholds": "NONE_OTHER_THAN_FINITE_COUNT_GREATER_THAN_ZERO",
        "features_audited": list(names),
        "training_blocks": len({c["block"] for c in cells}),
        "cells": cells,
        "removed": removed,
        "retained": [n for n in names if n not in removed],
        "decision_uses_model_outcomes": False,
        "status": "PASSED" if not removed else "FEATURE_CONTRACT_REVISION_REQUIRED",
    }


def require_feature_availability(
    rows: list[dict[str, Any]], contracts: dict[str, Any], names: tuple[str, ...]
) -> None:
    audit = audit_feature_availability(rows, contracts, names)
    if audit["removed"]:
        raise ValueError(f"all-missing TRAIN features: {audit['removed']}")
