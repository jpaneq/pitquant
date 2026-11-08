"""Forward learning (ADR-0064): a procedure that keeps learning, judged before it is trusted.

1. **One-time exam.** The frozen V1 model and the *learning procedure* (monthly expanding refit,
   same features and parameters, wider US universe) are both evaluated on everything V1 never
   saw: decisions from the V1 seal to the last mature target. Rules are pre-registered in an
   ``EXAM_PROTOCOL`` record and predictions are frozen (file + hash) before any outcome is read.
2. **Policy.** The exam picks the live policy: ``LEARNING`` (the latest monthly refit is the
   champion) or ``FROZEN_V1``. The exam can only be run once per market.
3. **Monthly refit.** Each calendar month a new model is fitted on all labels matured before
   the fit date. Under ``LEARNING`` it becomes champion automatically: what was validated is
   the procedure, not one set of coefficients.
4. **Self-correction.** V1 and the latest refit keep issuing forecasts side by side. A
   pre-registered rule on *matured forward* forecasts switches the policy when the other arm
   is better with a 90 % bootstrap interval that excludes zero. Every switch is recorded.

No orders, no costs, no tuning: features, parameters and rules are fixed in this file.
"""

from __future__ import annotations

import hashlib
import io
from collections.abc import Iterable
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
from pitquant.forward.engine import (
    FEATURES,
    MARKETS,
    TICKERS,
    VERSION,
    append,
    digest,
    features,
    fit_model,
    records,
)
from pitquant.forward.storage import publish

LEARNING = "forward-logistic-price-v2-learning"
# Frozen: the routine's US large caps (SP500 + US names of the MSCI World list) on 2026-11-08.
# Current constituents chosen today => survivorship bias; reported, not corrected.
US_UNIVERSE: list[str] = [
    *TICKERS,
    *[
        "META",
        "V",
        "UNH",
        "LLY",
        "AVGO",
        "TSLA",
        "MA",
        "COST",
        "HD",
        "WMT",
        "ABBV",
        "MRK",
        "CVX",
        "BAC",
        "ORCL",
        "CRM",
        "NFLX",
        "ADBE",
        "CSCO",
        "PEP",
        "TMO",
        "ACN",
        "MCD",
        "ABT",
        "LIN",
        "DIS",
        "WFC",
        "CAT",
        "IBM",
        "GE",
        "QCOM",
        "TXN",
        "AMGN",
        "INTU",
        "VZ",
        "PFE",
        "BA",
        "HON",
        "UNP",
        "LOW",
        "SPGI",
        "NEE",
        "RTX",
        "LMT",
        "UPS",
    ],
]
BTC_FIRST_DAY_MS = 1502928000000  # 2017-08-17, first BTCUSDT daily candle on Binance spot
RULES: dict[str, Any] = {
    "exam_window": "first decision on the V1 seal date; last decision whose target is mature",
    "arms": {
        "A_FROZEN_V1": "V1 coefficients, never refitted",
        "B_LEARNING": "refit on the 1st of every month with labels matured before that day",
    },
    "universe": "US_UNIVERSE for equities (V1 scored on the same rows), BTC for BTC",
    "primary_metric": "log loss of p_up against the realised direction (return > 0)",
    "base_rate": "constant p = V1 training up-rate (known before the exam)",
    "uncertainty": "block bootstrap by calendar month of the decision, 2000 draws, 90 % interval",
    "policy": "LEARNING if mean logloss(A) - logloss(B) > 0, else FROZEN_V1",
    "signal_verdict": (
        "EVIDENCE_OF_SIGNAL if the 90 % interval of base-rate minus arm logloss is above zero; "
        "WORSE_THAN_BASE_RATE if below zero; otherwise NO_EVIDENCE"
    ),
    "forward_switch": (
        "on matured forward forecasts paired by (ticker, feature_date): switch policy when "
        "n >= 200 pairs over >= 20 dates and the 90 % date-bootstrap interval of "
        "logloss(current) - logloss(other) is entirely above zero"
    ),
    "seed": 20261108,
}
SWITCH_MIN_PAIRS = 200
SWITCH_MIN_DATES = 20


# ---------------------------------------------------------------- data


def universe(market: str) -> list[str]:
    return ["BTC"] if market == "BTC" else US_UNIVERSE


def backfill_btc(session: Session, store: Any) -> dict[str, Any]:
    """Daily BTCUSDT candles since 2017 from Binance's public endpoint (idempotent)."""
    from pitquant.btc.providers import PublicProvider

    provider = PublicProvider(session, store)
    start, step = BTC_FIRST_DAY_MS, 1000 * 86_400_000
    now_ms = int(utc_now().timestamp() * 1000)
    windows = 0
    while start < now_ms:
        provider.spot(start_ms=start, end_ms=start + step - 1)
        session.commit()
        start += step
        windows += 1
    return {"windows": windows, "source": "BINANCE_SPOT", "vintage": "current, not historical PIT"}


def _scores(model: dict[str, Any], x: np.ndarray) -> np.ndarray:
    """Vectorised twin of ``engine.probability`` (same imputation, scaling and clipping)."""
    x = np.where(np.isnan(x), np.asarray(model["imputer"]), x)
    z = (x - np.asarray(model["mean"])) / np.asarray(model["scale"])
    score = np.clip(z @ np.asarray(model["coef"]) + float(model["intercept"]), -700, 700)
    if not np.isfinite(score).all():
        raise ValueError("NONFINITE_MODEL_SCORE")
    return np.asarray(1 / (1 + np.exp(-score)), dtype=float)


def _decisions(frames: dict[str, pd.DataFrame], market: str, start: date) -> pd.DataFrame:
    """Feature rows from ``start`` on. Features are causal, so one pass over the full frame
    equals recomputing on each truncated past. Outcomes are NOT attached here."""
    h = int(MARKETS[market]["horizon"])
    out = []
    for ticker, bars in sorted(frames.items()):
        x = features(bars)
        x["target_date"] = pd.Series(bars.index, index=bars.index).shift(-h)
        x["ticker"] = ticker
        x["feature_date"] = x.index
        keep = (x.index >= start) & x.ret60.notna() & x.sma200.notna() & x.target_date.notna()
        out.append(x[keep])
    rows = pd.concat(out, ignore_index=True) if out else pd.DataFrame()
    if rows.empty:
        raise ValueError("NO_EXAM_DECISIONS")
    return rows.sort_values(["feature_date", "ticker"], ignore_index=True)


def _outcomes(frames: dict[str, pd.DataFrame], rows: pd.DataFrame) -> np.ndarray:
    actual = []
    for ticker, day, target in rows[["ticker", "feature_date", "target_date"]].itertuples(
        index=False
    ):
        b = frames[ticker]
        sig = b.get("signal_close", b.close)
        actual.append(float(sig.loc[target] / sig.loc[day] - 1))
    return np.asarray(actual, dtype=float)


# ---------------------------------------------------------------- statistics


def _logloss(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return np.asarray(-(y * np.log(p) + (1 - y) * np.log1p(-p)), dtype=float)


def cluster_interval(
    values: np.ndarray, clusters: Iterable[Any], seed: int = RULES["seed"], draws: int = 2000
) -> dict[str, float]:
    """Mean and 90 % interval, resampling whole clusters (dates or months)."""
    keys = np.asarray([str(c) for c in clusters])
    uniq, inverse = np.unique(keys, return_inverse=True)
    sums = np.bincount(inverse, weights=values, minlength=len(uniq))
    counts = np.bincount(inverse, minlength=len(uniq)).astype(float)
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(uniq), size=(draws, len(uniq)))
    means = sums[pick].sum(axis=1) / counts[pick].sum(axis=1)
    return {
        "mean": float(values.mean()),
        "low90": float(np.quantile(means, 0.05)),
        "high90": float(np.quantile(means, 0.95)),
        "clusters": len(uniq),
    }


def _verdict(interval: dict[str, float]) -> str:
    if interval["low90"] > 0:
        return "EVIDENCE_OF_SIGNAL"
    if interval["high90"] < 0:
        return "WORSE_THAN_BASE_RATE"
    return "NO_EVIDENCE"


def _arm(p: np.ndarray, y: np.ndarray, base: float, months: np.ndarray) -> dict[str, Any]:
    ll = _logloss(p, y)
    base_ll = _logloss(np.full_like(p, base), y)
    gain = cluster_interval(base_ll - ll, months)
    return {
        "n": len(p),
        "accuracy": float(((p >= 0.5) == (y == 1)).mean()),
        "brier": float(((p - y) ** 2).mean()),
        "logloss": float(ll.mean()),
        "mean_p_up": float(p.mean()),
        "gain_vs_base_rate": gain,
        "signal_verdict": _verdict(gain),
    }


# ---------------------------------------------------------------- exam


def baseline_model(s: Session, market: str) -> Record | None:
    return next((m for m in records(s, "MODEL", market) if m.payload["baseline"]), None)


def exam_record(s: Session, market: str) -> Record | None:
    return s.scalar(select(Record).where(Record.record_key == f"exam:{LEARNING}:{market}"))


def run_exam(s: Session, market: str, root: Path, now: datetime | None = None) -> Record:
    """Evaluate V1 and the learning procedure once on the period V1 never saw."""
    now = require_aware(now or utc_now())
    done = exam_record(s, market)
    if done is not None:
        return done
    v1 = baseline_model(s, market)
    if v1 is None:
        raise ValueError("V1_REQUIRED_BEFORE_EXAM")
    seal = date.fromisoformat(str(MARKETS[market]["cutoff"]))
    key = f"exam:{LEARNING}:{market}"
    append(
        s,
        "protocol:" + key,
        "EXAM_PROTOCOL",
        market,
        {
            **RULES,
            "market": market,
            "seal": str(seal),
            "v1_model_id": v1.record_id,
            "registered_at": now.isoformat(),
            "evidence": "CURRENT_VINTAGE_NOT_HISTORICAL_PIT",
        },
    )
    s.commit()  # pre-registration survives anything below
    frames, exclusions = training_frames(
        s, market, now, tickers=universe(market), full_history=True
    )
    rows = _decisions(frames, market, seal)
    x = rows[FEATURES].to_numpy(float)
    p_a = _scores(v1.payload, x)
    p_b = np.full(len(rows), np.nan)
    month_start = rows.feature_date.map(lambda d: date(d.year, d.month, 1))
    refits = []
    for m0 in sorted(month_start.unique()):
        past = {t: b[b.index < m0].copy() for t, b in frames.items()}
        model = fit_model(
            s,
            market,
            past,
            exclusions,
            root,
            replay_at=m0,
            now=now,
            cutoff=m0,
            family=LEARNING,
            label=f"exam-{m0:%Y-%m}",
            archive=False,
        )
        mask = (month_start == m0).to_numpy()
        p_b[mask] = _scores(model.payload, x[mask])
        refits.append(
            {"month": str(m0), "model_id": model.record_id, "n": model.payload["train_n"]}
        )
    # Freeze every prediction before reading any outcome.
    buffer = io.BytesIO()
    np.savez_compressed(
        buffer,
        ticker=rows.ticker.to_numpy(str),
        feature_date=rows.feature_date.astype(str).to_numpy(str),
        target_date=rows.target_date.astype(str).to_numpy(str),
        p_v1=p_a,
        p_learning=p_b,
        momentum_up=(rows.ret20 > 0).to_numpy(),
    )
    frozen = root / f"exam-{market}-{now:%Y%m%d}-predictions.npz"
    publish(frozen, buffer.getvalue())
    append(
        s,
        "predictions:" + key,
        "EXAM_PREDICTIONS",
        market,
        {
            "file": str(frozen),
            "sha256": hashlib.sha256(frozen.read_bytes()).hexdigest(),
            "n": len(rows),
            "refits": refits,
            "frozen_at": utc_now().isoformat(),
        },
    )
    s.commit()
    actual = _outcomes(frames, rows)
    valid = np.isfinite(actual)  # a missing target close is a hole, never a guess
    rows, actual, p_a, p_b = (
        rows[valid].reset_index(drop=True),
        actual[valid],
        p_a[valid],
        p_b[valid],
    )
    y = (actual > 0).astype(float)
    months = month_start[valid].astype(str).to_numpy()
    base = float(v1.payload.get("train_up_rate") or 0.5)
    momentum = (rows.ret20 > 0).to_numpy()
    in_v1 = rows.ticker.isin(v1.payload["universe"]).to_numpy()
    diff = cluster_interval(_logloss(p_a, y) - _logloss(p_b, y), months)
    result: dict[str, Any] = {
        "market": market,
        "window": {
            "first_decision": str(rows.feature_date.min()),
            "last_decision": str(rows.feature_date.max()),
            "last_target": str(rows.target_date.max()),
        },
        "n": len(rows),
        "missing_target_rows": int((~valid).sum()),
        "tickers": sorted(frames),
        "excluded": exclusions,
        "months": len(set(months)),
        "base_rate_p": base,
        "always_up_accuracy": float(y.mean()),
        "momentum_accuracy": float((momentum == (y == 1)).mean()),
        "base_rate_logloss": float(_logloss(np.full_like(y, base), y).mean()),
        "arms": {
            "A_FROZEN_V1": _arm(p_a, y, base, months),
            "B_LEARNING": _arm(p_b, y, base, months),
        },
        "v1_universe_only": {
            "n": int(in_v1.sum()),
            "A_FROZEN_V1": _arm(p_a[in_v1], y[in_v1], base, months[in_v1]) if in_v1.any() else None,
            "B_LEARNING": _arm(p_b[in_v1], y[in_v1], base, months[in_v1]) if in_v1.any() else None,
        },
        "learning_minus_frozen_gain": diff,
        "policy": "LEARNING" if diff["mean"] > 0 else "FROZEN_V1",
        "predictions_file": str(frozen),
        "evaluated_at": utc_now().isoformat(),
        "evidence": "RETROSPECTIVE_CURRENT_VINTAGE_NOT_HISTORICAL_PIT; survivorship bias",
        "overlap": f"{MARKETS[market]['horizon']}-step targets overlap; intervals use month blocks",
        "costs": "NOT_MODELED",
    }
    row = append(s, key, "EXAM", market, result)
    set_policy(s, market, result["policy"], "EXAM", {"exam_id": row.record_id}, now)
    s.commit()
    return row


# ---------------------------------------------------------------- policy and refits


def current_policy(s: Session, market: str) -> dict[str, Any] | None:
    rows = records(s, "POLICY", market)
    return rows[-1].payload if rows else None


def set_policy(
    s: Session, market: str, policy: str, reason: str, evidence: dict[str, Any], now: datetime
) -> Record:
    payload = {
        "policy": policy,
        "reason": reason,
        "evidence": evidence,
        "decided_at": now.isoformat(),
    }
    return append(s, f"policy:{market}:{digest(payload)}", "POLICY", market, payload)


def learning_models(s: Session, market: str) -> list[Record]:
    return [m for m in records(s, "MODEL", market) if m.payload.get("family") == LEARNING]


def champion(s: Session, market: str) -> Record | None:
    policy = current_policy(s, market)
    if policy is None:
        return baseline_model(s, market)
    if policy["policy"] == "LEARNING":
        refits = learning_models(s, market)
        if refits:
            return refits[-1]
    return baseline_model(s, market)


def monthly_refit(s: Session, market: str, root: Path, now: datetime | None = None) -> Record:
    """Fit this month's model on every label matured before today (idempotent per month)."""
    now = require_aware(now or utc_now())
    if exam_record(s, market) is None:
        raise ValueError("EXAM_REQUIRED_BEFORE_LEARNING")
    frames, exclusions = training_frames(
        s, market, now, tickers=universe(market), full_history=True
    )
    return fit_model(
        s,
        market,
        frames,
        exclusions,
        root,
        now=now,
        cutoff=now.date(),
        family=LEARNING,
        label=f"{now:%Y-%m}",
    )


def forward_pairs(s: Session, market: str) -> list[dict[str, Any]]:
    """Matured forward forecasts of V1 and of the learning refits on the same (ticker, day)."""
    v1 = baseline_model(s, market)
    refit_ids = {m.record_id for m in learning_models(s, market)}
    outcome = {r.payload["prediction_id"]: r.payload for r in records(s, "OUTCOME", market)}
    v1_p: dict[tuple[str, str], tuple[float, float]] = {}
    learn_p: dict[tuple[str, str], tuple[float, float]] = {}
    for pred in records(s, "PREDICTION", market):
        o = outcome.get(pred.record_id)
        if o is None:
            continue
        identity = (pred.payload["ticker"], pred.payload["feature_date"])
        value = (float(pred.payload["p_up"]), float(o["actual_return"] > 0))
        if v1 is not None and pred.payload["model_id"] == v1.record_id:
            v1_p[identity] = value
        elif pred.payload["model_id"] in refit_ids:
            learn_p[identity] = value  # later refits overwrite: one learning forecast per key
    return [
        {
            "ticker": k[0],
            "date": k[1],
            "p_v1": v1_p[k][0],
            "p_learning": learn_p[k][0],
            "up": v1_p[k][1],
        }
        for k in sorted(set(v1_p) & set(learn_p))
        if v1_p[k][1] == learn_p[k][1]
    ]


def forward_comparison(s: Session, market: str) -> dict[str, Any]:
    pairs = forward_pairs(s, market)
    if not pairs:
        return {"pairs": 0, "dates": 0}
    y = np.asarray([p["up"] for p in pairs])
    ll_v1 = _logloss(np.asarray([p["p_v1"] for p in pairs]), y)
    ll_learn = _logloss(np.asarray([p["p_learning"] for p in pairs]), y)
    dates = [p["date"] for p in pairs]
    return {
        "pairs": len(pairs),
        "dates": len(set(dates)),
        "v1_logloss": float(ll_v1.mean()),
        "learning_logloss": float(ll_learn.mean()),
        "learning_gain": cluster_interval(ll_v1 - ll_learn, dates),
    }


def review_policy(s: Session, market: str, now: datetime) -> dict[str, Any]:
    """Apply the pre-registered forward switch rule."""
    policy = current_policy(s, market)
    cmp = forward_comparison(s, market)
    if policy is None or cmp["pairs"] < SWITCH_MIN_PAIRS or cmp["dates"] < SWITCH_MIN_DATES:
        return {"switched": False, "comparison": cmp}
    gain = cmp["learning_gain"]
    target = None
    if policy["policy"] == "FROZEN_V1" and gain["low90"] > 0:
        target = "LEARNING"
    elif policy["policy"] == "LEARNING" and gain["high90"] < 0:
        target = "FROZEN_V1"
    if target is None:
        return {"switched": False, "comparison": cmp}
    set_policy(s, market, target, "FORWARD_SWITCH_RULE", cmp, now)
    return {"switched": True, "to": target, "comparison": cmp}


def learning_step(s: Session, market: str, root: Path, now: datetime) -> dict[str, Any]:
    """Exam once, this month's refit, then the forward switch rule. Order matters."""
    exam = run_exam(s, market, root, now)
    refit = monthly_refit(s, market, root, now)
    review = review_policy(s, market, now)
    s.commit()
    best = champion(s, market)
    return {
        "market": market,
        "exam_id": exam.record_id,
        "policy": (current_policy(s, market) or {}).get("policy"),
        "refit": refit.payload["version"],
        "champion": best.payload["version"] if best else None,
        "switched": review["switched"],
    }


def learning_dashboard(s: Session) -> list[dict[str, Any]]:
    out = []
    for market in MARKETS:
        exam = exam_record(s, market)
        best = champion(s, market)
        out.append(
            {
                "market": market,
                "family": LEARNING,
                "exam": exam.payload if exam else None,
                "policy_history": [r.payload for r in records(s, "POLICY", market)],
                "champion": {
                    "model_id": best.record_id,
                    "version": best.payload["version"],
                    "family": best.payload.get("family", VERSION),
                }
                if best
                else None,
                "refits": [
                    {
                        "model_id": m.record_id,
                        "version": m.payload["version"],
                        "trained_at": m.payload["trained_at"],
                        "train_n": m.payload["train_n"],
                        "train_target_end": m.payload["train_target_end"],
                        "tickers": len(m.payload["universe"]),
                    }
                    for m in learning_models(s, market)
                ],
                "forward": forward_comparison(s, market),
                "rules": RULES,
            }
        )
    return out
