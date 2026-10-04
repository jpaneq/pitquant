# ruff: noqa: E501
"""DATA READINESS FOR FIRST ML (ADR-0049): the gates, the single eligibility function and the funnel. Nothing is trained and no gate is lowered: a gate that cannot be closed scientifically is BLOCKED with its exact reason.

``first_ml_eligibility`` is the ONLY place that decides whether a research snapshot may feed the first model; scripts only call it. Reasons, in the order they are checked (first failing one is the funnel stage):
HOLDOUT, OOT, UNIVERSE_NOT_CANONICAL / NOT_INDEX_MEMBER_AT_T, SECURITY_IDENTITY_NOT_READY, PRICE_DATA_NOT_READY, BENCHMARK_NOT_READY, RETURN_BASIS_MISMATCH, FX_NOT_READY, TARGET_IMMATURE, INSUFFICIENT_HISTORY,
FUNDAMENTALS_NOT_READY / UNSUPPORTED_SECTOR (fundamental family only).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.db.models import Security
from pitquant.research import benchmark_contract as BC
from pitquant.research import first_ml_contract as C

ORDER = (
    "HOLDOUT", "OOT", "UNIVERSE_NOT_CANONICAL", "NOT_INDEX_MEMBER_AT_T", "SECURITY_IDENTITY_NOT_READY", "PRICE_DATA_NOT_READY", "BENCHMARK_NOT_READY", "RETURN_BASIS_MISMATCH", "FX_NOT_READY", "TARGET_IMMATURE",
    "INSUFFICIENT_HISTORY", "FUNDAMENTALS_NOT_READY", "UNSUPPORTED_SECTOR",
)  # fmt: skip
GATE_STATES = ("READY", "PARTIAL", "BLOCKED", "NOT_APPLICABLE")


@dataclass
class EligibilityContext:
    """Everything the eligibility decision needs, computed ONCE (and testable with plain dicts)."""

    cohorts: dict[
        date, dict[str, Any]
    ]  # decision date -> {"status": MEMBERSHIP_READY|BLOCKED|NO_ANCHOR, "members": frozenset[anchor security_id]}
    bridge: dict[
        str, frozenset[str]
    ]  # research security_id -> anchor security_ids (membership_bridge); absent = identity unresolved
    identity_ready: set[
        str
    ]  # research security_ids whose identity is resolved enough to test membership
    price_accepted: bool  # D05 gate (the price source is canonical / accepted)
    price_present: set[
        str
    ]  # security_ids with research-grade bars (present, adjusted, provenance recorded)
    holdout: tuple[date, date] = C.HOLDOUT
    oot_start: date = C.OOT_START
    extra: dict[str, Any] = field(default_factory=dict)


def first_ml_eligibility(
    ctx: EligibilityContext,
    snap: dict[str, Any],
    target: dict[str, Any] | None,
    *,
    family: str = "PRICE",
) -> dict[str, Any]:
    """``snap``: security_id, decision_session, exchange, features {name: value}, meta. ``target``: the research-targets-v2 row for the 12M horizon (dict) or None. ``family``: PRICE | FUNDAMENTALS.
    Returns {"eligible": bool, "reasons": [all failing reasons in ORDER], "first_reason": str | None}. All reasons are listed; the funnel uses the first."""
    d: date = snap["decision_session"]
    sid: str = snap["security_id"]
    reasons: list[str] = []
    if ctx.holdout[0] <= d <= ctx.holdout[1]:
        reasons.append("HOLDOUT")
    if d >= ctx.oot_start:
        reasons.append("OOT")
    cohort = ctx.cohorts.get(d)
    if snap["exchange"] != "XNYS" or cohort is None or cohort["status"] != "MEMBERSHIP_READY":
        reasons.append("UNIVERSE_NOT_CANONICAL")
    elif sid in ctx.bridge and not (ctx.bridge[sid] & cohort["members"]):
        reasons.append("NOT_INDEX_MEMBER_AT_T")
    if sid not in ctx.identity_ready:
        reasons.append("SECURITY_IDENTITY_NOT_READY")
    if not ctx.price_accepted or sid not in ctx.price_present:
        reasons.append("PRICE_DATA_NOT_READY")
    bc = ((target or {}).get("details") or {}).get("benchmark_contract") or {}
    if target is None or bc.get("benchmark_quality_status") not in BC.APPROVED_FOR_ML:
        if (
            bc.get("comparability") == "NOT_COMPARABLE_RETURN_BASIS"
            or bc.get("benchmark_quality_status") == "PRICE_RETURN_ONLY"
        ):
            reasons.append("RETURN_BASIS_MISMATCH")
        elif (
            bc.get("comparability") == "FX_NOT_READY"
            or bc.get("benchmark_quality_status") == "FX_MISMATCH"
        ):
            reasons.append("FX_NOT_READY")
        else:
            reasons.append("BENCHMARK_NOT_READY")
    elif target.get("status") == "OK" and bc.get("comparability") != "COMPARABLE":
        reasons.append(
            "BENCHMARK_NOT_READY"
        )  # benchmark has no price in the window (e.g. URTH before 2012)
    if (
        target is None
        or target.get("status") != "OK"
        or (target.get("outperform") is None and bc.get("comparability") == "COMPARABLE")
    ):
        reasons.append("TARGET_IMMATURE")
    f = snap["features"]
    if any(f.get(n) is None for n in C.CORE_PRICE_FEATURES):
        reasons.append("INSUFFICIENT_HISTORY")
    if family == "FUNDAMENTALS":
        status = (snap.get("meta") or {}).get("fundamental_status")
        if status == "UNSUPPORTED_SECTOR":
            reasons.append("UNSUPPORTED_SECTOR")
        elif status != "OK" or any(f.get(n) is None for n in C.CORE_FUNDAMENTAL_FEATURES):
            reasons.append("FUNDAMENTALS_NOT_READY")
    uniq = [r for r in ORDER if r in reasons]
    return {"eligible": not uniq, "reasons": uniq, "first_reason": uniq[0] if uniq else None}


def funnel(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Cumulative funnel: each row is attributed to its FIRST failing reason (in ``ORDER``)."""
    out: dict[str, int] = {r: 0 for r in ORDER}
    ok = 0
    for r in rows:
        if r["eligible"]:
            ok += 1
        else:
            out[r["first_reason"]] += 1
    return {"raw": len(rows), "removed_by": out, "eligible": ok}


def gate(status: str, required: Any, actual: Any, reason: str | None) -> dict[str, Any]:
    if status not in GATE_STATES:
        raise ValueError(status)
    return {"status": status, "required": required, "actual": actual, "blocking_reason": reason}


def first_ml_baseline_ready(gates: dict[str, dict[str, Any]], required: tuple[str, ...]) -> bool:
    """True only if EVERY required gate is READY (an unknown or NOT_APPLICABLE required gate does not pass). Computing this NEVER starts training."""
    return all(gates.get(g, {}).get("status") == "READY" for g in required)


REQUIRED_GATES = (
    "D02_MONTHLY_RESEARCH_READY",
    "US_SECURITY_IDENTITY_READY",
    "D05_READY",
    "BENCHMARK_RETURN_BASIS_READY",
    "RESEARCH_SECURITY_COVERAGE_READY",
    "US_FUNDAMENTALS_READY",
    "RESEARCH_DATA_READY",
    "HOLDOUT_SEALED",
)


def fundamentals_months(
    rows: list[dict[str, Any]], min_months: int = C.REQUIRED_FUNDAMENTAL_MONTHS
) -> dict[str, Any]:
    """Per security: usable PIT fundamental months = DEV snapshots with status OK and every core metric present."""
    per: dict[str, dict[str, Any]] = {}
    for r in rows:
        if r["decision_session"] >= C.HOLDOUT[0]:
            continue
        p = per.setdefault(
            r["security_id"],
            {"ticker": r["ticker"], "usable": 0, "first": None, "last": None, "n": 0},
        )
        p["n"] += 1
        if (r.get("meta") or {}).get("fundamental_status") == "OK" and all(
            r["features"].get(n) is not None for n in C.CORE_FUNDAMENTAL_FEATURES
        ):
            p["usable"] += 1
            p["first"] = min(p["first"] or r["decision_session"], r["decision_session"])
            p["last"] = max(p["last"] or r["decision_session"], r["decision_session"])
    ok = [s for s, p in per.items() if p["usable"] >= min_months]
    return {"per_security": per, "n_ok": len(ok), "ok": ok}


def issuer_map(session: Session) -> dict[str, str | None]:
    return {s.security_id: s.issuer_id for s in session.scalars(select(Security))}
