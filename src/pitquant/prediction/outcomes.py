# ruff: noqa: E501
"""Prediction outcomes and calibration (ADR-0038).

* An outcome is resolved ONLY from the label engine (``compute_label`` / ``realized_outcomes``), once the label is knowable (``label_available_at <= as_of``).
  A label window that reaches the sealed holdout is NEVER resolved (``HOLDOUT_SEALED``): a 12M prediction made in 2021-11 stays pending.
* Before the outcome exists the status is ``PENDING`` (no row). The prediction error is ``actual - predicted``.
* ``calibration`` compares the mean predicted P(outperform) with the observed outperform frequency per bucket; a bucket with fewer than
  ``MIN_BUCKET_N`` observations shows its N and NO rate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.analyzer.market import benchmark_security
from pitquant.backtest.targets import LABEL_VERSION, compute_label, target_session
from pitquant.config.settings import Settings
from pitquant.core.timeutils import utc_now
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.db.models import RealizedOutcome
from pitquant.db.models_lab import PredictionOutcome, PredictionSnapshot

MIN_BUCKET_N = 10
CALIBRATION_BUCKETS: tuple[tuple[str, float, float], ...] = (
    ("<50", 0.0, 0.50), ("50-55", 0.50, 0.55), ("55-60", 0.55, 0.60), ("60-65", 0.60, 0.65), ("65-70", 0.65, 0.70), ("70-75", 0.70, 0.75), ("75+", 0.75, 1.0000001),
)  # fmt: skip


def error_fields(
    expected_excess: float | None, p_outperform: float | None, actual_excess: float | None
) -> dict[str, Any]:
    """prediction_error = actual - predicted; predicted_outperform from P(outperform) (>= 0.5) or, without it, the sign of the expected excess return."""
    out: dict[str, Any] = {
        "prediction_error": None,
        "predicted_outperform": None,
        "classification_correct": None,
        "direction_correct": None,
    }
    if actual_excess is None:
        return out
    if expected_excess is not None:
        out["prediction_error"] = actual_excess - expected_excess
        out["direction_correct"] = (expected_excess > 0) == (actual_excess > 0)
    pred = (
        (p_outperform >= 0.5)
        if p_outperform is not None
        else ((expected_excess > 0) if expected_excess is not None else None)
    )
    out["predicted_outperform"] = pred
    if pred is not None:
        out["classification_correct"] = pred == (actual_excess > 0)
    return out


def calibration(rows: list[tuple[float, bool]], min_n: int = MIN_BUCKET_N) -> list[dict[str, Any]]:
    """``rows``: (predicted P(outperform), outperformed). Per bucket: N, mean predicted, observed rate (only with N >= min_n), gap."""
    out = []
    for name, lo, hi in CALIBRATION_BUCKETS:
        sel = [(p, y) for p, y in rows if lo <= p < hi]
        n = len(sel)
        row: dict[str, Any] = {
            "bucket": name,
            "n": n,
            "sample": "OK" if n >= min_n else "INSUFFICIENT_SAMPLE",
            "mean_predicted": None,
            "observed_rate": None,
            "gap": None,
        }
        if n >= min_n:
            mp, obs = sum(p for p, _ in sel) / n, sum(1 for _, y in sel if y) / n
            row.update(mean_predicted=mp, observed_rate=obs, gap=obs - mp)
        out.append(row)
    return out


@dataclass
class OutcomeStatus:
    status: str  # PENDING | RESOLVED | UNAVAILABLE | HOLDOUT_SEALED
    reason: str | None = None
    outcome: PredictionOutcome | None = None


def label_window(decision_at: datetime, horizon_months: int) -> tuple[date, date, datetime]:
    d = decision_at.date()
    tgt = target_session(d, horizon_months)
    cal = get_calendar("XNYS")
    from datetime import timedelta

    from pitquant.backtest.targets import DATA_LAG_MINUTES

    return d, tgt, cal.session_close(tgt) + timedelta(minutes=DATA_LAG_MINUTES)


def outcome_status(
    session: Session, settings: Settings, snap: PredictionSnapshot, as_of: datetime | None = None
) -> OutcomeStatus:
    as_of = as_of or utc_now()
    ho = settings.validation.final_holdout
    d, tgt, avail = label_window(snap.decision_at, snap.horizon_months)
    existing = session.scalars(
        select(PredictionOutcome).where(PredictionOutcome.prediction_id == snap.prediction_id)
    ).first()
    if existing is not None:
        return OutcomeStatus("RESOLVED", None, existing)
    if ho.start <= d <= ho.end or tgt >= ho.start:
        return OutcomeStatus(
            "HOLDOUT_SEALED",
            f"the {snap.horizon_months}M label window ({d} → {tgt}) reaches the sealed holdout {ho.start} → {ho.end}",
        )
    if as_of < avail:
        return OutcomeStatus("PENDING", f"label available at {avail.isoformat()}")
    return OutcomeStatus("PENDING", "not resolved yet")


def resolve_outcome(
    session: Session, settings: Settings, snap: PredictionSnapshot, as_of: datetime | None = None
) -> OutcomeStatus:
    """Append the outcome when (and only when) the label engine can compute it. Idempotent."""
    as_of = as_of or utc_now()
    st = outcome_status(session, settings, snap, as_of)
    if st.status != "PENDING" or as_of < label_window(snap.decision_at, snap.horizon_months)[2]:
        return st
    bench = benchmark_security(session)
    if bench is None:
        return OutcomeStatus("UNAVAILABLE", "no benchmark proxy with prices")
    d = label_window(snap.decision_at, snap.horizon_months)[0]
    row = session.scalars(
        select(RealizedOutcome).where(
            RealizedOutcome.security_id == snap.security_id,
            RealizedOutcome.decision_at == snap.decision_at,
            RealizedOutcome.horizon_months == snap.horizon_months,
            RealizedOutcome.label_version == LABEL_VERSION,
        )
    ).first()
    if row is None:
        lab = compute_label(session, snap.security_id, bench[0], d, snap.horizon_months)
        if lab.status != "OK":
            return OutcomeStatus("UNAVAILABLE", lab.reason)
        row = RealizedOutcome(
            security_id=snap.security_id, decision_at=snap.decision_at, horizon_months=snap.horizon_months, label_version=LABEL_VERSION, security_total_return=lab.security_total_return,
            benchmark_total_return=lab.benchmark_total_return, excess_total_return=lab.excess_total_return, outperform=lab.outperform, label_available_at=lab.label_available_at, status="OK",
        )  # fmt: skip
        session.add(row)
        session.flush()
    ef = error_fields(snap.expected_excess_return, snap.p_outperform, row.excess_total_return)
    out = PredictionOutcome(
        prediction_id=snap.prediction_id, realized_outcome_id=row.outcome_id, source="LABEL_ENGINE", resolved_at=as_of, actual_return=row.security_total_return,
        benchmark_return=row.benchmark_total_return, actual_excess_return=row.excess_total_return, actual_outperform=row.outperform, predicted_excess_return=snap.expected_excess_return,
        is_synthetic=snap.is_synthetic, **ef,
    )  # fmt: skip
    session.add(out)
    session.flush()
    return OutcomeStatus("RESOLVED", None, out)
