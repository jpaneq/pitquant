"""Incremental public BTC archiver and real API-derived readiness matrix."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from datetime import timedelta
from functools import partial
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.btc.contracts import Cohort, decision_time
from pitquant.btc.models import BTCResearchRecord
from pitquant.btc.providers import (
    DERIVATIVE_ENDPOINTS,
    NETWORK_CANDIDATES,
    FetchResult,
    PublicProvider,
)
from pitquant.btc.research import freeze, pin_config, readiness, record
from pitquant.btc.simulation import update
from pitquant.core.timeutils import utc_now
from pitquant.data.archive import ArchiveStore
from pitquant.db.models import Simulation


def collect(session: Session, store: ArchiveStore, *, discover: bool = False) -> dict[str, Any]:
    pin_config(session)  # protocol and holdout pinned BEFORE collection/evaluation
    provider = PublicProvider(session, store)
    reports = {}
    calls: list[tuple[str, Callable[[], FetchResult]]] = [
        ("spot", lambda: provider.spot()),
        ("funding", lambda: provider.funding()),
    ]
    if discover:
        calls += [
            ("spot_earliest_probe", lambda: provider.spot(earliest=True)),
            ("funding_earliest_probe", lambda: provider.funding(earliest=True)),
        ]
    calls += [(metric, partial(provider.derivatives, metric)) for metric in DERIVATIVE_ENDPOINTS]
    for name, call in calls:
        try:
            reports[name] = asdict(call())
        except Exception as exc:
            reports[name] = asdict(FetchResult("OFFICIAL_PUBLIC_ENDPOINT", "UNAVAILABLE", str(exc)))
        session.commit()  # retain successful originals even if another provider fails
    try:
        catalog, response = provider.catalog()
        reports["catalog"] = asdict(response)
        record(
            session,
            "CATALOG_SNAPSHOT",
            Cohort.FORWARD_PAPER,
            {"metrics": catalog, "raw_hash": response.raw_hash},
        )
        session.commit()
        for metric in NETWORK_CANDIDATES:
            try:
                reports[metric] = asdict(provider.network(metric, catalog))
            except Exception as exc:
                reports[metric] = asdict(
                    FetchResult("COIN_METRICS_COMMUNITY", "UNAVAILABLE", str(exc))
                )
            session.commit()
    except Exception as exc:
        reports["catalog"] = asdict(FetchResult("COIN_METRICS_COMMUNITY", "UNAVAILABLE", str(exc)))
    now = utc_now()
    report = {
        "collected_at": now.isoformat(),
        "sources": reports,
        "historical_pit": "BLOCKED: collection today is not proof of historical PIT availability",
        "retention_limited": list(DERIVATIVE_ENDPOINTS),
        "binance_symbol": "BTCUSDT",
        "quote_currency": "USDT_NOT_USD",
        "network_units": "CATALOG_METRIC_NATIVE_UNITS",
    }
    record(session, "COLLECTION", Cohort.FORWARD_PAPER, report)
    session.commit()
    return report


def activate_forward(session: Session) -> BTCResearchRecord:
    existing = session.scalars(
        select(BTCResearchRecord).where(BTCResearchRecord.kind == "FORWARD_ACTIVATION")
    ).first()
    return existing or record(
        session,
        "FORWARD_ACTIVATION",
        Cohort.FORWARD_PAPER,
        {
            "activated_at": utc_now().isoformat(),
            "frequency": "1D_UTC",
            "mode": "BTC_FORWARD_PAPER",
            "auto_trade": "NO_AUTO_PREDICTION_TRADE",
        },
    )


def forward_cycle(session: Session) -> dict[str, Any]:
    activation = session.scalars(
        select(BTCResearchRecord).where(BTCResearchRecord.kind == "FORWARD_ACTIVATION")
    ).first()
    if not activation:
        return {"status": "NOT_ACTIVATED"}
    now = utc_now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    frozen = None
    # Operational cutoff includes provider latency, never candles after the canonical close.
    if now <= midnight + timedelta(minutes=15):
        frozen = freeze(session, decision_time(midnight), Cohort.FORWARD_PAPER, now)
    updated = []
    for sim in session.scalars(select(Simulation).where(Simulation.asset_type == "BTC")):
        if (sim.source_provenance or {}).get("cohort") == Cohort.FORWARD_PAPER:
            updated.append(update(session, sim.simulation_id, now))
    session.commit()
    return {
        "snapshot_id": frozen.snapshot_id if frozen else None,
        "simulations": updated,
        "prediction_trade": "NO_AUTO_PREDICTION_TRADE",
    }


def baseline_experiment(session: Session) -> dict[str, Any]:
    status = readiness(session, Cohort.HISTORICAL_OOS)
    # No fallback to market history downloaded today: availability is a scientific gate.
    if status["status"] != "READY":
        return {"experiment": "BTC_CORE_BASELINE_V0", **status, "trained": False}
    raise ValueError(
        "VALIDATED_MODEL_ARTIFACT_REQUIRED: use the versioned offline experiment harness"
    )
