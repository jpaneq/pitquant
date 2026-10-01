"""Sealed final holdout (ADR-0014).

The holdout (Oct-2022 → Sep-2025, fixed in config before any result was seen) is never a
validation set. Its metrics can only be produced by ONE explicit, logged operation —
``evaluate_candidate_on_holdout`` — for a FROZEN model version, once per version. Results
are stored sealed in ``holdout_evaluations`` and are not exposed by analytics, the API or
the dashboard. Reading them back is itself an explicit, logged operation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pitquant.config.settings import Settings
from pitquant.core.errors import HoldoutAccessError
from pitquant.core.hashing import content_hash
from pitquant.db.models import HoldoutAccessLog, HoldoutEvaluation, ModelVersion
from pitquant.validation.splits import HoldoutAccess, HoldoutGuard

MAX_CANDIDATES_WARNING = 5  # beyond this, the holdout is turning into a validation set


@dataclass(frozen=True)
class HoldoutResult:
    evaluation_id: str
    model_version: str
    metrics: dict[str, Any]
    n_observations: int
    candidates_evaluated_so_far: int
    warning: str | None


def guard_analytics_range(settings: Settings, start: date, end: date) -> None:
    """Every development analytics/backtest query calls this: no overlap with the holdout."""
    h = settings.validation.final_holdout
    if start <= h.end and end >= h.start:
        raise HoldoutAccessError(
            f"range {start}..{end} overlaps the sealed holdout {h.start}..{h.end}; "
            "use evaluate_candidate_on_holdout"
        )


def evaluate_candidate_on_holdout(
    session: Session,
    settings: Settings,
    *,
    model_version: str,
    requested_by: str,
    reason: str,
    evaluate: Callable[[date, date], tuple[dict[str, Any], int]],
) -> HoldoutResult:
    """The ONLY way to compute holdout metrics. Logged, once per frozen model version."""
    mv = session.get(ModelVersion, model_version)
    if mv is None:
        raise HoldoutAccessError(f"unknown model version {model_version}")
    if (
        session.scalars(
            select(HoldoutEvaluation).where(HoldoutEvaluation.model_version == model_version)
        ).first()
        is not None
    ):
        raise HoldoutAccessError(f"{model_version} was already evaluated on the holdout")
    h = settings.validation.final_holdout
    log_rows: list[HoldoutAccessLog] = []

    def persist(access: HoldoutAccess) -> None:
        row = HoldoutAccessLog(
            model_version=access.model_version,
            reason=access.reason,
            requested_by=access.requested_by,
            accessed_at=access.accessed_at,
        )
        session.add(row)
        session.flush()
        log_rows.append(row)

    guard = HoldoutGuard(h.start, h.end, on_access=persist)
    guard.unlock(
        model_version=model_version,
        model_frozen=mv.frozen,
        reason=reason,
        requested_by=requested_by,
    )
    metrics, n = evaluate(h.start, h.end)
    ev = HoldoutEvaluation(
        access_id=log_rows[0].id,
        model_version=model_version,
        holdout_start=h.start,
        holdout_end=h.end,
        metrics=metrics,
        n_observations=n,
        metrics_hash=content_hash(metrics),
    )
    session.add(ev)
    session.flush()
    count = int(session.scalar(select(func.count()).select_from(HoldoutEvaluation)) or 0)
    warning = None
    if count > MAX_CANDIDATES_WARNING:
        warning = (
            f"{count} candidates evaluated on the holdout: apply multiple-testing "
            "corrections (Deflated Sharpe / PBO) before trusting any of them"
        )
    return HoldoutResult(ev.evaluation_id, model_version, metrics, n, count, warning)


def read_sealed_evaluation(
    session: Session, evaluation_id: str, *, requested_by: str, reason: str
) -> HoldoutEvaluation:
    """Explicit, logged read of a sealed result (e.g. for the promotion committee)."""
    if not reason.strip():
        raise HoldoutAccessError("a reason is mandatory to read a sealed holdout result")
    ev = session.get_one(HoldoutEvaluation, evaluation_id)
    session.add(
        HoldoutAccessLog(
            model_version=ev.model_version,
            requested_by=requested_by,
            reason=f"READ {evaluation_id}: {reason}",
        )
    )
    session.flush()
    return ev
