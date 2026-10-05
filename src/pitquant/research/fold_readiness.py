"""Read-only certification of existing first-ML rows; never builds labels or trains.

Calendar construction is unchanged. A missing per-fold row minimum is explicitly
UNSPECIFIED_CONTRACT and cannot certify a trainable fold (ADR-0055).
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime
from typing import Any

from dateutil.relativedelta import relativedelta

from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.research import benchmark_contract as BC
from pitquant.research import first_ml as FM
from pitquant.research import first_ml_contract as C
from pitquant.research.targets_v1 import LAG

AUDIT_VERSION = "first-ml-fold-readiness-v1"


def temporal_evidence(
    decision_at: datetime, target: dict[str, Any] | None, *, as_of: datetime
) -> dict[str, Any]:
    """Check nominal H12 window AND actual exit, without reading sealed prices.

    TEST labels may mature after the decision, but must exist by audit time.
    TRAIN labels must exist by fit time; callers pass that earlier cutoff.
    """
    if decision_at.tzinfo is None or as_of.tzinfo is None:
        raise ValueError("decision and availability cutoff must be timezone aware")
    end = decision_at + relativedelta(months=C.HORIZON_MONTHS)
    t = target or {}
    exit_session: date | None = t.get("exit_session")
    mature: datetime | None = t.get("label_available_at")
    if mature is not None and mature.tzinfo is None:
        raise ValueError("label availability must be timezone aware")
    last = max(end.date(), exit_session or end.date())
    touches_holdout = decision_at.date() <= C.HOLDOUT[1] and last >= C.HOLDOUT[0]
    touches_oot = last >= C.OOT_START
    price_ready = (
        t.get("status") == "OK"
        and t.get("entry_session") is not None
        and exit_session is not None
        and t["entry_session"] <= decision_at.date()
        and t["entry_session"] < exit_session <= end.date()
        and t.get("total_return") is not None
    )
    bc = (t.get("details") or {}).get("benchmark_contract") or {}
    benchmark_ready = (
        bc.get("benchmark_quality_status") in BC.APPROVED_FOR_ML
        and bc.get("comparability") == "COMPARABLE"
        and t.get("benchmark_total_return") is not None
        and t.get("outperform") is not None
    )
    mature_ready = (
        mature is not None
        and exit_session is not None
        and mature.date() >= exit_session
        and mature > decision_at
        and mature <= as_of
        and end <= as_of
    )
    if mature_ready and exit_session is not None and mature is not None:
        cal = get_calendar("XNYS")
        mature_ready = (
            cal.is_session(exit_session) and mature >= cal.session_close(exit_session) + LAG
        )
    failures = []
    for failed, reason in (
        (touches_holdout, "TARGET_WINDOW_TOUCHES_HOLDOUT"),
        (touches_oot, "TARGET_WINDOW_TOUCHES_OOT"),
        (not mature_ready, "LABEL_NOT_AVAILABLE_AT_CUTOFF"),
        (not price_ready, "TARGET_PRICE_NOT_READY"),
        (not benchmark_ready, "TARGET_BENCHMARK_NOT_READY"),
    ):
        if failed:
            failures.append(reason)
    return {
        "target_start": decision_at.isoformat(),
        "target_end": end.isoformat(),
        "actual_exit_session": str(exit_session) if exit_session else None,
        "target_mature_at": mature.isoformat() if mature and exit_session else None,
        "availability_cutoff": as_of.isoformat(),
        "touches_holdout": touches_holdout,
        "touches_oot": touches_oot,
        "mature": mature_ready,
        "price_ready": price_ready,
        "benchmark_ready": benchmark_ready,
        "target_available": not failures,
        "reasons": failures,
    }


def audit_folds(
    plan: C.FoldPlan,
    snapshots: list[dict[str, Any]],
    targets: dict[tuple[str, datetime], dict[str, Any]],
    ctx: FM.EligibilityContext,
    *,
    as_of: datetime,
) -> dict[str, Any]:
    """Audit every US TRAIN/TEST row on frozen calendar folds.

    There is no explicit per-fold minimum in FIRST_EQUITY_ML_12M_V0. The
    unrelated legacy global DEV minimum is deliberately not borrowed here.
    """
    if as_of.tzinfo is None:
        raise ValueError("audit cutoff must be timezone aware")
    folds = []
    for fold in plan.folds:
        candidates = [s for s in snapshots if s["exchange"] == "XNYS"]
        test = [
            s
            for s in candidates
            if fold.test_start <= C.month_index(s["decision_session"]) <= fold.test_end
        ]
        # Monthly open is the actual first test decision, not invented midnight.
        fit_at = min((s["decision_at"] for s in test), default=None)
        partitions: dict[str, Any] = {}
        for role, start, end in (
            ("TRAIN", fold.train_start, fold.train_end),
            ("TEST", fold.test_start, fold.test_end),
        ):
            rows = []
            for s in candidates:
                idx = C.month_index(s["decision_session"])
                if not start <= idx <= end:
                    continue
                t = targets.get((s["security_id"], s["decision_at"]))
                cutoff = as_of if role == "TEST" else min(fit_at or s["decision_at"], as_of)
                evidence = temporal_evidence(s["decision_at"], t, as_of=cutoff)
                reasons = list(evidence["reasons"])
                if role == "TRAIN":
                    if idx + C.HORIZON_MONTHS + C.EMBARGO_MONTHS > fold.test_start:
                        reasons.append("PURGE_EMBARGO_VIOLATION")
                    embargo_end = s["decision_at"] + relativedelta(
                        months=C.HORIZON_MONTHS + C.EMBARGO_MONTHS
                    )
                    if fit_at is not None and embargo_end > fit_at:
                        reasons.append("PURGE_EMBARGO_VIOLATION")
                    if fit_at is None:
                        reasons.append("NO_TEST_DECISION_FOR_FIT_CUTOFF")
                families = {}
                for family in ("PRICE", "FUNDAMENTALS"):
                    base = FM.first_ml_eligibility(ctx, s, t, family=family)
                    families[family] = sorted(set(reasons + base["reasons"]))
                rows.append(
                    {
                        "security_id": s["security_id"],
                        "decision_at": s["decision_at"].isoformat(),
                        **evidence,
                        "eligible": not families["PRICE"],
                        "family_reasons": families,
                    }
                )
            partitions[role] = {
                "calendar_rows": len(rows),
                "mature_target_rows": sum(r["mature"] for r in rows),
                "benchmark_ready_rows": sum(r["benchmark_ready"] for r in rows),
                "price_ready_rows": sum(r["price_ready"] for r in rows),
                "eligible_rows": sum(r["eligible"] for r in rows),
                "fundamentals_eligible_rows": sum(
                    not r["family_reasons"]["FUNDAMENTALS"] for r in rows
                ),
                "holdout_touching_rows_excluded": sum(r["touches_holdout"] for r in rows),
                "oot_touching_rows_excluded": sum(r["touches_oot"] for r in rows),
                "excluded_by": dict(
                    Counter(reason for r in rows for reason in r["family_reasons"]["PRICE"])
                ),
                "rows": sorted(rows, key=lambda r: (r["decision_at"], r["security_id"])),
            }
        test_months = {r["decision_at"][:7] for r in partitions["TEST"]["rows"] if r["eligible"]}
        folds.append(
            {
                "index": fold.index,
                "calendar_fold": True,
                "trainable_fold": False,
                "row_minimum_status": "UNSPECIFIED_CONTRACT",
                "minimum_rows_per_fold": None,
                "eligible_test_months": sorted(test_months),
                "complete_test_window": len(test_months) == C.TEST_MONTHS,
                "fit_at": fit_at.isoformat() if fit_at else None,
                **partitions,
            }
        )
    return {
        "version": AUDIT_VERSION,
        "as_of": as_of.astimezone(UTC).isoformat(),
        "calendar_folds": len(plan.folds),
        "trainable_folds": 0,
        "row_minimum_status": "UNSPECIFIED_CONTRACT",
        "folds": folds,
    }
