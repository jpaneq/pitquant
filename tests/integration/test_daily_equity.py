# ruff: noqa: E501, F811, F401
"""Daily forward paper routine (SYNTHETIC SYNF/SYNO): one run per universe, idempotent per day, frozen, never back-dated."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pitquant.config.settings import Settings
from pitquant.db.models_lab import StrategyDecision, StrategyRun
from pitquant.strategy import service as strat
from pitquant.strategy.daily import DAILY_STRATEGY_ID, daily_test, resolve_universe
from pitquant.strategy.spec import StrategyError
from tests.integration.test_analyzer_api import client
from tests.integration.test_simulation_lab import env

Env = tuple[Session, Settings, str, str]
D0 = datetime(2016, 6, 30, 23, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(strat, "CLOCK", lambda: D0)


def runs(s: Session) -> list[StrategyRun]:
    return list(s.scalars(select(StrategyRun).where(StrategyRun.strategy_id == DAILY_STRATEGY_ID)))


def test_first_call_creates_a_forward_run_and_records_one_decision(env: Env) -> None:
    s, cfg, _, _ = env
    out = daily_test(s, cfg, ["SYNF"], as_of=D0)
    assert (
        out["run_created"] is True
        and out["strategy"] == f"{DAILY_STRATEGY_ID} v1"
        and out["label"].startswith("RULE_BASED_NOT_BACKTEST_VALIDATED")
    )
    assert len(out["new_decisions"]) == 1 and out["new_decisions"][0]["decision"] in (
        "ENTER",
        "NO_ACTION",
    )
    assert {"INSUFFICIENT_SAMPLE", "COSTS_NOT_MODELED"} <= set(
        out["flags"]
    ) and "SYNTHETIC_TEST_DATA" not in out["flags"]  # a real forward run, never flagged synthetic
    assert (
        len(runs(s)) == 1
        and runs(s)[0].run_kind == "FORWARD_PAPER"
        and runs(s)[0].activated_at == D0
    )


def test_second_call_the_same_day_adds_nothing_and_reuses_the_run(env: Env) -> None:
    s, cfg, _, _ = env
    first = daily_test(s, cfg, ["SYNF"], as_of=D0)
    n = s.scalar(select(func.count()).select_from(StrategyDecision))
    again = daily_test(s, cfg, ["SYNF"], as_of=D0 + timedelta(minutes=30))
    assert (
        again["run_id"] == first["run_id"]
        and again["run_created"] is False
        and again["new_decisions"] == []
    )
    assert (
        s.scalar(select(func.count()).select_from(StrategyDecision)) == n
    )  # one decision per security per daily period


def test_next_day_decides_again_in_the_same_run(env: Env) -> None:
    s, cfg, _, _ = env
    first = daily_test(s, cfg, ["SYNF"], as_of=D0)
    nxt = daily_test(s, cfg, ["SYNF"], as_of=D0 + timedelta(days=1))
    assert (
        nxt["run_id"] == first["run_id"]
        and len(nxt["new_decisions"]) == 1
        and nxt["n_decisions_total"] == 2
    )


def test_a_stopped_run_is_replaced_by_a_new_one_never_reused(env: Env) -> None:
    s, cfg, sf, _ = env
    a = daily_test(s, cfg, ["SYNF"], as_of=D0)
    old = s.get_one(StrategyRun, a["run_id"])
    strat.stop_run(s, old)
    assert strat.run_status(s, old) == "STOPPED" and old.universe == [
        sf
    ]  # the universe of a run is frozen
    b = daily_test(s, cfg, ["SYNF"], as_of=D0 + timedelta(days=1))
    assert b["run_created"] is True and b["run_id"] != a["run_id"]


def test_forward_ticks_are_never_back_dated(env: Env) -> None:
    s, cfg, _, _ = env
    daily_test(s, cfg, ["SYNF"], as_of=D0)
    with pytest.raises(StrategyError, match="before the activation"):
        daily_test(s, cfg, ["SYNF"], as_of=D0 - timedelta(days=30))


def test_unknown_ticker_is_refused_not_guessed(env: Env) -> None:
    s, cfg, _, _ = env
    with pytest.raises(StrategyError, match="exactly one security"):
        daily_test(s, cfg, ["NOPE"], as_of=D0)


def test_default_universe_skips_securities_without_enough_price_history(env: Env) -> None:
    s, _, sf, so = env
    assert sf in resolve_universe(s, None)
    ids = resolve_universe(s, None)
    assert so not in ids  # SYNO has fundamentals only: no bars
    assert isinstance(ids, list)
