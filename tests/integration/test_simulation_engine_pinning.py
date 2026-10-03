# ruff: noqa: E501, F401, F811, RUF059
"""Version-pinned simulation engines (ADR-0037): a simulation keeps the engine it was created under; update, replay and counterfactual resolve it by
that pin; a missing engine fails closed; event engine/schema versions are checked. SYNTHETIC data (SYNF)."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from datetime import UTC, date, datetime
from typing import Any

import pandas as pd
import pytest
from sqlalchemy.orm import Session

from pitquant import cli
from pitquant.config.settings import Settings
from pitquant.core.errors import ImmutableRecordError
from pitquant.db.models import Simulation, SimulationCounterfactual, SimulationEvent
from pitquant.simulation import registry
from pitquant.simulation import service as sim
from pitquant.simulation.engine import Evaluation, PlanLevels
from tests.integration.test_analyzer_api import client
from tests.integration.test_simulation_lab import LATER, T0, env, make, plan_for

Env = tuple[Session, Settings, str, str]


class DifferentEngine(registry.SimulationEngineV1):
    """A fixture engine with a deliberately different rule: a simulation NEVER expires. Only used to prove pinning."""

    version: str = "v_test_different"
    event_schema_version: int = 2
    event_labels: tuple[str, ...] = ("v_test_different",)
    folds = 0

    def evaluate(
        self, plan: PlanLevels, bars: pd.DataFrame, decision_date: date, **kw: Any
    ) -> Evaluation:
        return super().evaluate(
            dataclasses.replace(plan, expiration=None), bars, decision_date, **kw
        )

    def fold_events(self, events: list[dict[str, Any]], plan: PlanLevels) -> dict[str, Any]:
        DifferentEngine.folds += 1
        return super().fold_events(events, plan)


@pytest.fixture
def two_engines(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    DifferentEngine.folds = 0
    monkeypatch.setitem(registry.SIMULATION_ENGINES, "v_test_different", DifferentEngine())
    yield


def use_current(monkeypatch: pytest.MonkeyPatch, version: str) -> None:
    monkeypatch.setattr(registry, "CURRENT_SIMULATION_ENGINE_VERSION", version)


def never_stops(s: Session, cfg: Settings, sf: str, origin: str = "USER_DEFINED") -> sim.PlanInput:
    p = plan_for(s, cfg, sf)
    p.entry_type = "MARKET_REFERENCE"
    p.stop_loss, p.invalidation_level, p.target_1, p.target_2 = (
        p.entry_zone_high * 0.2,
        None,
        p.entry_zone_high * 5,
        None,
    )
    return p


def events_of(s: Session, sm: Simulation) -> list[SimulationEvent]:
    return sim.stored_events(s, sm.simulation_id)


def test_a_new_simulation_is_pinned_to_the_current_engine_and_the_pin_is_immutable(
    env: Env, two_engines: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    s, cfg, sf, _ = env
    a = make(env)
    assert (
        a.simulation_engine_version == "v1"
        and events_of(s, a)[0].engine_version == "v1"
        and events_of(s, a)[0].event_schema_version == 1
    )
    use_current(monkeypatch, "v_test_different")
    b = make(env)
    assert (
        b.simulation_engine_version == "v_test_different"
        and events_of(s, b)[0].event_schema_version == 2
    )
    a.simulation_engine_version = "v_test_different"
    with pytest.raises(ImmutableRecordError):
        s.flush()
    s.rollback()


def test_an_existing_simulation_stays_on_v1_after_the_current_engine_changes(
    env: Env, two_engines: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE regression test: v1 simulation -> CURRENT becomes another engine -> update still uses v1 (no divergence, no mixed events)."""
    s, cfg, sf, _ = env
    p = never_stops(s, cfg, sf)
    old = sim.create_simulation(s, cfg, sf, plan_origin="USER_DEFINED", plan=p, at=T0)
    sim.update_simulation(s, cfg, old.simulation_id, datetime(2016, 7, 15, 23, tzinfo=UTC))
    before = [(e.sequence_number, e.event_type, e.payload_json) for e in events_of(s, old)]
    use_current(monkeypatch, "v_test_different")
    r = sim.update_simulation(s, cfg, old.simulation_id, LATER)
    assert r.status == "OK"
    after = events_of(s, old)
    assert [
        (e.sequence_number, e.event_type, e.payload_json) for e in after[: len(before)]
    ] == before
    assert {e.engine_version for e in after} == {"v1"} and {
        e.event_schema_version for e in after
    } == {1}
    assert any(e.event_type == "EXPIRED" for e in after), "v1 expires the simulation at its horizon"
    new = sim.create_simulation(s, cfg, sf, plan_origin="USER_DEFINED", plan=p, at=T0)
    sim.update_simulation(s, cfg, new.simulation_id, LATER)
    assert new.simulation_engine_version == "v_test_different"
    assert not any(e.event_type == "EXPIRED" for e in events_of(s, new)), (
        "the different engine's rule applies to ITS simulation only"
    )
    assert {e.engine_version for e in events_of(s, new)} == {"v_test_different"}
    assert (
        sim.latest_outcome(s, old.simulation_id).state
        != sim.latest_outcome(s, new.simulation_id).state
    )


def test_two_engines_are_processed_in_one_run_each_with_its_own_savepoint(
    env: Env, two_engines: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    s, cfg, sf, _ = env
    p = never_stops(s, cfg, sf)
    a = sim.create_simulation(s, cfg, sf, plan_origin="USER_DEFINED", plan=p, at=T0)
    use_current(monkeypatch, "v_test_different")
    b = sim.create_simulation(s, cfg, sf, plan_origin="USER_DEFINED", plan=p, at=T0)
    res = {r.simulation_id: r for r in sim.update_active(s, cfg, LATER)}
    assert res[a.simulation_id].status == res[b.simulation_id].status == "OK"
    assert (
        sim.latest_outcome(s, a.simulation_id).engine_version == "v1"
        and sim.latest_outcome(s, b.simulation_id).engine_version == "v_test_different"
    )


def test_replay_uses_the_pinned_engine_and_reports_it(
    env: Env, two_engines: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    s, cfg, sf, _ = env
    use_current(monkeypatch, "v_test_different")
    b = sim.create_simulation(
        s, cfg, sf, plan_origin="USER_DEFINED", plan=never_stops(s, cfg, sf), at=T0
    )
    sim.update_simulation(s, cfg, b.simulation_id, LATER)
    use_current(monkeypatch, "v1")
    r = sim.replay_simulation(s, b.simulation_id)
    assert (
        r.match
        and r.engine_version == "v_test_different"
        and DifferentEngine.folds == 1
        and r.event_schema_versions == (2,)
    )
    a = make(env)
    sim.update_simulation(s, cfg, a.simulation_id, LATER)
    r1 = sim.replay_simulation(s, a.simulation_id)
    assert (
        r1.match and r1.engine_version == "v1" and DifferentEngine.folds == 1
    )  # the v1 simulation never touched the other engine


def test_counterfactual_uses_the_pinned_engine_not_the_current_one(
    env: Env, two_engines: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    s, cfg, sf, _ = env
    p = plan_for(s, cfg, sf)
    a = sim.create_simulation(s, cfg, sf, plan_origin="USER_MODIFIED", plan=p, at=T0)
    use_current(monkeypatch, "v_test_different")
    b = sim.create_simulation(s, cfg, sf, plan_origin="USER_MODIFIED", plan=p, at=T0)
    for x in (a, b):
        sim.update_simulation(s, cfg, x.simulation_id, LATER)
    ca = s.query(SimulationCounterfactual).filter_by(simulation_id=a.simulation_id).one()
    cb = s.query(SimulationCounterfactual).filter_by(simulation_id=b.simulation_id).one()
    assert (ca.simulation_engine_version, cb.simulation_engine_version) == (
        "v1",
        "v_test_different",
    )


def clone_with_engine(s: Session, src: Simulation, version: str) -> Simulation:
    cols = {
        c.key: getattr(src, c.key)
        for c in Simulation.__table__.columns
        if c.key not in ("simulation_id", "simulation_engine_version")
    }
    row = Simulation(**cols, simulation_engine_version=version)
    s.add(row)
    s.flush()
    return row


def test_a_missing_engine_fails_closed_and_is_not_reported_as_divergence(
    env: Env, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    s, cfg, sf, _ = env
    ghost = clone_with_engine(s, make(env), "v9")
    with pytest.raises(registry.EngineVersionUnavailable, match="ENGINE_VERSION_UNAVAILABLE"):
        sim.update_simulation(s, cfg, ghost.simulation_id, LATER)
    with pytest.raises(registry.EngineVersionUnavailable):
        sim.replay_simulation(s, ghost.simulation_id)
    with pytest.raises(registry.EngineVersionUnavailable):
        sim.evaluate_counterfactual(
            s, clone_with_engine(s, make(env, origin="USER_MODIFIED"), "v9"), LATER
        )
    res = {r.simulation_id: r for r in sim.update_active(s, cfg, LATER, ghost.simulation_id)}
    assert (
        res[ghost.simulation_id].status == "ENGINE_VERSION_UNAVAILABLE"
        and res[ghost.simulation_id].new_events == 0
    )
    assert sim.stored_events(s, ghost.simulation_id) == [], "nothing was run by another engine"
    s.commit()
    monkeypatch.setattr(cli, "get_settings", lambda: cfg)
    monkeypatch.setattr(cli, "make_engine", lambda _u: s.get_bind().engine)
    assert cli.main(["simulation-replay", ghost.simulation_id, "--verify"]) == 1
    assert "ENGINE_VERSION_UNAVAILABLE" in capsys.readouterr().out
    assert (
        cli.main(
            [
                "simulation-update",
                "--simulation-id",
                ghost.simulation_id,
                "--as-of",
                LATER.isoformat(),
            ]
        )
        == 1
    )
    assert "ENGINE_VERSION_UNAVAILABLE" in capsys.readouterr().out


def test_creating_with_an_unregistered_current_engine_fails_closed(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    s, cfg, sf, _ = env
    use_current(monkeypatch, "v9")
    with pytest.raises(registry.EngineVersionUnavailable):
        make(env)


def test_replay_verify_detects_an_event_written_by_another_engine(env: Env) -> None:
    s, cfg, sf, _ = env
    a = make(env)
    sim.update_simulation(s, cfg, a.simulation_id, LATER)
    n = len(events_of(s, a))
    s.add(
        SimulationEvent(
            simulation_id=a.simulation_id,
            sequence_number=n,
            event_type="OBSERVATION_RECORDED",
            occurred_at=T0.date(),
            payload_json={"horizon": "T+99"},
            engine_version="v_other",
            event_schema_version=1,
        )
    )
    s.flush()
    r = sim.replay_simulation(s, a.simulation_id)
    assert not r.match and any("v_other" in d and "pinned" in d for d in r.differences)


def test_events_written_before_the_pin_carry_the_v1_era_label_and_are_accepted(env: Env) -> None:
    s, cfg, sf, _ = env
    a = make(env)
    e0 = events_of(s, a)[0]
    s.connection().exec_driver_sql(
        "UPDATE simulation_events SET engine_version='sim-engine-2' WHERE event_id=?",
        (e0.event_id,),
    )  # simulate a pre-ADR-0037 row
    s.expire_all()
    assert registry.resolve_engine("v1").event_labels.count("sim-engine-2") == 1
    sim.update_simulation(s, cfg, a.simulation_id, LATER)
    assert sim.replay_simulation(s, a.simulation_id).match


def test_the_migration_contract_has_no_in_place_option() -> None:
    c = registry.EngineMigrationContract("s1", "v1", "v2", "COUNTERFACTUAL")
    assert (
        registry.EngineMigrationContract("s1", "v1", "v2", "FORK").migration_type == "FORK"
        and c.target_engine_version == "v2"
    )
    with pytest.raises(ValueError, match="in-place"):
        registry.EngineMigrationContract("s1", "v1", "v2", "IN_PLACE")
    with pytest.raises(ValueError, match="different"):
        registry.EngineMigrationContract("s1", "v1", "v1", "FORK")
    assert not any(
        n in dir(registry) for n in ("migrate", "migrate_simulation", "upgrade_simulation")
    )


def test_insights_never_mix_engines_silently(
    env: Env, two_engines: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    s, cfg, sf, _ = env
    first = make(env)
    use_current(monkeypatch, "v_test_different")
    second = make(env)
    for x in (first, second):
        sim.update_simulation(s, cfg, x.simulation_id, LATER)
    by_engine = sim.insights(s, "simulation_engine_version")
    assert {x["segment"] for x in by_engine["segments"]} == {
        "engine v1",
        "engine v_test_different",
    } and by_engine["mixed_engines"] is False
    other = sim.insights(s, "origin")
    assert other["mixed_engines"] is True and other["engines"] == {"v1": 1, "v_test_different": 1}
