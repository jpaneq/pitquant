"""Read-only certification of existing first-ML rows; never builds labels or trains.

Calendar, label safety and statistical coverage are distinct (ADR-0055 V2).
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime
from math import isfinite
from typing import Any

from dateutil.relativedelta import relativedelta

from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.research import benchmark_contract as BC
from pitquant.research import first_ml as FM
from pitquant.research import first_ml_contract as C
from pitquant.research.targets_v1 import LAG

AUDIT_VERSION = "first-ml-fold-readiness-v2"


def latest_label_safe_history(
    *,
    holdout_start: date = C.HOLDOUT[0],
    horizon: int = C.HORIZON_MONTHS,
    minimum_folds: int = C.MIN_FOLDS,
) -> tuple[C.FoldPlan, dict[str, Any]]:
    """Derive the latest full monthly H12 windows; inspect calendars, not outcomes.

    US security and SPY use XNYS last-known closes. The frozen target generator
    seals by NOMINAL horizon date, even if its previous close precedes holdout.
    """
    if horizon < 1 or minimum_folds < 1:
        raise ValueError("positive horizon and fold count required")
    cal = get_calendar("XNYS")
    month = holdout_start.replace(day=1)
    while True:
        month -= relativedelta(months=1)
        session = cal.session_on_or_after(month)
        decision = cal.session_open(session)
        target_end = decision + relativedelta(months=horizon)
        if target_end.date() < holdout_start:
            break
    count = (
        C.TRAIN_MIN_MONTHS
        + horizon
        + C.EMBARGO_MONTHS
        + C.TEST_MONTHS
        + (minimum_folds - 1) * C.STEP_MONTHS
    )
    start = month - relativedelta(months=count - 1)
    dates = [start + relativedelta(months=i) for i in range(count)]
    plan = C.walk_forward_folds(dates, horizon=horizon)
    if len(plan.folds) != minimum_folds or plan.folds[-1].test_end != C.month_index(month):
        raise ValueError("derived history does not satisfy frozen inclusive calendar contract")
    exit_session = cal.last_closed_session(target_end)
    return plan, {
        "last_admissible_decision_month": month.strftime("%Y-%m"),
        "last_decision_at": decision.isoformat(),
        "target_start": decision.isoformat(),
        "target_end": target_end.isoformat(),
        "security_exit_session": str(exit_session),
        "benchmark_exit_session": str(exit_session),
        "earliest_target_mature_at": (cal.session_close(exit_session) + LAG).isoformat(),
        "next_month_rejected": (month + relativedelta(months=1)).strftime("%Y-%m"),
        "minimum_ready_history_start": start.strftime("%Y-%m"),
        "last_required_dev_month": month.strftime("%Y-%m"),
        "minimum_contiguous_ready_months": count,
        "horizon_months": horizon,
        "holdout_start": str(holdout_start),
        "security_calendar": "XNYS",
        "benchmark_calendar": "XNYS",
        "semantics": "Nominal decision_at + H12 date < holdout start; security and SPY "
        "exit at their last closed session at that instant. No outcome data read.",
    }


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
    last = max(end.date(), exit_session or end.date())
    touches_holdout = decision_at.date() <= C.HOLDOUT[1] and last >= C.HOLDOUT[0]
    touches_oot = last >= C.OOT_START
    if touches_holdout or touches_oot:
        t = {}  # never inspect sealed outcome/benchmark values, even if supplied
    mature: datetime | None = t.get("label_available_at")
    if mature is not None and mature.tzinfo is None:
        raise ValueError("label availability must be timezone aware")
    price_ready = (
        t.get("status") == "OK"
        and t.get("entry_session") is not None
        and exit_session is not None
        and t["entry_session"] <= decision_at.date()
        and t["entry_session"] < exit_session <= end.date()
        and t.get("total_return") is not None
        and isfinite(t["total_return"])
    )
    if price_ready:
        cal = get_calendar("XNYS")
        price_ready = (
            cal.is_session(t["entry_session"])
            and cal.is_session(t["exit_session"])
            and cal.session_close(t["entry_session"]) <= decision_at
            and cal.session_close(t["exit_session"]) <= end
        )
    bc = (t.get("details") or {}).get("benchmark_contract") or {}
    benchmark_ready = (
        bc.get("benchmark_quality_status") in BC.APPROVED_FOR_ML
        and bc.get("comparability") == "COMPARABLE"
        and t.get("benchmark_total_return") is not None
        and t.get("outperform") is not None
        and isfinite(t["benchmark_total_return"])
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

    Label safety needs complete months, not a security-count threshold. The
    unspecified statistical coverage contract is never evaluated here.
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
                    safe_target = (
                        None if evidence["touches_holdout"] or evidence["touches_oot"] else t
                    )
                    base = FM.first_ml_eligibility(ctx, s, safe_target, family=family)
                    families[family] = sorted(set(reasons + base["reasons"]))
                rows.append(
                    {
                        "security_id": s["security_id"],
                        "issuer_id": s.get("issuer_id"),
                        "decision_at": s["decision_at"].isoformat(),
                        **evidence,
                        "eligible": not families["PRICE"],
                        "label_eligible": not reasons
                        and not any(
                            r in families["PRICE"]
                            for r in (
                                "HOLDOUT",
                                "OOT",
                                "UNIVERSE_NOT_CANONICAL",
                                "NOT_INDEX_MEMBER_AT_T",
                                "SECURITY_IDENTITY_NOT_READY",
                                "PRICE_DATA_NOT_READY",
                                "BENCHMARK_NOT_READY",
                                "RETURN_BASIS_MISMATCH",
                                "FX_NOT_READY",
                                "TARGET_IMMATURE",
                            )
                        ),
                        "family_reasons": families,
                    }
                )
            partitions[role] = {
                "calendar_rows": len(rows),
                "mature_target_rows": sum(r["mature"] for r in rows),
                "benchmark_ready_rows": sum(r["benchmark_ready"] for r in rows),
                "price_ready_rows": sum(r["price_ready"] for r in rows),
                "benchmark_exclusions": sum(not r["benchmark_ready"] for r in rows),
                "price_exclusions": sum(not r["price_ready"] for r in rows),
                "maturity_exclusions": sum(not r["mature"] for r in rows),
                "eligible_rows": sum(r["eligible"] for r in rows),
                "eligible_securities": len({r["security_id"] for r in rows if r["eligible"]}),
                "eligible_issuers": len(
                    {r["issuer_id"] for r in rows if r["eligible"] and r["issuer_id"]}
                ),
                "eligible_rows_without_issuer_id": sum(
                    r["eligible"] and not r["issuer_id"] for r in rows
                ),
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
            by_month = []
            for idx in range(start, end + 1):
                label = f"{(idx - 1) // 12:04d}-{(idx - 1) % 12 + 1:02d}"
                monthly = [r for r in rows if r["decision_at"][:7] == label]
                by_month.append(
                    {
                        "month": label,
                        "calendar_rows": len(monthly),
                        "label_ready_rows": sum(r["label_eligible"] for r in monthly),
                        "eligible_rows": sum(r["eligible"] for r in monthly),
                        "securities": len({r["security_id"] for r in monthly if r["eligible"]}),
                        "issuers": len(
                            {r["issuer_id"] for r in monthly if r["eligible"] and r["issuer_id"]}
                        ),
                    }
                )
            partitions[role]["rows_by_month"] = by_month
        test_months = {r["decision_at"][:7] for r in partitions["TEST"]["rows"] if r["eligible"]}
        test_label_safe = all(
            m["label_ready_rows"] > 0 for m in partitions["TEST"]["rows_by_month"]
        )
        train_label_months = sum(
            m["label_ready_rows"] > 0 for m in partitions["TRAIN"]["rows_by_month"]
        )
        train_label_safe = train_label_months >= C.TRAIN_MIN_MONTHS
        cal = get_calendar("XNYS")
        missing_history = []
        for idx in range(fold.train_start, fold.test_end + 1):
            day = date((idx - 1) // 12, (idx - 1) % 12 + 1, 1)
            cohort = ctx.cohorts.get(cal.session_on_or_after(day))
            if cohort is None or cohort["status"] != "MEMBERSHIP_READY":
                missing_history.append(day.strftime("%Y-%m"))
        calendar_valid = (
            fold.n_train_months == fold.train_end - fold.train_start + 1
            and fold.n_train_months >= C.TRAIN_MIN_MONTHS
            and fold.test_end - fold.test_start + 1 == C.TEST_MONTHS
            and fold.train_end + C.HORIZON_MONTHS + C.EMBARGO_MONTHS <= fold.test_start
            and fold.purged_months == fold.test_start - 1 - fold.train_end
        )
        label_safe = calendar_valid and test_label_safe and train_label_safe and not missing_history
        blocking = []
        if not calendar_valid:
            blocking.append("INVALID_CALENDAR")
        if missing_history:
            blocking.append("REQUIRED_MEMBERSHIP_HISTORY_NOT_READY")
        if not train_label_safe:
            blocking.append("TRAIN_LABEL_MONTHS_INCOMPLETE_AT_FIT")
        if not test_label_safe:
            blocking.append("TEST_LABEL_MONTHS_INCOMPLETE")
        folds.append(
            {
                "index": fold.index,
                "calendar_valid": calendar_valid,
                "label_safe": label_safe,
                "test_label_safe": test_label_safe,
                "train_label_safe": train_label_safe,
                "train_label_months": train_label_months,
                "months": {
                    "train_calendar": fold.n_train_months,
                    "train_label_ready": train_label_months,
                    "test_required": C.TEST_MONTHS,
                    "test_label_ready": sum(
                        m["label_ready_rows"] > 0 for m in partitions["TEST"]["rows_by_month"]
                    ),
                    "missing_membership_history": len(missing_history),
                },
                "securities": {
                    role: partitions[role]["eligible_securities"] for role in ("TRAIN", "TEST")
                },
                "issuers": {
                    role: partitions[role]["eligible_issuers"] for role in ("TRAIN", "TEST")
                },
                "coverage_evaluated": False,
                "ml_eligible": None,
                "ml_eligible_status": "NOT_YET_EVALUATED_BLOCKED_BY_COVERAGE",
                "status": "LABEL_SAFE" if label_safe else "BLOCKED",
                "blocking_reasons": blocking,
                "missing_history_months": missing_history,
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
        "label_safe_folds": sum(f["label_safe"] for f in folds),
        "test_label_safe_folds": sum(f["test_label_safe"] for f in folds),
        "coverage_evaluated": False,
        "ml_eligible_folds": None,
        "row_minimum_status": "UNSPECIFIED_CONTRACT",
        "folds": folds,
    }
