# ruff: noqa: E501, F401, F811, RUF059
"""``pitquant simulation-update`` / ``simulation-replay`` through ``cli.main`` (argparse, --as-of parsing, exit codes, per-simulation isolation)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from pitquant import cli
from pitquant.config.settings import Settings
from pitquant.db.models import Simulation, SimulationEvent
from pitquant.simulation import service as sim
from tests.integration.test_analyzer_api import client
from tests.integration.test_simulation_lab import LATER, env, make

Env = tuple[Session, Settings, str, str]


@pytest.fixture
def cli_env(env: Env, monkeypatch: pytest.MonkeyPatch) -> Iterator[Env]:
    """``cli.main`` opens its own session on ``settings.database.url``: point it at the fixture database (commit first)."""
    s, cfg, _sf, _so = env
    s.commit()
    monkeypatch.setattr(cli, "get_settings", lambda: cfg)
    monkeypatch.setattr(cli, "make_engine", lambda _url: s.get_bind().engine)
    yield env


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str]:
    code = cli.main(list(argv))
    return code, capsys.readouterr().out


def test_update_twice_second_run_reports_zero_new_events(
    cli_env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    s, cfg, sf, _ = cli_env
    sm = make(cli_env)
    s.commit()
    code, out = run(
        capsys, "simulation-update", "--as-of", "2016-12-31T23:00:00", "--json"
    )  # naive ISO string => UTC
    first = json.loads(out)
    assert code == 0 and first["new_events"] > 0 and first["failed"] == 0
    code, out = run(capsys, "simulation-update", "--as-of", "2016-12-31T23:00:00+00:00")
    assert code == 0 and "new_events = 0" in out
    assert [
        d
        for d in json.loads(
            run(capsys, "simulation-update", "--as-of", "2016-12-31T23:00:00Z", "--json")[1]
        )["detail"]
        if d["simulation_id"] == sm.simulation_id
    ] in ([], [d for d in []])


def test_single_simulation_update_and_replay_verify(
    cli_env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    s, cfg, sf, _ = cli_env
    sm = make(cli_env)
    s.commit()
    code, out = run(
        capsys,
        "simulation-update",
        "--simulation-id",
        sm.simulation_id,
        "--as-of",
        LATER.isoformat(),
        "--json",
    )
    assert code == 0 and json.loads(out)["simulations"] == 1
    code, out = run(capsys, "simulation-replay", sm.simulation_id, "--verify")
    assert code == 0 and out.startswith("MATCH")


def test_replay_verify_exits_nonzero_on_a_difference(
    cli_env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    from pitquant.db.models import SimulationOutcome

    s, cfg, sf, _ = cli_env
    sm = make(cli_env)
    sim.update_simulation(s, cfg, sm.simulation_id, LATER)
    lo = sim.latest_outcome(s, sm.simulation_id)
    s.add(
        SimulationOutcome(
            simulation_id=sm.simulation_id,
            evaluated_at=LATER,
            state="TP2",
            is_closed=True,
            entry_date=lo.entry_date,
            entry_price=1.0,
            exit_date=lo.exit_date,
            timeline=[],
            details={},
            event_count=lo.event_count,
        )
    )
    s.commit()
    code, out = run(capsys, "simulation-replay", sm.simulation_id, "--verify")
    assert code == 1 and "DIFFERENCES" in out
    code, _ = run(capsys, "simulation-replay", sm.simulation_id)
    assert code == 0  # without --verify a difference is reported, not an error


def test_one_failing_simulation_does_not_roll_back_the_others(
    cli_env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    s, cfg, sf, _ = cli_env
    good, bad = make(cli_env), make(cli_env)
    s.commit()
    # corrupt the stored log of `bad`: a later bar-dependent event that the engine will not reproduce
    sim.update_simulation(s, cfg, bad.simulation_id, datetime(2016, 7, 15, 23, tzinfo=UTC))
    s.commit()
    ev = sim.stored_events(s, bad.simulation_id)[-1]
    s.connection().execute(
        text("UPDATE simulation_events SET payload_json = :p WHERE event_id = :i"),
        {"p": json.dumps({"state_after": "STOPPED", "forged": True}), "i": ev.event_id},
    )  # raw SQL: the ORM guard is bypassed on purpose (PostgreSQL has its trigger)
    s.commit()
    code, out = run(capsys, "simulation-update", "--as-of", LATER.isoformat(), "--json")
    res = {d["simulation_id"]: d for d in json.loads(out)["detail"]}
    assert (
        code == 1
        and res[bad.simulation_id]["status"] == "DIVERGED"
        and "EVENT_LOG_DIVERGENCE" in res[bad.simulation_id]["error"]
    )
    assert res[good.simulation_id]["status"] == "OK" and res[good.simulation_id]["new_events"] > 0
    s.expire_all()
    assert (
        len(sim.stored_events(s, good.simulation_id)) > 1
    )  # the good simulation's events were committed despite the failure


def test_a_late_benchmark_value_is_not_a_divergence(cli_env: Env) -> None:
    s, cfg, sf, _ = cli_env
    sm = make(cli_env)
    sim.update_simulation(s, cfg, sm.simulation_id, LATER)
    bar = next(e for e in sim.stored_events(s, sm.simulation_id) if e.event_type == "BAR_PROCESSED")
    forged = {**bar.payload_json, "bench_close": 12345.0}
    assert sim._norm(
        {"type": bar.event_type, "date": str(bar.occurred_at), "payload": forged}
    ) == sim._norm(sim._as_dict(bar))
