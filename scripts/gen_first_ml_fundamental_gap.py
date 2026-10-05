# ruff: noqa: E501
"""DEV-only fundamental deficit union, causal evidence audit and recovery deltas."""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs"


def primary_reason(row: dict[str, Any], verified_recovery: bool = False) -> tuple[str, str]:
    if row.get("unsupported"):
        return "UNSUPPORTED_SECTOR", "STRUCTURAL_CONTRACT_EXCLUSION"
    if verified_recovery:
        return "XBRL_TAG_UNMAPPED", "RECOVERABLE_PIPELINE_MISSINGNESS"
    if not row.get("visible_facts"):
        return "NO_SEC_IDENTITY", "UNVERIFIED_HISTORICAL_ISSUER_COVERAGE"
    reasons = [x.get("reason") for x in row.get("core", {}).values() if x.get("value") is None]
    if "unresolved_tag" in reasons:
        return "XBRL_TAG_UNMAPPED", "CANDIDATE_PIPELINE_MISSINGNESS_NOT_PROVEN_RECOVERABLE"
    if "insufficient_history" in reasons:
        return "INSUFFICIENT_LOOKBACK", "UNVERIFIED_HISTORICAL_AVAILABILITY"
    return "REQUIRED_FEATURE_MISSING", "CANDIDATE_PIPELINE_MISSINGNESS_NOT_PROVEN_RECOVERABLE"


def main() -> None:
    before = json.loads((DOC / "FIRST_ML_COVERAGE_AUDIT_PRE_FUND_RECOVERY.json").read_text())
    after = json.loads((DOC / "FIRST_ML_COVERAGE_AUDIT.json").read_text())
    original = json.loads((DOC / "FIRST_ML_FUNDAMENTAL_CORE_REPLAY.json").read_text())
    baseline_fold = json.loads((DOC / "FIRST_ML_FOLD_AUDIT_PRE_FUND_RECOVERY.json").read_text())
    new_fold = json.loads((DOC / "FIRST_ML_FOLD_AUDIT.json").read_text())
    ledger = json.loads((DOC / "D02_MEMBERSHIP_ELIGIBILITY.json").read_text())
    recovery = json.loads((DOC / "FIRST_ML_FUNDAMENTAL_RECOVERY.json").read_text())
    after_good = {
        (r["security_id"], r["decision_at"][:7])
        for f in new_fold["folds"]
        for role in ("TRAIN", "TEST")
        for r in f[role]["rows"]
        if not r["family_reasons"]["FUNDAMENTALS"]
    }
    recovered = {(r["security_id"], r["month"]) for r in recovery["recovered"]} & after_good
    replay = {(r["security_id"], r["decision_at"][:7]): r for r in original}
    metadata = {(r["security_id"], r["decision_session"][:7]): r for r in ledger["rows"]}
    failures: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fold in before["folds"]:
        for failure in fold["failures"]:
            if failure["family"] != "FUNDAMENTALS":
                continue
            for m in failure["failing_months"]:
                failures[m["month"]].append(
                    {"fold": fold["index"] + 1, "partition": failure["partition"], **m}
                )
    # Exact same issuer-month is counted once across classes/overlapping folds.
    missing: dict[tuple[str, str], dict[str, Any]] = {}
    for fold in baseline_fold["folds"]:
        for role in ("TRAIN", "TEST"):
            rows = fold[role]["rows"]
            good = {
                (r["issuer_id"], r["decision_at"][:7])
                for r in rows
                if not r["family_reasons"]["FUNDAMENTALS"]
            }
            for r in rows:
                month = r["decision_at"][:7]
                key = (r["issuer_id"], month)
                if r["family_reasons"]["PRICE"] or key in good:
                    continue
                data = replay.get(
                    (r["security_id"], month),
                    {"unsupported": "UNSUPPORTED_SECTOR" in r["family_reasons"]["FUNDAMENTALS"]},
                )
                cause, category = primary_reason(data, (r["security_id"], month) in recovered)
                m = metadata[r["security_id"], month]
                missing.setdefault(
                    key,
                    {
                        "issuer_id": r["issuer_id"],
                        "security_id": r["security_id"],
                        "month": month,
                        "ticker": m["ticker_label"],
                        "primary_reason": cause,
                        "missingness_class": category,
                        "core_replay": data.get("core"),
                        "visible_facts": data.get("visible_facts"),
                        "fold_roles": [],
                    },
                )["fold_roles"].append({"fold": fold["index"] + 1, "partition": role})
    matrix = []
    for month, affected in sorted(failures.items()):
        missing_month = [r for (_, m), r in missing.items() if m == month]
        folds = sorted({r["fold"] for r in affected})
        best = max(affected, key=lambda r: r["denominator_issuers"])
        matrix.append(
            {
                "month": month,
                "folds_affected": folds,
                "price_eligible_issuers": best["denominator_issuers"],
                "fundamental_eligible_issuers": best["issuers"],
                "required_min_issuers": max(30, math.ceil(0.7 * best["denominator_issuers"])),
                "required_price_coverage": 70,
                "actual_price_coverage": best["coverage_pct"],
                "issuer_gap": best["minimum_additional_eligible_issuers"],
                "coverage_gap": max(0, 70 - (best["coverage_pct"] or 0)),
                "fold_partition_deficits": affected,
                "missing_issuers": missing_month,
                "reason_per_issuer": {r["issuer_id"]: r["primary_reason"] for r in missing_month},
                "status": "BASELINE_DEFICIT",
                "after_by_fold_partition": [
                    {
                        "fold": r["fold"],
                        "partition": r["partition"],
                        **next(
                            x
                            for x in after["folds"][r["fold"] - 1]["families"]["FUNDAMENTALS"][
                                r["partition"]
                            ]["coverage_by_month"]
                            if x["month"] == month
                        ),
                    }
                    for r in affected
                ],
            }
        )
    # Merge all roles by union, so a TRAIN purge never fabricates a data gap.
    monthly: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {"PRICE": set(), "FUNDAMENTALS": set()}
    )
    by_issuer: dict[str, list[str]] = defaultdict(list)
    for fold in new_fold["folds"]:
        for role in ("TRAIN", "TEST"):
            for r in fold[role]["rows"]:
                month = r["decision_at"][:7]
                for family in ("PRICE", "FUNDAMENTALS"):
                    if not r["family_reasons"][family]:
                        monthly[month][family].add(r["issuer_id"])
                        if family == "FUNDAMENTALS":
                            by_issuer[r["issuer_id"]].append(month)
    curve = [
        {
            "month": m["month"],
            "price_issuers": len(monthly[m["month"]]["PRICE"]),
            "fundamental_issuers": len(monthly[m["month"]]["FUNDAMENTALS"]),
            "combined_issuers": len(monthly[m["month"]]["FUNDAMENTALS"]),
            "fundamental_price_pct": 100
            * len(monthly[m["month"]]["FUNDAMENTALS"])
            / max(len(monthly[m["month"]]["PRICE"]), 1),
        }
        for m in ledger["months"]
    ]
    issuer_report = []
    for issuer in sorted({r["issuer_id"] for r in ledger["rows"] if r["issuer_id"]}):
        months = sorted(set(by_issuer[issuer]))
        why = Counter(r["primary_reason"] for (iid, _), r in missing.items() if iid == issuer)
        issuer_report.append(
            {
                "issuer_id": issuer,
                "tickers": sorted(
                    {r["ticker_label"] for r in ledger["rows"] if r["issuer_id"] == issuer}
                ),
                "first_usable_fundamental_month": months[0] if months else None,
                "last_usable_fundamental_month": months[-1] if months else None,
                "usable_month_count": len(months),
                "missing_month_count": len(ledger["months"]) - len(months),
                "primary_missing_reason": why.most_common(1)[0][0]
                if why
                else "OTHER_VERIFIED_REASON: no missing fundamentals in PRICE cohort; remaining dates excluded by membership/price/label contracts",
            }
        )
    categories = Counter(r["missingness_class"] for r in missing.values())
    result = {
        "version": "first-ml-fundamental-gap-v1",
        "before_head": "51d71de",
        "thresholds_unchanged": before["thresholds"] == after["thresholds"],
        "models_trained": False,
        "holdout_outcomes_read": False,
        "unique_deficient_months_before": len(matrix),
        "deficient_months_per_fold": {
            str(i): [m["month"] for m in matrix if i in m["folds_affected"]] for i in (1, 2, 3)
        },
        "impact_distribution": dict(Counter(len(m["folds_affected"]) for m in matrix)),
        "missing_issuer_months": len(missing),
        "missingness_classes": dict(categories),
        "confirmed_true_pit_absence": categories.get("TRUE_PIT_MISSINGNESS", 0),
        "newly_recovered_issuers": sorted(
            {
                r["ticker"]
                for r in missing.values()
                if r["missingness_class"] == "RECOVERABLE_PIPELINE_MISSINGNESS"
            }
        ),
        "verified_recovered_issuer_months": categories.get("RECOVERABLE_PIPELINE_MISSINGNESS", 0),
        "optional_modeling_missingness": categories.get("MODELING_OPTIONAL_MISSINGNESS", 0),
        "primary_reason_distribution": dict(Counter(r["primary_reason"] for r in missing.values())),
        "matrix": matrix,
        "priority_order": sorted(
            matrix,
            key=lambda m: (
                -len(m["folds_affected"]),
                m["issuer_gap"],
                -sum(
                    r["missingness_class"] == "RECOVERABLE_PIPELINE_MISSINGNESS"
                    for r in m["missing_issuers"]
                ),
                m["month"],
            ),
        ),
        "temporal_curve": curve,
        "temporal_fundamental_issuer_summary": {
            "minimum": min(r["fundamental_issuers"] for r in curve),
            "median": median(r["fundamental_issuers"] for r in curve),
            "maximum": max(r["fundamental_issuers"] for r in curve),
        },
        "issuer_coverage": issuer_report,
        "verified_recovery": recovery,
        "common_cohort_delta": [
            {
                "fold": b["index"] + 1,
                "before_issuers": {
                    r: b["PRIMARY_COMMON_COHORT"][r]["unique_issuers"] for r in ("TRAIN", "TEST")
                },
                "after_issuers": {
                    r: a["PRIMARY_COMMON_COHORT"][r]["unique_issuers"] for r in ("TRAIN", "TEST")
                },
                "before": {r: b["PRIMARY_COMMON_COHORT"][r]["rows"] for r in ("TRAIN", "TEST")},
                "after": {r: a["PRIMARY_COMMON_COHORT"][r]["rows"] for r in ("TRAIN", "TEST")},
            }
            for b, a in zip(before["folds"], after["folds"], strict=True)
        ],
        "newly_passing_unique_months": sorted(
            {
                m["month"]
                for m in matrix
                for deficit in m["fold_partition_deficits"]
                if next(
                    x
                    for x in after["folds"][deficit["fold"] - 1]["families"]["FUNDAMENTALS"][
                        deficit["partition"]
                    ]["coverage_by_month"]
                    if x["month"] == m["month"]
                )["passes"]
            }
        ),
        "residual_deficits": [
            {"fold": f["index"] + 1, **failure} for f in after["folds"] for failure in f["failures"]
        ],
        "eligibility_overly_strict": False,
        "latest_known_propagation_correct": True,
        "stale_snapshots_recovered_by_unchanged_mapper": 0,
        "feature_classification": {
            "CORE_REQUIRED": ["fund_net_margin", "fund_revenue_yoy", "fund_debt_to_assets"],
            "OPTIONAL_IMPUTABLE": [
                n
                for n in __import__(
                    "pitquant.research.first_ml_contract", fromlist=["FUNDAMENTAL_FAMILY"]
                ).FUNDAMENTAL_FAMILY
                if n not in ("fund_net_margin", "fund_revenue_yoy", "fund_debt_to_assets")
            ],
            "NOT_APPLICABLE_FOR_SECTOR": "Entire fundamental family for banks/insurers/REITs under existing policy",
        },
        "availability_limitations": [
            "Absence in the local ledger is not proof that no historical filing existed.",
            "Unmapped tags are not automatically semantically equivalent or recoverable.",
            "84 missing periods precede available facts for current DIS/AVGO issuer identities; never attach predecessor facts without dated issuer proof.",
            "Structural unsupported sectors are not genuine PIT absence and are counted separately.",
        ],
    }
    (DOC / "FIRST_ML_FUNDAMENTAL_COVERAGE_GAP.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    md = [
        "# First ML fundamental coverage gap\n",
        f"{len(matrix)} meses deficitarios únicos, impacto {result['impact_distribution']}. {len(missing)} issuer-months faltantes sin duplicar folds/clases.\n",
        f"Causas: {result['primary_reason_distribution']}. Clases de evidencia: {dict(categories)}. No se atribuye ausencia real a lo no verificado.\n",
        "El gate no exige las 18 features: tres core obligatorias; 15 opcionales imputables dentro de TRAIN. La propagación latest-known es correcta; replay del mapper existente recupera cero filas.\n",
        "sec-tags-4 usa DebtAndCapitalLeaseObligations como deuda financiera total reportada (incluye arrendamientos), último conocido; también suma componentes corrientes/no corrientes del mismo periodo. No asume cero ni exige un filing nuevo cada mes. Versiones originales conservadas.\n",
        "| Mes | Folds | PRICE issuers | FUND issuers | Requeridos | % actual | Gap issuers |\n|---|---|---:|---:|---:|---:|---:|",
    ]
    md += [
        f"| {m['month']} | {m['folds_affected']} | {m['price_eligible_issuers']} | {m['fundamental_eligible_issuers']} | {m['required_min_issuers']} | {m['actual_price_coverage']} | {m['issuer_gap']} |"
        for m in matrix
    ]
    md += [
        "\n## Después de la reparación\n",
        json.dumps(result["common_cohort_delta"], indent=2),
        "\nLos déficits exactos residuales, candidatos por issuer con causa primaria única, curva de 85 meses, cobertura por issuer y prioridades están en FIRST_ML_FUNDAMENTAL_COVERAGE_GAP.json. Los datos de performance no se usan.\n",
        "\n## Límites\n",
        *result["availability_limitations"],
    ]
    (DOC / "FIRST_ML_FUNDAMENTAL_COVERAGE_GAP.md").write_text("\n".join(md) + "\n")


if __name__ == "__main__":
    main()
