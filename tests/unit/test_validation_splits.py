"""Walk-forward, purging, embargo, label availability and holdout (§29–35)."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from dateutil.relativedelta import relativedelta

from pitquant.backtest.labels import label_window
from pitquant.core.errors import HoldoutAccessError, LabelLeakageError
from pitquant.core.types import Horizon, ValidationMode
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.validation.splits import (
    HoldoutGuard,
    PurgedWalkForward,
    assert_training_labels_available,
)
from tests.conftest import ny, utc

pytestmark = pytest.mark.pit


def make_obs(
    horizon_months: int, start: str = "2000-01-01", end: str = "2025-12-01"
) -> pd.DataFrame:
    t = pd.date_range(start, end, freq="MS", tz="UTC") + pd.Timedelta(hours=14, minutes=30)
    label_end = pd.DatetimeIndex([x + pd.DateOffset(months=horizon_months) for x in t])
    return pd.DataFrame(
        {
            "t_exec": t,
            "label_end": label_end,
            "label_available_at": label_end + pd.Timedelta(hours=1),
        }
    )


HOLDOUT = HoldoutGuard(date(2022, 10, 1), date(2025, 9, 30))


def splitter(**kw: object) -> PurgedWalkForward:
    base: dict[str, object] = dict(
        first_test_start=date(2010, 1, 1),
        train_min_months=60,
        validation_months=24,
        test_months=12,
        step_months=12,
        embargo=relativedelta(months=12),
        holdout=HOLDOUT,
    )
    base.update(kw)
    return PurgedWalkForward(**base)  # type: ignore[arg-type]


def test_label_window_from_real_calendar() -> None:
    w = label_window(get_calendar("XNYS"), ny(2019, 8, 1, 16, 0), Horizon.M12)
    assert w.t_exec == utc(2019, 8, 2, 13, 30)
    assert w.label_end == utc(2020, 8, 3, 20, 0)  # 2020-08-02 is Sunday -> Monday close
    assert w.label_available_at == utc(2020, 8, 3, 21, 0)


def test_label_availability() -> None:
    """§33 example: retrain at 2020-01-01; a 12M signal from 2019-08-01 must be excluded."""
    obs = make_obs(12)
    for fold in splitter().split(obs):
        tr = obs.loc[fold.train_idx]
        assert (tr["label_available_at"] <= fold.train_cutoff).all()
        assert fold.n_label_unavailable > 0
    cutoff = utc(2020, 1, 1)
    series = obs.loc[obs["t_exec"] < pd.Timestamp(cutoff), "label_available_at"]
    with pytest.raises(LabelLeakageError):
        assert_training_labels_available(series, cutoff)


def test_purged_training() -> None:
    obs = make_obs(12)
    for fold in splitter().split(obs):
        tr = obs.loc[fold.train_idx]
        val_start = fold.test_start - pd.DateOffset(months=24)
        assert (tr["label_end"] < val_start).all()  # no outcome interval reaches evaluation
        assert set(fold.train_idx).isdisjoint(fold.val_idx)
        assert set(fold.train_idx).isdisjoint(fold.test_idx)
        assert tr["t_exec"].max() < obs.loc[fold.test_idx, "t_exec"].min()  # no shuffle


def test_embargo() -> None:
    obs = make_obs(6)  # short labels: availability alone would leave a 6M gap; embargo widens it
    folds = list(splitter(embargo=relativedelta(months=12)).split(obs))
    assert all(f.n_embargoed > 0 for f in folds)
    for f in folds:
        val_start = f.test_start - pd.DateOffset(months=24)
        tr = obs.loc[f.train_idx]
        assert (tr["t_exec"] < val_start - pd.DateOffset(months=12)).all()
    no_embargo = list(splitter(embargo=relativedelta(months=0)).split(obs))
    assert len(no_embargo[0].train_idx) > len(folds[0].train_idx)


def test_validation_labels_known_at_decision_time() -> None:
    obs = make_obs(12)
    for fold in splitter().split(obs):
        va = obs.loc[fold.val_idx]
        assert (va["label_available_at"] <= fold.decision_time).all()


def test_holdout_never_used_for_training() -> None:
    obs = make_obs(12)
    folds = list(splitter().split(obs))
    hs = pd.Timestamp("2022-10-01", tz="UTC")
    for f in folds:
        used = obs.loc[list(f.train_idx) + list(f.val_idx) + list(f.test_idx)]
        assert (used["t_exec"] < hs).all()
        assert (used["label_end"] < hs).all()  # strict: labels may not peek into holdout
    with pytest.raises(HoldoutAccessError):
        HOLDOUT.assert_development_safe(obs)


def test_holdout_unlock_requires_frozen_model_and_is_logged() -> None:
    logged: list[str] = []
    g = HoldoutGuard(
        date(2022, 10, 1), date(2025, 9, 30), on_access=lambda a: logged.append(a.model_version)
    )
    with pytest.raises(HoldoutAccessError):
        g.unlock(model_version="m1", model_frozen=False, reason="final eval", requested_by="jairo")
    with pytest.raises(HoldoutAccessError):
        g.unlock(model_version="m1", model_frozen=True, reason="  ", requested_by="jairo")
    g.unlock(model_version="m1", model_frozen=True, reason="final eval", requested_by="jairo")
    assert logged == ["m1"] and g.is_unlocked_for("m1") and len(g.log) == 1


def test_rolling_window_limits_train_history() -> None:
    obs = make_obs(12)
    folds = list(splitter(mode=ValidationMode.ROLLING, rolling_train_months=48).split(obs))
    expanding = list(splitter().split(obs))
    assert len(folds[-1].train_idx) < len(expanding[-1].train_idx)
    first = obs.loc[folds[-1].train_idx, "t_exec"].min()
    val_start = folds[-1].test_start - pd.DateOffset(months=24)
    assert first >= val_start - pd.DateOffset(months=48)


def test_naive_observation_times_rejected() -> None:
    obs = make_obs(12)
    obs["t_exec"] = obs["t_exec"].dt.tz_localize(None)
    with pytest.raises(ValueError):
        next(splitter().split(obs))
