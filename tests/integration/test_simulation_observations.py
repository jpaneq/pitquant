# ruff: noqa: E501, F401, F811, RUF059
"""Historical observations (ADR-0037): cadence, point-in-time, immutability, descriptive facts, post-mortem sources, bars_to_entry.
SYNTHETIC data (SYNF)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.analyzer.service import AnalyzerService
from pitquant.config.settings import Settings
from pitquant.core.errors import ImmutableRecordError
from pitquant.db.models import Simulation, SimulationObservation, SimulationOutcome
from pitquant.simulation import observations as obs
from pitquant.simulation import service as sim
from pitquant.simulation.engine import PlanLevels, evaluate, fold_events
from tests.integration.test_analyzer_api import client
from tests.integration.test_simulation_lab import LATER, T0, env, make, plan_for
from tests.unit.test_feature_engine_v0 import add_fact

Env = tuple[Session, Settings, str, str]


def long_sim(env: Env) -> Simulation:
    """A simulation that stays open for ~120 sessions (far stop, far target) so late observations exist."""
    s, cfg, sf, _ = env
    p = plan_for(s, cfg, sf)
    p.entry_type, p.stop_loss, p.invalidation_level, p.target_1, p.target_2 = (
        "MARKET_REFERENCE",
        p.entry_zone_high * 0.2,
        None,
        p.entry_zone_high * 5,
        None,
    )
    return sim.create_simulation(
        s, cfg, sf, plan_origin="USER_DEFINED", plan=p, at=T0, horizon_sessions=120
    )


def periodic(s: Session, sm: Simulation) -> list[SimulationObservation]:
    return list(
        s.scalars(
            select(SimulationObservation)
            .where(
                SimulationObservation.simulation_id == sm.simulation_id,
                SimulationObservation.kind == "PERIODIC",
            )
            .order_by(SimulationObservation.source_bar_date)
        )
    )


# ───────────────────────────────────────────── cadence (pure)
def ev(t: str, d: str, **p: Any) -> dict[str, Any]:
    return {"type": t, "date": d, "payload": p}


def bar_events(n: int) -> list[dict[str, Any]]:
    days = [d.date().isoformat() for d in pd.bdate_range("2024-01-02", periods=n)]
    return [ev("SIMULATION_CREATED", "2024-01-01", state_after="CREATED")] + [
        ev("BAR_PROCESSED", d, close=100.0) for d in days
    ]


def test_cadence_is_t1_t5_t20_then_every_20_bars_counted_in_bars_not_calendar_days() -> None:
    m = obs.milestones(bar_events(65))
    days = [d.date().isoformat() for d in pd.bdate_range("2024-01-02", periods=65)]
    assert [(d, lbl) for d, lbls in m.items() for lbl in lbls] == [
        (days[0], "T+1"),
        (days[4], "T+5"),
        (days[19], "T+20"),
        (days[39], "T+40"),
        (days[59], "T+60"),
    ]


def test_key_events_and_final_are_merged_into_one_observation_per_date() -> None:
    e = bar_events(5)
    e += [
        ev("ENTRY_FILLED", "2024-01-03", price=100.0, state_after="ENTERED"),
        ev("TP1_TOUCHED", "2024-01-08", target=110.0),
        ev("STOP_TRIGGERED", "2024-01-09", price=95.0, state_after="STOPPED"),
    ]
    m = obs.milestones(e)
    assert m["2024-01-03"] == ["EVENT:ENTRY_FILLED"]
    assert m["2024-01-08"] == [
        "EVENT:TP1_TOUCHED",
        "T+5",
    ]  # the 5th BAR is Jan 8 (the weekend is skipped)
    assert m["2024-01-09"] == [
        "EVENT:STOP_TRIGGERED",
        "FINAL",
    ]  # ONE observation for the closing date, not two identical snapshots


def test_an_open_simulation_has_no_final_observation_and_a_creation_only_log_has_none() -> None:
    assert obs.milestones(bar_events(3)) == {"2024-01-02": ["T+1"]}
    assert obs.milestones(bar_events(0)) == {}


# ───────────────────────────────────────────── recording: point in time, idempotent, immutable
def test_update_records_the_observations_with_their_versions_and_is_idempotent(env: Env) -> None:
    s, cfg, sf, _ = env
    sm = long_sim(env)
    r1 = sim.update_simulation(s, cfg, sm.simulation_id, LATER)
    rows = periodic(s, sm)
    assert r1.new_observations == len(rows) > 0 and r1.observation_errors == []
    labels = [o.horizon_label for o in rows]
    assert (
        any(lbl.startswith("T+1") for lbl in labels)
        and any("T+5" in lbl for lbl in labels)
        and any("T+20" in lbl for lbl in labels)
    )
    assert all(
        o.observation_schema_version == 1
        and o.analyzer_version == "analyzer-v0"
        and o.feature_version
        for o in rows
    )
    r2 = sim.update_simulation(s, cfg, sm.simulation_id, LATER)
    assert r2.new_observations == 0 and len(periodic(s, sm)) == len(rows)
    # the legacy event OBSERVATION_RECORDED (price only) is untouched
    assert any(
        e.event_type == "OBSERVATION_RECORDED" for e in sim.stored_events(s, sm.simulation_id)
    )


def test_each_observation_uses_only_what_was_available_at_its_bar_date(env: Env) -> None:
    s, cfg, sf, _ = env
    sm = long_sim(env)
    sim.update_simulation(s, cfg, sm.simulation_id, LATER)
    rows = periodic(s, sm)
    assert len(rows) >= 3
    for o in rows:
        p, d = o.payload, o.source_bar_date
        assert o.observed_at.date() <= LATER.date()
        assert str(p["technical_snapshot"]["last_session"]) <= str(
            d
        )  # no bar after the observation date
        assert p["technical_snapshot"]["as_of"].startswith(o.observed_at.isoformat()[:10])
        assert str(p["valuation_snapshot"]["price_date"]) <= str(
            d
        )  # valuation priced with a bar <= the date
        assert (
            p["fundamental_snapshot"]["latest_filing_available_at"] is None
            or p["fundamental_snapshot"]["latest_filing_available_at"] <= o.observed_at.isoformat()
        )
        for z in (p["support_resistance_snapshot"].get("supports") or []) + (
            p["support_resistance_snapshot"].get("resistances") or []
        ):
            assert str(z["calculation_at"]) <= str(
                d
            )  # S/R recomputed ONLY with the history of that date
        assert p["quote"]["session"] <= str(d)
        assert p["market_regime_snapshot"]["trend"] == p["technical_snapshot"]["trend"]


def test_a_filing_published_after_an_observation_is_not_in_it_but_is_in_a_later_one(
    env: Env,
) -> None:
    s, cfg, sf, _ = env
    sm = long_sim(env)
    # a quarterly filing for the period ending 2016-06-30, made available on 2016-09-02 (after T+20 ≈ 2016-07-29)
    # a fiscal-year (March) 10-K for the period ending 2016-03-31, made available on 2016-09-02 (after T+20 ≈ 2016-07-29)
    for tag, v in (("Revenues", 1300.0), ("NetIncomeLoss", 130.0)):
        add_fact(
            s,
            sf,
            tag,
            date(2015, 4, 1),
            date(2016, 3, 31),
            v,
            datetime(2016, 9, 2, 21, tzinfo=UTC),
            form="10-K",
        )
    s.flush()
    sim.update_simulation(s, cfg, sm.simulation_id, datetime(2016, 12, 31, 23, tzinfo=UTC))
    rows = periodic(s, sm)
    early = [o for o in rows if o.source_bar_date < date(2016, 9, 2)]
    late = [o for o in rows if o.source_bar_date >= date(2016, 9, 3)]
    assert early and late
    for o in early:
        assert str(o.payload["fundamental_snapshot"]["latest_period"]) < "2016-03-31"
    assert any(
        str(o.payload["fundamental_snapshot"]["latest_period"]) == "2016-03-31" for o in late
    )


def test_a_recorded_observation_is_immutable_and_current_analysis_never_rewrites_history(
    env: Env,
) -> None:
    s, cfg, sf, _ = env
    sm = make(env)
    sim.update_simulation(s, cfg, sm.simulation_id, LATER)
    before = {
        o.observation_id: (o.payload, o.horizon_label, o.analyzer_version) for o in periodic(s, sm)
    }
    AnalyzerService(s, cfg).analysis(
        sf, datetime(2026, 10, 3, tzinfo=UTC)
    )  # a CURRENT analysis (today)
    sim.thesis_snapshot(s, cfg, sm.simulation_id, LATER)
    sim.update_simulation(s, cfg, sm.simulation_id, LATER)
    after = {
        o.observation_id: (o.payload, o.horizon_label, o.analyzer_version)
        for o in periodic(s, sm)
        if o.observation_id in before
    }
    assert after == before
    o = periodic(s, sm)[0]
    o.payload = {"tampered": True}
    with pytest.raises(ImmutableRecordError):
        s.flush()
    s.rollback()


def test_a_different_analyzer_version_does_not_recompute_an_existing_observation(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    s, cfg, sf, _ = env
    sm = long_sim(env)
    sim.update_simulation(s, cfg, sm.simulation_id, datetime(2016, 8, 15, 23, tzinfo=UTC))
    first = {o.observation_id: o.analyzer_version for o in periodic(s, sm)}
    monkeypatch.setattr(obs, "ANALYZER_VERSION", "analyzer-v9")
    sim.update_simulation(s, cfg, sm.simulation_id, LATER)
    rows = periodic(s, sm)
    assert {
        o.observation_id: o.analyzer_version for o in rows if o.observation_id in first
    } == first  # old rows keep their version
    assert {o.analyzer_version for o in rows if o.observation_id not in first} == {
        "analyzer-v9"
    }  # a NEW observation carries the new one


def test_an_analyzer_failure_is_reported_and_never_blocks_the_event_log(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    s, cfg, sf, _ = env
    sm = make(env)

    def boom(*_a: Any, **_k: Any) -> Any:
        raise RuntimeError("analyzer unavailable")

    monkeypatch.setattr(AnalyzerService, "fundamentals", boom)
    r = sim.update_simulation(s, cfg, sm.simulation_id, LATER)
    assert (
        r.new_events > 0
        and r.new_observations == 0
        and r.observation_errors
        and "analyzer unavailable" in r.observation_errors[0]
    )
    assert sim.replay_simulation(s, sm.simulation_id).match
    monkeypatch.undo()
    assert (
        sim.update_simulation(s, cfg, sm.simulation_id, LATER).new_observations > 0
    )  # retried by the next update


def test_the_holdout_is_never_analysed(env: Env) -> None:
    s, cfg, sf, _ = env
    sm = make(env)
    sim.update_simulation(s, cfg, sm.simulation_id, LATER)
    assert all(
        not (
            cfg.validation.final_holdout.start
            <= o.source_bar_date
            <= cfg.validation.final_holdout.end
        )
        for o in periodic(s, sm)
    )


# ───────────────────────────────────────────── descriptive facts
def fake_sim(**over: Any) -> Any:
    base = dict(
        technical_snapshot={"trend": {"state": "UPTREND"}, "risk": {"vol63": 0.2}}, price_snapshot={"price": 100.0}, support_resistance_snapshot={"supports": [{"lower": 95.0}], "resistances": [{"upper": 110.0}]},
        valuation_snapshot={"current": {"pe": 20.0}}, fundamental_snapshot={"latest_period": "2015-12-31", "latest_filing_available_at": "2016-02-20"},
        market_regime_snapshot={"trend": {"state": "UPTREND"}, "overextension": {"state": "NORMAL"}},
    )  # fmt: skip
    return SimpleNamespace(**{**base, **over})


def obs_payload(**over: Any) -> dict[str, Any]:
    base = {
        "price": 100.0, "technical_snapshot": {"trend": {"state": "UPTREND"}, "risk": {"vol63": 0.2}}, "valuation_snapshot": {"current": {"pe": 20.0}},
        "fundamental_snapshot": {"latest_period": "2015-12-31", "latest_filing_available_at": "2016-02-20"}, "market_regime_snapshot": {"trend": {"state": "UPTREND"}, "overextension": {"state": "NORMAL"}},
    }  # fmt: skip
    return {**base, **over}


def facts(**over: Any) -> dict[str, dict[str, Any]]:
    return {f["fact"]: f for f in obs.thesis_facts(fake_sim(), obs_payload(**over), "obs-1")}


def test_no_fact_when_nothing_changed() -> None:
    assert facts() == {}


def test_trend_support_resistance_volatility_valuation_fundamental_and_regime_facts() -> None:
    f = facts(price=90.0, technical_snapshot={"trend": {"state": "DOWNTREND"}, "risk": {"vol63": 0.3}}, valuation_snapshot={"current": {"pe": 15.0}},
              fundamental_snapshot={"latest_period": "2016-03-31", "latest_filing_available_at": "2016-05-10"}, market_regime_snapshot={"trend": {"state": "DOWNTREND"}, "overextension": {"state": "NORMAL"}})  # fmt: skip
    assert set(f) == {
        "trend_changed",
        "support_broken",
        "volatility_expanded",
        "valuation_compressed",
        "fundamental_snapshot_changed",
        "regime_changed",
    }
    assert (
        f["trend_changed"]["t0"] == "UPTREND"
        and f["trend_changed"]["observed"] == "DOWNTREND"
        and f["trend_changed"]["source_observation_id"] == "obs-1"
    )
    assert (
        "no threshold is validated" in f["volatility_expanded"]["definition"]
        and "judgement" in f["fundamental_snapshot_changed"]["definition"]
    )
    assert set(facts(price=120.0)) == {"resistance_broken"} and set(
        facts(valuation_snapshot={"current": {"pe": 25.0}})
    ) == {"valuation_expanded"}


def test_a_fact_needs_both_sides_to_exist_nothing_is_invented() -> None:
    assert (
        facts(
            technical_snapshot={},
            valuation_snapshot={},
            fundamental_snapshot={},
            market_regime_snapshot={},
        )
        == {}
    )


def test_trend_flip_only_for_a_reversal() -> None:
    assert obs.trend_flip("STRONG_UPTREND", "DOWNTREND") and obs.trend_flip("DOWNTREND", "UPTREND")
    assert not obs.trend_flip("STRONG_UPTREND", "UPTREND") and not obs.trend_flip(None, "UPTREND")


def test_postmortem_derives_its_flags_from_the_recorded_observation_with_source_ids(
    env: Env,
) -> None:
    s, cfg, sf, _ = env
    EARLY = datetime(2016, 7, 15, 23, tzinfo=UTC)
    p = plan_for(s, cfg, sf)
    p.entry_type = "MARKET_REFERENCE"
    sm = sim.create_simulation(s, cfg, sf, plan_origin="USER_DEFINED", plan=p, at=T0)
    sim.update_simulation(s, cfg, sm.simulation_id, EARLY)
    sim.close_manual(s, cfg, sm.simulation_id, at=EARLY, price=float(p.entry_zone_high))
    sim.update_simulation(s, cfg, sm.simulation_id, EARLY)
    last = sim.latest_periodic(s, sm.simulation_id)
    assert last is not None and last.payload["labels"]
    payload = dict(last.payload)
    payload["technical_snapshot"] = {
        **payload["technical_snapshot"],
        "trend": {"state": "DOWNTREND"},
    }
    s.add(
        SimulationObservation(
            simulation_id=sm.simulation_id,
            observed_at=EARLY,
            kind="PERIODIC",
            payload=payload,
            horizon_label="FINAL|crafted",
            source_bar_date=date(2016, 7, 16),
            observation_schema_version=1,
            analyzer_version="analyzer-v0",
            feature_version="v0.2",
        )
    )
    s.flush()
    flags = {
        f["flag"]: f
        for f in sim.postmortem_facts(s, cfg, sm.simulation_id, EARLY)["diagnostic_flags"]
    }
    assert "TREND_REVERSED" in flags, "UPTREND -> DOWNTREND is a reversal"
    assert (
        flags["TREND_REVERSED"]["source_observation_ids"]
        and flags["TREND_REVERSED"]["observation_bar_date"] == "2016-07-16"
        and "cause" not in str(flags["TREND_REVERSED"]).lower().replace("no cause", "")
    )


def test_thesis_evolution_is_read_only_and_lists_versions_and_facts(env: Env) -> None:
    s, cfg, sf, _ = env
    sm = make(env)
    sim.update_simulation(s, cfg, sm.simulation_id, LATER)
    before = [o.payload for o in periodic(s, sm)]
    ev_ = sim.thesis_evolution(s, sm.simulation_id)
    assert [e["label"] for e in ev_] == [o.horizon_label for o in periodic(s, sm)] and all(
        e["observation_schema_version"] == 1 and isinstance(e["facts"], list) for e in ev_
    )
    assert [o.payload for o in periodic(s, sm)] == before


# ───────────────────────────────────────────── bars_to_entry
D0 = date(2024, 1, 11)  # Thursday


def bars(rows: list[tuple[str, float, float, float, float]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["d", "open", "high", "low", "close"])
    df.index = [date.fromisoformat(x) for x in df.pop("d")]
    return df


LIM = PlanLevels("LIMIT", 100.0, 100.0, 95.0, 110.0, exit_policy="TRACK_TARGETS_ONLY")


def test_bars_to_entry_is_zero_for_market_reference_at_t0() -> None:
    plan = PlanLevels(
        "MARKET_REFERENCE", 100.0, 100.0, 95.0, 110.0, exit_policy="TRACK_TARGETS_ONLY"
    )
    e = evaluate(plan, bars([("2024-01-12", 100, 101, 99, 100)]), D0, reference_price=100.0)
    assert e.metrics["bars_to_entry"] == 0 and fold_events(e.events, plan)["bars_to_entry"] == 0


def test_bars_to_entry_is_one_when_the_first_bar_fills() -> None:
    e = evaluate(LIM, bars([("2024-01-12", 101, 102, 99, 100)]), D0)
    assert e.metrics["bars_to_entry"] == 1 and fold_events(e.events, LIM)["bars_to_entry"] == 1


def test_bars_to_entry_counts_market_bars_not_calendar_days_across_weekend_and_holiday() -> None:
    """Thu 2024-01-11 decision; bars Fri 12th, (Sat/Sun/Mon 15th MLK closed: no bars), Tue 16th fills => 2 bars, 5 calendar days."""
    rows = [("2024-01-12", 104, 105, 102, 103), ("2024-01-16", 103, 104, 99, 100)]
    e = evaluate(LIM, bars(rows), D0)
    assert (
        e.metrics["bars_to_entry"] == 2
        and e.metrics["days_waiting_entry"] == 5
        and e.metrics["days_to_entry"] == 5
    )  # days_waiting_entry is UNCHANGED
    assert fold_events(e.events, LIM)["bars_to_entry"] == 2


def test_bars_to_entry_is_none_while_waiting() -> None:
    e = evaluate(LIM, bars([("2024-01-12", 104, 105, 102, 103)]), D0)
    assert e.metrics["bars_to_entry"] is None and "bars_to_entry" not in fold_events(e.events, LIM)


def test_bars_to_entry_is_persisted_and_replay_verified(env: Env) -> None:
    s, cfg, sf, _ = env
    p = plan_for(s, cfg, sf)
    sm = sim.create_simulation(s, cfg, sf, plan_origin="USER_DEFINED", plan=p, at=T0)
    sim.update_simulation(s, cfg, sm.simulation_id, LATER)
    out = sim.latest_outcome(s, sm.simulation_id)
    if out.entry_date is not None:
        assert out.bars_to_entry is not None and out.bars_to_entry >= 1
    r = sim.replay_simulation(s, sm.simulation_id)
    assert r.match
    q = plan_for(s, cfg, sf)
    q.entry_type = "MARKET_REFERENCE"
    m = sim.create_simulation(s, cfg, sf, plan_origin="USER_DEFINED", plan=q, at=T0)
    sim.update_simulation(s, cfg, m.simulation_id, LATER)
    assert (
        sim.latest_outcome(s, m.simulation_id).bars_to_entry == 0
        and sim.replay_simulation(s, m.simulation_id).match
    )


def test_update_reports_bars_loaded_and_bars_new(env: Env) -> None:
    s, cfg, sf, _ = env
    sm = make(env)
    a = sim.update_simulation(s, cfg, sm.simulation_id, datetime(2016, 7, 15, 23, tzinfo=UTC))
    b = sim.update_simulation(s, cfg, sm.simulation_id, datetime(2016, 7, 15, 23, tzinfo=UTC))
    assert a.bars_new == a.bars_loaded > 0 or a.bars_new <= a.bars_loaded
    assert b.bars_new == 0 and b.new_events == 0 and b.bars_loaded == a.bars_loaded
    c = sim.update_simulation(s, cfg, sm.simulation_id, datetime(2016, 7, 29, 23, tzinfo=UTC))
    assert (
        c.bars_loaded > a.bars_loaded and c.bars_new == c.bars_loaded - a.bars_new
        if not sim.latest_outcome(s, sm.simulation_id).is_closed
        else True
    )


def test_nothing_is_observed_on_or_before_the_decision_date() -> None:
    """A MARKET_REFERENCE entry is dated T0: its event must not create an observation that merely repeats the T0 snapshot."""
    e = bar_events(2)
    e.insert(1, ev("ENTRY_FILLED", "2024-01-01", price=100.0, state_after="ENTERED"))
    assert obs.milestones(e) == {"2024-01-02": ["T+1"]}
