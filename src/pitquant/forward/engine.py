"""Small price-only logistic pilots. No fitting on reserved outcomes, no auto orders."""

from __future__ import annotations

import hashlib
import io
import json
import math
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.core.timeutils import require_aware, utc_now
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.db.models_forward import ForwardPilotRecord as Record
from pitquant.forward.storage import publish

FEATURES = [
    "ret1",
    "ret5",
    "ret20",
    "ret60",
    "vol20",
    "sma20",
    "sma50",
    "sma200",
    "atr14",
    "volume_z20",
]
PARAMS: dict[str, Any] = {
    "penalty": "l2",
    "C": 1.0,
    "max_iter": 2000,
    "random_state": 20261103,
    "solver": "lbfgs",
}
MARKETS: dict[str, dict[str, Any]] = {
    "EQUITY": {"horizon": 20, "reviews": [1, 5, 10, 20], "cutoff": "2022-10-01"},
    "BTC": {"horizon": 30, "reviews": [1, 7, 14, 30], "cutoff": "2025-10-01"},
}
TICKERS = ["AAPL", "MSFT", "KO", "JNJ", "JPM", "XOM", "PG", "AMZN", "GOOGL", "NVDA"]
VERSION = "forward-logistic-price-v1"


def encoded(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(encoded(value)).hexdigest()


def append(s: Session, key: str, kind: str, market: str, payload: dict[str, Any]) -> Record:
    old = s.scalar(select(Record).where(Record.record_key == key))
    if old:
        if old.payload_hash != digest(old.payload):
            raise ValueError("JOURNAL_INTEGRITY_ERROR")
        if old.payload_hash != digest(payload):
            raise ValueError("IMMUTABLE_RECORD_CONFLICT: " + key)
        return old
    row = Record(
        record_key=key, kind=kind, market=market, payload=payload, payload_hash=digest(payload)
    )
    s.add(row)
    s.flush()
    return row


def records(s: Session, kind: str, market: str | None = None) -> list[Record]:
    query = select(Record).where(Record.kind == kind).order_by(Record.created_at, Record.record_id)
    if market:
        query = query.where(Record.market == market)
    rows = list(s.scalars(query))
    if any(r.payload_hash != digest(r.payload) for r in rows):
        raise ValueError("JOURNAL_INTEGRITY_ERROR")
    return rows


def features(bars: pd.DataFrame) -> pd.DataFrame:
    """Causal, scale-free features. Missing prices never forward-filled."""
    close = bars["close"].astype(float)
    signal = bars.get("signal_close", close).astype(float)
    out = pd.DataFrame(index=bars.index)
    for h in (1, 5, 20, 60):
        out[f"ret{h}"] = signal.pct_change(h, fill_method=None)
    out["vol20"] = signal.pct_change(fill_method=None).rolling(20).std(ddof=0)
    for n in (20, 50, 200):
        out[f"sma{n}"] = close / close.rolling(n).mean() - 1
    prev = close.shift(1)
    tr = pd.concat(
        [bars.high - bars.low, (bars.high - prev).abs(), (bars.low - prev).abs()], axis=1
    ).max(axis=1)
    out["atr14"] = tr.rolling(14).mean() / close
    vol = bars.volume.astype(float)
    sd = vol.rolling(20).std(ddof=0)
    out["volume_z20"] = (vol - vol.rolling(20).mean()) / sd.replace(0, np.nan)
    # Require full warmup without calendar holes; optional volume alone may be imputed.
    valid = close.notna().rolling(201).sum() == 201
    out.loc[~valid, :] = np.nan
    return out[FEATURES].replace([np.inf, -np.inf], np.nan)


def training_rows(
    bars: pd.DataFrame, market: str, ticker: str, cutoff: date | None = None
) -> pd.DataFrame:
    """Rows whose feature AND target dates are strictly before ``cutoff`` (default: V1 seal)."""
    cutoff = cutoff or date.fromisoformat(str(MARKETS[market]["cutoff"]))
    # Filter BEFORE any target construction: reserved prices cannot enter a target.
    b = bars[bars.index < cutoff]
    h = int(MARKETS[market]["horizon"])
    x = features(b)
    price = b.get("signal_close", b.close)
    x["actual_return"] = price.shift(-h) / price - 1
    x["target_date"] = pd.Series(b.index, index=b.index).shift(-h)
    x["ticker"] = ticker
    x["feature_date"] = x.index
    return x[x.ret60.notna() & x.sma200.notna() & x.actual_return.notna()].copy()


def fit_model(
    s: Session,
    market: str,
    frames: dict[str, pd.DataFrame],
    exclusions: dict[str, str],
    root: Path,
    *,
    candidate: bool = False,
    replay_at: date | None = None,
    now: datetime | None = None,
    cutoff: date | None = None,
    family: str = VERSION,
    label: str | None = None,
    archive: bool = True,
) -> Record:
    """Fit one logistic model with the frozen V1 features/parameters.

    Defaults reproduce V1 exactly. ``family``/``label``/``cutoff`` identify the learning
    refits (ADR-0064): same algorithm, wider universe, training window up to ``cutoff``.
    ``archive=False`` skips the compact training archive (exam refits; hash still recorded).
    """
    import sklearn
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from threadpoolctl import threadpool_limits

    now = require_aware(now or utc_now())
    version = label or (
        ("replay-" + str(replay_at))
        if replay_at
        else (now.strftime("%Y-%m") if candidate else "v1")
    )
    key = f"model:{family}:{market}:{version}"
    existing = s.scalar(select(Record).where(Record.record_key == key))
    if existing:
        if digest(existing.payload) != existing.payload_hash:
            raise ValueError("MODEL_INTEGRITY_ERROR")
        return existing
    rows = [training_rows(b, market, t, cutoff) for t, b in sorted(frames.items())]
    data = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    if candidate:
        seen = set()
        learned = []
        for outcome in records(s, "OUTCOME", market):
            p = outcome.payload
            pred = s.get(Record, p["prediction_id"])
            if pred is None or p["due_at"] > now.isoformat() or p["observed_at"] > now.isoformat():
                continue
            v = pred.payload
            identity = (v["ticker"], v["feature_date"])
            if identity not in seen:
                learned.append(
                    {
                        **dict(zip(FEATURES, v["features"], strict=True)),
                        "actual_return": p["actual_return"],
                        "ticker": v["ticker"],
                        "feature_date": date.fromisoformat(v["feature_date"]),
                        "target_date": date.fromisoformat(p["target_date"]),
                    }
                )
                seen.add(identity)
        if not learned:
            raise ValueError("NO_NEW_MATURE_FORWARD_LABELS")
        data = pd.concat([data, pd.DataFrame(learned)], ignore_index=True)
    if len(data) < 250 or data.actual_return.gt(0).nunique() != 2:
        raise ValueError("INSUFFICIENT_ALLOWED_TRAINING_DATA")
    if data[FEATURES].isna().all().any():
        raise ValueError("ALL_MISSING_TRAIN_COLUMN")
    x = data[FEATURES].to_numpy(float)
    y = data.actual_return.gt(0).astype(int).to_numpy()
    if replay_at is not None and (data.target_date >= replay_at).any():
        raise ValueError("IMMATURE_REPLAY_TRAIN_LABEL")
    metadata = data[["ticker", "feature_date", "target_date"]].astype(str).to_dict("records")
    dataset_hash = digest(
        {
            "rows": metadata,
            "x": np.where(np.isnan(x), 0, x).tolist(),
            "missing": np.isnan(x).tolist(),
            "y": y.tolist(),
        }
    )
    protocol = {
        "version": VERSION,
        "market": market,
        "horizon": MARKETS[market]["horizon"],
        "reviews": MARKETS[market]["reviews"],
        "features": FEATURES,
        "formulas": (
            "ret1/5/20/60 on internal TR; close/SMA20/50/200-1; "
            "population volatility20; ATR14/close; volume z20; minimum201 consecutive bars"
        ),
        "parameters": PARAMS,
        "dataset_hash": dataset_hash,
        "sources": {t: b.attrs for t, b in frames.items()},
        "n": len(data),
        "universe": sorted(frames),
        "excluded": exclusions,
        "target": "return > 0; exactly zero is DOWN_OR_FLAT",
        "train_before": str(cutoff) if cutoff else MARKETS[market]["cutoff"],
        "candidate_forward_labels": candidate,
        "evidence": "RETROSPECTIVE_CURRENT_VINTAGE_NOT_HISTORICAL_PIT",
        "holdout_outcomes_accessed": 0,
        "oot_outcomes_accessed": 0,
        "frozen_at": now.isoformat(),
        "auto_orders": False,
        "costs": "NOT_MODELED",
        "selection": "fixed parameters; no tuning",
    }
    if family != VERSION:  # V1 protocol keys stay byte-identical
        protocol["family"] = family
        protocol["learning_adr"] = "ADR-0064"
    append(s, f"protocol:{key}", "PROTOCOL", market, protocol)
    s.commit()  # must survive a failed fit
    target: Path | None = None
    artifact_hash: str | None = None
    if archive:
        root.mkdir(parents=True, exist_ok=True)
        target = root / f"{market}-{version}-{dataset_hash[:12]}.npz"
        buffer = io.BytesIO()
        np.savez_compressed(
            buffer,
            x=x,
            y=y,
            ticker=data.ticker.to_numpy(str),
            feature_date=data.feature_date.astype(str).to_numpy(str),
            target_date=data.target_date.astype(str).to_numpy(str),
        )
        publish(target, buffer.getvalue())
        with np.load(target, allow_pickle=False) as checked:
            if not np.array_equal(checked["x"], x, equal_nan=True) or not np.array_equal(
                checked["y"], y
            ):
                raise ValueError("TRAINING_ARCHIVE_INTEGRITY_ERROR")
        publish(root / f"{market}-{version}-protocol.json", encoded(protocol))
        artifact_hash = hashlib.sha256(target.read_bytes()).hexdigest()
    pipeline = make_pipeline(
        SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(**PARAMS)
    )
    with threadpool_limits(limits=2):
        pipeline.fit(x, y)
    imputer, scaler, classifier = pipeline.steps[0][1], pipeline.steps[1][1], pipeline.steps[2][1]
    if int(classifier.n_iter_[0]) >= PARAMS["max_iter"]:
        raise ValueError("MODEL_DID_NOT_CONVERGE")
    payload = {
        "version": version,
        "status": "EXPERIMENTAL_NOT_VALIDATED",
        "trained_at": now.isoformat(),
        "protocol_key": f"protocol:{key}",
        "protocol_hash": digest(protocol),
        "dataset_hash": dataset_hash,
        "dataset_file": str(target) if target else None,
        "dataset_file_sha256": artifact_hash,
        "train_n": len(data),
        "train_up_rate": float(y.mean()),
        "train_feature_start": str(data.feature_date.min()),
        "train_feature_end": str(data.feature_date.max()),
        "train_target_end": str(data.target_date.max()),
        "universe": sorted(frames),
        "excluded": exclusions,
        "parameters": PARAMS,
        "sklearn_version": sklearn.__version__,
        "feature_names": FEATURES,
        "imputer": imputer.statistics_.tolist(),
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "coef": classifier.coef_[0].tolist(),
        "intercept": float(classifier.intercept_[0]),
        "classes": classifier.classes_.tolist(),
        "baseline": not candidate and family == VERSION and replay_at is None,
    }
    if family != VERSION:
        payload["family"] = family
    if archive:
        publish(root / f"{market}-{version}-model.json", encoded(payload))
    row = append(s, key, "REPLAY_MODEL" if replay_at else "MODEL", market, payload)
    s.commit()
    return row


def probability(model: dict[str, Any], values: list[float | None]) -> float:
    x = np.array([np.nan if v is None else v for v in values], dtype=float)
    x = np.where(np.isnan(x), model["imputer"], x)
    z = (x - np.asarray(model["mean"])) / np.asarray(model["scale"])
    score = float(z @ np.asarray(model["coef"]) + model["intercept"])
    if not math.isfinite(score):
        raise ValueError("NONFINITE_MODEL_SCORE")
    return float(1 / (1 + math.exp(-max(-700, min(700, score)))))


def due_date(market: str, day: date, steps: int) -> date:
    if market == "BTC":
        return day + timedelta(days=steps)
    cal = get_calendar("XNYS")
    for _ in range(steps):
        day = cal.next_session(day)
    return day


def predict(
    s: Session, model: Record, ticker: str, bars: pd.DataFrame, now: datetime | None = None
) -> Record:
    now = require_aware(now or utc_now())
    if digest(model.payload) != model.payload_hash:
        raise ValueError("MODEL_INTEGRITY_ERROR")
    if datetime.fromisoformat(model.payload["trained_at"]) > now:
        raise ValueError("MODEL_NOT_YET_AVAILABLE")
    market = model.market
    cal = get_calendar("XNYS")
    latest = now.date() - timedelta(days=1) if market == "BTC" else cal.last_closed_session(now)
    bars = bars[bars.index <= latest]
    if bars.empty or bars.index[-1] != latest:
        raise ValueError("STALE_PRICE_DATA")
    x = features(bars).iloc[-1]
    if pd.isna(x.ret60) or pd.isna(x.sma200):
        raise ValueError("MISSING_FEATURE_HISTORY")
    values = [None if pd.isna(v) else float(v) for v in x]
    day = bars.index[-1]
    key = f"prediction:{model.record_id}:{ticker}:{day}"
    existing = s.scalar(select(Record).where(Record.record_key == key))
    if existing:
        return existing
    h = int(MARKETS[market]["horizon"])
    target = due_date(market, day, h)
    maturity = (
        datetime.combine(target + timedelta(days=1), datetime.min.time(), UTC)
        if market == "BTC"
        else cal.session_close(target)
    )
    payload = {
        "model_id": model.record_id,
        "model_hash": model.payload_hash,
        "version": model.payload["version"],
        "ticker": ticker,
        "generated_at": now.isoformat(),
        "feature_date": str(day),
        "features": values,
        "reference_price": float(bars.close.iloc[-1]),
        "reference_signal": float(bars.get("signal_close", bars.close).iloc[-1]),
        "due_at": maturity.isoformat(),
        "target_date": str(target),
        "horizon": h,
        "p_up": probability(model.payload, values),
        "momentum_up": bool(x.ret20 > 0),
        "input_hash": digest(
            {"features": values, "reference": float(bars.close.iloc[-1]), "date": str(day)}
        ),
        "source_vintage": bars.attrs,
        "status": "EXPERIMENTAL_UNCALIBRATED",
        "auto_trade": False,
    }
    return append(s, key, "PREDICTION", market, payload)


def review(
    s: Session, prediction: Record, bars: pd.DataFrame, now: datetime | None = None
) -> list[Record]:
    now = require_aware(now or utc_now())
    p = prediction.payload
    start = date.fromisoformat(p["feature_date"])
    created = datetime.fromisoformat(p["generated_at"])
    out = []
    for step in MARKETS[prediction.market]["reviews"]:
        day = due_date(prediction.market, start, int(step))
        available = (
            datetime.combine(day + timedelta(days=1), datetime.min.time(), UTC)
            if prediction.market == "BTC"
            else get_calendar("XNYS").session_close(day)
        )
        if (
            available > now
            or available <= created
            or day not in bars.index
            or start not in bars.index
        ):
            continue
        key = f"review:{prediction.record_id}:{step}"
        if s.scalar(select(Record).where(Record.record_key == key)):
            continue
        close = float(bars.loc[day, "close"])
        signal = float(bars.loc[day].get("signal_close", close))
        actual = signal / float(bars.loc[start].get("signal_close", bars.loc[start, "close"])) - 1
        if not all(math.isfinite(v) for v in (close, signal, actual)):
            continue
        final = step == MARKETS[prediction.market]["horizon"]
        payload = {
            "prediction_id": prediction.record_id,
            "step": step,
            "target_date": str(day),
            "due_at": available.isoformat(),
            "observed_at": now.isoformat(),
            "close": close,
            "actual_return": actual,
            "final": final,
            "hit": bool((p["p_up"] >= 0.5) == (actual > 0)) if final else None,
            "costs": "NOT_MODELED",
            "paper_return": None,
            "note": "Forecast direction only; not a trade or investable portfolio",
        }
        out.append(append(s, key, "OUTCOME" if final else "REVIEW", prediction.market, payload))
    return out


def dashboard(s: Session) -> dict[str, Any]:
    from pitquant.forward.paper import statistics

    markets = []
    outcomes = records(s, "OUTCOME")
    predictions = records(s, "PREDICTION")
    for market in MARKETS:
        models = records(s, "MODEL", market)
        for m in models:
            pp = [r for r in predictions if r.payload["model_id"] == m.record_id]
            ids = {r.record_id for r in pp}
            oo = [r for r in outcomes if r.payload["prediction_id"] in ids]
            by_id = {r.record_id: r.payload for r in pp}
            brier, logs, hits, always, momentum = [], [], [], [], []
            for r in oo:
                p, y = by_id[r.payload["prediction_id"]], float(r.payload["actual_return"] > 0)
                prob = min(1 - 1e-12, max(1e-12, p["p_up"]))
                brier.append((prob - y) ** 2)
                logs.append(-(y * math.log(prob) + (1 - y) * math.log1p(-prob)))
                hits.append(r.payload["hit"])
                always.append(y)
                momentum.append(bool(p["momentum_up"] == bool(y)))
            nonoverlap = 0
            last_end: dict[str, str] = {}
            for pred in sorted(pp, key=lambda row: row.payload["feature_date"]):
                v = pred.payload
                if v["ticker"] not in last_end or v["feature_date"] >= last_end[v["ticker"]]:
                    nonoverlap += 1
                    last_end[v["ticker"]] = v["target_date"]
            markets.append(
                {
                    "market": market,
                    "model_id": m.record_id,
                    "model": m.payload,
                    "n": len(pp),
                    "mature": len(oo),
                    "nonoverlap_n": nonoverlap,
                    "abstentions": 0,
                    "paper": statistics(s, m.record_id),
                    "pending": len(pp) - len(oo),
                    "hits": sum(hits),
                    "failures": len(hits) - sum(hits),
                    "accuracy": float(np.mean(hits)) if hits else None,
                    "brier": float(np.mean(brier)) if brier else None,
                    "logloss": float(np.mean(logs)) if logs else None,
                    "always_up_accuracy": float(np.mean(always)) if always else None,
                    "momentum_accuracy": float(np.mean(momentum)) if momentum else None,
                }
            )
    comparisons = []
    outcome_by_pred = {r.payload["prediction_id"]: r.payload for r in outcomes}
    for market in MARKETS:
        models = records(s, "MODEL", market)
        baseline = next((m for m in models if m.payload["baseline"]), None)
        if baseline is None:
            continue
        base_predictions = {
            (p.payload["ticker"], p.payload["feature_date"]): p
            for p in predictions
            if p.payload["model_id"] == baseline.record_id
        }
        for candidate in (m for m in models if not m.payload["baseline"]):
            paired = []
            for pred in predictions:
                if pred.payload["model_id"] != candidate.record_id:
                    continue
                identity = (pred.payload["ticker"], pred.payload["feature_date"])
                ref = base_predictions.get(identity)
                if ref and ref.record_id in outcome_by_pred and pred.record_id in outcome_by_pred:
                    a, b = outcome_by_pred[ref.record_id], outcome_by_pred[pred.record_id]
                    if (
                        a["target_date"] != b["target_date"]
                        or a["actual_return"] != b["actual_return"]
                    ):
                        continue  # no comparison of different vintages/outcomes
                    paired.append((ref, pred, a))
            comparisons.append(
                {
                    "market": market,
                    "baseline_id": baseline.record_id,
                    "candidate_id": candidate.record_id,
                    "version": candidate.payload["version"],
                    "matched_mature_n": len(paired),
                    "baseline_accuracy": float(
                        np.mean(
                            [
                                (a.payload["p_up"] >= 0.5) == (o["actual_return"] > 0)
                                for a, _, o in paired
                            ]
                        )
                    )
                    if paired
                    else None,
                    "candidate_accuracy": float(
                        np.mean(
                            [
                                (b.payload["p_up"] >= 0.5) == (o["actual_return"] > 0)
                                for _, b, o in paired
                            ]
                        )
                    )
                    if paired
                    else None,
                    "auto_promotion": False,
                }
            )
    replay_latest = {}
    for r in records(s, "REPLAY"):
        replay_latest[(r.market, r.payload["window_months"])] = {"market": r.market, **r.payload}
    return {
        "version": VERSION,
        "markets": markets,
        "comparisons": comparisons,
        "predictions": [
            {
                "id": r.record_id,
                "market": r.market,
                **r.payload,
                "issued_at": r.created_at.isoformat(),
            }
            for r in reversed(predictions[-200:])
        ],
        "reviews": [r.payload for r in records(s, "REVIEW")[-200:]],
        "outcomes": [r.payload for r in outcomes[-200:]],
        "gaps": [{"market": r.market, **r.payload} for r in records(s, "GAP")[-100:]],
        "replays": list(replay_latest.values()),
        "simulations": [{"id": r.record_id, **r.payload} for r in records(s, "SIMULATION_LINK")],
        "auto_orders": False,
        "costs": "NOT_MODELED",
    }
