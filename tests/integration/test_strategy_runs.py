# ruff: noqa: E501, F401, F811, RUF059
"""Strategy runs (ADR-0039) on SYNTHETIC data (SYNF): decisions, AUTO_PAPER authority, SYNTHETIC / HISTORICAL / FORWARD_PAPER runners, PIT."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.config.settings import Settings
from pitquant.core.errors import HoldoutAccessError
from pitquant.db.models import Simulation
from pitquant.db.models_lab import StrategyDecision, StrategyRunEvent, StrategySimulationLink
from pitquant.simulation import service as sim
from pitquant.strategy import service as strat
from pitquant.strategy.spec import (
    StrategyError,
    new_version,
    preset_hybrid,
    preset_prediction_only,
    preset_trade_plan_only,
    save_strategy,
)
from tests.integration.test_analyzer_api import client
from tests.integration.test_simulation_lab import env
from tests.support.synthetic_predictions import synthetic_prediction

Env = tuple[Session, Settings, str, str]
D0 = datetime(2016, 6, 30, 23, 0, tzinfo=UTC)
D1 = datetime(2016, 7, 14, 23, 0, tzinfo=UTC)
D2 = datetime(2016, 7, 28, 23, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def fixture_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PITQUANT_E2E_FIXTURE", "1")


def decisions(s: Session, run_id: str) -> list[StrategyDecision]:
    return list(
        s.scalars(
            select(StrategyDecision)
            .where(StrategyDecision.run_id == run_id)
            .order_by(StrategyDecision.decision_at, StrategyDecision.created_at)
        )
    )


def pred_run(
    env: Env, p0: float = 0.72, p1: float = 0.48
) -> tuple[Session, Settings, str, strat.StrategyRun]:
    s, cfg, sf, _ = env
    synthetic_prediction(s, sf, D0, 6, p=p0, expected=0.08)
    synthetic_prediction(s, sf, D1, 6, p=p1, expected=0.01)
    spec = preset_prediction_only("PRED_E2E")
    spec.risk_rules = {**spec.risk_rules, "max_holding_sessions": 60}
    row = save_strategy(s, spec, "tester")
    run = strat.create_run(s, cfg, row, "SYNTHETIC", [sf])
    return s, cfg, sf, run


# ───────────────────────────────────────────── SYNTHETIC run: prediction -> strategy -> simulation -> exit
def test_synthetic_runs_exist_only_in_fixture_mode(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    s, cfg, sf, _ = env
    row = save_strategy(s, preset_trade_plan_only("SYN_GUARD", min_rr1=0.1), "tester")
    monkeypatch.delenv("PITQUANT_E2E_FIXTURE")
    with pytest.raises(StrategyError, match="fixture/test mode"):
        strat.create_run(s, cfg, row, "SYNTHETIC", [sf])


def test_prediction_enters_then_deterioration_exits_with_a_full_audit(env: Env) -> None:
    s, cfg, sf, run = pred_run(env)
    ds = strat.run_synthetic(s, cfg, run, [D0, D1])
    assert [d.decision for d in ds] == ["ENTER", "EXIT"] and ds[
        1
    ].exit_reason == "PREDICTION_DETERIORATION"
    enter, exit_ = ds
    assert (
        enter.prediction_snapshot_id
        and enter.rules_failed == []
        and "p_entry" in enter.rules_passed
        and enter.rule_inputs["p_outperform"] == 0.72
        and enter.is_synthetic
    )
    assert exit_.rule_inputs["prediction_drop_from_entry"] == pytest.approx(0.24) and {
        "p_exit",
        "p_drop",
    } <= set(exit_.rules_passed)
    links = list(
        s.scalars(select(StrategySimulationLink).order_by(StrategySimulationLink.created_at))
    )
    assert [(link.role, link.decision_id) for link in links] == [
        ("ENTRY", enter.decision_id),
        ("EXIT", exit_.decision_id),
    ] and links[0].simulation_id == links[1].simulation_id
    sm = s.get_one(Simulation, links[0].simulation_id)
    assert sm.mode == "AUTO_PAPER" and sm.is_synthetic and sm.plan_origin == "USER_DEFINED"
    out = sim.latest_outcome(s, sm.simulation_id)
    assert out.is_closed and out.state == "CLOSED_MANUAL" and out.exit_date == D1.date()
    assert strat.exit_reason_for(s, sm.simulation_id) == "PREDICTION_DETERIORATION"
    assert sim.replay_simulation(
        s, sm.simulation_id
    ).match  # the existing Simulation Lab machinery (events, replay) is reused as is


def test_synthetic_simulations_never_count_as_evidence(env: Env) -> None:
    s, cfg, sf, run = pred_run(env)
    strat.run_synthetic(s, cfg, run, [D0, D1])
    ev = sim.evidence_summary(s)
    assert ev.n_simulations == 0 and ev.n_closed == 0
    assert sim.insights(s, "origin")["segments"] == []


def test_a_period_is_decided_once_so_a_rerun_is_idempotent(env: Env) -> None:
    s, cfg, sf, run = pred_run(env)
    first = strat.run_synthetic(s, cfg, run, [D0, D1])
    again = strat.process_decision(s, cfg, run, sf, D0)
    assert again is None and len(decisions(s, run.run_id)) == len(first) == 2
    assert len(s.scalars(select(Simulation)).all()) == 1


def test_a_prediction_generated_after_the_decision_is_never_used(env: Env) -> None:
    s, cfg, sf, _ = env
    synthetic_prediction(
        s, sf, D0, 6, p=0.80, expected=0.1, generated_at=D0 + timedelta(days=3)
    )  # known only 3 days later: look-ahead
    row = save_strategy(s, preset_prediction_only("LATE_GEN"), "tester")
    run = strat.create_run(s, cfg, row, "SYNTHETIC", [sf])
    (d,) = strat.run_synthetic(s, cfg, run, [D0])
    assert (
        d.decision == "NO_ACTION"
        and "PREDICTION_NOT_VALIDATED" in d.rules_failed
        and d.prediction_snapshot_id is None
    )


def test_without_a_prediction_a_prediction_strategy_does_nothing(env: Env) -> None:
    s, cfg, sf, _ = env
    row = save_strategy(s, preset_hybrid("NO_PRED"), "tester")
    run = strat.create_run(s, cfg, row, "SYNTHETIC", [sf])
    (d,) = strat.run_synthetic(s, cfg, run, [D0])
    assert (
        d.decision == "NO_ACTION"
        and d.prediction_snapshot_id is None
        and s.scalars(select(Simulation)).all() == []
    )


def test_a_synthetic_run_refuses_a_non_synthetic_runner(env: Env) -> None:
    s, cfg, sf, run = pred_run(env)
    with pytest.raises(StrategyError, match="HISTORICAL run"):
        strat.run_historical(s, cfg, run, [D0])


# ───────────────────────────────────────────── AUTO_PAPER by authority
def test_auto_paper_needs_an_authority_and_prediction_authority_stays_disabled(env: Env) -> None:
    s, cfg, sf, _ = env
    with pytest.raises(sim.AutoPaperDisabled):
        sim.create_simulation(s, cfg, sf, plan_origin="PITQUANT", at=D0, mode="AUTO_PAPER")
    pred = sim.AutoPaperAuthority("P", 1, "PREDICTION_ONLY", "HISTORICAL")
    assert (
        pred.allowed()[0] is False
        and "AUTO_PAPER_PREDICTION = DISABLED_NOT_VALIDATED" in pred.allowed()[1]
    )
    with pytest.raises(sim.AutoPaperDisabled, match="DISABLED_NOT_VALIDATED"):
        sim.create_simulation(
            s, cfg, sf, plan_origin="PITQUANT", at=D0, mode="AUTO_PAPER", authority=pred
        )
    assert sim.AutoPaperAuthority("T", 1, "TRADE_PLAN_ONLY", "FORWARD_PAPER").allowed()[0] is True
    assert sim.AutoPaperAuthority("P", 1, "HYBRID", "SYNTHETIC").allowed()[0] is True


# ───────────────────────────────────────────── TRADE_PLAN_ONLY (works without any model)
def test_trade_plan_only_opens_a_trade_plan_paper_trade_without_a_prediction(env: Env) -> None:
    s, cfg, sf, _ = env
    row = save_strategy(s, preset_trade_plan_only("TPO", min_rr1=0.1), "tester")
    run = strat.create_run(s, cfg, row, "SYNTHETIC", [sf])
    (d,) = strat.run_synthetic(s, cfg, run, [D0])
    assert (
        d.decision == "ENTER"
        and d.prediction_snapshot_id is None
        and d.trade_plan_hash
        and d.trade_plan_snapshot["setup_type"]
    )
    assert {"plan_available", "quality_gate", "risk_gate_rr1"} <= set(d.rules_passed)
    sm = s.get_one(Simulation, s.scalars(select(StrategySimulationLink.simulation_id)).one())
    assert (
        sm.plan_origin == "PITQUANT"
        and sm.prediction_status == "NOT_YET_VALIDATED"
        and sm.model_id is None
    )  # no prediction attached to the simulation


def test_an_engine_closed_position_is_recorded_once_as_an_exit_with_the_mapped_reason(
    env: Env,
) -> None:
    s, cfg, sf, _ = env
    spec = preset_trade_plan_only("TPO_EXPIRY", min_rr1=0.1)
    spec.risk_rules = {"max_holding_sessions": 5}
    run = strat.create_run(s, cfg, save_strategy(s, spec, "tester"), "SYNTHETIC", [sf])
    strat.run_synthetic(s, cfg, run, [D0, D0 + timedelta(days=60)])
    ds = decisions(s, run.run_id)
    exits = [d for d in ds if d.decision == "EXIT"]
    assert len(exits) == 1 and exits[0].rule_inputs["position_closed_by"] == "SIMULATION_ENGINE"
    sid = s.scalars(select(StrategySimulationLink.simulation_id)).first()
    assert (
        exits[0].exit_reason in ("HORIZON_EXPIRY", "STOP", "TARGET", "THESIS_INVALIDATION")
        and strat.exit_reason_for(s, sid) == exits[0].exit_reason
    )


def test_max_positions_limits_open_trades(env: Env) -> None:
    s, cfg, sf, so = env
    spec = preset_trade_plan_only("TPO_MAX", min_rr1=0.1)
    spec.max_positions = 1
    run = strat.create_run(s, cfg, save_strategy(s, spec, "tester"), "SYNTHETIC", [sf])
    strat.run_synthetic(s, cfg, run, [D0, D0 + timedelta(days=1)])
    assert (
        len(s.scalars(select(Simulation)).all()) == 1
    )  # the second day finds the first trade open: HOLD, never a second entry


# ───────────────────────────────────────────── HISTORICAL: gated, PIT, versions
def test_a_historical_run_is_blocked_while_the_data_gates_are_closed_and_executes_nothing(
    env: Env,
) -> None:
    s, cfg, sf, _ = env
    row = save_strategy(s, preset_trade_plan_only("HIST_BLOCK", min_rr1=0.1), "tester")
    run = strat.create_run(s, cfg, row, "HISTORICAL", [sf])
    assert strat.run_status(s, run) == "BLOCKED"
    assert (
        any("US_FUNDAMENTALS_READY" in r for r in run.blocked_reasons)
        and run.readiness["US_FUNDAMENTALS_READY"] is False
    )
    assert (
        strat.run_historical(s, cfg, run, [D0]) == [] and s.scalars(select(Simulation)).all() == []
    )
    assert [
        e.event_type
        for e in s.scalars(
            select(StrategyRunEvent)
            .where(StrategyRunEvent.run_id == run.run_id)
            .order_by(StrategyRunEvent.created_at)
        )
    ] == ["CREATED", "BLOCKED"]


OPEN_GATES = {
    "D02_MONTHLY_RESEARCH_READY": True,
    "US_D05_RESEARCH_READY": True,
    "US_SECURITY_IDENTITY_READY": True,
    "US_FUNDAMENTALS_READY": True,
}


def test_historical_with_open_gates_uses_only_data_known_at_each_date_and_records_the_versions(
    env: Env,
) -> None:
    s, cfg, sf, _ = env
    v1 = save_strategy(s, preset_trade_plan_only("HIST_PIT", min_rr1=0.1), "tester")
    new_version(s, "HIST_PIT", {"max_positions": 2}, "tester")  # v2 exists, the run is bound to v1
    run = strat.create_run(s, cfg, v1, "HISTORICAL", [sf], readiness=OPEN_GATES)
    assert (
        run.blocked_reasons == []
        and (run.strategy_version, run.simulation_engine_version) == (1, "v1")
        and run.commit_sha
    )
    ds = strat.run_historical(s, cfg, run, [D0, D1])
    assert ds and all(d.strategy_version == 1 for d in ds)
    for d in ds:  # each plan was generated AT its decision instant (PIT as_of), never later
        assert (
            d.trade_plan_snapshot["plan_as_of"].startswith(d.decision_at.date().isoformat())
            and datetime.fromisoformat(d.trade_plan_snapshot["plan_as_of"]) <= d.decision_at
        )
    first = ds[0]
    plan_t0 = sim.AnalyzerService(s, cfg).trade_plan(sf, D0)
    assert sim.AnalyzerService(s, cfg).trade_plan(sf, D0)["as_of"] == plan_t0["as_of"] and plan_t0[
        "as_of"
    ].startswith("2016-06-30")  # PIT as_of, no later data
    assert (
        first.decision_at == D0
        and first.trade_plan_snapshot["entry_zone_low"]
        <= first.trade_plan_snapshot["entry_zone_high"]
    )


def test_a_prediction_family_historical_run_without_a_validated_model_never_acts(env: Env) -> None:
    s, cfg, sf, _ = env
    row = save_strategy(s, preset_prediction_only("HIST_PRED"), "tester")
    run = strat.create_run(s, cfg, row, "HISTORICAL", [sf], readiness=OPEN_GATES)
    ds = strat.run_historical(s, cfg, run, [D0])
    assert (
        [d.decision for d in ds] == ["NO_ACTION"]
        and "PREDICTION_NOT_VALIDATED" in ds[0].rules_failed
        and s.scalars(select(Simulation)).all() == []
    )


def test_the_sealed_holdout_is_never_decided_on(env: Env, settings: Settings) -> None:
    s, cfg, sf, _ = env
    run = strat.create_run(
        s,
        cfg,
        save_strategy(s, preset_trade_plan_only("HOLDOUT", min_rr1=0.1), "tester"),
        "HISTORICAL",
        [sf],
        readiness=OPEN_GATES,
    )
    inside = datetime(2023, 6, 1, 23, tzinfo=UTC)
    with pytest.raises(HoldoutAccessError):
        strat.run_historical(s, cfg, run, [inside])


# ───────────────────────────────────────────── FORWARD_PAPER: frozen, server clock, nothing back-dated
def test_forward_paper_is_frozen_activated_by_the_server_clock_and_never_back_dated(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    s, cfg, sf, _ = env
    monkeypatch.setattr(strat, "CLOCK", lambda: D0)
    v1 = save_strategy(s, preset_trade_plan_only("FWD", min_rr1=0.1), "tester")
    run = strat.create_run(s, cfg, v1, "FORWARD_PAPER", [sf])
    assert run.activated_at == D0 and strat.run_status(s, run) == "ACTIVE" and not run.is_synthetic
    new_version(s, "FWD", {"max_positions": 9}, "tester")  # the strategy is edited AFTER activation
    assert strat.forward_tick(
        s, cfg, run, as_of=D0 + timedelta(days=0)
    )  # tick at activation: allowed
    d = decisions(s, run.run_id)[0]
    assert (d.strategy_version, d.decision) == (
        1,
        "ENTER",
    ) and not d.is_synthetic  # still version 1: frozen
    with pytest.raises(StrategyError, match="before the activation"):
        strat.forward_tick(s, cfg, run, as_of=D0 - timedelta(days=30))
    n = len(decisions(s, run.run_id))
    assert (
        strat.forward_tick(s, cfg, run, as_of=D0 + timedelta(minutes=30)) == []
        and len(decisions(s, run.run_id)) == n
    )  # same period: no duplicate
    sm = s.get_one(Simulation, s.scalars(select(StrategySimulationLink.simulation_id)).first())
    assert not sm.is_synthetic and sm.mode == "AUTO_PAPER" and sm.decision_at >= D0


def test_forward_paper_for_a_prediction_family_is_refused_until_a_validated_model_exists(
    env: Env,
) -> None:
    s, cfg, sf, _ = env
    for preset in (preset_prediction_only("FWD_P"), preset_hybrid("FWD_H")):
        with pytest.raises(StrategyError, match="DISABLED_NOT_VALIDATED"):
            strat.create_run(s, cfg, save_strategy(s, preset, "tester"), "FORWARD_PAPER", [sf])


def test_forward_predictions_before_activation_are_ignored(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    s, cfg, sf, _ = env
    old = synthetic_prediction(s, sf, D0 - timedelta(days=10), 6)
    row = save_strategy(s, preset_trade_plan_only("FWD_OLD", min_rr1=0.1), "tester")
    monkeypatch.setattr(strat, "CLOCK", lambda: D0)
    run = strat.create_run(s, cfg, row, "FORWARD_PAPER", [sf])
    assert strat.lookup_prediction(s, sf, 6, D0, exact=False, not_before=run.activated_at) is None
    assert (
        strat.lookup_prediction(s, sf, 6, D0, exact=False) is not None
        and old.decision_at < run.activated_at
    )


def test_a_run_event_log_is_the_lifecycle(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    s, cfg, sf, _ = env
    monkeypatch.setattr(strat, "CLOCK", lambda: D0)
    run = strat.create_run(
        s,
        cfg,
        save_strategy(s, preset_trade_plan_only("LIFE", min_rr1=0.1), "tester"),
        "FORWARD_PAPER",
        [sf],
    )
    strat.forward_tick(s, cfg, run, as_of=D0)
    strat.stop_run(s, run)
    assert [
        e.event_type
        for e in s.scalars(
            select(StrategyRunEvent)
            .where(StrategyRunEvent.run_id == run.run_id)
            .order_by(StrategyRunEvent.created_at)
        )
    ] == ["CREATED", "ACTIVATED", "TICK", "STOPPED"]
    assert strat.run_status(s, run) == "STOPPED"
    with pytest.raises(StrategyError, match="not ACTIVE"):
        strat.forward_tick(s, cfg, run, as_of=D0 + timedelta(days=1))
