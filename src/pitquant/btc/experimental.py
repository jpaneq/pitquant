"""User-requested price baseline: retrospective market research vs real forward forecasts.

Retrospective candles retrieved today are NOT historical PIT evidence. Existing historical
readiness gates and champion remain untouched. Inputs/cutoffs/models/outcomes are pinned.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.btc.contracts import (
    DATA_VERSION,
    ENGINE_VERSION,
    HORIZONS,
    STRATEGY_VERSION,
    Cohort,
    ResearchConfig,
    digest,
    prediction_contract,
)
from pitquant.btc.features import feature_payload
from pitquant.btc.models import (
    BTCDatum,
    BTCFeatureSnapshot,
    BTCPredictionSnapshot,
    BTCResearchRecord,
)
from pitquant.btc.research import (
    baseline_models,
    calibration,
    commit_sha,
    pin_config,
    record,
    temporal_folds,
)
from pitquant.core.timeutils import utc_now

VERSION = "btc-price-experimental-v1"
MODEL_VERSION = "btc-elastic-logistic-experimental-v1"


def price_frame(session: Session, now: datetime) -> tuple[pd.DataFrame, str]:
    versions: dict[datetime, BTCDatum] = {}
    for r in session.scalars(
        select(BTCDatum)
        .where(
            BTCDatum.source == "BINANCE_SPOT",
            BTCDatum.metric == "spot",
            BTCDatum.cohort == Cohort.FORWARD_PAPER,
            BTCDatum.exchange_timestamp <= now,
            BTCDatum.available_at <= now,
        )
        .order_by(BTCDatum.available_at, BTCDatum.datum_id)
    ):
        versions[r.exchange_timestamp] = r
    rows = [versions[t] for t in sorted(versions)]
    frame = pd.DataFrame(
        [r.payload for r in rows], index=pd.DatetimeIndex([r.exchange_timestamp for r in rows])
    )
    if frame.empty:
        raise ValueError("PRICE_HISTORY_REQUIRED")
    # Missing calendar days remain NaN; no OHLC/volume imputation or fabricated continuity.
    frame = frame.reindex(pd.date_range(frame.index.min(), frame.index.max(), freq="D"))
    return frame, digest([r.datum_id for r in rows])


def vectors(frame: pd.DataFrame) -> pd.DataFrame:
    c = frame["close"]
    ret = np.log(c / c.shift(1))
    x = pd.DataFrame(index=frame.index)
    for n in (1, 3, 7, 14, 30, 90, 180, 365):
        x[f"log_return_{n}d"] = np.log(c / c.shift(n))
    for n in (20, 50, 200):
        x[f"distance_sma{n}"] = c / c.rolling(n).mean() - 1
    for n in (7, 30, 90):
        x[f"vol_{n}d"] = ret.rolling(n).std() * math.sqrt(365)
    tr = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - c.shift()).abs(),
            (frame["low"] - c.shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    x["atr_ratio"] = tr.rolling(14).mean() / c
    v = frame["volume"]
    x["volume_z30"] = (v - v.rolling(30).mean()) / v.rolling(30).std().replace(0, np.nan)
    # Full one-year OHLC continuity is required, independently of model imputation.
    x = x.where(c.rolling(366).count().eq(366), np.nan)
    return x


def _parameters(pipeline: Any) -> dict[str, Any]:
    imputer, scaler, estimator = pipeline.steps[0][1], pipeline.steps[1][1], pipeline.steps[2][1]
    return {
        "imputer": imputer.statistics_.tolist(),
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "coef": np.asarray(estimator.coef_).reshape(-1).tolist(),
        "intercept": float(np.asarray(estimator.intercept_).reshape(-1)[0]),
    }


def score(params: dict[str, Any], x: np.ndarray) -> float:
    values = np.where(np.isnan(x), np.asarray(params["imputer"]), x)
    z = (values - np.asarray(params["mean"])) / np.asarray(params["scale"])
    return float(z @ np.asarray(params["coef"]) + params["intercept"])


def build_models(session: Session) -> list[dict[str, Any]]:
    cfg = ResearchConfig(**pin_config(session).payload)
    # Freeze research parameters BEFORE fitting or seeing validation metrics.
    protocol = record(
        session,
        "PRICE_BASELINE_PROTOCOL",
        "RETROSPECTIVE",
        {
            "version": MODEL_VERSION,
            "feature_version": VERSION,
            "research_config": asdict(cfg),
            "implementation_hash": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "regression": "ElasticNet(alpha=.01,l1_ratio=.5)",
            "classification": "LogisticRegression",
            "claim": "RETROSPECTIVE_NOT_HISTORICAL_PIT",
        },
    )
    session.commit()
    frame, data_hash = price_frame(session, utc_now())
    ho = datetime.fromisoformat(cfg.holdout_start).replace(tzinfo=UTC)
    # Exclude holdout prices BEFORE computing any historical training/validation labels.
    training_frame = frame.loc[frame.index < ho]
    x = vectors(training_frame)
    complete = x["log_return_365d"].notna()
    result = []
    for horizon in HORIZONS:
        labels = np.log(training_frame["close"].shift(-horizon) / training_frame["close"])
        usable = x.index[complete & labels.notna()]
        folds = temporal_folds([t.to_pydatetime() for t in usable], horizon, cfg)
        if not folds:
            result.append({"horizon": horizon, "status": "BLOCKED_BY_DATA"})
            continue
        oos = []
        for fold in folds:
            train, val = fold["train"], fold["validation"]
            y = labels.loc[train].to_numpy()
            reg, cls = baseline_models(x.loc[train].to_numpy(), y, (y > 0).astype(int))
            predicted, probs = (
                reg.predict(x.loc[val].to_numpy()),
                cls.predict_proba(x.loc[val].to_numpy())[:, 1],
            )
            # Store predictions as phase1 before adding outcomes to the retrospective record.
            frozen = record(
                session,
                "PRICE_OOS_PREDICTIONS",
                "RETROSPECTIVE",
                {
                    "horizon": horizon,
                    "protocol_hash": protocol.record_hash,
                    "validation": [t.isoformat() for t in val],
                    "expected_log_return": predicted.tolist(),
                    "p_up": probs.tolist(),
                    "data_hash": data_hash,
                },
            )
            session.commit()
            for i, t in enumerate(val):
                actual = math.expm1(float(labels.loc[t]))
                expected = math.expm1(float(predicted[i]))
                oos.append(
                    {
                        "decision_at": t.isoformat(),
                        "p_up": float(probs[i]),
                        "up": int(actual > 0),
                        "actual": actual,
                        "expected": expected,
                        "error": expected - actual,
                        "prediction_hash": frozen.record_hash,
                    }
                )
        train_dates = usable[-cfg.train_days :]
        if len(train_dates) < cfg.train_days:
            raise ValueError("INSUFFICIENT_FINAL_TRAINING_WINDOW")
        y = labels.loc[train_dates].to_numpy()
        reg, cls = baseline_models(x.loc[train_dates].to_numpy(), y, (y > 0).astype(int))
        payload = {
            "status": "EXPERIMENTAL_NOT_VALIDATED",
            "model_version": MODEL_VERSION,
            "feature_version": VERSION,
            "horizon": horizon,
            "features": list(x.columns),
            "reg": _parameters(reg),
            "cls": _parameters(cls),
            "train_start": train_dates[0].isoformat(),
            "train_end": train_dates[-1].isoformat(),
            "last_training_label": (train_dates[-1] + timedelta(days=horizon)).isoformat(),
            "holdout_start": cfg.holdout_start,
            "protocol_hash": protocol.record_hash,
            "data_hash": data_hash,
            "commit_sha": commit_sha(),
            "oos": oos,
            "calibration": calibration(oos),
            "n_raw": len(oos),
            "nonoverlap_cohorts": sum(f["nonoverlap_cohorts"] for f in folds),
            "always_up_hit_rate": float(np.mean([p["up"] for p in oos])),
            "brier_score": float(np.mean([(p["p_up"] - p["up"]) ** 2 for p in oos])),
            "effective_n_claimed": False,
            "mae": float(np.mean([abs(p["error"]) for p in oos])),
            "direction_hit_rate": float(
                np.mean([(p["p_up"] >= 0.5) == bool(p["up"]) for p in oos])
            ),
            "historical_pit": False,
            "champion": False,
        }
        model = record(session, "PRICE_BASELINE_MODEL", "RETROSPECTIVE", payload)
        session.commit()
        result.append({"record_id": model.record_id, **payload})
    return result


def latest_models(session: Session) -> dict[int, BTCResearchRecord]:
    models = {}
    for r in session.scalars(
        select(BTCResearchRecord)
        .where(BTCResearchRecord.kind == "PRICE_BASELINE_MODEL")
        .order_by(BTCResearchRecord.created_at)
    ):
        if r.payload.get("model_version") == MODEL_VERSION:
            models[r.payload["horizon"]] = r
    return models


def forecast(session: Session) -> BTCFeatureSnapshot:
    now = utc_now()
    frame, _ = price_frame(session, now)
    cutoff = frame.index[-1].to_pydatetime()
    if cutoff != now.replace(hour=0, minute=0, second=0, microsecond=0):
        raise ValueError("CURRENT_COMPLETED_DAILY_BAR_REQUIRED")
    existing = session.scalar(
        select(BTCFeatureSnapshot).where(
            BTCFeatureSnapshot.decision_at == cutoff,
            BTCFeatureSnapshot.feature_version == VERSION,
            BTCFeatureSnapshot.cohort == Cohort.FORWARD_PAPER,
        )
    )
    if existing:
        return existing
    models = latest_models(session)
    if set(models) != set(HORIZONS):
        raise ValueError("EXPERIMENTAL_MODELS_NOT_BUILT")
    x = vectors(frame).iloc[-1]
    if pd.isna(x["log_return_365d"]):
        raise ValueError("CONTINUOUS_PRICE_HISTORY_REQUIRED")
    payload = feature_payload(
        session, cutoff, Cohort.FORWARD_PAPER, now, allow_delayed_knowledge=True
    )
    payload.update(
        generated_at=now.isoformat(),
        snapshot_mode="MANUAL_FORWARD_1D",
        historical_pit=False,
        model_features={k: None if pd.isna(v) else float(v) for k, v in x.items()},
    )
    versions = {
        "data_version": DATA_VERSION,
        "feature_version": VERSION,
        "model_version": MODEL_VERSION,
        "strategy_version": STRATEGY_VERSION,
        "simulation_engine_version": ENGINE_VERSION,
        "commit_sha": commit_sha(),
    }
    snap = BTCFeatureSnapshot(
        decision_at=cutoff,
        cohort=Cohort.FORWARD_PAPER,
        payload=payload,
        snapshot_hash=digest({"payload": payload, "versions": versions}),
        **versions,
    )
    session.add(snap)
    session.flush()
    for horizon in HORIZONS:
        model = models[horizon]
        values = x[model.payload["features"]].to_numpy(dtype=float)
        log_return = score(model.payload["reg"], values)
        logit = score(model.payload["cls"], values)
        p_up = float(1 / (1 + np.exp(-np.clip(logit, -500, 500))))
        contract = {
            **prediction_contract(horizon),
            "status": "EXPERIMENTAL_NOT_VALIDATED",
            "model_version": MODEL_VERSION,
            "model_record_id": model.record_id,
            "model_hash": model.record_hash,
            "expected_return": math.expm1(log_return),
            "expected_log_return": log_return,
            "return_transform": "EXP_OF_POINT_LOG_FORECAST",
            "p_up": p_up,
            "target_price": float(frame.iloc[-1]["close"]) * math.exp(log_return),
            "reference_price": float(frame.iloc[-1]["close"]),
            "reference_at": cutoff.isoformat(),
            "generated_at": now.isoformat(),
            "target_at": (cutoff + timedelta(days=horizon)).isoformat(),
            "data_quality": "PRICE_ONLY_RETROSPECTIVE_MODEL",
            "snapshot_hash": snap.snapshot_hash,
        }
        session.add(
            BTCPredictionSnapshot(
                snapshot_id=snap.snapshot_id,
                horizon=horizon,
                payload=contract,
                prediction_hash=digest(contract),
            )
        )
    session.flush()
    return snap
