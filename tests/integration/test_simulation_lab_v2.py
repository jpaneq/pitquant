# ruff: noqa: E501, F401, F811, RUF059
"""Simulation Lab ADR-0036: event store, idempotent update, replay, counterfactual, insights, post-mortem facts, transitions.
SYNTHETIC data (SYNF). PAPER TRADE, NO REAL MONEY."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.config.settings import Settings
from pitquant.core.errors import ImmutableRecordError
from pitquant.db.models import (
    Simulation,
    SimulationCounterfactual,
    SimulationEvent,
    SimulationOutcome,
)
from pitquant.simulation import service as sim
from tests.integration.test_analyzer_api import client
from tests.integration.test_simulation_lab import LATER, T0, env, make, plan_for

MID = datetime(2016, 9, 30, 23, 0, tzinfo=UTC)
EARLY = datetime(2016, 7, 15, 23, 0, tzinfo=UTC)
Env = tuple[Session, Settings, str, str]


def events(s: Session, sm: Simulation) -> list[SimulationEvent]:
    return sim.stored_events(s, sm.simulation_id)


def outcomes(s: Session, sm: Simulation) -> int:
    return len(
        s.scalars(
            select(SimulationOutcome).where(SimulationOutcome.simulation_id == sm.simulation_id)
        ).all()
    )


def test_creation_writes_the_first_event_and_a_snapshot_hash(env: Env) -> None:
    s, cfg, sf, _ = env
    sm = make(env)
    ev = events(s, sm)
    assert [(e.sequence_number, e.event_type) for e in ev] == [(0, "SIMULATION_CREATED")]
    assert (
        sm.snapshot_hash
        and sim.verify_snapshot(sm)
        and sm.source_provenance["event_engine_version"] == "sim-engine-2"
    )
    assert (
        sm.final_simulated_plan["exit_policy"] == "TRACK_TARGETS_ONLY"
    )  # no invented partial scheme
    assert sm.final_simulated_plan["risk_reward"]["tp1"] > 0


def test_update_is_idempotent_second_run_appends_zero_events_and_no_outcome(env: Env) -> None:
    s, cfg, sf, _ = env
    sm = make(env)
    r1 = sim.update_simulation(s, cfg, sm.simulation_id, LATER)
    n_ev, n_out = len(events(s, sm)), outcomes(s, sm)
    r2 = sim.update_simulation(s, cfg, sm.simulation_id, LATER)
    assert r1.new_events > 0 and r1.outcome_created
    assert r2.new_events == 0 and not r2.outcome_created
    assert (len(events(s, sm)), outcomes(s, sm)) == (n_ev, n_out)


def test_incremental_updates_equal_one_full_update_and_never_rewrite_history(env: Env) -> None:
    s, cfg, sf, _ = env
    a, b = make(env), make(env)
    sim.update_simulation(s, cfg, a.simulation_id, MID)
    first = [(e.sequence_number, e.event_type, e.payload_json) for e in events(s, a)]
    sim.update_simulation(s, cfg, a.simulation_id, LATER)
    sim.update_simulation(s, cfg, b.simulation_id, LATER)
    full_a = [(e.sequence_number, e.event_type, e.payload_json) for e in events(s, a)]
    full_b = [(e.sequence_number, e.event_type, e.payload_json) for e in events(s, b)]
    assert full_a[: len(first)] == first and full_a == full_b


def test_an_update_at_an_earlier_instant_adds_nothing_and_materialises_no_older_state(
    env: Env,
) -> None:
    s, cfg, sf, _ = env
    sm = make(env)
    sim.update_simulation(s, cfg, sm.simulation_id, LATER)
    before = outcomes(s, sm)
    r = sim.update_simulation(s, cfg, sm.simulation_id, MID)
    assert r.new_events == 0 and outcomes(s, sm) == before


def test_point_in_time_no_event_belongs_to_a_bar_after_the_evaluation_instant(env: Env) -> None:
    s, cfg, sf, _ = env
    sm = make(env)
    sim.update_simulation(s, cfg, sm.simulation_id, MID)
    assert all(e.occurred_at <= MID.date() for e in events(s, sm))
    assert all(
        e.occurred_at > T0.date() for e in events(s, sm) if e.event_type == "BAR_PROCESSED"
    )  # nothing at or before T0 is traded


def test_replay_rebuilds_the_persisted_state_from_t0_and_events_only(env: Env) -> None:
    s, cfg, sf, _ = env
    sm = make(env)
    sim.update_simulation(s, cfg, sm.simulation_id, LATER)
    r = sim.replay_simulation(s, sm.simulation_id)
    assert r.match and r.differences == [] and r.n_events == len(events(s, sm))
    lo = sim.latest_outcome(s, sm.simulation_id)
    assert r.folded["state"] == lo.state and r.folded.get("entry_price") == lo.entry_price


def test_replay_reports_a_persisted_state_that_the_events_do_not_support(env: Env) -> None:
    s, cfg, sf, _ = env
    sm = make(env)
    sim.update_simulation(s, cfg, sm.simulation_id, LATER)
    lo = sim.latest_outcome(s, sm.simulation_id)
    s.add(
        SimulationOutcome(
            simulation_id=sm.simulation_id,
            evaluated_at=LATER,
            state="TP1",
            is_closed=True,
            entry_date=lo.entry_date,
            entry_price=1.0,
            exit_date=lo.exit_date,
            timeline=[],
            details={},
            event_count=lo.event_count,
        )
    )
    s.flush()
    r = sim.replay_simulation(s, sm.simulation_id)
    assert not r.match and any("state" in d or "entry_price" in d for d in r.differences)


def test_events_and_snapshot_are_append_only_and_tampering_is_detected(env: Env) -> None:
    s, cfg, sf, _ = env
    sm = make(env)
    sim.update_simulation(s, cfg, sm.simulation_id, LATER)
    ev = events(s, sm)[0]
    ev.payload_json = {"state_after": "STOPPED"}
    with pytest.raises(ImmutableRecordError):
        s.flush()
    s.rollback()
    sm2 = make(env)
    sm2.stop_loss = 1.0  # in-memory edit, never flushed: the hash no longer matches
    assert not sim.verify_snapshot(sm2)
    with pytest.raises(sim.SimulationError, match="SNAPSHOT_TAMPERED"):
        sim.update_simulation(s, cfg, sm2.simulation_id, LATER)
    s.rollback()


def test_market_reference_enters_at_the_stored_price_at_t0(env: Env) -> None:
    s, cfg, sf, _ = env
    p = plan_for(s, cfg, sf)
    px = float(sim.AnalyzerService(s, cfg).quote(sf, T0)["price"])
    p.entry_type, p.entry_price = "MARKET_REFERENCE", None
    sm = sim.create_simulation(s, cfg, sf, plan_origin="USER_DEFINED", plan=p, at=T0)
    assert (
        sm.entry_type == "MARKET_REFERENCE"
        and sm.entry_zone_low == sm.entry_zone_high == pytest.approx(px)
    )
    sim.update_simulation(s, cfg, sm.simulation_id, LATER)
    fill = next(e for e in events(s, sm) if e.event_type == "ENTRY_FILLED")
    assert (
        fill.occurred_at == T0.date()
        and fill.payload_json["fill_method"] == "MARKET_REFERENCE"
        and fill.payload_json["price"] == pytest.approx(px)
    )


def test_position_sizing_modes(env: Env) -> None:
    s, cfg, sf, _ = env
    p = plan_for(s, cfg, sf)
    fixed = sim.create_simulation(
        s,
        cfg,
        sf,
        plan_origin="USER_DEFINED",
        plan=p,
        at=T0,
        sizing_mode="FIXED_NOTIONAL",
        notional=10_000.0,
    )
    assert (
        fixed.position_size_simulated == int(10_000 // p.entry_zone_high)
        and fixed.final_simulated_plan["sizing"]["mode"] == "FIXED_NOTIONAL"
    )
    with pytest.raises(sim.SimulationError, match="notional"):
        sim.create_simulation(
            s, cfg, sf, plan_origin="USER_DEFINED", plan=p, at=T0, sizing_mode="FIXED_NOTIONAL"
        )
    with pytest.raises(sim.SimulationError, match="sizing_mode"):
        sim.create_simulation(
            s, cfg, sf, plan_origin="USER_DEFINED", plan=p, at=T0, sizing_mode="KELLY"
        )


def test_invalid_plans_fail_closed(env: Env) -> None:
    s, cfg, sf, _ = env
    p = plan_for(s, cfg, sf)
    p.stop_loss = p.entry_zone_high * 1.01
    with pytest.raises(sim.SimulationError):
        sim.create_simulation(s, cfg, sf, plan_origin="USER_DEFINED", plan=p, at=T0)
    p = plan_for(s, cfg, sf)
    p.exit_policy, p.exit_fractions = "PARTIAL_FRACTIONS", [0.8, 0.5, 0.0]
    with pytest.raises(sim.SimulationError, match="sum"):
        sim.create_simulation(s, cfg, sf, plan_origin="USER_DEFINED", plan=p, at=T0)


def test_cancel_only_before_the_entry_and_manual_close_only_with_a_position(env: Env) -> None:
    s, cfg, sf, _ = env
    p = plan_for(s, cfg, sf)
    px = p.entry_zone_high
    (
        p.entry_zone_low,
        p.entry_zone_high,
        p.stop_loss,
        p.invalidation_level,
        p.target_1,
        p.target_2,
    ) = px * 0.5, px * 0.55, px * 0.4, None, px * 0.7, None
    waiting = sim.create_simulation(s, cfg, sf, plan_origin="USER_DEFINED", plan=p, at=T0)
    assert sim.update_simulation(s, cfg, waiting.simulation_id, EARLY).state == "WAITING_ENTRY"
    with pytest.raises(sim.SimulationError, match="OPEN position"):
        sim.close_manual(s, cfg, waiting.simulation_id, at=EARLY, price=px)
    sim.cancel_simulation(s, cfg, waiting.simulation_id, at=EARLY)
    assert sim.update_simulation(s, cfg, waiting.simulation_id, EARLY).state == "CANCELLED"
    assert [e.event_type for e in events(s, waiting)][-1] == "CANCELLED"
    q = plan_for(s, cfg, sf)
    q.entry_type = "MARKET_REFERENCE"
    entered = sim.create_simulation(s, cfg, sf, plan_origin="USER_DEFINED", plan=q, at=T0)
    sim.update_simulation(s, cfg, entered.simulation_id, EARLY)
    with pytest.raises(sim.SimulationError, match="not entered"):
        sim.cancel_simulation(s, cfg, entered.simulation_id, at=EARLY)


def test_postmortem_facts_keep_prediction_and_execution_apart_and_infer_no_cause(env: Env) -> None:
    s, cfg, sf, _ = env
    p = plan_for(s, cfg, sf)
    p.entry_type = "MARKET_REFERENCE"
    sm = sim.create_simulation(s, cfg, sf, plan_origin="USER_DEFINED", plan=p, at=T0)
    sim.update_simulation(s, cfg, sm.simulation_id, EARLY)
    sim.close_manual(s, cfg, sm.simulation_id, at=EARLY, price=float(p.entry_zone_high))
    sim.update_simulation(s, cfg, sm.simulation_id, EARLY)
    f = sim.postmortem_facts(s, cfg, sm.simulation_id, EARLY)
    assert (
        f["prediction_outcome"] is None
        and f["prediction_status"] == "NOT_YET_VALIDATED"
        and f["execution_outcome"] == "CLOSED_MANUAL"
    )
    assert f["stop_quality"]["stop_distance_atr"] is not None and "STOP_TOO_TIGHT" not in str(f)
    pm = sim.classify_postmortem(
        s, sm.simulation_id, primary_cause="NO_CLEAR_ERROR", classified_by="tester"
    )
    assert pm.metrics["facts_at_classification"]["prediction_outcome"] is None


def test_hypothesis_is_untested_and_never_touches_models(env: Env) -> None:
    s, cfg, sf, _ = env
    sm = make(env)
    h = sim.propose_hypothesis(
        s,
        statement="stops of < 1 ATR stop out often",
        evidence={"n": 3},
        created_by="tester",
        simulation_id=sm.simulation_id,
    )
    assert h.status == "UNTESTED" and h.evidence["simulation_id"] == sm.simulation_id
    with pytest.raises(sim.SimulationError):
        sim.propose_hypothesis(s, statement="x", evidence={}, created_by="t", status="PROMOTED")


def test_insights_are_descriptive_and_flag_small_samples(env: Env) -> None:
    s, cfg, sf, _ = env
    for _i in range(2):
        sm = make(env)
        sim.update_simulation(s, cfg, sm.simulation_id, LATER)
    out = sim.insights(s, "origin")
    seg = next(x for x in out["segments"] if x["segment"] == "USER_DEFINED")
    assert (
        seg["n"] >= 2 and seg["sample"] == "INSUFFICIENT_SAMPLE" and "return" not in seg
    )  # no statistics below min N
    assert out["note"].startswith("descriptive") and not any(
        "recommendation" in x for x in out["segments"]
    )
    with pytest.raises(sim.SimulationError, match="segmentation"):
        sim.insights(s, "astrology")


def test_user_modified_keeps_both_plans_and_the_counterfactual_never_replaces_the_real_outcome(
    env: Env,
) -> None:
    s, cfg, sf, _ = env
    p = plan_for(s, cfg, sf)
    sm = sim.create_simulation(s, cfg, sf, plan_origin="USER_MODIFIED", plan=p, at=T0)
    assert sm.original_pitquant_plan and sm.final_simulated_plan["stop_loss"] == pytest.approx(
        p.stop_loss
    )
    sim.update_simulation(s, cfg, sm.simulation_id, LATER)
    cf = s.scalars(
        select(SimulationCounterfactual).where(
            SimulationCounterfactual.simulation_id == sm.simulation_id
        )
    ).all()
    assert (
        len(cf) == 1
        and cf[0].label == "COUNTERFACTUAL"
        and "NOT THE REAL OUTCOME" in cf[0].details["label"]
    )
    n = len(cf)
    sim.update_simulation(s, cfg, sm.simulation_id, LATER)
    assert (
        len(
            s.scalars(
                select(SimulationCounterfactual).where(
                    SimulationCounterfactual.simulation_id == sm.simulation_id
                )
            ).all()
        )
        == n
    )  # idempotent
    comp = sim.compare_plans(s, sm.simulation_id)
    assert comp["real"]["label"] == "REAL SIMULATION" and comp["counterfactual"][
        "label"
    ].startswith("COUNTERFACTUAL")
    assert comp["pitquant_original"]["stop_loss"] != comp["user_plan"]["stop_loss"]
    assert sim.replay_simulation(
        s, sm.simulation_id
    ).match  # the counterfactual is not part of the real event log


def test_pitquant_origin_has_no_counterfactual(env: Env) -> None:
    s, cfg, sf, _ = env
    sm = sim.create_simulation(s, cfg, sf, plan_origin="PITQUANT", at=T0)
    sim.update_simulation(s, cfg, sm.simulation_id, LATER)
    assert s.scalars(select(SimulationCounterfactual)).all() == []


def test_explain_lists_every_source_and_version(env: Env) -> None:
    s, cfg, sf, _ = env
    sm = make(env)
    sim.update_simulation(s, cfg, sm.simulation_id, LATER)
    x = sim.explain_simulation(s, sm.simulation_id)
    assert (
        x["snapshot_verified"]
        and x["provenance"]["price"]["source"] == "SYN"
        and x["versions"]["event_engine"] == "sim-engine-2"
    )
    assert x["versions"]["prediction_status"] == "NOT_YET_VALIDATED" and x["provenance"][
        "benchmark"
    ]["kind"] in ("SPY_TOTAL_RETURN_PROXY", None)


def test_update_active_skips_closed_simulations_and_can_target_one(env: Env) -> None:
    s, cfg, sf, _ = env
    a, b = make(env), make(env)
    res = sim.update_active(s, cfg, LATER, a.simulation_id)
    assert [r.simulation_id for r in res] == [a.simulation_id]
    all_ = sim.update_active(s, cfg, LATER)
    assert {r.simulation_id for r in all_} >= {b.simulation_id}
    again = sim.update_active(s, cfg, LATER)
    assert sum(r.new_events for r in again) == 0


def test_http_surface_events_replay_compare_explain_insights_hypothesis(client: TestClient) -> None:
    created = client.post(
        "/simulations",
        json={"security": "SYNF", "plan_origin": "PITQUANT", "as_of": T0.isoformat()},
    )
    if created.status_code != 200:
        pytest.skip(f"no PITQuant setup at this date: {created.text}")
    sid = created.json()["simulation_id"]
    up = client.post(f"/simulations/{sid}/update").json()
    assert "new_events" in up
    assert client.post(f"/simulations/{sid}/update").json()["new_events"] == 0
    assert client.get(f"/simulations/{sid}/events").json()[0]["type"] == "SIMULATION_CREATED"
    assert client.get(f"/simulations/{sid}/replay").json()["match"] is True
    assert client.get(f"/simulations/{sid}/explain").json()["banner"].startswith("PAPER")
    assert client.get(f"/simulations/{sid}/compare").json()["plan_origin"] == "PITQUANT"
    assert client.get("/simulations/insights", params={"by": "origin"}).json()["by"] == "origin"
    assert client.get("/simulations/insights", params={"by": "nope"}).status_code == 422
    h = client.post(
        f"/simulations/{sid}/hypothesis", json={"statement": "s", "created_by": "tester"}
    )
    assert h.json()["status"] == "UNTESTED"
    assert client.get("/simulations/hypotheses").json()[0]["status"] == "UNTESTED"
    assert client.get(f"/simulations/{sid}").json()["events"][0]["sequence"] == 0


def test_a_v0_row_without_event_zero_hash_or_exit_policy_still_updates_with_the_legacy_behaviour(
    env: Env,
) -> None:
    """Rows created before ADR-0036 have no event #0, no snapshot hash and no exit policy: they update (event #0 is written by the first update)."""
    s, cfg, sf, _ = env
    src = make(env)
    cols = {
        c.key: getattr(src, c.key)
        for c in Simulation.__table__.columns
        if c.key not in ("simulation_id", "snapshot_hash", "source_provenance")
    }
    plan = {
        k: v
        for k, v in src.final_simulated_plan.items()
        if k not in ("exit_policy", "exit_fractions", "risk_reward", "sizing", "stop_distance_pct")
    }
    old = Simulation(**{**cols, "final_simulated_plan": plan})
    s.add(old)
    s.flush()
    assert old.snapshot_hash is None and sim.stored_events(s, old.simulation_id) == []
    sim.update_simulation(s, cfg, old.simulation_id, LATER)
    ev = sim.stored_events(s, old.simulation_id)
    assert ev[0].sequence_number == 0 and ev[0].event_type == "SIMULATION_CREATED"
    assert sim.plan_of(old).exit_policy == "LEGACY_HALF_AT_TP1"
    assert sim.replay_simulation(s, old.simulation_id).match
