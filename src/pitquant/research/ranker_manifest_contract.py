"""Explicit common-feature metadata bindings, independent of estimator outcomes."""

from __future__ import annotations

from typing import Any

from pitquant.research.ranking_preregistration import digest


def assert_ranker_feature_binding(manifest: dict[str, Any]) -> None:
    features = manifest["contracts"]["features"]
    n = len(features["names"])
    sha = digest(features)
    if n != features["base_count"] or sha != manifest["feature_contract_sha256"]:
        raise ValueError("raw feature contract binding mismatch")
    models = manifest["contracts"]["models"]
    for name in ("L2R_M4", "EXPANDED_M4R_CONTROL"):
        if (
            models[name].get("raw_feature_count") != n
            or models[name].get("raw_feature_contract_sha256") != sha
        ):
            raise ValueError("explicit common RAW feature count/hash required before fit")
    if models["EXPANDED_M4R_CONTROL"].get("transformed_feature_count") != 2 * n:
        raise ValueError("control missingness indicator contract mismatch")
