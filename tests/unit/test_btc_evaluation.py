# ruff: noqa: E501
"""Follow-up routine for frozen BTC predictions (SYNTHETIC fixture only)."""

from datetime import timedelta
from pathlib import Path

import pytest

from pitquant.btc.contracts import Cohort, digest, prediction_contract
from pitquant.btc.evaluation import analysis, evaluate_due, historical_returns
from pitquant.btc.fixtures import T0, load_synthetic_btc
from pitquant.btc.models import BTCFeatureSnapshot, BTCPredictionSnapshot, BTCResearchRecord
from pitquant.btc.research import freeze
from pitquant.btc.simulation import create


def numeric_snapshot(session, original, forecasts: dict[int, tuple[float, float]]):
    snap = BTCFeatureSnapshot(
        decision_at=T0, cohort=Cohort.SYNTHETIC, feature_version="SYNTHETIC_FORECAST", data_version=original.data_version, model_version="SYNTHETIC_MODEL",
        strategy_version=original.strategy_version, simulation_engine_version=original.simulation_engine_version, commit_sha=original.commit_sha, payload=original.payload, snapshot_hash=digest({"s": "n"}),
    )  # fmt: skip
    session.add(snap)
    session.flush()
    for horizon, (expected, p_up) in forecasts.items():
        payload = {
            **prediction_contract(horizon),
            "status": "EXPERIMENTAL_NOT_VALIDATED",
            "model_version": "SYNTHETIC_MODEL",
            "expected_return": expected,
            "p_up": p_up,
        }
        session.add(
            BTCPredictionSnapshot(
                snapshot_id=snap.snapshot_id,
                horizon=horizon,
                payload=payload,
                prediction_hash=digest(payload),
            )
        )
    session.flush()


@pytest.fixture
def seeded(session, tmp_path: Path):
    load_synthetic_btc(session, tmp_path)
    original = freeze(session, T0, Cohort.SYNTHETIC)
    numeric_snapshot(session, original, {7: (0.07, 0.8), 30: (-0.02, 0.4)})
    return original


def test_immature_predictions_are_pending_not_errors(session, seeded):
    out = evaluate_due(session, T0 + timedelta(days=3), Cohort.SYNTHETIC)
    assert (
        out["revealed"] == []
        and out["awaiting_target_bar"] == []
        and out["pending_not_mature"] >= 7
    )
    a = analysis(session, T0 + timedelta(days=3), Cohort.SYNTHETIC)
    assert (
        a["counts"]["EVALUATED"] == 0
        and a["next_maturity"] == (T0 + timedelta(days=7)).isoformat()
        and a["horizons"] == {}
    )
    pending = next(i for i in a["items"] if i["horizon"] == 7 and i["predicted"] == 0.07)
    assert pending["state"] == "PENDING" and pending["days_remaining"] == pytest.approx(4.0)


def test_matured_predictions_are_revealed_once_and_idempotently(session, seeded):
    now = T0 + timedelta(days=31)
    first = evaluate_due(session, now, Cohort.SYNTHETIC)
    assert (
        len(first["revealed"]) >= 4 and first["pending_not_mature"] >= 1
    )  # 7D and 30D matured, 90D+ pending
    n = len(session.query(BTCResearchRecord).filter_by(kind="REVEAL_OUTCOME").all())
    assert (
        evaluate_due(session, now, Cohort.SYNTHETIC)["revealed"] == []
        and len(session.query(BTCResearchRecord).filter_by(kind="REVEAL_OUTCOME").all()) == n
    )


@pytest.mark.pit
def test_analysis_compares_with_history_and_flags_small_samples(session, seeded):
    now = T0 + timedelta(days=31)
    evaluate_due(session, now, Cohort.SYNTHETIC)
    a = analysis(session, now, Cohort.SYNTHETIC)
    h7 = a["horizons"]["7"]
    ev = next(
        i
        for i in a["items"]
        if i["state"] == "EVALUATED" and i["horizon"] == 7 and i["predicted"] == 0.07
    )
    assert (
        ev["actual"] == pytest.approx(0.1)
        and ev["error"] == pytest.approx(-0.03)
        and ev["direction_correct"] is True
    )
    assert (
        h7["n_scored"] == 1
        and "INSUFFICIENT_SAMPLE" in h7["flags"]
        and h7["beats_baselines"] is None
    )  # one observation proves nothing
    assert (
        h7["mae"] == pytest.approx(0.03)
        and h7["baseline_zero_mae"] == pytest.approx(0.1)
        and h7["skill_vs_zero"] == pytest.approx(0.7)
        and h7["direction_hit_rate"] == 1.0
    )
    assert (
        h7["brier_p_up"] == pytest.approx(0.04) and "RETROSPECTIVE_HISTORY_NOT_PIT" in h7["flags"]
    )
    assert (
        ev["hist_n"] > 0 and 0 <= ev["hist_percentile_of_actual"] <= 1
    )  # history known up to the decision date only
    assert a["math_ok"] is True and a["warning"].startswith("NOT_VALIDATED")


def test_historical_returns_skip_missing_days():
    from datetime import UTC, datetime

    d = lambda n: datetime(2026, 1, n, tzinfo=UTC)  # noqa: E731
    closes = {d(1): 100.0, d(2): 110.0, d(4): 121.0}  # day 3 missing
    assert historical_returns(closes, 1) == [pytest.approx(0.1)]  # 4th has no 3rd: not interpolated
    assert create is not None
