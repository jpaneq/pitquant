"""Pre-training US panel coverage; owner-fixed thresholds (ADR-0057).

Membership denominators include only the configured, reconstructed valid US
cohort, not the full S&P 500. Labels only test class degeneracy; they never
select observations or change the structural thresholds. No model is fitted.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from statistics import median
from typing import Any

from sqlalchemy.orm import Session

from pitquant.data.archive import ArchiveStore, archive_document, sha256_hex
from pitquant.research import first_ml_contract as C
from pitquant.research.membership_evidence import ACCEPTED
from pitquant.research.membership_evidence import VERSION as MEMBERSHIP_VERSION

VERSION = "FIRST_ML_COVERAGE_V1"
FAMILIES = ("PRICE", "FUNDAMENTALS", "COMBINED")
THRESHOLDS: dict[str, dict[str, Any]] = {
    "PRICE": {"issuers": 40, "ratio": 0.8, "denominator": "VALID_MEMBERSHIP_ISSUERS"},
    "FUNDAMENTALS": {"issuers": 30, "ratio": 0.7, "denominator": "PRICE_ELIGIBLE_ISSUERS"},
    "COMBINED": {"issuers": 30, "ratio": 0.7, "denominator": "PRICE_ELIGIBLE_ISSUERS"},
}


def _identity(row: dict[str, Any], period: dict[str, Any] | None) -> bool:
    return bool(
        period
        and row.get("issuer_id")
        and row.get("security_id")
        and row["issuer_id"] == period.get("issuer_id")
        and period.get("membership_research_eligible") is True
        and period.get("evidence_tier") in ACCEPTED
        and period.get("provenance")
        and period.get("evidence_version") == MEMBERSHIP_VERSION
        and period.get("decision_session") == row["decision_at"][:10]
        and not row.get("touches_holdout")
        and not row.get("touches_oot")
    )


def _stats(
    rows: list[dict[str, Any]], months: list[str], sectors: dict[str, str]
) -> dict[str, Any]:
    issuers = Counter(str(r["issuer_id"]) for r in rows)
    securities = {r["security_id"] for r in rows}
    counts = {m: len({r["issuer_id"] for r in rows if r["decision_at"][:7] == m}) for m in months}
    monthly_rows = Counter(r["decision_at"][:7] for r in rows)
    issuer_months = {(r["issuer_id"], r["decision_at"][:7]) for r in rows}
    return {
        "rows": len(rows),
        "unique_securities": len(securities),
        "unique_issuers": len(issuers),
        "unique_months": len(monthly_rows),
        "issuer_month_observations": len(issuer_months),
        "observations_per_issuer": dict(sorted(issuers.items())),
        "observations_per_month": {m: monthly_rows[m] for m in months},
        "monthly_issuers": counts,
        "minimum_monthly_issuers": min(counts.values(), default=0),
        "median_monthly_issuers": median(counts.values()) if counts else 0,
        "maximum_monthly_issuers": max(counts.values(), default=0),
        "top_issuer_observation_share": max(issuers.values(), default=0) / max(len(rows), 1),
        "top_five_issuer_observation_share": sum(n for _, n in issuers.most_common(5))
        / max(len(rows), 1),
        "sector_observations": dict(
            sorted(Counter(sectors.get(r["security_id"], "UNKNOWN") for r in rows).items())
        ),
        "effective_sample_size": "NOT_FORMALLY_ESTIMATED",
    }


def structural_month(issuers: int, denominator: int, family: str) -> dict[str, Any]:
    threshold = THRESHOLDS[family]
    required = max(int(threshold["issuers"]), math.ceil(float(threshold["ratio"]) * denominator))
    return {
        "issuers": issuers,
        "denominator_issuers": denominator,
        "coverage_pct": 100 * issuers / denominator if denominator else None,
        "required_issuers": threshold["issuers"],
        "required_coverage_pct": 100 * float(threshold["ratio"]),
        "minimum_additional_eligible_issuers": max(0, required - issuers),
        "passes": denominator > 0 and issuers >= required,
    }


def partition_pass(months: list[dict[str, Any]], role: str) -> bool:
    if not months:
        return False
    passing = sum(m["passes"] for m in months)
    return (
        (len(months) == C.TEST_MONTHS and passing == len(months))
        if role == "TEST"
        else passing >= math.ceil(0.9 * len(months))
    )


def audit_coverage(
    fold_audit: dict[str, Any],
    projection: dict[str, Any],
    snapshots: list[dict[str, Any]],
    targets: dict[tuple[str, Any], dict[str, Any]],
) -> dict[str, Any]:
    """Freeze outcome-blind common/native cohorts then count DEV binary labels.

    Missing labels/identity/duplicate observation keys fail closed. Family
    missingness comes from first_ml_eligibility; risk fields permit TRAIN-only
    median imputation under the existing M4 contract, not a new complete-case rule.
    """
    periods = {(r["security_id"], r["decision_session"][:7]): r for r in projection["rows"]}
    if len(periods) != len(projection["rows"]):
        raise ValueError("duplicate membership period")
    if any(date.fromisoformat(r["decision_session"]) >= C.HOLDOUT[0] for r in projection["rows"]):
        raise ValueError("sealed or OOT membership period")
    sectors = {r["security_id"]: r.get("sector") or "UNKNOWN" for r in projection["rows"]}
    snaps = {
        (r["security_id"], r["decision_at"].isoformat()): r
        for r in snapshots
        if r["decision_session"] < C.HOLDOUT[0] and r["exchange"] == "XNYS"
    }
    labels = {
        (sid, at.isoformat()): t.get("outperform")
        for (sid, at), t in targets.items()
        if at.date() < C.HOLDOUT[0]
        and (not t.get("exit_session") or t["exit_session"] < C.HOLDOUT[0])
    }
    folds = []
    for fold in fold_audit["folds"]:
        result: dict[str, Any] = {
            "index": fold["index"],
            "label_safe": fold["label_safe"],
            "dates": fold.get("dates"),
            "fit_at": fold.get("fit_at"),
            "families": {},
            "PRIMARY_COMMON_COHORT": {},
            "feature_diagnostics": {},
        }
        selected: dict[tuple[str, str], list[dict[str, Any]]] = {}
        identity_errors: list[tuple[str, str]] = []
        for role in ("TRAIN", "TEST"):
            rows = fold[role]["rows"]
            keys = [(r["security_id"], r["decision_at"]) for r in rows]
            if len(set(keys)) != len(keys):
                raise ValueError("duplicate fold observation")
            months = [m["month"] for m in fold[role]["rows_by_month"]]
            if any(date.fromisoformat(m + "-01") >= C.HOLDOUT[0] for m in months):
                raise ValueError("sealed or OOT fold")
            for family in FAMILIES:
                eligibility_family = "FUNDAMENTALS" if family == "COMBINED" else family
                candidates = [r for r in rows if not r["family_reasons"][eligibility_family]]
                bad = [
                    r
                    for r in candidates
                    if not _identity(r, periods.get((r["security_id"], r["decision_at"][:7])))
                ]
                identity_errors.extend((r["security_id"], r["decision_at"]) for r in bad)
                selected[role, family] = [
                    r
                    for r in candidates
                    if _identity(r, periods.get((r["security_id"], r["decision_at"][:7])))
                ]
            for family in FAMILIES:
                cohort = selected[role, family]
                stats = _stats(cohort, months, sectors)
                monthly = []
                for month in months:
                    if family == "PRICE":
                        denominator = len(
                            {
                                p["issuer_id"]
                                for (_, m), p in periods.items()
                                if m == month
                                and p["membership_research_eligible"]
                                and p.get("issuer_id")
                            }
                        )
                    else:
                        denominator = len(
                            {
                                r["issuer_id"]
                                for r in selected[role, "PRICE"]
                                if r["decision_at"][:7] == month
                            }
                        )
                    monthly.append(
                        {
                            "month": month,
                            **structural_month(
                                stats["monthly_issuers"][month], denominator, family
                            ),
                        }
                    )
                stats.update(
                    {
                        "coverage_by_month": monthly,
                        "passes": partition_pass(monthly, role),
                        "passing_months": sum(m["passes"] for m in monthly),
                        "required_passing_months": len(months)
                        if role == "TEST"
                        else math.ceil(0.9 * len(months)),
                    }
                )
                stats["observation_keys"] = [
                    [r["security_id"], r["decision_at"]]
                    for r in sorted(cohort, key=lambda r: (r["security_id"], r["decision_at"]))
                ]
                stats["cohort_sha256"] = hashlib.sha256(
                    json.dumps(stats["observation_keys"], separators=(",", ":")).encode()
                ).hexdigest()
                stats["cohort_role"] = "FAMILY_NATIVE_COHORT_SECONDARY_ONLY"
                label_counts = Counter(
                    labels.get((r["security_id"], r["decision_at"])) for r in cohort
                )
                stats["labels"] = {
                    "positive": label_counts.get(True, 0),
                    "negative": label_counts.get(False, 0),
                    "missing_or_invalid": len(cohort)
                    - label_counts.get(True, 0)
                    - label_counts.get(False, 0),
                    "base_rate": label_counts.get(True, 0) / len(cohort) if cohort else None,
                }
                result["families"].setdefault(family, {})[role] = stats
            # All M0-M4 use exactly this intersection for both training and test.
            common_keys = set.intersection(
                *(
                    {(r["security_id"], r["decision_at"]) for r in selected[role, family]}
                    for family in FAMILIES
                )
            )
            common = [
                r
                for r in selected[role, "COMBINED"]
                if (r["security_id"], r["decision_at"]) in common_keys
            ]
            common_stats = _stats(common, months, sectors)
            counts = Counter(labels.get((r["security_id"], r["decision_at"])) for r in common)
            binary = counts.get(True, 0) + counts.get(False, 0)
            valid_labels = binary == len(common) and set(counts) <= {True, False}
            common_stats["labels"] = {
                "positive": counts.get(True, 0),
                "negative": counts.get(False, 0),
                "missing_or_invalid": len(common) - binary,
                "base_rate": counts.get(True, 0) / binary if binary else None,
                "non_degenerate": valid_labels
                and counts.get(True, 0) > 0
                and counts.get(False, 0) > 0,
            }
            common_stats["observation_keys"] = [list(k) for k in sorted(common_keys)]
            common_stats["cohort_sha256"] = hashlib.sha256(
                json.dumps(common_stats["observation_keys"], separators=(",", ":")).encode()
            ).hexdigest()
            common_stats["models"] = [m.model_id for m in C.MODELS]
            common_stats["complete_months"] = (
                len(months) == C.TEST_MONTHS and all(common_stats["monthly_issuers"].values())
                if role == "TEST"
                else sum(n > 0 for n in common_stats["monthly_issuers"].values())
                >= math.ceil(0.9 * len(months))
            )
            result["PRIMARY_COMMON_COHORT"][role] = common_stats
            if role == "TRAIN":
                for model in (C.M2, C.M3, C.M4):
                    # Fixed candidates, no screening fitted. No future/TEST feature data used.
                    observed = {
                        n
                        for n in model.features
                        if any(
                            snaps.get((r["security_id"], r["decision_at"]), {})
                            .get("features", {})
                            .get(n)
                            is not None
                            for r in common
                        )
                    }
                    result["feature_diagnostics"][model.model_id] = {
                        "raw_candidate_features": len(model.features),
                        "entering_preprocessing": len(model.features),
                        "train_observed_features": len(observed),
                        "all_missing_train_features": sorted(set(model.features) - observed),
                        "train_rows": len(common),
                        "train_issuers": common_stats["unique_issuers"],
                        "rows_per_feature": len(common) / len(model.features),
                        "note": "Fixed candidates; indicators/scaling/screening not fitted.",
                    }
        result["identity_valid"] = not identity_errors
        result["identity_errors"] = sorted(set(identity_errors))
        result["passes"] = bool(
            fold["label_safe"]
            and result["identity_valid"]
            and all(
                result["families"][family][role]["passes"]
                for family in FAMILIES
                for role in ("TRAIN", "TEST")
            )
            and all(
                result["PRIMARY_COMMON_COHORT"][role]["labels"]["non_degenerate"]
                and result["PRIMARY_COMMON_COHORT"][role]["complete_months"]
                for role in ("TRAIN", "TEST")
            )
        )
        result["failures"] = [
            {
                "family": family,
                "partition": role,
                "allowed_failed_months": len(result["families"][family][role]["coverage_by_month"])
                - result["families"][family][role]["required_passing_months"],
                "minimum_months_to_repair": result["families"][family][role][
                    "required_passing_months"
                ]
                - result["families"][family][role]["passing_months"],
                "failing_months": [
                    m
                    for m in result["families"][family][role]["coverage_by_month"]
                    if not m["passes"]
                ],
            }
            for family in FAMILIES
            for role in ("TRAIN", "TEST")
            if not result["families"][family][role]["passes"]
        ]
        result["common_class_failures"] = [
            role
            for role in ("TRAIN", "TEST")
            if not result["PRIMARY_COMMON_COHORT"][role]["labels"]["non_degenerate"]
        ]
        folds.append(result)
    excluded = [r for r in projection["rows"] if not r["membership_research_eligible"]]
    exclusions = {
        name: dict(
            sorted(
                Counter(
                    (
                        r["decision_session"][:7]
                        if field == "decision_session"
                        else str(r.get(field) or "UNKNOWN")
                    )
                    if field
                    else r["decision_session"][:4]
                    for r in excluded
                ).items()
            )
        )
        for name, field in (
            ("year", None),
            ("month", "decision_session"),
            ("issuer", "issuer_id"),
            ("security", "security_id"),
            ("sector", "sector"),
            ("reason", "exclusion_reason"),
            ("evidence_tier", "evidence_tier"),
        )
    }
    # Missingness-only pathology flags, never performance-based corrections.
    flags = []
    by_month: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in projection["rows"]:
        by_month[r["decision_session"][:7]].append(r)
    for month, rows in sorted(by_month.items()):
        configured_sectors = {r.get("sector") for r in rows if r.get("sector")}
        included_sectors = {r.get("sector") for r in rows if r["membership_research_eligible"]}
        missing = configured_sectors - included_sectors
        if missing:
            flags.append(
                {
                    "month": month,
                    "flag": "CONFIGURED_SECTOR_ABSENT",
                    "sectors": sorted(str(x) for x in missing),
                }
            )
        ids = [r["issuer_id"] for r in rows if r["membership_research_eligible"]]
        duplicate = [i for i, n in Counter(ids).items() if n > 1]
        if duplicate:
            flags.append(
                {
                    "month": month,
                    "flag": "MULTIPLE_SHARE_CLASSES_ISSUER_DEDUPLICATED",
                    "issuers": duplicate,
                }
            )
    for f in folds:
        for role in ("TRAIN", "TEST"):
            failing = [
                m["month"]
                for m in f["families"]["PRICE"][role]["coverage_by_month"]
                if not m["passes"]
            ]
            if failing:
                flags.append(
                    {
                        "fold": f["index"],
                        "partition": role,
                        "flag": "BELOW_FIXED_PRICE_MONTHLY_COVERAGE",
                        "months": failing,
                    }
                )
    ready = len(folds) == C.MIN_FOLDS and all(f["passes"] for f in folds)
    return {
        "version": VERSION,
        "experiment": C.EXPERIMENT_ID,
        "scope": "US_ONLY_CONFIGURED_VALID_MEMBERSHIP",
        "target": "outperform_12m",
        "thresholds": THRESHOLDS,
        "train_passing_fraction": 0.9,
        "test_passing_fraction": 1.0,
        "legacy_global_required_securities": C.REQUIRED_SECURITIES,
        "legacy_gate_used": False,
        "effective_sample_size": "NOT_FORMALLY_ESTIMATED",
        "common_train_required": True,
        "primary_comparison": "PRIMARY_COMMON_COHORT",
        "native_comparison": "SECONDARY_ONLY",
        "membership_ledger": projection.get("ledger"),
        "identity_valid": bool(folds) and all(f["identity_valid"] for f in folds),
        "ready": ready,
        "folds": folds,
        "excluded_security_periods": len(excluded),
        "exclusion_distribution": exclusions,
        "selection_structure_flags": flags,
        "limitations": [
            "Configured universe selection/survivorship bias persists.",
            "Sector categories are descriptive current metadata, not historical predictors.",
            "Panel rows are dependent; no formally estimated effective N.",
            "Retrospective membership reference is not an investor feature.",
        ],
        "models_trained": False,
    }


def persist_coverage(
    session: Session, store: ArchiveStore, report: dict[str, Any]
) -> dict[str, str]:
    """Content-addressed audit and exact resolver/feature contract sources."""
    report["source_archives"] = []
    for path in (Path(__file__), Path(C.__file__)):
        raw = path.read_bytes()
        row = archive_document(
            session,
            store,
            provider="FIRST_ML_COVERAGE_SOURCE",
            source_identifier=VERSION + ":" + sha256_hex(raw),
            data=raw,
            mime_type="text/plain",
            parser_version=VERSION,
        )
        report["source_archives"].append(
            {"archive_id": row.archive_id, "sha256": row.sha256, "raw_document": row.storage_uri}
        )
    content = {k: v for k, v in report.items() if k != "archive"}
    raw = json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
    row = archive_document(
        session,
        store,
        provider="FIRST_ML_COVERAGE_AUDIT",
        source_identifier=VERSION + ":" + sha256_hex(raw),
        data=raw,
        mime_type="application/json",
        parser_version=VERSION,
    )
    return {"archive_id": row.archive_id, "sha256": row.sha256, "raw_document": row.storage_uri}
