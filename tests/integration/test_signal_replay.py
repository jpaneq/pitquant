# ruff: noqa: E501, F811, F401
"""Retrospective signal replay (SYNTHETIC SYNF). In memory only, PIT plan at T, outcome on bars after T, split basis, sealed holdout."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pitquant.analyzer.replay import forward_markers, markers_of, retrospective_replay, split_factor
from pitquant.config.settings import Settings
from pitquant.db.models import Simulation, SimulationEvent
from pitquant.simulation import service as sim
from tests.integration.test_analyzer_api import client
from tests.integration.test_simulation_lab import env

Env = tuple[Session, Settings, str, str]
NOW = datetime(2016, 12, 31, 23, tzinfo=UTC)


def replay(env: Env, start: date, end: date, **kw):
    s, cfg, sf, _ = env
    return retrospective_replay(s, cfg, sf, start, end, now=NOW, **kw)


def test_replay_writes_nothing_and_is_labelled_retrospective(env: Env) -> None:
    s, _, _, _ = env
    n_sim = s.scalar(select(func.count()).select_from(Simulation))
    n_ev = s.scalar(select(func.count()).select_from(SimulationEvent))
    r = replay(env, date(2015, 1, 5), date(2016, 11, 30), step_sessions=3)
    assert (
        r["status"] == "OK" and r["writes_to_database"] is False and "RETROSPECTIVE" in r["label"]
    )
    assert {
        "RETROSPECTIVE_NOT_PIT",
        "RULE_BASED_NOT_BACKTEST_VALIDATED",
        "COSTS_NOT_MODELED",
    } <= set(r["summary"]["flags"])
    assert (
        s.scalar(select(func.count()).select_from(Simulation)) == n_sim
        and s.scalar(select(func.count()).select_from(SimulationEvent)) == n_ev
    )  # nothing reaches evidence
    s.rollback()


def test_small_samples_quote_no_rates(env: Env) -> None:
    r = replay(env, date(2015, 1, 5), date(2015, 6, 30), step_sessions=10)
    assert (
        r["summary"]["n_closed"] < 10
        and "INSUFFICIENT_SAMPLE" in r["summary"]["flags"]
        and "hit_rate" not in r["summary"]
    )


@pytest.mark.pit
def test_plan_uses_only_bars_known_at_the_decision(env: Env) -> None:
    from pitquant.analyzer.service import AnalyzerService, clear_cache
    from pitquant.data.calendars.market_calendar import get_calendar

    s, cfg, sf, _ = env
    r = replay(env, date(2015, 1, 5), date(2016, 11, 30), step_sessions=3)
    assert r["trades"], "the synthetic trend must produce at least one plan"
    t = r["trades"][0]
    d = date.fromisoformat(t["decision_date"])
    clear_cache()
    plan = sim._pitquant_plan(
        AnalyzerService(s, cfg).trade_plan(sf, get_calendar("XNYS").session_close(d))
    )
    assert (
        plan is not None
        and t["stop"] == pytest.approx(plan["stop_loss"])
        and t["entry_zone"] == [plan["entry_zone_low"], plan["entry_zone_high"]]
    )
    assert all(
        m["time"] > t["decision_date"] for m in markers_of([t])
    )  # every fill/exit is AFTER the decision session


@pytest.mark.pit
def test_markers_are_in_chart_units_across_a_split(env: Env) -> None:
    # SYNF splits 2:1 on 2016-03-15; a trade decided before it is stored in decision-date units and converted to the chart's split-adjusted basis
    r = replay(env, date(2016, 1, 4), date(2016, 3, 10), step_sessions=2, horizon_sessions=60)
    crossing = [t for t in r["trades"] if t["entry_date"] and t["split_factor"] == 2.0]
    assert crossing, "a pre-split decision must carry factor 2"
    t = crossing[0]
    assert t["entry_price_chart"] == pytest.approx(t["entry_price"] / 2.0)
    assert all(x["price_chart"] == pytest.approx(x["price"] / 2.0) for x in t["exits"])
    assert split_factor([{"ratio": 4.0}, {"ratio": 2.0}]) == 8.0


def test_holdout_is_never_plotted(env: Env) -> None:
    s, cfg, sf, _ = env
    ho = cfg.validation.final_holdout
    # the SYNF bars end in 2016: put the sealed window on the synthetic history to prove decisions and windows touching it are skipped
    from pitquant.config.settings import HoldoutConfig

    sealed = cfg.model_copy(
        update={
            "validation": cfg.validation.model_copy(
                update={
                    "final_holdout": HoldoutConfig(start=date(2016, 5, 2), end=date(2016, 7, 29))
                }
            )
        }
    )
    r = retrospective_replay(
        s,
        sealed,
        sf,
        date(2016, 1, 4),
        date(2016, 11, 30),
        step_sessions=2,
        horizon_sessions=20,
        now=NOW,
    )
    lo, hi = "2016-05-02", "2016-07-29"
    assert r["summary"]["holdout_skipped"] > 0
    for t in r["trades"]:
        assert not (lo <= t["decision_date"] <= hi)
        end = max(x["date"] for x in t["exits"]) if t["exits"] else t["decision_date"]
        assert not (
            t["decision_date"] < lo <= end
        )  # a window that reaches the holdout is skipped, not plotted
    assert all(not (lo <= m["time"] <= hi) for m in r["markers"])
    assert ho.start.year == 2022


def test_forward_markers_come_from_real_simulations_only(env: Env) -> None:
    s, cfg, sf, _ = env
    assert forward_markers(s, sf, NOW) == []  # the replay never creates forward markers
    row = sim.create_simulation(
        s, cfg, sf, at=datetime(2016, 6, 30, 21, tzinfo=UTC), capital=100_000.0, risk_pct=1.0
    )
    fm = forward_markers(s, sf, NOW)
    assert (
        [m["kind"] for m in fm][:1] == ["PLAN"]
        and all(m["origin"] == "MANUAL_SIMULATION" for m in fm)
        and row.simulation_id == fm[0]["simulation_id"]
    )


def test_endpoint_returns_both_layers_separately(client) -> None:
    r = client.get("/analyzer/SYNF/signals", params={"years": 2, "step": 5})
    assert r.status_code == 200
    body = r.json()
    assert (
        body["retrospective"]["label"].startswith("RETROSPECTIVE")
        and body["forward"] == []
        and body["holdout"]["sealed"] is True
    )
    assert client.get("/analyzer/SYNF/signals", params={"profile": "X"}).status_code == 422
