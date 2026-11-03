"""Walk-forward on permitted portions only; freeze predictions before revealing labels."""

from __future__ import annotations

import math
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.db.models_forward import ForwardPilotRecord as Record
from pitquant.forward.data import training_frames
from pitquant.forward.engine import (
    FEATURES,
    MARKETS,
    VERSION,
    append,
    due_date,
    features,
    fit_model,
    probability,
)


def replay_window(
    s: Session, market: str, months: int, now: datetime, root: Path
) -> dict[str, Any]:
    start = now.date() - relativedelta(months=months)
    cutoff = date.fromisoformat(str(MARKETS[market]["cutoff"]))
    key = f"replay:{VERSION}:{market}:{months}:{now.date()}"
    prior = s.scalar(select(Record).where(Record.record_key == key))
    if prior:
        return prior.payload
    contract = {
        "market": market,
        "months": months,
        "requested_start": str(start),
        "requested_end": str(now.date()),
        "cutoff_exclusive": str(cutoff),
        "refit": "first permitted decision of each calendar month; fixed parameters",
        "vintage": "RETROSPECTIVE_CURRENT_VINTAGE_NOT_HISTORICAL_PIT",
        "holdout_outcomes_accessed": 0,
        "oot_outcomes_accessed": 0,
        "nonoverlap": "greedy intervals per ticker; not an estimated effective sample size",
    }
    append(s, "protocol:" + key, "REPLAY_PROTOCOL", market, contract)
    s.commit()
    if start >= cutoff:
        result = {
            **contract,
            "window_months": months,
            "status": "BLOCKED_RESERVED_PERIODS",
            "reason": "All requested decision dates fall in sealed historical/OOT periods.",
            "n": 0,
            "nonoverlap_n": 0,
            "accuracy": None,
            "brier": None,
            "logloss": None,
        }
        append(s, key, "REPLAY", market, result)
        s.commit()
        return result
    frames, exclusions = training_frames(s, market, now)
    dates = sorted(
        {
            day
            for frame in frames.values()
            for day in frame.index
            if start <= day < cutoff
            and due_date(market, day, int(MARKETS[market]["horizon"])) < cutoff
        }
    )
    observed = []
    model = None
    previous_month = None
    last_nonoverlap: dict[str, date] = {}
    for day in dates:
        if previous_month != (day.year, day.month):
            past = {t: b[b.index < day].copy() for t, b in frames.items()}
            model = fit_model(s, market, past, exclusions, root, replay_at=day, now=now)
            previous_month = (day.year, day.month)
        assert model is not None
        target = due_date(market, day, int(MARKETS[market]["horizon"]))
        for ticker, b in frames.items():
            if day not in b.index or target not in b.index:
                continue
            x = features(b[b.index <= day]).iloc[-1]
            if pd.isna(x.ret60) or pd.isna(x.sma200):
                continue
            values = [None if pd.isna(v) else float(v) for v in x[FEATURES]]
            pred_key = f"replay-p:{market}:{months}:{now.date()}:{ticker}:{day}"
            old = s.scalar(select(Record).where(Record.record_key == pred_key))
            prediction = old or append(
                s,
                pred_key,
                "REPLAY_PREDICTION",
                market,
                {
                    "model_id": model.record_id,
                    "model_hash": model.payload_hash,
                    "ticker": ticker,
                    "decision_date": str(day),
                    "target_date": str(target),
                    "features": values,
                    "p_up": probability(model.payload, values),
                    "momentum_up": bool(x.ret20 > 0),
                    "vintage": "RETROSPECTIVE_NOT_FORWARD",
                },
            )
            s.commit()  # no outcome is read or published before this prediction survives failure
            signal = b.get("signal_close", b.close)
            actual = float(signal.loc[target] / signal.loc[day] - 1)
            if not math.isfinite(actual):
                continue
            p = prediction.payload["p_up"]
            up = actual > 0
            nonoverlap = ticker not in last_nonoverlap or day >= last_nonoverlap[ticker]
            if nonoverlap:
                last_nonoverlap[ticker] = target
            outcome = {
                "prediction_id": prediction.record_id,
                "actual_return": actual,
                "up": up,
                "hit": bool((p >= 0.5) == up),
                "brier": (p - float(up)) ** 2,
                "logloss": -(
                    float(up) * math.log(max(p, 1e-12))
                    + (1 - float(up)) * math.log(max(1 - p, 1e-12))
                ),
                "always_up_hit": up,
                "momentum_hit": bool(prediction.payload["momentum_up"] == up),
                "nonoverlap": nonoverlap,
            }
            append(s, "outcome:" + prediction.record_id, "REPLAY_OUTCOME", market, outcome)
            s.commit()
            observed.append(outcome)
    result = {
        **contract,
        "window_months": months,
        "status": "PARTIAL_RESERVED_PERIODS" if observed else "NO_PERMITTED_COHORTS",
        "reason": (
            "Only pre-reservation decisions with mature pre-reservation targets evaluated; "
            "later dates remain excluded."
        ),
        "n": len(observed),
        "nonoverlap_n": sum(o["nonoverlap"] for o in observed),
        "first_decision": str(dates[0]) if dates else None,
        "last_decision": str(dates[-1]) if dates else None,
        "excluded": exclusions,
        **{
            name: float(np.mean([o[field] for o in observed])) if observed else None
            for name, field in [
                ("accuracy", "hit"),
                ("brier", "brier"),
                ("logloss", "logloss"),
                ("always_up_accuracy", "always_up_hit"),
                ("momentum_accuracy", "momentum_hit"),
            ]
        },
        "return_basis": "gross price/TR observations; not an investable strategy or net PnL",
    }
    append(s, key, "REPLAY", market, result)
    s.commit()
    return result
