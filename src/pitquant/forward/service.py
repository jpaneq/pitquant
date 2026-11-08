"""Orchestrate a bounded pilot run and independently review existing paper operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.config.settings import Settings
from pitquant.core.timeutils import utc_now
from pitquant.db.models_forward import ForwardPilotRecord as Record
from pitquant.forward.data import load_frame, training_frames
from pitquant.forward.engine import (
    MARKETS,
    VERSION,
    append,
    dashboard,
    digest,
    fit_model,
    predict,
    records,
    review,
)


def run_cycle(
    s: Session,
    root: Path,
    *,
    train: bool = False,
    candidate: bool = False,
    learn: bool = False,
    cfg: Settings | None = None,
) -> dict[str, Any]:
    from pitquant.forward.learning import learning_step

    now = utc_now()
    summary: dict[str, Any] = {
        "started_at": now.isoformat(),
        "fits": [],
        "forecasts": [],
        "gaps": [],
        "reviews": 0,
        "orders_opened": 0,
        "learning": [],
    }
    for market in MARKETS:
        if train or candidate:
            try:
                frames, exclusions = training_frames(s, market, now)
                before = len(records(s, "MODEL", market))
                m = fit_model(s, market, frames, exclusions, root, candidate=candidate, now=now)
                summary["fits"].append(
                    {
                        "market": market,
                        "model_id": m.record_id,
                        "new_fit": len(records(s, "MODEL", market)) > before,
                        "n": m.payload["train_n"],
                    }
                )
            except ValueError as exc:
                summary["gaps"].append({"market": market, "reason": str(exc)})
        if learn:  # ADR-0064: exam once, monthly refit, forward switch rule
            try:
                summary["learning"].append(learning_step(s, market, root, now))
            except ValueError as exc:
                summary["gaps"].append({"market": market, "reason": "LEARNING: " + str(exc)})
        models = records(s, "MODEL", market)
        active = [m for m in models if m.payload["baseline"]]
        challengers = [m for m in models if not m.payload["baseline"]]
        # Latest model of each family keeps forecasting next to V1 (legacy candidates, refits).
        for family in sorted({m.payload.get("family", VERSION) for m in challengers}):
            active.append(
                [m for m in challengers if m.payload.get("family", VERSION) == family][-1]
            )
        frames_live = {}
        tickers = sorted({t for m in active for t in m.payload["universe"]})
        for ticker in tickers:
            try:
                frames_live[ticker] = load_frame(s, market, ticker, now)
            except ValueError as exc:
                summary["gaps"].append({"market": market, "ticker": ticker, "reason": str(exc)})
        for m in active:
            for ticker in m.payload["universe"]:
                if ticker not in frames_live:
                    continue
                try:
                    row = predict(s, m, ticker, frames_live[ticker], utc_now())
                    summary["forecasts"].append(
                        {
                            "id": row.record_id,
                            "market": market,
                            "ticker": ticker,
                            "p_up": row.payload["p_up"],
                        }
                    )
                except ValueError as exc:
                    summary["gaps"].append({"market": market, "ticker": ticker, "reason": str(exc)})
        # Review all versions, including prior challengers; no history is discarded.
        for p in records(s, "PREDICTION", market):
            ticker = p.payload["ticker"]
            if ticker in frames_live:
                summary["reviews"] += len(review(s, p, frames_live[ticker], utc_now()))
        for months in (12, 24):
            key = f"replay:{VERSION}:{market}:{months}"
            if s.scalar(select(Record).where(Record.record_key == key)) is None:
                append(
                    s,
                    key,
                    "REPLAY",
                    market,
                    {
                        "window_months": months,
                        "status": "BLOCKED_RESERVED_PERIODS",
                        "reason": (
                            "Recent window intersects sealed outcomes. No reserved outcomes read; "
                            "permitted replay segments require complete mature cohorts."
                        ),
                        "holdout_outcomes_accessed": 0,
                        "oot_outcomes_accessed": 0,
                    },
                )
    for gap in summary["gaps"]:
        payload = {**gap, "observed_at": now.isoformat()}
        append(s, "gap:" + digest(payload), "GAP", gap["market"], payload)
    if cfg is not None:
        from pitquant.forward.paper import refresh

        summary["simulations_reviewed"] = refresh(s, cfg, now)
    s.commit()
    return summary


def status(s: Session) -> dict[str, Any]:
    from pitquant.forward.learning import activity, learning_dashboard

    return {**dashboard(s), "learning": learning_dashboard(s), "activity": activity(s)}
