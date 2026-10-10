"""Preflight the metadata correction only; no estimator or execution API."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from pitquant.research.feature_availability import require_feature_availability
from pitquant.research.ranker_manifest_contract import assert_ranker_feature_binding
from pitquant.research.ranking_preregistration import digest, encoded, verify_manifest, write_once

ROOT = Path(__file__).resolve().parents[1]
ID = "FIRST_EQUITY_CROSS_SECTIONAL_RANK_12M_V0R1"


def main() -> None:
    manifest = json.loads(
        (ROOT / "docs" / (ID + "_MANIFEST_METADATA_REVISION_2.json")).read_bytes()
    )
    verify_manifest(manifest)
    assert_ranker_feature_binding(manifest)
    inputs = json.loads(
        gzip.decompress((ROOT / "data/research/equity-ranking-v0r1/inputs.json.gz").read_bytes())
    )
    integrity = json.loads(
        (ROOT / "data/research/equity-ranking-v0r1/inputs-integrity.json").read_bytes()
    )
    if digest(inputs) != integrity["sha256"]:
        raise ValueError("derived input hash mismatch")
    require_feature_availability(
        inputs["rows"], manifest["contracts"], tuple(manifest["contracts"]["features"]["names"])
    )
    write_once(
        ROOT / "docs" / (ID + "_METADATA_REVISION_2_PREFLIGHT.json"),
        encoded(
            {
                "status": "PASSED_PREFLIGHT_ONLY_NOT_EXECUTED",
                "manifest_sha256": manifest["manifest_sha256"],
                "input_sha256": integrity["sha256"],
                "feature_contract_sha256": manifest["feature_contract_sha256"],
                "real_fits_in_this_correction": 0,
                "outer_predictions": 0,
                "dev_adaptive_iteration": 3,
                "first_attempt_remains_invalidated": True,
                "execution_permission": "HUMAN_REVIEW_REQUIRED; NO_REPLAY_OR_RERUN",
            }
        ),
    )


if __name__ == "__main__":
    main()
