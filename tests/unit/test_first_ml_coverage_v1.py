"""Owner-fixed structural gates; synthetic cohorts, no fitting or performance."""

from __future__ import annotations

import copy
from datetime import UTC, date, datetime
from typing import Any

import pytest

from pitquant.research import first_ml as FM
from pitquant.research import first_ml_contract as C
from pitquant.research.coverage_v1 import audit_coverage, partition_pass, structural_month


def sample() -> tuple[
    dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[tuple[str, Any], dict[str, Any]]
]:
    projection: dict[str, Any] = {"rows": []}
    snaps = []
    targets = {}
    partitions = {}
    for role, year, count in (("TRAIN", 2014, 40), ("TEST", 2018, 40)):
        rows = []
        months = []
        for month in range(1, 13):
            at = datetime(year, month, 2, 14, tzinfo=UTC)
            months.append({"month": at.strftime("%Y-%m")})
            for i in range(count):
                sid = f"SYN{i}"
                row = {
                    "security_id": sid,
                    "issuer_id": f"SYNISS{i}",
                    "decision_at": at.isoformat(),
                    "family_reasons": {"PRICE": [], "FUNDAMENTALS": []},
                    "touches_holdout": False,
                    "touches_oot": False,
                }
                rows.append(row)
                projection["rows"].append(
                    {
                        "security_id": sid,
                        "issuer_id": row["issuer_id"],
                        "decision_session": at.date().isoformat(),
                        "membership_research_eligible": True,
                        "evidence_tier": "CORROBORATED_HISTORICAL",
                        "evidence_version": "d02-membership-evidence-v1",
                        "provenance": [{"synthetic": True}],
                        "sector": "SYNTHETIC",
                    }
                )
                snaps.append(
                    {
                        "security_id": sid,
                        "decision_at": at,
                        "decision_session": at.date(),
                        "exchange": "XNYS",
                        "features": dict.fromkeys(C.M4.features, 1),
                    }
                )
                targets[sid, at] = {
                    "outperform": bool(i % 2),
                    "exit_session": date(year + 1, month, 2),
                }
        partitions[role] = {"rows": rows, "rows_by_month": months}
    audit = {
        "folds": [{"index": i, "label_safe": True, **copy.deepcopy(partitions)} for i in range(3)]
    }
    return audit, projection, snaps, targets


def test_legacy_100_is_not_gate_and_global_identity_partial_is_independent() -> None:
    report = audit_coverage(*sample())
    assert C.REQUIRED_SECURITIES == 100
    assert report["ready"] and not report["legacy_gate_used"]
    gates = {g: {"status": "READY"} for g in FM.REQUIRED_GATES}
    gates["US_SECURITY_IDENTITY_READY"] = {"status": "PARTIAL"}
    assert FM.first_ml_baseline_ready(gates, FM.REQUIRED_GATES)


@pytest.mark.parametrize(
    ("family", "n", "den", "passes"),
    [
        ("PRICE", 39, 40, False),
        ("PRICE", 40, 50, True),
        ("PRICE", 40, 51, False),
        ("FUNDAMENTALS", 29, 40, False),
        ("FUNDAMENTALS", 30, 40, True),
        ("FUNDAMENTALS", 30, 44, False),
        ("COMBINED", 30, 40, True),
        ("COMBINED", 30, 44, False),
        ("PRICE", 40, 0, False),
    ],
)
def test_fixed_monthly_thresholds(family: str, n: int, den: int, passes: bool) -> None:
    assert structural_month(n, den, family)["passes"] is passes


def test_train_90_percent_and_test_full_twelve() -> None:
    assert partition_pass([{"passes": True}] * 9 + [{"passes": False}], "TRAIN")
    assert not partition_pass([{"passes": True}] * 8 + [{"passes": False}] * 2, "TRAIN")
    assert not partition_pass([{"passes": True}] * 11, "TEST")
    assert not partition_pass([{"passes": True}] * 11 + [{"passes": False}], "TEST")


def test_duplicate_classes_do_not_inflate_issuers() -> None:
    audit, projection, snaps, targets = sample()
    for p in projection["rows"]:
        p["issuer_id"] = "SYNISS0"
    for fold in audit["folds"]:
        for role in ("TRAIN", "TEST"):
            for row in fold[role]["rows"]:
                row["issuer_id"] = "SYNISS0"
    report = audit_coverage(audit, projection, snaps, targets)
    stats = report["folds"][0]["families"]["PRICE"]["TEST"]
    assert stats["unique_securities"] == 40 and stats["unique_issuers"] == 1
    assert not report["ready"]


def test_common_train_and_test_identical_for_all_models_native_can_differ() -> None:
    audit, projection, snaps, targets = sample()
    for fold in audit["folds"]:
        for role in ("TRAIN", "TEST"):
            for row in fold[role]["rows"]:
                if row["security_id"] == "SYN0":
                    row["family_reasons"]["FUNDAMENTALS"] = ["FUNDAMENTALS_NOT_READY"]
    report = audit_coverage(audit, projection, snaps, targets)
    for f in report["folds"]:
        for role in ("TRAIN", "TEST"):
            common = f["PRIMARY_COMMON_COHORT"][role]
            assert common["rows"] == 39 * 12
            assert common["models"] == [m.model_id for m in C.MODELS]
            assert f["families"]["PRICE"][role]["rows"] == 40 * 12
            assert not any(k[0] == "SYN0" for k in common["observation_keys"])


@pytest.mark.parametrize("role", ["TRAIN", "TEST"])
def test_single_class_rejected_after_cohort_freezing(role: str) -> None:
    audit, projection, snaps, targets = sample()
    year = 2014 if role == "TRAIN" else 2018
    for (_, at), target in targets.items():
        if at.year == year:
            target["outperform"] = True
    report = audit_coverage(audit, projection, snaps, targets)
    assert not report["ready"]
    assert not report["folds"][0]["PRIMARY_COMMON_COHORT"][role]["labels"]["non_degenerate"]


@pytest.mark.pit
def test_excluded_identity_never_enters_common_cohort() -> None:
    audit, projection, snaps, targets = sample()
    for p in projection["rows"]:
        if p["security_id"] == "SYN0":
            p["membership_research_eligible"] = False
            p["evidence_tier"] = "UNVERIFIED"
    for fold in audit["folds"]:
        for role in ("TRAIN", "TEST"):
            for row in fold[role]["rows"]:
                if row["security_id"] == "SYN0":
                    row["family_reasons"] = {
                        f: ["MEMBERSHIP_UNVERIFIED"] for f in ("PRICE", "FUNDAMENTALS")
                    }
    report = audit_coverage(audit, projection, snaps, targets)
    assert report["identity_valid"]
    assert not any(
        k[0] == "SYN0"
        for k in report["folds"][0]["PRIMARY_COMMON_COHORT"]["TEST"]["observation_keys"]
    )


@pytest.mark.pit
@pytest.mark.parametrize("year", [2023, 2026])
def test_sealed_and_oot_fold_rejected(year: int) -> None:
    audit, projection, snaps, targets = sample()
    audit["folds"][0]["TEST"]["rows_by_month"][0]["month"] = f"{year}-01"
    with pytest.raises(ValueError, match="sealed or OOT"):
        audit_coverage(audit, projection, snaps, targets)


@pytest.mark.pit
def test_no_performance_inspection_or_label_driven_selection() -> None:
    args = sample()
    before = audit_coverage(*args)
    for t in args[3].values():
        t.update({"auc": 1, "sharpe": -999, "total_return": 1e20})
        t["outperform"] = not t["outperform"]
    after = audit_coverage(*args)
    assert before["ready"] == after["ready"]
    for b, a in zip(before["folds"], after["folds"], strict=True):
        assert b["families"] == a["families"]
        assert (
            b["PRIMARY_COMMON_COHORT"]["TEST"]["cohort_sha256"]
            == a["PRIMARY_COMMON_COHORT"]["TEST"]["cohort_sha256"]
        )


def test_missing_identity_fails_closed() -> None:
    audit, projection, snaps, targets = sample()
    projection["rows"][0]["issuer_id"] = None
    report = audit_coverage(audit, projection, snaps, targets)
    assert not report["identity_valid"] and not report["ready"]


def test_missing_month_remains_in_train_denominator() -> None:
    audit, projection, snaps, targets = sample()
    for f in audit["folds"]:
        f["TRAIN"]["rows"] = [r for r in f["TRAIN"]["rows"] if r["decision_at"][5:7] != "01"]
    report = audit_coverage(audit, projection, snaps, targets)
    assert report["ready"]
    assert report["folds"][0]["families"]["PRICE"]["TRAIN"]["passing_months"] == 11
    assert report["folds"][0]["families"]["PRICE"]["TRAIN"]["required_passing_months"] == 11


def test_missing_test_month_fails_despite_eleven_good_months() -> None:
    audit, projection, snaps, targets = sample()
    for f in audit["folds"]:
        f["TEST"]["rows"] = [r for r in f["TEST"]["rows"] if r["decision_at"][5:7] != "01"]
    report = audit_coverage(audit, projection, snaps, targets)
    assert not report["ready"]
    assert report["folds"][0]["failures"][0]["failing_months"][0]["issuers"] == 0


def test_common_cohort_archive_idempotent_revision_and_immutable(session, tmp_path) -> None:
    from pitquant.core.errors import ImmutableRecordError
    from pitquant.data.archive import ArchiveStore
    from pitquant.db.models import RawSourceArchive
    from pitquant.research.coverage_v1 import persist_coverage

    store = ArchiveStore(tmp_path)
    report = audit_coverage(*sample())
    original = persist_coverage(session, store, report)
    assert persist_coverage(session, store, report) == original
    amended = copy.deepcopy(report)
    amended["limitations"].append("SYNTHETIC additional limitation")
    revision = persist_coverage(session, store, amended)
    assert original["sha256"] != revision["sha256"]
    assert store.get(original["sha256"]) != store.get(revision["sha256"])
    row = session.get_one(RawSourceArchive, original["archive_id"])
    session.commit()
    row.notes = "SYNTHETIC attempted modification"
    with pytest.raises(ImmutableRecordError):
        session.flush()
    session.rollback()
