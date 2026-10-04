# ruff: noqa: E501
"""Routine that checks frozen BTC predictions once their horizon has matured, and analyses them against history (display/research only).

* ``evaluate_due``: for every prediction whose ``target_at <= now`` and that has no outcome yet, run the existing blind ``reveal`` (idempotent, append-only). A prediction that is
  not mature is reported ``PENDING`` with its maturity date, never an error; a mature one whose exact target bar is not archived yet is ``AWAITING_TARGET_BAR``.
* ``analysis``: per horizon, error vs realised return, direction hit rate, Brier of p_up, and a comparison with two honest baselines (predict 0, predict the historical mean H-day
  return). The historical H-day return distribution comes from the archived daily closes up to each decision date (RETROSPECTIVE: archived today, not proof of PIT availability).
  Samples under ``MIN_N`` are flagged ``INSUFFICIENT_SAMPLE`` and overlapping horizons are not independent observations.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.btc.contracts import Cohort, target_time
from pitquant.btc.models import (
    BTCDatum,
    BTCFeatureSnapshot,
    BTCPredictionSnapshot,
    BTCResearchRecord,
)
from pitquant.btc.research import reveal
from pitquant.core.timeutils import utc_now

MIN_N = 10


def _rows(session: Session, cohort: str) -> list[tuple[BTCPredictionSnapshot, BTCFeatureSnapshot]]:
    q = (
        select(BTCPredictionSnapshot, BTCFeatureSnapshot)
        .join(
            BTCFeatureSnapshot, BTCFeatureSnapshot.snapshot_id == BTCPredictionSnapshot.snapshot_id
        )
        .where(BTCFeatureSnapshot.cohort == cohort)
        .order_by(BTCFeatureSnapshot.decision_at, BTCPredictionSnapshot.horizon)
    )
    return [(p, s) for p, s in session.execute(q)]


def _outcomes(session: Session, cohort: str) -> dict[str, BTCResearchRecord]:
    return {
        r.prediction_id: r
        for r in session.scalars(
            select(BTCResearchRecord).where(
                BTCResearchRecord.kind == "REVEAL_OUTCOME", BTCResearchRecord.cohort == cohort
            )
        )
        if r.prediction_id
    }


def evaluate_due(
    session: Session, now: datetime | None = None, cohort: str = Cohort.FORWARD_PAPER
) -> dict[str, Any]:
    """Reveal every matured, not-yet-evaluated prediction. Safe to run as often as wanted: a second run reveals nothing new."""
    now = now or utc_now()
    done = _outcomes(session, cohort)
    revealed, awaiting, pending = [], [], 0
    for pred, snap in _rows(session, cohort):
        if pred.prediction_id in done:
            continue
        end = target_time(snap.decision_at, pred.horizon)
        if end > now:
            pending += 1
            continue
        try:
            with session.begin_nested():
                rec = reveal(session, pred.prediction_id, now)
            revealed.append(rec.record_id)
        except ValueError as exc:  # e.g. EXACT_TARGET_PRICE_REQUIRED: the target bar is not archived yet; retried next run
            awaiting.append(
                {
                    "prediction_id": pred.prediction_id,
                    "horizon": pred.horizon,
                    "target_at": end.isoformat(),
                    "reason": str(exc),
                }
            )
    return {
        "evaluated_at": now.isoformat(),
        "revealed": revealed,
        "awaiting_target_bar": awaiting,
        "pending_not_mature": pending,
    }


def _closes(session: Session, cohort: str, upto: datetime) -> dict[datetime, float]:
    rows = session.scalars(
        select(BTCDatum)
        .where(
            BTCDatum.metric == "spot",
            BTCDatum.cohort == cohort,
            BTCDatum.exchange_timestamp <= upto,
        )
        .order_by(BTCDatum.exchange_timestamp, BTCDatum.retrieved_at)
    )
    return {r.exchange_timestamp: float(r.payload["close"]) for r in rows}  # last revision per bar


def historical_returns(closes: dict[datetime, float], horizon: int) -> list[float]:
    """H-day simple returns over consecutive-calendar-day pairs only (a missing day yields no return; nothing is interpolated)."""
    out = []
    for t, c in closes.items():
        prev = closes.get(t - timedelta(days=horizon))
        if prev:
            out.append(c / prev - 1.0)
    return out


def _pct_rank(sample: list[float], value: float) -> float | None:
    return sum(1 for x in sample if x <= value) / len(sample) if sample else None


def analysis(
    session: Session, now: datetime | None = None, cohort: str = Cohort.FORWARD_PAPER
) -> dict[str, Any]:
    now = now or utc_now()
    outcomes = _outcomes(session, cohort)
    items: list[dict[str, Any]] = []
    by_h: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for pred, snap in _rows(session, cohort):
        end = target_time(snap.decision_at, pred.horizon)
        pl, o = pred.payload, outcomes.get(pred.prediction_id)
        item: dict[str, Any] = {
            "prediction_id": pred.prediction_id, "decision_at": snap.decision_at.isoformat(), "horizon": pred.horizon, "target_at": end.isoformat(), "model_version": pl.get("model_version"), "status": pl.get("status"),
            "predicted": pl.get("expected_return"), "p_up": pl.get("p_up"), "reference_price": pl.get("reference_price"), "target_price": pl.get("target_price"),
            "state": "EVALUATED" if o else ("PENDING" if end > now else "AWAITING_TARGET_BAR"), "days_remaining": max(0.0, round((end - now).total_seconds() / 86400, 2)) if end > now else 0.0,
        }  # fmt: skip
        if o:
            actual = o.payload["actual"]
            hist = historical_returns(_closes(session, cohort, snap.decision_at), pred.horizon)
            item |= {"actual": actual, "error": None if item["predicted"] is None else item["predicted"] - actual, "up": bool(o.payload["UP_H"]), "hist_n": len(hist), "hist_mean": mean(hist) if hist else None, "hist_percentile_of_actual": _pct_rank(hist, actual)}  # fmt: skip
            if item["predicted"] is not None:
                item["direction_correct"] = (item["predicted"] > 0) == item["up"]
            by_h[pred.horizon].append(item)
        items.append(item)
    horizons = {}
    for h, rows in sorted(by_h.items()):
        scored = [r for r in rows if r["predicted"] is not None]
        n = len(scored)
        s: dict[str, Any] = {
            "n_evaluated": len(rows),
            "n_scored": n,
            "flags": ["OVERLAPPING_HORIZONS_NOT_INDEPENDENT", "RETROSPECTIVE_HISTORY_NOT_PIT"]
            + (["INSUFFICIENT_SAMPLE"] if n < MIN_N else []),
        }
        if n:
            mae = mean(abs(r["error"]) for r in scored)
            zero = mean(abs(r["actual"]) for r in scored)
            hm = [r for r in scored if r["hist_mean"] is not None]
            hist_mae = mean(abs(r["hist_mean"] - r["actual"]) for r in hm) if hm else None
            s |= {
                "mae": mae, "bias": mean(r["error"] for r in scored), "baseline_zero_mae": zero, "baseline_hist_mean_mae": hist_mae, "skill_vs_zero": None if zero == 0 else 1 - mae / zero,
                "skill_vs_hist_mean": None if not hist_mae else 1 - mae / hist_mae, "direction_hit_rate": mean(1.0 if r["direction_correct"] else 0.0 for r in scored),
                "always_up_hit_rate": mean(1.0 if r["up"] else 0.0 for r in scored),
                "brier_p_up": mean((r["p_up"] - (1.0 if r["up"] else 0.0)) ** 2 for r in scored if r["p_up"] is not None) if any(r["p_up"] is not None for r in scored) else None,
                "mean_hist_percentile_of_actual": mean(r["hist_percentile_of_actual"] for r in scored if r["hist_percentile_of_actual"] is not None) if any(r["hist_percentile_of_actual"] is not None for r in scored) else None,
            }  # fmt: skip
            s["beats_baselines"] = (
                None
                if n < MIN_N
                else bool((s["skill_vs_zero"] or -1) > 0 and (s["skill_vs_hist_mean"] or -1) > 0)
            )
        horizons[str(h)] = s
    nxt = min((r["target_at"] for r in items if r["state"] == "PENDING"), default=None)
    return {"cohort": cohort, "as_of": now.isoformat(), "items": items, "horizons": horizons, "next_maturity": nxt, "counts": {k: sum(1 for r in items if r["state"] == k) for k in ("EVALUATED", "PENDING", "AWAITING_TARGET_BAR")}, "warning": "NOT_VALIDATED: descriptive follow-up of frozen predictions; no model is promoted", "math_ok": all(math.isfinite(v) for h in horizons.values() for v in h.values() if isinstance(v, float))}  # fmt: skip
