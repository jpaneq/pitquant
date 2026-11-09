# ruff: noqa: E501
"""v3 = price + company fundamentals (ADR-0066). Same algorithm, horizon and parameters as V1/v2.

Like v2, v3 is a *procedure* (monthly expanding refit) judged once before it is trusted:

1. **Exam v3** on the same decisions as the v2 exam (V1 seal → last mature target), US equities:
   arm B = v2 procedure (price only, its exam refits are reused), arm C = v3 procedure (price +
   6 fundamentals). Rules pre-registered, predictions frozen before outcomes.
2. **Policy.** ``LEARNING_V3`` only if v3 beats v2 (mean log loss of B − C > 0). Otherwise the
   current policy stays and v3 keeps competing on real forecasts.
3. **Forward switch v2 ↔ v3** with the same pre-registered rule as v1 ↔ v2.

Honesty note recorded in the protocol: this window was already used for the v2 exam, so we know
price alone fails there. The six fundamentals were chosen from prior literature, not from these
results, and nothing is tuned; still, the exam is not as virgin as the first one.
"""

from __future__ import annotations

import hashlib
import io
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.core.timeutils import require_aware, utc_now
from pitquant.db.models_forward import ForwardPilotRecord as Record
from pitquant.forward.data import training_frames
from pitquant.forward.engine import FEATURES, MARKETS, append, fit_model, records
from pitquant.forward.fundamentals import FUND_FEATURES, FUND_SET, attach, fund_table
from pitquant.forward.learning import (
    LEARNING,
    POLICY_FAMILY,
    RULES,
    SWITCH_MIN_DATES,
    SWITCH_MIN_PAIRS,
    US_UNIVERSE,
    _arm,
    _decisions,
    _logloss,
    _outcomes,
    _scores,
    cluster_interval,
    current_policy,
    exam_record,
    set_policy,
)
from pitquant.forward.storage import publish

V3 = POLICY_FAMILY["LEARNING_V3"]
MARKET = "EQUITY"
EXTRA = tuple(FUND_FEATURES)
RULES_V3: dict[str, Any] = {
    **{k: RULES[k] for k in ("exam_window", "primary_metric", "uncertainty", "seed")},
    "arms": {
        "B_PRICE_V2": "v2 procedure: monthly refit, 10 price features (exam refits reused)",
        "C_PRICE_FUND_V3": f"v3 procedure: monthly refit, 10 price + 6 fundamentals ({FUND_SET})",
    },
    "fundamentals": FUND_FEATURES,
    "fundamentals_timing": "first session of each month at the open; SEC acceptance instant",
    "policy": "LEARNING_V3 if mean logloss(B) - logloss(C) > 0, else keep the current policy",
    "forward_switch": RULES["forward_switch"].replace(
        "current) - logloss(other", "v2) - logloss(v3"
    ),
    "adaptivity": "window already used by the v2 exam; features chosen a priori, nothing tuned",
}


def fund_frames(
    s: Session, now: datetime, since: date | None = None, *, live: bool = False
) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """Price frames of the US universe with the six fundamentals attached (point-in-time)."""
    if live:
        from pitquant.forward.data import load_frame

        frames, exclusions = {}, {}
        for t in US_UNIVERSE:
            try:
                frames[t] = load_frame(s, MARKET, t, now)
            except ValueError as exc:
                exclusions[t] = str(exc)
    else:
        frames, exclusions = training_frames(s, MARKET, now, tickers=US_UNIVERSE, full_history=True)
    out = {}
    for ticker, bars in frames.items():
        out[ticker] = attach(bars, fund_table(s, ticker, now, since))
        out[ticker].attrs = bars.attrs
    return out, exclusions


def v3_models(s: Session) -> list[Record]:
    return [m for m in records(s, "MODEL", MARKET) if m.payload.get("family") == V3]


def exam_v3(s: Session) -> Record | None:
    return s.scalar(select(Record).where(Record.record_key == f"exam:{V3}:{MARKET}"))


def run_exam_v3(s: Session, root: Path, now: datetime | None = None) -> Record:
    now = require_aware(now or utc_now())
    done = exam_v3(s)
    if done is not None:
        return done
    first = exam_record(s, MARKET)
    if first is None:
        raise ValueError("V2_EXAM_REQUIRED_BEFORE_V3")
    seal = date.fromisoformat(str(MARKETS[MARKET]["cutoff"]))
    key = f"exam:{V3}:{MARKET}"
    append(
        s, "protocol:" + key, "EXAM_PROTOCOL", MARKET,
        {**RULES_V3, "market": MARKET, "seal": str(seal), "registered_at": now.isoformat(),
         "evidence": "CURRENT_VINTAGE_NOT_HISTORICAL_PIT"},
    )  # fmt: skip
    s.commit()
    frames, exclusions = fund_frames(s, now)
    if all(f[list(EXTRA)].isna().all().all() for f in frames.values()):
        raise ValueError("NO_FUNDAMENTALS_INGESTED")
    rows = _decisions(frames, MARKET, seal, EXTRA)
    month_start = rows.feature_date.map(lambda d: date(d.year, d.month, 1))
    x_price = rows[FEATURES].to_numpy(float)
    x_full = rows[[*FEATURES, *EXTRA]].to_numpy(float)
    p_b = np.full(len(rows), np.nan)
    p_c = np.full(len(rows), np.nan)
    for m0 in sorted(month_start.unique()):
        past = {t: b[b.index < m0].copy() for t, b in frames.items()}
        common = dict(replay_at=m0, now=now, cutoff=m0, label=f"exam-{m0:%Y-%m}", archive=False)
        b = fit_model(s, MARKET, past, exclusions, root, family=LEARNING, **common)
        c = fit_model(s, MARKET, past, exclusions, root, family=V3, extra_features=EXTRA, **common)
        mask = (month_start == m0).to_numpy()
        p_b[mask] = _scores(b.payload, x_price[mask])
        p_c[mask] = _scores(c.payload, x_full[mask])
    buffer = io.BytesIO()
    np.savez_compressed(
        buffer, ticker=rows.ticker.to_numpy(str),
        feature_date=rows.feature_date.astype(str).to_numpy(str),
        target_date=rows.target_date.astype(str).to_numpy(str), p_v2=p_b, p_v3=p_c,
    )  # fmt: skip
    frozen = root / f"exam-v3-{MARKET}-{now:%Y%m%d}-predictions.npz"
    publish(frozen, buffer.getvalue())
    append(
        s, "predictions:" + key, "EXAM_PREDICTIONS", MARKET,
        {"file": str(frozen), "sha256": hashlib.sha256(frozen.read_bytes()).hexdigest(),
         "n": len(rows), "frozen_at": utc_now().isoformat()},
    )  # fmt: skip
    s.commit()
    actual = _outcomes(frames, rows)
    valid = np.isfinite(actual)
    rows, p_b, p_c, actual = (
        rows[valid].reset_index(drop=True),
        p_b[valid],
        p_c[valid],
        actual[valid],
    )
    y = (actual > 0).astype(float)
    months = month_start[valid].astype(str).to_numpy()
    base = float(first.payload["base_rate_p"])
    gain = cluster_interval(_logloss(p_b, y) - _logloss(p_c, y), months)
    coverage = {n: float(rows[n].notna().mean()) for n in EXTRA}
    frame = pd.DataFrame(
        {"month": months, "y": y, "b": (p_b >= 0.5) == (y == 1), "c": (p_c >= 0.5) == (y == 1)}
    )
    monthly = [
        {"month": m, "n": len(g), "up_rate": float(g.y.mean()), "acc_v2": float(g.b.mean()), "acc_v3": float(g.c.mean())}
        for m, g in frame.groupby("month", sort=True)
    ]  # fmt: skip
    current = (current_policy(s, MARKET) or {}).get("policy")
    result: dict[str, Any] = {
        "market": MARKET,
        "window": {"first_decision": str(rows.feature_date.min()), "last_decision": str(rows.feature_date.max())},
        "n": len(rows),
        "months": len(set(months)),
        "tickers": sorted(frames),
        "excluded": exclusions,
        "fundamental_coverage": coverage,
        "base_rate_p": base,
        "always_up_accuracy": float(y.mean()),
        "arms": {"B_PRICE_V2": _arm(p_b, y, base, months), "C_PRICE_FUND_V3": _arm(p_c, y, base, months)},
        "v3_minus_v2_gain": gain,
        "monthly": monthly,
        "policy": "LEARNING_V3" if gain["mean"] > 0 else current,
        "evaluated_at": utc_now().isoformat(),
        "evidence": "RETROSPECTIVE_CURRENT_VINTAGE; survivorship bias; window reused (see protocol)",
        "costs": "NOT_MODELED",
    }  # fmt: skip
    row = append(s, key, "EXAM", MARKET, result)
    if result["policy"] != current:
        set_policy(s, MARKET, "LEARNING_V3", "EXAM_V3", {"exam_id": row.record_id}, now)
    s.commit()
    return row


def monthly_refit_v3(s: Session, root: Path, now: datetime) -> Record:
    if exam_v3(s) is None:
        raise ValueError("EXAM_V3_REQUIRED_BEFORE_LEARNING")
    frames, exclusions = fund_frames(s, now)
    return fit_model(
        s, MARKET, frames, exclusions, root, now=now, cutoff=now.date(),
        family=V3, label=f"{now:%Y-%m}", extra_features=EXTRA,
    )  # fmt: skip


def forward_comparison_v3(s: Session) -> dict[str, Any]:
    """Matured real forecasts of v2 and v3 refits on the same (ticker, day)."""
    families = {m.record_id: m.payload.get("family") for m in records(s, "MODEL", MARKET)}
    outcome = {r.payload["prediction_id"]: r.payload for r in records(s, "OUTCOME", MARKET)}
    by: dict[str, dict[tuple[str, str], tuple[float, float]]] = {LEARNING: {}, V3: {}}
    for pred in records(s, "PREDICTION", MARKET):
        family = families.get(pred.payload["model_id"])
        o = outcome.get(pred.record_id)
        if family in by and o is not None:
            key = (pred.payload["ticker"], pred.payload["feature_date"])
            by[str(family)][key] = (float(pred.payload["p_up"]), float(o["actual_return"] > 0))
    keys = sorted(set(by[LEARNING]) & set(by[V3]))
    if not keys:
        return {"pairs": 0, "dates": 0}
    y = np.array([by[LEARNING][k][1] for k in keys])
    ll2 = _logloss(np.array([by[LEARNING][k][0] for k in keys]), y)
    ll3 = _logloss(np.array([by[V3][k][0] for k in keys]), y)
    return {
        "pairs": len(keys),
        "dates": len({k[1] for k in keys}),
        "v2_logloss": float(ll2.mean()),
        "v3_logloss": float(ll3.mean()),
        "v3_gain": cluster_interval(ll2 - ll3, [k[1] for k in keys]),
    }


def review_policy_v3(s: Session, now: datetime) -> dict[str, Any]:
    policy = (current_policy(s, MARKET) or {}).get("policy")
    cmp = forward_comparison_v3(s)
    if (
        policy not in ("LEARNING", "LEARNING_V3")
        or cmp["pairs"] < SWITCH_MIN_PAIRS
        or cmp["dates"] < SWITCH_MIN_DATES
    ):
        return {"switched": False, "comparison": cmp}
    gain = cmp["v3_gain"]
    target = "LEARNING_V3" if policy == "LEARNING" and gain["low90"] > 0 else None
    target = "LEARNING" if policy == "LEARNING_V3" and gain["high90"] < 0 else target
    if target is None:
        return {"switched": False, "comparison": cmp}
    set_policy(s, MARKET, target, "FORWARD_SWITCH_RULE_V3", cmp, now)
    return {"switched": True, "to": target, "comparison": cmp}


def step_v3(s: Session, root: Path, now: datetime) -> dict[str, Any]:
    exam = run_exam_v3(s, root, now)
    refit = monthly_refit_v3(s, root, now)
    review = review_policy_v3(s, now)
    s.commit()
    return {
        "exam_id": exam.record_id,
        "refit": refit.payload["version"],
        "switched": review["switched"],
    }


def v3_dashboard(s: Session) -> dict[str, Any]:
    exam = exam_v3(s)
    return {
        "family": V3,
        "features": FUND_FEATURES,
        "exam": exam.payload if exam else None,
        "refits": [
            {
                "version": m.payload["version"],
                "train_n": m.payload["train_n"],
                "trained_at": m.payload["trained_at"],
            }
            for m in v3_models(s)
        ],
        "forward": forward_comparison_v3(s),
    }
