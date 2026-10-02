# ruff: noqa: E501
"""Research Lab foundation (ADR-0030): walk-forward, holdout, metrics, contracts, plan state machine."""

from __future__ import annotations

from datetime import UTC, date, datetime

import numpy as np
import pandas as pd
import pytest

from pitquant.core.errors import HoldoutAccessError, PITQuantError
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.research.baselines import BASELINES, ELASTIC_NET, FORBIDDEN_TARGETS, LOGISTIC
from pitquant.research.metrics import (
    classification_metrics,
    regression_metrics,
    roc_auc,
    spearman,
)
from pitquant.research.missingness import blocking_summary, missingness_report
from pitquant.research.prediction_contract import PredictionRecord
from pitquant.research.trade_plan_backtest import PlanSpec, PlanState, evaluate_plan
from pitquant.research.walkforward import (
    Fold,
    WalkForwardConfig,
    assert_fold_clear_of_holdout,
    dry_run,
    plan_folds,
    usable_dates,
)

HOLD = (date(2022, 10, 1), date(2025, 9, 30))


def monthly(y0: int, y1: int) -> list[date]:
    cal = get_calendar("XNYS")
    return [cal.session_on_or_after(date(y, m, 1)) for y in range(y0, y1 + 1) for m in range(1, 13)]


@pytest.mark.pit
def test_label_window_reaching_holdout_is_excluded() -> None:
    ds = usable_dates(monthly(2011, 2026), 6, HOLD)
    assert ds and max(ds) < date(2022, 4, 2)  # 6M label from 2022-04 reaches 2022-10
    assert not [d for d in ds if HOLD[0] <= d <= HOLD[1]]
    assert max(usable_dates(monthly(2011, 2026), 12, HOLD)) < max(ds)


@pytest.mark.pit
@pytest.mark.parametrize("kind", ["EXPANDING", "ROLLING"])
def test_folds_never_touch_holdout_and_embargo_holds(kind: str) -> None:
    cfg = WalkForwardConfig(window_kind=kind, purge_months=1, embargo_months=1)  # type: ignore[arg-type]
    folds = plan_folds(monthly(2011, 2026), cfg, HOLD)
    assert folds
    for f in folds:
        assert_fold_clear_of_holdout(f, 6, HOLD)
        assert f.train_end < f.validation_start
        assert f.validation_end < HOLD[0]
    if kind == "EXPANDING":
        assert len({f.train_start for f in folds}) == 1


def test_dry_run_empty_when_too_little_history() -> None:
    assert dry_run(monthly(2020, 2021), WalkForwardConfig(), HOLD) == []


@pytest.mark.pit
def test_fold_inside_holdout_raises() -> None:
    bad = Fold(0, date(2012, 1, 1), date(2020, 1, 1), date(2022, 11, 1), date(2022, 12, 1), 1, 1)
    with pytest.raises(HoldoutAccessError):
        assert_fold_clear_of_holdout(bad, 6, HOLD)


def test_metrics_basic() -> None:
    y = np.array([1.0, 2.0, 3.0, 4.0])
    assert spearman(y, y) == pytest.approx(1.0)
    assert regression_metrics(y, y).rmse == pytest.approx(0.0)
    assert roc_auc(np.array([0, 0, 1, 1]), np.array([0.1, 0.2, 0.8, 0.9])) == pytest.approx(1.0)
    assert (
        classification_metrics(np.array([0, 1, 1, 0]), np.array([0.2, 0.8, 0.7, 0.3])).brier < 0.1
    )


def test_missingness_by_year_and_security() -> None:
    rows = [
        {
            "security_id": "A",
            "decision_session": "2020-01-02",
            "features": {"f": 1.0},
            "feature_reasons": {},
            "blocking_reason": [],
        },
        {
            "security_id": "B",
            "decision_session": "2021-01-04",
            "features": {"f": None},
            "feature_reasons": {"f": "NO_TAG"},
            "blocking_reason": ["NO_PRICE_HISTORY"],
        },
    ]
    rep = missingness_report(rows, ["f"], {"A": "Tech"})
    assert rep["f"]["missing"] == 1 and rep["f"]["by_year"]["2021"]["missing"] == 1
    assert rep["f"]["by_sector"]["UNKNOWN"]["missing"] == 1
    assert blocking_summary(rows) == {"NO_PRICE_HISTORY": 1}


def test_prediction_contract() -> None:
    t0, t1 = datetime(2020, 1, 2, tzinfo=UTC), datetime(2020, 1, 3, tzinfo=UTC)
    kw = dict(
        experiment_id="e",
        model_id="m",
        model_version="1",
        security_id="s",
        feature_snapshot_id="f",
        expected_excess_return=0.01,
    )
    PredictionRecord(generated_at=t1, decision_at=t0, probability=None, **kw)  # type: ignore[arg-type]
    with pytest.raises(PITQuantError):
        PredictionRecord(generated_at=t0, decision_at=t1, probability=None, **kw)  # type: ignore[arg-type]
    with pytest.raises(PITQuantError):  # probability without calibration
        PredictionRecord(generated_at=t1, decision_at=t0, probability=0.6, **kw)  # type: ignore[arg-type]
    with pytest.raises(Exception):  # noqa: B017 — naive datetime
        PredictionRecord(generated_at=datetime(2020, 1, 3), decision_at=t0, probability=None, **kw)  # type: ignore[arg-type]


def test_baselines_fixed_and_hashed() -> None:
    assert set(BASELINES) == {ELASTIC_NET.kind, LOGISTIC.kind}
    assert ELASTIC_NET.config_hash == ELASTIC_NET.config_hash != LOGISTIC.config_hash
    assert not {ELASTIC_NET.target, LOGISTIC.target} & FORBIDDEN_TARGETS


def _bars(rows: list[tuple[str, float, float, float, float]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["d", "open", "high", "low", "close"])
    df.index = [date.fromisoformat(x) for x in df.pop("d")]
    return df


SPEC = PlanSpec(
    date(2024, 1, 2), entry=100, entry_kind="LIMIT_BELOW", stop=95, target_1=110, target_2=120
)


def test_plan_not_triggered_and_expired() -> None:
    ev = evaluate_plan(SPEC, _bars([("2024-01-03", 105, 108, 102, 106)]))
    assert ev.state in (PlanState.PENDING, PlanState.NOT_TRIGGERED, PlanState.EXPIRED)
    assert ev.entered_on is None


def test_plan_ambiguous_when_entry_and_stop_same_candle() -> None:
    ev = evaluate_plan(SPEC, _bars([("2024-01-03", 102, 103, 94, 96)]))
    assert ev.state is PlanState.AMBIGUOUS_INTRABAR


def test_plan_ambiguous_when_stop_and_target_same_candle() -> None:
    ev = evaluate_plan(
        SPEC, _bars([("2024-01-03", 101, 101, 99, 100), ("2024-01-04", 100, 112, 94, 100)])
    )
    assert ev.state is PlanState.AMBIGUOUS_INTRABAR


def test_plan_gap_through_stop_stops_at_open() -> None:
    ev = evaluate_plan(
        SPEC, _bars([("2024-01-03", 101, 101, 99, 100), ("2024-01-04", 90, 92, 88, 91)])
    )
    assert ev.state is PlanState.STOPPED


def test_plan_requires_bars_after_decision() -> None:
    with pytest.raises(ValueError):
        evaluate_plan(SPEC, _bars([("2024-01-02", 100, 101, 99, 100)]))
