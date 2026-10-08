"""Independent offline contract verification of targeted data closure artifacts."""

import gzip
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import pytest

from pitquant.research import us_coverage_scale as A
from pitquant.research import us_universe_scale as U

DOCS = Path(__file__).resolve().parents[2] / "docs"


@pytest.fixture(scope="module")
def closure():
    return json.loads((DOCS / "US_LARGE_CAP_RESEARCH_TARGETED_CLOSURE_V1.json").read_bytes())


def test_source_preservation_and_exact_bounded_capacity_retry(closure):
    storage = closure["storage"]
    assert storage["capacity_blockage_eliminated"]
    assert len(storage["retry_ledger"]) == storage["successful_urls"] == 186
    assert storage["recovered_ciks"] == 39
    assert storage["failed_urls"] == 0
    assert len({r["url"] for r in storage["retry_ledger"]}) == 186
    assert all(
        r["before"]["error"] == "DISK_CAPACITY_RESERVE_5_GIB" for r in storage["retry_ledger"]
    )
    assert all(
        r["after"]["sha256"] and r["after"]["status"] == 200 for r in storage["retry_ledger"]
    )
    assert (
        sum(r["bytes_saved"] for r in storage["compaction_ledger"])
        == storage["allocated_bytes_saved"]
    )
    net = sum(g["COMBINED"] for g in closure["stage_net_gains"].values())
    assert net == 466
    assert (
        closure["after"]["combined_issuer_months"] - closure["before"]["combined_issuer_months"]
        == net
    )
    assert closure["stage_losses"]["sec5"]["COMBINED"] == 72
    for ledger in ("frozen_artifact_hashes", "implementation_hashes"):
        for path, sha in closure[ledger].items():
            assert hashlib.sha256((DOCS.parent / path).read_bytes()).hexdigest() == sha


@pytest.mark.pit
def test_target_free_candidate_reconciles_scientific_counts_and_frozen_folds(closure):
    data = (DOCS / closure["candidate"]["path"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == closure["candidate"]["sha256"]
    payload = json.loads(gzip.decompress(data))
    assert not payload["has_targets"] and not payload["training_ready"]
    assert U.digest(payload["scientific_rows"]) == closure["candidate"]["scientific_sha256"]
    assert len(payload["rows"]) == len(payload["scientific_rows"]) == 42977
    assert len({r["security_id"] for r in payload["rows"]}) == 696
    A.validate_candidate(payload["rows"])
    months = [m["month"] for m in closure["after"]["months"]]
    assert U.aggregate(payload["rows"], months) == closure["after"]
    counts = defaultdict(set)
    for row, sci in zip(payload["rows"], payload["scientific_rows"], strict=True):
        assert (row["security_id"], row["month"]) == (sci["security_id"], sci["month"])
        if sci["combined_scientific_eligible"]:
            assert row["eligibility"]["COMBINED"]
            assert all(
                sci[k]
                for k in (
                    "membership_valid",
                    "identity_valid",
                    "price_valid",
                    "benchmark_valid",
                    "fundamental_valid",
                    "feature_valid",
                    "label_constructible",
                )
            )
            counts[row["month"]].add(row["issuer_id"])
    assert len(months) == 85
    assert [len(counts[m]) for m in months] == [
        m["scientific_issuers"] for m in closure["scientific"]["months"]
    ]
    frozen = json.loads((DOCS / "FIRST_ML_COVERAGE_AUDIT.json").read_bytes())
    for original, current in zip(frozen["folds"], closure["folds"], strict=True):
        assert current["dates"] == original["dates"]
        assert current["fit_at"] == original["fit_at"]
        for part in ("TRAIN", "TEST"):
            expected = sorted(original["PRIMARY_COMMON_COHORT"][part]["monthly_issuers"])
            assert current["months"][part] == expected
            assert (
                U.summarize_counts([len(counts[m]) for m in expected])
                == current["scientific_coverage"][part]
            )


def test_no_double_counting_mapping_or_repair_associations(closure):
    reviewed = closure["xbrl_mapping_debt"]
    assert len(reviewed) == 113
    assert all(r["issuer_month_impact"] >= 100 or r["issuer_count"] >= 5 for r in reviewed)
    assert all(r["primary_taxonomy_definition"] for r in reviewed)
    units = set().union(*(set(map(tuple, r["units"])) for r in closure["marginal_repairs"]))
    assert len(units) == closure["repair_curve"]["all"] == 538
    assert sum(closure["stage_gains"][s]["COMBINED"] for s in ("storage", "sec5", "aliases")) == 538
    assert closure["dev_adaptive_iteration"] == 2
    assert (
        closure["new_fits"]
        == closure["holdout_outcomes_accessed"]
        == closure["oot_outcomes_accessed"]
        == 0
    )
