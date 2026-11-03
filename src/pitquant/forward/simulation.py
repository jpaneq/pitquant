"""Explicit manual bridge to the existing simulation engines; no pilot trade engine."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.btc.contracts import (
    DATA_VERSION,
    ENGINE_VERSION,
    STRATEGY_VERSION,
    Cohort,
    prediction_contract,
)
from pitquant.btc.features import feature_payload
from pitquant.btc.models import BTCFeatureSnapshot, BTCPredictionSnapshot
from pitquant.btc.research import commit_sha
from pitquant.config.settings import Settings
from pitquant.core.timeutils import utc_now
from pitquant.db.models_forward import ForwardPilotRecord as Record
from pitquant.forward.engine import VERSION, append, digest
from pitquant.positions.universe_ingest import find_security


def create(s: Session, cfg: Settings, prediction_id: str, notional: float) -> dict[str, Any]:
    if notional <= 0:
        raise ValueError("POSITIVE_NOTIONAL_REQUIRED")
    p = s.get(Record, prediction_id)
    if p is None or p.kind != "PREDICTION" or p.payload_hash != digest(p.payload):
        raise ValueError("VALID_FROZEN_PREDICTION_REQUIRED")
    old = s.scalar(select(Record).where(Record.record_key == f"simulation:{prediction_id}"))
    if old:
        return old.payload
    now = utc_now()
    if now >= datetime.fromisoformat(p.payload["due_at"]):
        raise ValueError("PREDICTION_ALREADY_MATURE")
    frozen = {
        "prediction_id": p.record_id,
        "prediction_hash": p.payload_hash,
        "model_id": p.payload["model_id"],
        "model_hash": p.payload["model_hash"],
        "payload": p.payload,
    }
    if p.market == "EQUITY":
        from pitquant.simulation.service import create_simulation

        sid = find_security(s, p.payload["ticker"])
        if sid is None:
            raise ValueError("SECURITY_NOT_RESOLVED")
        sim = create_simulation(
            s,
            cfg,
            sid,
            horizon_sessions=20,
            sizing_mode="FIXED_NOTIONAL",
            notional=notional,
            forward_prediction=frozen,
        )
    else:
        from pitquant.btc.simulation import create as create_btc

        at = now.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=UTC)
        features = feature_payload(s, at, Cohort.FORWARD_PAPER, now, allow_delayed_knowledge=True)
        features.update(generated_at=now.isoformat(), snapshot_mode="MANUAL_FORWARD_PILOT")
        version = VERSION + ":" + p.payload["version"]
        snap = s.scalar(
            select(BTCFeatureSnapshot).where(
                BTCFeatureSnapshot.decision_at == at,
                BTCFeatureSnapshot.feature_version == version,
                BTCFeatureSnapshot.cohort == Cohort.FORWARD_PAPER,
            )
        )
        if snap is None:
            snap = BTCFeatureSnapshot(
                decision_at=at,
                cohort=Cohort.FORWARD_PAPER,
                feature_version=version,
                data_version=DATA_VERSION,
                model_version=version,
                strategy_version=STRATEGY_VERSION,
                simulation_engine_version=ENGINE_VERSION,
                commit_sha=commit_sha(),
                payload=features,
                snapshot_hash=digest({"features": features, "prediction": frozen}),
            )
            s.add(snap)
            s.flush()
            body = {
                **prediction_contract(30),
                "status": "EXPERIMENTAL_NOT_VALIDATED",
                "p_up": p.payload["p_up"],
                "model_version": version,
                "generated_at": now.isoformat(),
                "forward_prediction": frozen,
            }
            s.add(
                BTCPredictionSnapshot(
                    snapshot_id=snap.snapshot_id,
                    horizon=30,
                    payload=body,
                    prediction_hash=digest(body),
                )
            )
            s.flush()
        sim = create_btc(s, snap, days=30, notional=notional)
    payload = {
        "simulation_id": sim.simulation_id,
        **frozen,
        "created_at": now.isoformat(),
        "notional": notional,
        "costs": "NOT_MODELED",
    }
    row = append(s, f"simulation:{prediction_id}", "SIMULATION_LINK", p.market, payload)
    s.commit()
    return row.payload
