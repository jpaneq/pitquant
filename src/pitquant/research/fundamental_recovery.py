"""sec-tags-4 bounded research repair; no Analyzer/V0 or price changes (ADR-0058)."""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.core.errors import DataQualityError
from pitquant.core.hashing import content_hash
from pitquant.db.models_research import ResearchFeatureSnapshot
from pitquant.features.v0 import fundamentals as F
from pitquant.features.v0.engine import load_facts
from pitquant.market.canonical import FEATURE_VERSION as BASE_VERSION
from pitquant.research import first_ml_contract as C
from pitquant.research.dataset_v1 import guard_snapshot, rank_cohort

FEATURE_VERSION = "first-ml-features-sec4-v4"
TAG_VERSION = "sec-tags-4"


def reported_total_debt(facts: list[F.Fact], decision_at: datetime) -> F.Metric:
    """Latest KNOWN total, or same-period noncurrent + current debt/lease.

    Components in a sum must agree on period. A previously reported total remains
    known until superseded; a newer assets fact never makes that debt unknowable.
    This preserves the existing engine's independent latest-known denominators.
    """
    visible = F.visible(facts, decision_at)
    inst = {
        (f.concept, f.period_end): f for f in visible if f.unit == "USD" and f.period_start is None
    }
    candidates: list[tuple[Any, F.Metric]] = []
    for (tag, end), total in inst.items():
        if tag == "DebtAndCapitalLeaseObligations" and total.value >= 0:
            candidates.append(
                (
                    end,
                    F.Metric(
                        total.value,
                        None,
                        total.available_at,
                        [F._prov(total, "reported_total_debt")],
                        "DebtAndCapitalLeaseObligations: reported total financial debt",
                    ),
                )
            )
        if tag == "LongTermDebtAndCapitalLeaseObligations" and total.value >= 0:
            current = inst.get(("DebtCurrent", end))
            if current is not None and current.value >= 0:
                candidates.append(
                    (
                        end,
                        F.Metric(
                            total.value + current.value,
                            None,
                            max(total.available_at, current.available_at),
                            [
                                F._prov(total, "noncurrent_debt_and_lease"),
                                F._prov(current, "current_debt_and_lease"),
                            ],
                            "noncurrent debt/lease + DebtCurrent (same period)",
                        ),
                    )
                )
    if not candidates:
        return F.Metric.missing(
            "missing_fundamental", "explicit total or same-period noncurrent/current pair required"
        )
    end = max(end for end, _ in candidates)
    latest = [m for e, m in candidates if e == end]
    if max(m.value or 0 for m in latest) - min(m.value or 0 for m in latest) > max(
        1, abs(latest[0].value or 0) * 1e-8
    ):
        return F.Metric.missing("conflicting_tags")
    return latest[0]


def repair_features(
    features: dict[str, Any], facts: list[F.Fact], decision_at: datetime, *, supported: bool
) -> dict[str, Any]:
    result = copy.deepcopy(features)
    if not supported:
        return result
    debt = reported_total_debt(facts, decision_at)
    if debt.value is None:
        return result
    visible = F.visible(facts, decision_at)
    for name, denominator in (("fund_debt_to_assets", "assets"), ("fund_debt_to_equity", "equity")):
        if name not in result:
            continue
        ratio = F.safe_div(
            debt, F.latest_instant(visible, denominator), f"debt / {denominator}", den_positive=True
        )
        if ratio.value is not None:
            result[name].update(
                value=ratio.value,
                available_at=ratio.available_at.isoformat() if ratio.available_at else None,
                missing_reason=None,
                mapping_version=TAG_VERSION,
                provenance=ratio.provenance,
                formula=ratio.formula,
            )
    guard_snapshot(result, decision_at)
    return result


def rebuild(session: Session) -> dict[str, Any]:
    """New append-only US DEV snapshot version; original values never overwritten."""
    originals = list(
        session.scalars(
            select(ResearchFeatureSnapshot)
            .where(
                ResearchFeatureSnapshot.feature_set_version == BASE_VERSION,
                ResearchFeatureSnapshot.exchange == "XNYS",
                ResearchFeatureSnapshot.decision_session < C.HOLDOUT[0],
            )
            .order_by(ResearchFeatureSnapshot.security_id, ResearchFeatureSnapshot.decision_at)
        )
    )
    groups: dict[str, list[dict[str, Any]]] = {}
    facts_by_sid: dict[str, list[F.Fact]] = {}
    recovered = []
    for old in originals:
        if old.security_id not in facts_by_sid:
            facts_by_sid[old.security_id] = load_facts(
                session, old.security_id, datetime(2022, 10, 1, tzinfo=UTC)
            )
        features = repair_features(
            old.features,
            facts_by_sid[old.security_id],
            old.decision_at,
            supported=old.meta.get("fundamental_status") == "OK",
        )
        if (
            old.features.get("fund_debt_to_assets", {}).get("value") is None
            and features.get("fund_debt_to_assets", {}).get("value") is not None
        ):
            recovered.append(
                {
                    "security_id": old.security_id,
                    "month": str(old.decision_session)[:7],
                    "ticker": old.meta.get("ticker"),
                    "source_snapshot": old.snapshot_id,
                    "feature": features["fund_debt_to_assets"],
                }
            )
        groups.setdefault(str(old.decision_session), []).append({"old": old, "features": features})
    existing = {
        (r.security_id, r.decision_at): r
        for r in session.scalars(
            select(ResearchFeatureSnapshot).where(
                ResearchFeatureSnapshot.feature_set_version == FEATURE_VERSION
            )
        )
    }
    added = 0
    for rows in groups.values():
        rank_cohort(rows)
        for r in rows:
            old = r["old"]
            # Re-ranking fundamentals never modifies price-family values/ranks.
            if any(
                r["features"].get(n) != old.features.get(n) for n in C.PRICE_FAMILY + C.RISK_FAMILY
            ):
                raise DataQualityError("price/risk feature changed during fundamental-only repair")
            digest = content_hash(r["features"])
            prior = existing.get((old.security_id, old.decision_at))
            if prior:
                if prior.feature_hash != digest:
                    raise DataQualityError("immutable recovery version differs; bump version")
                continue
            ranks = copy.deepcopy(old.ranks)
            for name in r["ranks"]:
                if not name.startswith(("fund_", "val_")):
                    continue
                if name in r["ranks"]:
                    ranks.setdefault("ranks", {})[name] = r["ranks"][name]
                    ranks.setdefault("reasons", {})[name] = r["rank_reasons"].get(name)
            meta = {
                **old.meta,
                "fundamental_recovery_version": TAG_VERSION,
                "source_snapshot_id": old.snapshot_id,
                "source_feature_version": BASE_VERSION,
            }
            session.add(
                ResearchFeatureSnapshot(
                    security_id=old.security_id,
                    decision_at=old.decision_at,
                    decision_session=old.decision_session,
                    exchange=old.exchange,
                    feature_set_version=FEATURE_VERSION,
                    cohort_definition=old.cohort_definition,
                    cohort_size=old.cohort_size,
                    features=r["features"],
                    ranks=ranks,
                    meta=meta,
                    feature_hash=digest,
                    code_commit=old.code_commit,
                )
            )
            added += 1
    session.flush()
    return {
        "version": TAG_VERSION,
        "feature_version": FEATURE_VERSION,
        "rows_added": added,
        "recovered": recovered,
        "price_and_risk_unchanged": True,
        "no_imputation": True,
    }
