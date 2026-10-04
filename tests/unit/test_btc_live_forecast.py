"""Quote freshness and immutable forecast-to-operation tracking (synthetic only)."""

import io
import json
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from pitquant.btc.contracts import Cohort, digest, prediction_contract
from pitquant.btc.fixtures import T0, load_synthetic_btc
from pitquant.btc.models import BTCFeatureSnapshot, BTCPredictionSnapshot, BTCResearchRecord
from pitquant.btc.quote import LiveQuote
from pitquant.btc.research import freeze
from pitquant.btc.simulation import create, prediction_tracking, update


def test_live_quote_cache_and_stale_source_fail_closed(monkeypatch):
    calls = []
    clock = [0.0]
    payload = {
        "symbol": "BTCUSDT",
        "closeTime": int(T0.timestamp() * 1000),
        "lastPrice": "100",
        "bidPrice": "99",
        "askPrice": "101",
        "priceChangePercent": "2",
    }

    def respond(*args, **kwargs):
        calls.append(1)
        return io.BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr("urllib.request.urlopen", respond)
    monkeypatch.setattr("pitquant.btc.quote.utc_now", lambda: T0)
    monkeypatch.setattr("pitquant.btc.quote.time.monotonic", lambda: clock[0])
    quote = LiveQuote()
    assert quote.get()["price"] == 100
    assert quote.get()["usage"] == "DISPLAY_ONLY_NOT_PIT"
    assert len(calls) == 1
    clock[0] = 6
    payload["closeTime"] -= 31000
    with pytest.raises(ValueError, match="STALE"):
        quote.get()


@pytest.mark.pit
def test_operation_preserves_experimental_forecast_and_waits_for_its_horizon(
    session, tmp_path: Path
):
    load_synthetic_btc(session, tmp_path)
    original = freeze(session, T0, Cohort.SYNTHETIC)
    snap = BTCFeatureSnapshot(
        decision_at=T0,
        cohort=Cohort.SYNTHETIC,
        feature_version="SYNTHETIC_FORECAST",
        data_version=original.data_version,
        model_version="SYNTHETIC_MODEL",
        strategy_version=original.strategy_version,
        simulation_engine_version=original.simulation_engine_version,
        commit_sha=original.commit_sha,
        payload=original.payload,
        snapshot_hash=digest({"synthetic": original.snapshot_hash}),
    )
    session.add(snap)
    session.flush()
    payload = {
        **prediction_contract(7),
        "status": "EXPERIMENTAL_NOT_VALIDATED",
        "model_version": "SYNTHETIC_MODEL",
        "expected_return": 0.07,
        "p_up": 0.8,
    }
    prediction = BTCPredictionSnapshot(
        snapshot_id=snap.snapshot_id, horizon=7, payload=payload, prediction_hash=digest(payload)
    )
    session.add(prediction)
    session.flush()
    sim = create(session, snap, notional=50, days=7)
    pinned = sim.source_provenance["prediction_at_creation"]
    assert sim.model_version == "SYNTHETIC_MODEL"
    assert pinned["prediction_hash"] == prediction.prediction_hash
    update(session, sim.simulation_id, T0 + timedelta(days=3))
    early = prediction_tracking(session, sim)
    assert early["plan_status"] == "TARGETS_MET"
    assert early["actual"] is None and early["forecast_correct"] is None
    update(session, sim.simulation_id, T0 + timedelta(days=7))
    tracking = prediction_tracking(session, sim)
    assert tracking["actual"] == pytest.approx(0.1)
    assert tracking["error"] == pytest.approx(-0.03)
    assert tracking["forecast_correct"] is True
    assert tracking["tp1_met"] and tracking["tp2_met"]
    assert tracking["frozen"]["prediction_hash"] == pinned["prediction_hash"]
    update(session, sim.simulation_id, T0 + timedelta(days=8))
    assert (
        len(
            session.scalars(
                select(BTCResearchRecord).where(
                    BTCResearchRecord.prediction_id == prediction.prediction_id
                )
            ).all()
        )
        == 1
    )


@pytest.mark.pit
def test_experimental_features_do_not_read_future_candles():
    import numpy as np
    import pandas as pd

    from pitquant.btc.experimental import vectors

    index = pd.date_range("2020-01-01", periods=500, tz="UTC")
    prices = 100 + np.sin(np.arange(500) / 20)
    frame = pd.DataFrame(
        {"close": prices, "high": prices + 1, "low": prices - 1, "volume": 1000 + np.arange(500)},
        index=index,
    )
    expected = vectors(frame.iloc[:401]).iloc[-1]
    frame.iloc[401:, frame.columns.get_loc("close")] = 999999
    pd.testing.assert_series_equal(vectors(frame).iloc[400], expected)
