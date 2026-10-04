"""BTC synthetic scientific harness: UTC, provenance, freeze/reveal and engine compatibility."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.btc.contracts import Cohort, ResearchConfig, decision_time, digest
from pitquant.btc.features import feature_payload
from pitquant.btc.fixtures import T0, load_synthetic_btc
from pitquant.btc.models import BTCDatum, BTCPredictionSnapshot
from pitquant.btc.research import freeze, pin_config, readiness, reveal, temporal_folds
from pitquant.btc.simulation import BTCSimulationEngine, create, postmortem, update
from pitquant.core.errors import ImmutableRecordError
from pitquant.simulation.engine import PlanLevels
from pitquant.simulation.registry import SimulationEngineV1
from pitquant.simulation.service import evidence_summary, replay_simulation

pytestmark = pytest.mark.pit


@pytest.fixture
def btc(session: Session, tmp_path: Path):
    load_synthetic_btc(session, tmp_path)
    return session


def test_utc_is_required_and_daily_boundary_is_canonical():
    with pytest.raises(ValueError):
        decision_time(T0 + timedelta(hours=1))
    assert decision_time(T0) == T0


def test_future_candle_and_null_missing_features(btc):
    f = feature_payload(btc, T0, Cohort.SYNTHETIC)
    assert f["price_features"]["price"] == 100
    assert f["derivatives_features"]["open_interest"] is None
    assert f["price_features"]["drawdown_from_ATH"] is None
    assert f["availability"]["open_interest"] == "SOURCE_RETENTION_LIMIT"
    assert f["momentum_features"]["log_return_365d"] == 0
    assert all(datetime.fromisoformat(p["exchange_timestamp"]) <= T0 for p in f["provenance"])


@pytest.mark.parametrize("metric", ["funding_rate", "active_addresses"])
def test_future_auxiliary_data_is_unavailable(btc, metric):
    original = btc.scalar(select(BTCDatum))
    btc.add(
        BTCDatum(
            source="SYNTHETIC",
            metric=metric,
            cohort=Cohort.SYNTHETIC,
            exchange_timestamp=T0 + timedelta(days=1),
            available_at=T0,
            retrieved_at=T0,
            payload={"value": 123.0},
            raw_hash=original.raw_hash,
            archive_id=original.archive_id,
            value_hash=digest(metric),
        )
    )
    btc.flush()
    f = feature_payload(btc, T0, Cohort.SYNTHETIC)
    assert f["derivatives_features"]["funding_rate_current"] is None
    assert f["network_features"]["active_addresses"] is None


def test_prediction_immutable_and_label_inaccessible_until_mature(btc):
    snapshot = freeze(btc, T0, Cohort.SYNTHETIC)
    prediction = btc.scalar(select(BTCPredictionSnapshot).where(BTCPredictionSnapshot.horizon == 7))
    assert prediction.payload["p_up"] is None
    with pytest.raises(ValueError, match="LABEL_NOT_MATURE"):
        reveal(btc, prediction.prediction_id, T0 + timedelta(days=6))
    outcome = reveal(btc, prediction.prediction_id, T0 + timedelta(days=7))
    assert outcome.payload["future_simple_return_H"] == pytest.approx(0.1)
    assert outcome.payload["UP_H"] == 1
    assert outcome.payload["error"] is None
    assert freeze(btc, T0, Cohort.SYNTHETIC).snapshot_hash == snapshot.snapshot_hash
    prediction.payload = {"p_up": 0.99}
    with pytest.raises(ImmutableRecordError):
        btc.flush()


def test_revisions_never_recalculate_forward_snapshot(btc):
    frozen = freeze(btc, T0, Cohort.SYNTHETIC)
    old_hash = frozen.snapshot_hash
    old = btc.scalar(select(BTCDatum).where(BTCDatum.exchange_timestamp == T0))
    revised = {**old.payload, "close": 900.0}
    btc.add(
        BTCDatum(
            source=old.source,
            metric="spot",
            cohort=Cohort.SYNTHETIC,
            exchange_timestamp=T0,
            available_at=T0 + timedelta(days=1),
            retrieved_at=T0 + timedelta(days=1),
            payload=revised,
            archive_id=old.archive_id,
            raw_hash=old.raw_hash,
            value_hash=digest(revised),
        )
    )
    btc.flush()
    assert freeze(btc, T0, Cohort.SYNTHETIC).snapshot_hash == old_hash
    assert feature_payload(btc, T0, Cohort.SYNTHETIC)["price_features"]["price"] == 100


def test_btc_holdout_frozen_before_any_experiment(btc):
    config = pin_config(btc)
    assert config.payload["holdout_start"] == "2025-10-01"
    with pytest.raises(ValueError, match="frozen"):
        pin_config(btc, replace(ResearchConfig(), holdout_start="2026-01-01"))
    with pytest.raises(ValueError, match="BTC_HOLDOUT_SEALED"):
        freeze(btc, datetime(2026, 1, 1, tzinfo=UTC), Cohort.HISTORICAL_OOS)
    assert readiness(btc, Cohort.HISTORICAL_OOS)["status"] == "BLOCKED_BY_DATA"


def test_walkforward_purges_365d_overlapping_labels():
    config = ResearchConfig(
        train_days=40,
        validation_days=10,
        embargo_days=5,
        holdout_start="2030-01-01",
        holdout_end="2030-12-31",
    )
    dates = [datetime(2020, 1, 1, tzinfo=UTC) + timedelta(days=n) for n in range(1000)]
    folds = temporal_folds(dates, 365, config)
    assert folds
    for fold in folds:
        assert max(fold["train"]) + timedelta(days=370) < min(fold["validation"])
        assert fold["nonoverlap_cohorts"] < fold["raw_n"]
        assert not fold["effective_n_claimed"]


def test_fractional_weekend_simulation_replay_and_explicit_postmortem(btc):
    snapshot = freeze(btc, T0, Cohort.SYNTHETIC)
    sim = create(btc, snapshot, notional=10)
    assert sim.position_size_simulated == 0.1
    assert sim.asset_type == "BTC" and sim.simulation_engine_version == "btc-v0"
    result = update(btc, sim.simulation_id, T0 + timedelta(days=10))
    assert result["is_closed"]
    assert update(btc, sim.simulation_id, T0 + timedelta(days=10))["new_events"] == 0
    replay = replay_simulation(btc, sim.simulation_id)
    assert replay.match, replay.differences
    pm = postmortem(btc, sim.simulation_id, "VOLATILITY_EXPANSION", "explicit-tester")
    assert pm.classified_by == "explicit-tester"
    assert evidence_summary(btc).n_simulations == 0  # BTC never contaminates equity summaries


def test_btc_engine_preserves_frozen_bar_semantics_on_weekends():
    bars = pd.DataFrame(
        {"open": [100, 101], "high": [101, 112], "low": [99, 90], "close": [100, 105]},
        index=[datetime(2026, 10, 3).date(), datetime(2026, 10, 4).date()],
    )
    plan = PlanLevels("MARKET", 100, 100, 95, 110)
    a = SimulationEngineV1().evaluate(plan, bars, datetime(2026, 10, 2).date())
    b = BTCSimulationEngine().evaluate(plan, bars, datetime(2026, 10, 2).date())
    assert a.state == b.state and a.events == b.events
    assert b.state.value == "AMBIGUOUS_INTRABAR"


def test_reverting_provider_revision_is_archived(session, tmp_path):
    from types import SimpleNamespace

    from pitquant.btc.features import known_data
    from pitquant.btc.fixtures import load_synthetic_btc
    from pitquant.btc.providers import PublicProvider
    from pitquant.data.archive import ArchiveStore

    load_synthetic_btc(session, tmp_path)
    original = session.scalar(select(BTCDatum))
    provider = PublicProvider(session, ArchiveStore(tmp_path))
    for i, price in enumerate((100.0, 101.0, 100.0)):
        archive = SimpleNamespace(
            retrieved_at=T0 + timedelta(minutes=i),
            sha256=original.raw_hash,
            archive_id=original.archive_id,
        )
        provider.save(archive, "REVISION_TEST", "revision", T0, {"price": price})
    rows = [
        r
        for r in known_data(session, T0, Cohort.FORWARD_PAPER, T0 + timedelta(minutes=2))
        if r.metric == "revision"
    ]
    assert len(rows) == 1
    assert rows[0].payload["price"] == 100.0
    assert (
        len(session.scalars(select(BTCDatum).where(BTCDatum.source == "REVISION_TEST")).all()) == 3
    )


def test_strategy_harness_reuses_event_store_and_separates_overlapping_trades(btc):
    from pitquant.btc.simulation import strategy_test

    snap = freeze(btc, T0, Cohort.SYNTHETIC)
    result = strategy_test(btc, [snap], 7)
    assert result["returns"][0] == pytest.approx(0.06)
    assert result["trades"][0]["excess_vs_buy_and_hold"] == pytest.approx(-0.04)
    assert result["evaluation_unit"] == "INDEPENDENT_OVERLAPPING_TRADES_NOT_PORTFOLIO"
    assert strategy_test(btc, [snap], 7) == result


def test_custom_research_windows_remain_pinned_on_read(btc):
    config = ResearchConfig(train_days=730, validation_days=90)
    pinned = pin_config(btc, config)
    assert pin_config(btc).record_hash == pinned.record_hash
    assert readiness(btc, Cohort.HISTORICAL_OOS)["holdout"]["train_days"] == 730


def test_identical_raw_response_preserves_new_fetch_receipt(session, tmp_path, monkeypatch):
    import io

    from pitquant.btc.providers import SPOT, PublicProvider
    from pitquant.data.archive import ArchiveStore

    provider = PublicProvider(session, ArchiveStore(tmp_path))
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: io.BytesIO(b'{"value": 100}'))
    monkeypatch.setattr("pitquant.btc.providers.utc_now", lambda: T0)
    _, first = provider.get(SPOT, "/api/v3/klines", {"symbol": "BTCUSDT"})
    monkeypatch.setattr("pitquant.btc.providers.utc_now", lambda: T0 + timedelta(minutes=2))
    _, again = provider.get(SPOT, "/api/v3/klines", {"symbol": "BTCUSDT"})
    assert first.archive_id == again.archive_id
    assert first.sha256 == again.sha256
    assert again.retrieved_at == T0 + timedelta(minutes=2)
    assert first.retrieved_at == T0
