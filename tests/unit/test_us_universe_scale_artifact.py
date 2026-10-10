"""Offline verification of the delivered availability candidate, without outcomes."""

import gzip
import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from pitquant.research import us_coverage_scale as A
from pitquant.research import us_universe_scale as U

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"


@pytest.fixture(scope="module")
def reports():
    return tuple(
        json.loads((DOCS / (name + ".json")).read_bytes())
        for name in (
            "US_LARGE_CAP_RESEARCH_UNIVERSE_V1",
            "US_LARGE_CAP_RESEARCH_COVERAGE_EXPANSION_BASELINE_V1",
        )
    )


def test_frozen_science_and_implementation_are_bound_to_original_bytes(reports):
    universe, _ = reports
    assert universe["initial_head"] == "97743c4c05b676ca4aff633a1afb55fa549274fb"
    assert len(universe["frozen_artifact_hashes"]) >= 39
    for field in ("frozen_artifact_hashes", "implementation_hashes"):
        for path, expected in universe[field].items():
            assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, path


@pytest.mark.pit
def test_delivered_candidate_is_historical_target_free_and_reconciles_reports(reports):
    universe, coverage = reports
    path = DOCS / universe["candidate"]["path"]
    body = path.read_bytes()
    assert hashlib.sha256(body).hexdigest() == universe["candidate"]["sha256"]
    candidate = json.loads(gzip.decompress(body))
    assert not candidate["has_targets"]
    assert not candidate["training_ready"]
    assert candidate["hashes"] == coverage["hashes"] == universe["hashes"]
    rows = candidate["rows"]
    assert len(rows) == universe["historical_membership_records"]
    assert len({r["security_id"] for r in rows}) == universe["unique_securities"]
    assert dict(Counter(r["membership_tier"] for r in rows)) == universe["evidence_tiers"]
    months = [m["month"] for m in coverage["expanded"]["months"]]
    assert len(months) == len(set(months)) == 85
    assert (months[0], months[-1]) == ("2014-09", "2021-09")
    A.validate_candidate(rows)
    assert U.aggregate(rows, months) == coverage["expanded"]
    assert U.digest(rows) == coverage["hashes"]["coverage"]
    for row in rows:
        assert U.START <= date.fromisoformat(row["decision_at"][:10]) <= U.END
        if row["eligibility"]["COMBINED"]:
            assert row["membership_tier"] in ("OFFICIAL_DIRECT", "CORROBORATED_HISTORICAL")
            assert row["identity_status"] == "PRIMARY_MATCH"
            assert not row["blockers"]
    for series in candidate["historical_market_series"].values():
        for bar in series.get("bars", []):
            assert U.PRICE_START <= date.fromisoformat(bar["session"]) <= U.END
    for key in ("holdout_outcomes_accessed", "oot_outcomes_accessed", "new_fits"):
        assert coverage[key] == 0
    assert coverage["dev_adaptive_iteration"] == 2
    assert coverage["scientific_coverage_gate"] == "NOT_DEFINED"
