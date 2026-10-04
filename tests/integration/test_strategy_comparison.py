# ruff: noqa: E501, F401, F811
"""Strategy comparison (ADR-0039): same inputs, several strategies, the BUY_AND_HOLD baseline, honest flags. SYNTHETIC data (SYNF)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.config.settings import Settings
from pitquant.db.models_lab import StrategyDecision, StrategyRunResult
from pitquant.strategy import service as strat
from pitquant.strategy.evaluation import compare_runs, evaluate_run, input_series_hash, run_metrics
from pitquant.strategy.spec import (
    preset_buy_and_hold,
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
ASOF = datetime(2016, 8, 31, 23, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def fixture_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PITQUANT_E2E_FIXTURE", "1")


def runs(
    env: Env, names: list[str] | None = None
) -> tuple[Session, Settings, dict[str, strat.StrategyRun]]:
    s, cfg, sf, _ = env
    synthetic_prediction(s, sf, D0, 6, p=0.72, expected=0.08)
    synthetic_prediction(s, sf, D1, 6, p=0.48, expected=0.01)
    specs = {
        "PRED": preset_prediction_only("CMP_PRED"), "PLAN": preset_trade_plan_only("CMP_PLAN", min_rr1=0.1), "HYB": preset_hybrid("CMP_HYB"), "BH": preset_buy_and_hold("CMP_BH"),
    }  # fmt: skip
    out = {}
    for k, spec in specs.items():
        spec.max_positions = 4
        run = strat.create_run(s, cfg, save_strategy(s, spec, "tester"), "SYNTHETIC", [env[2]])
        strat.run_synthetic(s, cfg, run, [D0, D1])
        out[k] = run
    return s, cfg, out


def test_four_strategies_share_the_same_input_series(env: Env) -> None:
    s, cfg, r = runs(env)
    hashes = {k: input_series_hash(s, run) for k, run in r.items()}
    assert len(set(hashes.values())) == 1, hashes  # same predictions, same dates, same universe
    cmp = compare_runs(
        s, cfg, [r["PRED"].run_id, r["PLAN"].run_id, r["HYB"].run_id, r["BH"].run_id], ASOF
    )
    assert cmp["comparable"] is True and cmp["synthetic"] is True
    fam = {row["family"]: row for row in cmp["rows"]}
    assert set(fam) == {"PREDICTION_ONLY", "TRADE_PLAN_ONLY", "HYBRID", "BUY_AND_HOLD"}
    assert all(
        "NOT_COMPARABLE_INPUTS" not in row["flags"] and "SYNTHETIC_TEST_DATA" in row["flags"]
        for row in cmp["rows"]
    )
    assert cmp["baseline"]["name"] == "BUY_AND_HOLD" and cmp["baseline"]["portfolio"] is not None


def test_different_inputs_are_not_presented_as_comparable(env: Env) -> None:
    s, cfg, r = runs(env)
    sf = env[2]
    spec = preset_trade_plan_only("CMP_OTHER_DATES", min_rr1=0.1)
    other = strat.create_run(s, cfg, save_strategy(s, spec, "tester"), "SYNTHETIC", [sf])
    strat.run_synthetic(s, cfg, other, [D0, D1, D1 + timedelta(days=7)])  # one more decision date
    cmp = compare_runs(s, cfg, [r["PLAN"].run_id, other.run_id], ASOF)
    assert cmp["comparable"] is False and all(
        "NOT_COMPARABLE_INPUTS" in row["flags"] for row in cmp["rows"]
    )


def test_prediction_strategy_exits_on_deterioration_while_buy_and_hold_never_sells(
    env: Env,
) -> None:
    s, cfg, r = runs(env)
    pm, _ = run_metrics(s, cfg, r["PRED"], ASOF)
    assert pm["trades"]["n_trades"] == 1 and pm["exit_reasons"] == {"PREDICTION_DETERIORATION": 1}
    assert pm["portfolio"]["days"] > 0 and pm["portfolio_definition"].startswith(
        "EQUAL_WEIGHT_SLEEVES"
    )
    bh, _ = run_metrics(s, cfg, r["BH"], ASOF)
    assert (
        bh["trades"]["n_trades"] == 1 and bh["exit_reasons"] == {} and bh["portfolio"]["days"] > 0
    )


def test_every_result_states_its_sample_costs_and_synthetic_status(env: Env) -> None:
    s, cfg, r = runs(env)
    m, flags = run_metrics(s, cfg, r["PRED"], ASOF)
    assert (
        {"INSUFFICIENT_SAMPLE", "COSTS_NOT_MODELED", "SYNTHETIC_TEST_DATA"} <= set(flags)
        and m["trades"]["sample"] == "INSUFFICIENT_SAMPLE"
        and m["trades"]["hit_rate"] is None
    )  # N=1: no rate
    assert m["risk_free"] == "RF_ZERO" and m["costs"] == {
        "commission_bps": 0.0,
        "slippage_bps": 0.0,
    }


def test_underperforming_buy_and_hold_is_flagged_and_excess_is_stated(env: Env) -> None:
    s, cfg, r = runs(env)
    m, flags = run_metrics(s, cfg, r["PRED"], ASOF)
    sr, bh = m["portfolio"]["total_return"], m["buy_and_hold"]["total_return"]
    assert m["excess_vs_buy_and_hold"] == pytest.approx(sr - bh)
    assert ("UNDERPERFORMS_BUY_AND_HOLD" in flags) == (sr < bh)


def test_costs_in_basis_points_reduce_the_result(env: Env) -> None:
    s, cfg, sf, _ = env
    synthetic_prediction(s, sf, D0, 6, p=0.72, expected=0.08)
    synthetic_prediction(s, sf, D1, 6, p=0.48, expected=0.01)
    totals = {}
    for tag, bps in (("FREE", 0.0), ("COSTLY", 50.0)):
        spec = preset_prediction_only(f"COST_{tag}")
        spec.costs = {"commission_bps": bps, "slippage_bps": bps}
        run = strat.create_run(s, cfg, save_strategy(s, spec, "tester"), "SYNTHETIC", [sf])
        strat.run_synthetic(s, cfg, run, [D0, D1])
        m, flags = run_metrics(s, cfg, run, ASOF)
        totals[tag] = (m["portfolio"]["total_return"], "COSTS_NOT_MODELED" in flags)
    assert (
        totals["COSTLY"][0] < totals["FREE"][0]
        and totals["FREE"][1] is True
        and totals["COSTLY"][1] is False
    )


def test_evaluate_run_is_append_only_and_carries_the_input_hash(env: Env) -> None:
    s, cfg, r = runs(env)
    a, b = (
        evaluate_run(s, cfg, r["PRED"], ASOF),
        evaluate_run(s, cfg, r["PRED"], ASOF + timedelta(days=1)),
    )
    assert (
        a.result_id != b.result_id
        and a.prediction_series_hash == input_series_hash(s, r["PRED"])
        and len(
            s.scalars(
                select(StrategyRunResult).where(StrategyRunResult.run_id == r["PRED"].run_id)
            ).all()
        )
        == 2
    )
