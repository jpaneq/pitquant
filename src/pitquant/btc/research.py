"""Blind prediction freeze/reveal, temporal purging and gated baseline experiments."""

from __future__ import annotations

import math
import subprocess
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.btc.contracts import (
    DATA_VERSION,
    ENGINE_VERSION,
    FEATURE_VERSION,
    HORIZONS,
    STRATEGY_VERSION,
    Cohort,
    ResearchConfig,
    decision_time,
    digest,
    prediction_contract,
    target_time,
)
from pitquant.btc.features import feature_payload, known_data
from pitquant.btc.models import BTCFeatureSnapshot, BTCPredictionSnapshot, BTCResearchRecord
from pitquant.core.timeutils import require_aware, utc_now


def commit_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def record(
    session: Session,
    kind: str,
    cohort: str,
    payload: dict[str, Any],
    prediction_id: str | None = None,
) -> BTCResearchRecord:
    hash_ = digest(
        {"kind": kind, "cohort": cohort, "prediction_id": prediction_id, "payload": payload}
    )
    existing = session.scalar(
        select(BTCResearchRecord).where(BTCResearchRecord.record_hash == hash_)
    )
    if existing:
        return existing
    row = BTCResearchRecord(
        kind=kind, cohort=cohort, payload=payload, prediction_id=prediction_id, record_hash=hash_
    )
    session.add(row)
    session.flush()
    return row


def pin_config(session: Session, config: ResearchConfig | None = None) -> BTCResearchRecord:
    config = config or ResearchConfig()
    existing = session.scalars(
        select(BTCResearchRecord).where(BTCResearchRecord.kind == "RESEARCH_CONFIG")
    ).first()
    if existing and existing.payload != asdict(config):
        raise ValueError("research protocol already frozen; use a versioned challenger")
    return record(session, "RESEARCH_CONFIG", Cohort.HISTORICAL_OOS, asdict(config))


def guard_holdout(session: Session, at: datetime, cohort: str) -> None:
    if cohort != Cohort.HISTORICAL_OOS:
        return
    config = pin_config(session).payload
    start = datetime.fromisoformat(config["holdout_start"]).replace(tzinfo=UTC)
    # Labels may not consume any sealed date either; callers guard target boundary too.
    if at >= start:
        raise ValueError(
            "BTC_HOLDOUT_SEALED: historical experiments stop before the reserved final period"
        )


def freeze(
    session: Session, at: datetime, cohort: str, knowledge_at: datetime | None = None
) -> BTCFeatureSnapshot:
    decision_time(at)
    Cohort(cohort)
    if cohort == Cohort.FORWARD_PAPER and at > utc_now():
        raise ValueError("FUTURE_FORWARD_DECISION")
    guard_holdout(session, at, cohort)
    existing = session.scalar(
        select(BTCFeatureSnapshot).where(
            BTCFeatureSnapshot.decision_at == at,
            BTCFeatureSnapshot.cohort == cohort,
            BTCFeatureSnapshot.feature_version == FEATURE_VERSION,
        )
    )
    if existing:
        return existing  # forward snapshots are NEVER recalculated from corrected data
    payload = feature_payload(session, at, cohort, knowledge_at)
    versions = {
        "data_version": DATA_VERSION,
        "feature_version": FEATURE_VERSION,
        "model_version": None,
        "strategy_version": STRATEGY_VERSION,
        "simulation_engine_version": ENGINE_VERSION,
        "commit_sha": commit_sha(),
    }
    hash_ = digest({"cohort": cohort, "payload": payload, **versions})
    row = BTCFeatureSnapshot(
        decision_at=at, cohort=cohort, payload=payload, snapshot_hash=hash_, **versions
    )
    session.add(row)
    session.flush()
    for horizon in HORIZONS:
        contract = prediction_contract(horizon)
        contract.update(
            data_quality="READY" if payload["spot_ready"] else "BLOCKED_BY_DATA",
            versions=versions,
            snapshot_hash=hash_,
            decision_at=at.isoformat(),
        )
        prediction = BTCPredictionSnapshot(
            snapshot_id=row.snapshot_id,
            horizon=horizon,
            payload=contract,
            prediction_hash=digest({"feature_hash": hash_, "prediction": contract}),
        )
        session.add(prediction)
    session.flush()
    return row


def reveal(session: Session, prediction_id: str, now: datetime) -> BTCResearchRecord:
    require_aware(now)
    pred = session.get_one(BTCPredictionSnapshot, prediction_id)
    snap = session.get_one(BTCFeatureSnapshot, pred.snapshot_id)
    if snap.cohort == Cohort.FORWARD_PAPER and now > utc_now():
        raise ValueError("FUTURE_FORWARD_REVEAL")
    end = target_time(snap.decision_at, pred.horizon)
    if now < end:
        raise ValueError("LABEL_NOT_MATURE")
    guard_holdout(session, end, snap.cohort)
    if snap.cohort == Cohort.HISTORICAL_OOS:
        cfg = pin_config(session).payload
        ho_start = datetime.fromisoformat(cfg["holdout_start"]).replace(tzinfo=UTC)
        ho_end = datetime.fromisoformat(cfg["holdout_end"]).replace(tzinfo=UTC) + timedelta(days=1)
        if snap.decision_at < ho_end and end >= ho_start:
            raise ValueError("LABEL_OVERLAPS_BTC_HOLDOUT")
    # Outcome reads future only in phase 2; frozen prediction and T0 features are unchanged.
    rows = known_data(session, now, snap.cohort)
    exact = [r for r in rows if r.metric == "spot" and r.exchange_timestamp == end]
    price = snap.payload["price_features"].get("price")
    if not snap.payload["spot_ready"] or not price or len(exact) != 1:
        raise ValueError("EXACT_TARGET_PRICE_REQUIRED")
    simple = exact[0].payload["close"] / price - 1
    log_return = math.log1p(simple)
    expected = pred.payload.get("expected_return")
    return record(
        session,
        "REVEAL_OUTCOME",
        snap.cohort,
        {
            "prediction_hash": pred.prediction_hash,
            "horizon": pred.horizon,
            "target_at": end.isoformat(),
            "future_log_return_H": log_return,
            "future_simple_return_H": simple,
            "UP_H": int(simple > 0),
            "predicted": expected,
            "actual": simple,
            "error": None if expected is None else expected - simple,
            "target_datum_id": exact[0].datum_id,
            "raw_hash": exact[0].raw_hash,
        },
        prediction_id,
    )


def temporal_folds(
    dates: list[datetime], horizon: int, config: ResearchConfig
) -> list[dict[str, Any]]:
    if horizon not in HORIZONS:
        raise ValueError("unsupported horizon")
    if not dates:
        return []
    dates = sorted(set(dates))[:: config.decision_step_days]
    start = dates[0] + timedelta(days=config.train_days + horizon + config.embargo_days)
    stop = datetime.fromisoformat(config.holdout_start).replace(tzinfo=UTC)
    folds = []
    while start + timedelta(days=config.validation_days + horizon) <= min(dates[-1], stop):
        val_end = start + timedelta(days=config.validation_days)
        train = [
            d
            for d in dates
            if start - timedelta(days=config.train_days + horizon + config.embargo_days) <= d
            and d + timedelta(days=horizon + config.embargo_days) < start
        ]
        validation = [
            d for d in dates if start <= d < val_end and d + timedelta(days=horizon) < stop
        ]
        if len(train) >= math.ceil(config.train_days / config.decision_step_days) and len(
            validation
        ) >= math.ceil(config.validation_days / config.decision_step_days):
            folds.append(
                {
                    "train": train,
                    "validation": validation,
                    "nonoverlap_cohorts": len(
                        validation[:: max(1, math.ceil(horizon / config.decision_step_days))]
                    ),
                    "raw_n": len(validation),
                    "effective_n_claimed": False,
                }
            )
        start = val_end + timedelta(days=horizon + config.embargo_days)
    return folds


def calibration(predictions: list[dict[str, float]]) -> list[dict[str, Any]]:
    result = []
    for lo, hi in (
        (0.50, 0.55),
        (0.55, 0.60),
        (0.60, 0.65),
        (0.65, 0.70),
        (0.70, 0.75),
        (0.75, 1.01),
    ):
        group = [p for p in predictions if lo <= p["p_up"] < hi]
        result.append(
            {
                "lower": lo,
                "upper": min(hi, 1),
                "n": len(group),
                "predicted": float(np.mean([p["p_up"] for p in group])) if group else None,
                "actual": float(np.mean([p["up"] for p in group])) if group else None,
            }
        )
    return result


def baseline_fit(
    x_train: np.ndarray, log_returns: np.ndarray, up: np.ndarray, x_validation: np.ndarray
) -> dict[str, Any]:
    """Training-only imputation/scaling; never fits on validation. Separate models per horizon."""
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import ElasticNet, LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    reg = make_pipeline(
        SimpleImputer(keep_empty_features=True),
        StandardScaler(),
        ElasticNet(alpha=0.01, l1_ratio=0.5, random_state=0),
    )
    cls = make_pipeline(
        SimpleImputer(keep_empty_features=True),
        StandardScaler(),
        LogisticRegression(random_state=0, max_iter=2000),
    )
    if len(set(up.tolist())) != 2:
        raise ValueError("training classification needs both outcomes")
    reg.fit(x_train, log_returns)
    cls.fit(x_train, up)
    return {
        "expected_log_return": reg.predict(x_validation).tolist(),
        "p_up": cls.predict_proba(x_validation)[:, 1].tolist(),
        "quantiles": None,
        "status": "EXPERIMENTAL_OOS_NOT_PROMOTED",
    }


def readiness(session: Session, cohort: str) -> dict[str, Any]:
    snaps = list(
        session.scalars(select(BTCFeatureSnapshot).where(BTCFeatureSnapshot.cohort == cohort))
    )
    usable = sorted(s.decision_at for s in snaps if s.payload["spot_ready"])
    config = ResearchConfig(**pin_config(session).payload)
    gates = {}
    for horizon in HORIZONS:
        folds = temporal_folds(usable, horizon, config)
        gates[f"BTC_{horizon}D_HISTORY_READY"] = bool(folds) and cohort == Cohort.HISTORICAL_OOS
    return {
        "status": "READY" if any(gates.values()) else "BLOCKED_BY_DATA",
        "gates": gates,
        "earliest_usable": usable[0].isoformat() if usable else None,
        "latest_usable": usable[-1].isoformat() if usable else None,
        "usable_frozen_snapshots": len(usable),
        "holdout": asdict(config),
        "blockers": []
        if any(gates.values())
        else ["NO_SUFFICIENT_HISTORICAL_PIT_SNAPSHOTS_BEFORE_FROZEN_HOLDOUT"],
        "derivatives_history_ready": False,
        "champion": None,
    }


def historical_test(
    session: Session,
    start: datetime,
    end: datetime,
    horizon: int,
    feature_version: str = FEATURE_VERSION,
    model_version: str = "btc-core-baseline-v0",
    strategy_version: str = STRATEGY_VERSION,
) -> dict[str, Any]:
    """Two-phase OOS harness. Features -> pinned model prediction -> future reveal -> metrics."""
    if start > end or horizon not in HORIZONS:
        raise ValueError("valid start/end/horizon required")
    config = ResearchConfig(**pin_config(session).payload)
    if (feature_version, model_version, strategy_version) != (
        config.feature_version,
        config.model_version,
        config.strategy_version,
    ):
        raise ValueError("versions differ from frozen research protocol")
    ho_start = datetime.fromisoformat(config.holdout_start).replace(tzinfo=UTC)
    if end + timedelta(days=horizon) >= ho_start:
        raise ValueError("BTC_HOLDOUT_SEALED: experiment must finish labels before holdout")
    snaps = {
        s.decision_at: s
        for s in session.scalars(
            select(BTCFeatureSnapshot).where(
                BTCFeatureSnapshot.cohort == Cohort.HISTORICAL_OOS,
                BTCFeatureSnapshot.decision_at >= start,
                BTCFeatureSnapshot.decision_at <= end,
                BTCFeatureSnapshot.feature_version == feature_version,
            )
        )
        if s.payload["spot_ready"]
    }
    folds = temporal_folds(list(snaps), horizon, config)
    if not folds:
        result: dict[str, Any] = {
            "status": "BLOCKED_BY_DATA",
            "trained": False,
            "blockers": ["NO_COMPLETE_PURGED_PIT_WALK_FORWARD_FOLD"],
            "horizon": horizon,
            "feature_version": feature_version,
            "model_version": model_version,
            "strategy_version": strategy_version,
            "config_hash": config.config_hash,
        }
        record(session, "HISTORICAL_TEST", Cohort.HISTORICAL_OOS, result)
        return result
    families = (
        "price_features",
        "momentum_features",
        "trend_features",
        "volatility_features",
        "volume_features",
        "network_features",
    )
    keys = sorted(
        (family, key) for family in families for key in next(iter(snaps.values())).payload[family]
    )

    def vector(snapshot: BTCFeatureSnapshot) -> list[float]:
        return [
            float(snapshot.payload[f][k])
            if snapshot.payload[f].get(k) is not None
            else float("nan")
            for f, k in keys
        ]

    scored: list[dict[str, Any]] = []
    for fold_number, fold in enumerate(folds):
        cutoff = min(fold["validation"])
        known = known_data(session, cutoff, Cohort.HISTORICAL_OOS)
        price_by_time = {
            r.exchange_timestamp: r.payload["close"] for r in known if r.metric == "spot"
        }
        train = [t for t in fold["train"] if target_time(t, horizon) in price_by_time]
        if len(train) != len(fold["train"]):
            raise ValueError("TRAINING_LABEL_NOT_AVAILABLE_BEFORE_VALIDATION")
        returns = np.array(
            [
                math.log(
                    price_by_time[target_time(t, horizon)]
                    / snaps[t].payload["price_features"]["price"]
                )
                for t in train
            ]
        )
        result = baseline_fit(
            np.array([vector(snaps[t]) for t in train]),
            returns,
            (returns > 0).astype(int),
            np.array([vector(snaps[t]) for t in fold["validation"]]),
        )
        for i, t in enumerate(fold["validation"]):
            pred = session.scalar(
                select(BTCPredictionSnapshot).where(
                    BTCPredictionSnapshot.snapshot_id == snaps[t].snapshot_id,
                    BTCPredictionSnapshot.horizon == horizon,
                )
            )
            assert pred is not None
            payload: dict[str, Any] = {
                "decision_at": t.isoformat(),
                "feature_hash": snaps[t].snapshot_hash,
                "config_hash": config.config_hash,
                "model_version": model_version,
                "fold": fold_number,
                "expected_log_return": result["expected_log_return"][i],
                "expected_return": math.expm1(result["expected_log_return"][i]),
                "return_transform": "EXP_OF_POINT_LOG_FORECAST_NOT_MEAN_SIMPLE_RETURN",
                "p_up": result["p_up"][i],
                "quantiles": None,
                "status": "EXPERIMENTAL_OOS_NOT_PROMOTED",
            }
            prediction = record(
                session, "OOS_MODEL_PREDICTION", Cohort.HISTORICAL_OOS, payload, pred.prediction_id
            )
            session.commit()  # durable phase 1 barrier BEFORE phase 2 can read the future
            outcome = reveal(session, pred.prediction_id, target_time(t, horizon))
            scored.append(
                {
                    "p_up": payload["p_up"],
                    "up": outcome.payload["UP_H"],
                    "actual": outcome.payload["future_simple_return_H"],
                    "expected": payload["expected_return"],
                    "prediction_hash": prediction.record_hash,
                }
            )
    result = {
        "status": "EXPERIMENTAL_OOS_NOT_PROMOTED",
        "trained": True,
        "horizon": horizon,
        "n_raw": len(scored),
        "effective_n_claimed": False,
        "nonoverlap_cohorts": sum(f["nonoverlap_cohorts"] for f in folds),
        "calibration": calibration(scored),
        "predictions": scored,
        "mean_absolute_error": float(np.mean([abs(p["expected"] - p["actual"]) for p in scored])),
        "buy_and_hold": "REALIZED_BTC_RETURN_PER_MATCHING_HORIZON",
        "strategy_superiority": "NOT_CLAIMED",
        "config_hash": config.config_hash,
    }
    record(session, "BASELINE_EXPERIMENT", Cohort.HISTORICAL_OOS, result)
    return result
