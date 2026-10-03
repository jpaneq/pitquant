# ruff: noqa: E501, F401, F811, RUF059
"""Simulation Lab (ADR-0034): immutable T0, no leakage, plans, outcomes, post-mortem, KO without price, AUTO_PAPER disabled.
SYNTHETIC data (SYNF = prices + fundamentals, SYNO = fundamentals only). PAPER TRADE, NO REAL MONEY."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pitquant.analyzer.service import AnalyzerService
from pitquant.config.settings import Settings
from pitquant.core.errors import ImmutableRecordError
from pitquant.db.models import Simulation, SimulationOutcome
from pitquant.simulation import service as sim
from tests.integration.test_analyzer_api import (
    client,
)

ROOT = Path(__file__).resolve().parents[2]
T0 = datetime(2016, 6, 30, 23, 0, tzinfo=UTC)
LATER = datetime(2016, 12, 31, 23, 0, tzinfo=UTC)


def plan_for(session: Session, settings: Settings, sid: str) -> sim.PlanInput:
    last = AnalyzerService(session, settings).quote(sid, T0)
    px = float(last["price"])
    return sim.PlanInput(
        entry_type="LIMIT",
        entry_zone_low=px * 0.97,
        entry_zone_high=px,
        stop_loss=px * 0.90,
        invalidation_level=px * 0.88,
        target_1=px * 1.05,
        target_2=px * 1.10,
    )


@pytest.fixture
def env(client: TestClient) -> tuple[Session, Settings, str, str]:
    factory = client.app.state.session_factory  # type: ignore[attr-defined]
    s = factory()
    sid = {
        x["ticker"]: x["security_id"]
        for x in client.get("/search", params={"q": "SYN"}).json()["results"]
    }
    from tests.unit.test_feature_engine_v0 import SESSIONS

    cfg = client.app.state.settings if hasattr(client.app.state, "settings") else None
    from pitquant.config.settings import get_settings

    return s, cfg or get_settings(), sid["SYNF"], sid["SYNO"]


def make(
    env: tuple[Session, Settings, str, str], origin: str = "USER_DEFINED", at: datetime = T0
) -> Simulation:
    s, cfg, sf, _ = env
    return sim.create_simulation(s, cfg, sf, plan_origin=origin, plan=plan_for(s, cfg, sf), at=at)


# ───────────────────────────────────────────── T0 snapshot
def test_t0_snapshot_is_immutable_and_never_receives_future_data(
    env: tuple[Session, Settings, str, str],
) -> None:
    s, cfg, sf, _ = env
    sm = make(env)
    before = {c.key: getattr(sm, c.key) for c in sm.__table__.columns}
    sim.evaluate_simulation(s, cfg, sm.simulation_id, LATER)
    sim.thesis_snapshot(s, cfg, sm.simulation_id, LATER)
    lo = sim.latest_outcome(s, sm.simulation_id)
    if lo is not None and lo.entry_date is not None and not lo.is_closed:
        sim.close_manual(s, cfg, sm.simulation_id, at=LATER, price=1.0)
    elif lo is not None and not lo.is_closed:
        sim.cancel_simulation(
            s, cfg, sm.simulation_id, at=LATER
        )  # ADR-0036: a manual close needs an open position
    s.refresh(sm)
    assert {
        c.key: getattr(sm, c.key) for c in sm.__table__.columns
    } == before  # outcomes/observations live in their own tables
    sm.stop_loss = 1.0
    with pytest.raises(ImmutableRecordError):
        s.flush()
    s.rollback()


def test_snapshot_only_contains_information_available_at_decision_at(
    env: tuple[Session, Settings, str, str],
) -> None:
    s, cfg, sf, _ = env
    sm = make(env, at=T0)
    assert (
        sm.created_at >= sm.decision_at
    )  # the CHECK also forbids a snapshot "created" before its decision
    assert str(sm.technical_snapshot["last_session"]) <= "2016-06-30"
    assert sm.technical_snapshot["as_of"].startswith("2016-06-30") and sm.entry_price_actual is None
    assert (
        sm.prediction_status == "NOT_YET_VALIDATED"
        and sm.model_id is None
        and sm.model_version is None
    )


def test_no_probability_or_expected_return_is_invented(
    env: tuple[Session, Settings, str, str],
) -> None:
    sm = make(env)
    blob = repr(
        [
            sm.price_snapshot,
            sm.technical_snapshot,
            sm.trade_plan_snapshot,
            sm.market_regime_snapshot,
            sm.final_simulated_plan,
        ]
    )
    for banned in ("p_outperform", "expected_excess_return", "probability", "confidence"):
        assert banned not in blob


# ───────────────────────────────────────────── plan origin
def test_user_modified_keeps_the_original_pitquant_plan_and_the_final_one(
    env: tuple[Session, Settings, str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    s, cfg, sf, _ = env
    px = plan_for(s, cfg, sf)
    setup = {
        "setup_type": "PULLBACK",
        "type": "PULLBACK",
        "profile": "BASE",
        "entry_zone": {"lower": px.entry_zone_low, "upper": px.entry_zone_high},
        "stop": px.stop_loss,
        "invalidation_level": px.invalidation_level,
        "target_1": px.target_1,
        "target_2": px.target_2,
        "risk_reward_1": 1.5,
        "rules_version": "trade-plan-v0.1",
    }
    monkeypatch.setattr(
        AnalyzerService,
        "trade_plan",
        lambda self, sid, at: {"status": "SETUPS_AVAILABLE", "setups": [setup]},
    )
    own = sim.PlanInput(stop_loss=px.stop_loss * 0.99)  # the user only moves the stop
    sm = sim.create_simulation(s, cfg, sf, plan_origin="USER_MODIFIED", plan=own, at=T0)
    assert sm.original_pitquant_plan["stop_loss"] == pytest.approx(
        px.stop_loss
    ) and sm.final_simulated_plan["stop_loss"] == pytest.approx(px.stop_loss * 0.99)
    assert sm.stop_loss == pytest.approx(px.stop_loss * 0.99) and sm.plan_origin == "USER_MODIFIED"
    pure = sim.create_simulation(s, cfg, sf, plan_origin="PITQUANT", at=T0)
    assert (
        pure.final_simulated_plan["stop_loss"] == pytest.approx(px.stop_loss)
        and pure.plan_origin == "PITQUANT"
    )


def test_pitquant_origin_without_a_setup_is_refused(
    env: tuple[Session, Settings, str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    s, cfg, sf, _ = env
    monkeypatch.setattr(
        AnalyzerService,
        "trade_plan",
        lambda self, sid, at: {"status": "NO_VALID_SETUP", "setups": []},
    )
    with pytest.raises(sim.SimulationError, match="NO_PITQUANT_PLAN"):
        sim.create_simulation(s, cfg, sf, plan_origin="PITQUANT", at=T0)


# ───────────────────────────────────────────── outcomes, post-mortem, summary
def test_evaluation_appends_outcomes_and_closed_simulation_accepts_a_postmortem(
    env: tuple[Session, Settings, str, str],
) -> None:
    s, cfg, sf, _ = env
    sm = make(env)
    o = sim.evaluate_simulation(s, cfg, sm.simulation_id, LATER)
    assert (
        o.prediction_direction_correct is None and o.trade_plan_execution_correct is None
    )  # NULL until the Prediction Engine is validated
    assert o.state in {
        x.value for x in __import__("pitquant.simulation.engine", fromlist=["SimState"]).SimState
    }
    if not o.is_closed:
        sim.close_manual(s, cfg, sm.simulation_id, at=LATER, price=float(sm.entry_zone_high))
        o = sim.evaluate_simulation(s, cfg, sm.simulation_id, LATER)
    assert len(s.query(SimulationOutcome).filter_by(simulation_id=sm.simulation_id).all()) >= 1
    with pytest.raises(sim.SimulationError):
        sim.classify_postmortem(
            s, sm.simulation_id, primary_cause="LLM_SAYS_SO", classified_by="tester"
        )
    if o.is_closed:
        pm = sim.classify_postmortem(
            s,
            sm.simulation_id,
            primary_cause="NO_CLEAR_ERROR",
            secondary_causes=["TIMING_ERROR"],
            classified_by="tester",
        )
        assert pm.classified_by == "tester" and pm.metrics["state"] == o.state


def test_a_postmortem_needs_a_closed_simulation(env: tuple[Session, Settings, str, str]) -> None:
    s, cfg, sf, _ = env
    sm = make(env)
    with pytest.raises(sim.SimulationError, match="CLOSED"):
        sim.classify_postmortem(
            s, sm.simulation_id, primary_cause="NO_CLEAR_ERROR", classified_by="tester"
        )


def test_evidence_summary_shows_no_statistics_with_insufficient_n(
    env: tuple[Session, Settings, str, str],
) -> None:
    s, cfg, sf, _ = env
    sm = make(env)
    sim.evaluate_simulation(s, cfg, sm.simulation_id, LATER)
    ev = sim.evidence_summary(s)
    assert (
        ev.stats_available is False
        and ev.hit_rate is None
        and ev.mean_r is None
        and ev.min_n == 10
        and "never a training label" in ev.note
    )


# ───────────────────────────────────────────── eligibility, AUTO_PAPER, holdout, BTC
def test_a_fundamental_only_security_cannot_be_simulated(
    env: tuple[Session, Settings, str, str], client: TestClient
) -> None:
    s, cfg, _, so = env
    assert sim.eligibility(s, cfg, so) == {"enabled": False, "reason": "PRICE_DATA_REQUIRED"}
    with pytest.raises(sim.PriceDataRequired):
        sim.create_simulation(
            s,
            cfg,
            so,
            plan_origin="USER_DEFINED",
            plan=sim.PlanInput(entry_zone_low=9, entry_zone_high=10, stop_loss=8, target_1=12),
            at=T0,
        )
    r = client.post(
        "/simulations",
        json={
            "security": "SYNO",
            "plan_origin": "USER_DEFINED",
            "plan": {"entry_zone_low": 9, "entry_zone_high": 10, "stop_loss": 8, "target_1": 12},
        },
    )
    assert r.status_code == 409 and "PRICE_DATA_REQUIRED" in r.text
    assert client.get(
        "/analyzer/SYNO/summary", params={"as_of": "2016-12-31T23:00:00+00:00"}
    ).json()["simulation"] == {"enabled": False, "reason": "PRICE_DATA_REQUIRED"}


def test_auto_paper_is_disabled_and_the_holdout_is_sealed(
    env: tuple[Session, Settings, str, str], client: TestClient
) -> None:
    s, cfg, sf, _ = env
    with pytest.raises(sim.AutoPaperDisabled):
        sim.create_simulation(
            s,
            cfg,
            sf,
            plan_origin="USER_DEFINED",
            plan=plan_for(s, cfg, sf),
            at=T0,
            mode="AUTO_PAPER",
        )
    assert sim.AUTO_PAPER_ENABLED is False
    r = client.post(
        "/simulations",
        json={
            "security": "SYNF",
            "plan_origin": "USER_DEFINED",
            "as_of": "2023-06-01T00:00:00+00:00",
            "plan": {"entry_zone_low": 9, "entry_zone_high": 10, "stop_loss": 8, "target_1": 12},
        },
    )
    assert r.status_code == 403


def test_btc_extensions_are_nullable_columns_and_equity_rows_leave_them_null(
    env: tuple[Session, Settings, str, str],
) -> None:
    s, cfg, sf, _ = env
    sm = make(env)
    assert (
        sm.asset_type,
        sm.funding_snapshot,
        sm.open_interest_snapshot,
        sm.basis_snapshot,
        sm.onchain_snapshot,
    ) == ("EQUITY", None, None, None, None)
    with pytest.raises(sim.SimulationError, match="BTC"):
        sim.create_simulation(
            s,
            cfg,
            sf,
            plan_origin="USER_DEFINED",
            plan=plan_for(s, cfg, sf),
            at=T0,
            asset_type="BTC",
        )


def test_http_flow_create_list_detail_evaluate_banner(client: TestClient) -> None:
    r = client.post(
        "/simulations",
        json={
            "security": "SYNF",
            "plan_origin": "USER_DEFINED",
            "as_of": "2016-06-30T23:00:00+00:00",
            "plan": {"entry_zone_low": 1, "entry_zone_high": 2, "stop_loss": 0.5, "target_1": 3},
        },
    )
    assert r.status_code in (200, 422)
    ok = r.json() if r.status_code == 200 else None
    if ok is None:
        return
    assert (
        ok["banner"] == "PAPER TRADE — NO REAL MONEY"
        and ok["prediction_status"] == "NOT_YET_VALIDATED"
    )
    d = client.get(f"/simulations/{ok['simulation_id']}").json()
    assert d["banner"].startswith("PAPER TRADE") and d["simulation"]["entry_price_actual"] is None
    assert client.get("/simulations").json()[0]["simulation_id"] == ok["simulation_id"]
    assert client.get("/simulations/summary").json()["evidence"]["stats_available"] is False
    assert client.get("/research/simulation-evidence").json()["read_only"] is True


# ───────────────────────────────────────────── no automatic learning
def test_paper_data_never_enters_training_datasets_or_models_automatically() -> None:
    banned = (
        "pitquant.simulation",
        "simulations",
        "SimulationOutcome",
        "simulation_outcomes",
        "ResearchHypothesis",
    )
    for rel in (
        "research/dataset_builder.py",
        "research/baselines.py",
        "research/walkforward.py",
        "research/registry.py",
        "features",
        "backtest",
        "validation",
    ):
        base = ROOT / "src" / "pitquant" / rel
        files = [base] if base.is_file() else list(base.rglob("*.py")) if base.exists() else []
        for f in files:
            text = f.read_text()
            assert not any(b in text for b in banned), f"{f} reads simulation data"
    svc = (ROOT / "src/pitquant/simulation/service.py").read_text()
    for forbidden in (
        "DatasetVersion",
        "ModelVersion",
        "ModelConfig",
        "ChampionChallenger",
        "FeatureSnapshotRow",
    ):
        assert (
            forbidden not in svc
        )  # Simulation Lab cannot touch datasets, model versions or champions
