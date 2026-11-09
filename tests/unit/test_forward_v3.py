"""v3 = price + fundamentals (ADR-0066): point-in-time attach, exam once, policy, fund padding."""

from datetime import UTC, date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from pitquant.forward import learning, learning_v3
from pitquant.forward.engine import FEATURES, fit_model, predict, records
from pitquant.forward.fundamentals import FUND_FEATURES, attach
from pitquant.forward.learning import champion, current_policy, run_exam, set_policy

NOW = datetime(2026, 11, 8, 23, tzinfo=UTC)


def bars(seed=1, start=date(2019, 1, 1), end=date(2026, 11, 6)):
    days = list(pd.bdate_range(start, end).date)
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.015, len(days))))
    return pd.DataFrame(
        dict(close=close, high=close * 1.01, low=close * 0.99, volume=rng.uniform(1, 3, len(days))),
        index=days,
    )


def table(frame, seed=2):
    """One fundamentals row per month start, as fund_table would return."""
    starts = sorted({date(d.year, d.month, 1) for d in frame.index})
    rng = np.random.default_rng(seed)
    data = rng.normal(0.1, 0.05, (len(starts), len(FUND_FEATURES)))
    return pd.DataFrame(data, index=starts, columns=FUND_FEATURES)


@pytest.mark.pit
def test_attach_uses_only_months_already_started():
    frame = bars(end=date(2024, 3, 29))
    t = table(frame)
    out = attach(frame, t)
    assert out.loc[date(2024, 2, 29), FUND_FEATURES[0]] == t.loc[date(2024, 2, 1), FUND_FEATURES[0]]
    assert out.loc[date(2024, 3, 1), FUND_FEATURES[0]] == t.loc[date(2024, 3, 1), FUND_FEATURES[0]]
    early = attach(frame, t[t.index >= date(2020, 1, 1)])
    assert early.loc[date(2019, 12, 31), FUND_FEATURES].isna().all()  # nothing known yet
    assert attach(frame, t.iloc[:0])[FUND_FEATURES].isna().all().all()


def test_v3_model_uses_16_inputs_and_funds_pad_missing(session, tmp_path):
    from pitquant.forward import funds

    frame = attach(bars(), table(bars()))
    m = fit_model(
        session,
        "EQUITY",
        {"SYN": frame},
        {},
        tmp_path,
        now=NOW,
        cutoff=date(2026, 10, 1),
        family=learning_v3.V3,
        label="t",
        extra_features=tuple(FUND_FEATURES),
    )
    assert m.payload["feature_names"] == [*FEATURES, *FUND_FEATURES]
    assert len(m.payload["coef"]) == 16
    pred = predict(session, m, "SYN", frame, NOW)
    assert len(pred.payload["features"]) == 16 and pred.payload["features"][-1] is not None
    nav = bars()[["close"]].copy()
    nav["high"] = nav["low"] = nav["signal_close"] = nav["close"]
    nav["volume"] = np.nan
    fp = funds.predict(session, m, "ES0119199000", nav, NOW)
    assert fp.payload["features"][10:] == [None] * 6 and 0 < fp.payload["p_up"] < 1


@pytest.fixture
def universe(monkeypatch):
    frames = {f"S{i}": bars(seed=i) for i in range(3)}
    monkeypatch.setattr(
        learning, "training_frames", lambda *a, **k: ({t: f.copy() for t, f in frames.items()}, {})
    )
    with_fund = {t: attach(f, table(f, seed=10 + i)) for i, (t, f) in enumerate(frames.items())}
    monkeypatch.setattr(
        learning_v3,
        "fund_frames",
        lambda *a, **k: ({t: f.copy() for t, f in with_fund.items()}, {}),
    )
    return frames


@pytest.mark.pit
def test_exam_v3_requires_v2_exam_and_runs_once(session, tmp_path, universe, monkeypatch):
    with pytest.raises(ValueError, match="V2_EXAM_REQUIRED"):
        learning_v3.run_exam_v3(session, tmp_path, NOW)
    fit_model(session, "EQUITY", dict(universe), {}, tmp_path, now=NOW)  # V1
    run_exam(session, "EQUITY", tmp_path, NOW)
    exam = learning_v3.run_exam_v3(session, tmp_path, NOW)
    p = exam.payload
    assert p["arms"]["B_PRICE_V2"]["n"] == p["arms"]["C_PRICE_FUND_V3"]["n"] == p["n"] > 0
    assert p["fundamental_coverage"][FUND_FEATURES[0]] == 1.0
    protos = [
        r for r in records(session, "EXAM_PROTOCOL") if "C_PRICE_FUND_V3" in r.payload["arms"]
    ]
    assert protos and protos[0].created_at <= exam.created_at
    refits = [
        r for r in records(session, "REPLAY_MODEL") if r.payload.get("family") == learning_v3.V3
    ]
    assert refits and all(
        r.payload["train_target_end"] < r.payload["version"][5:] + "-01" for r in refits
    )
    expected = "LEARNING_V3" if p["v3_minus_v2_gain"]["mean"] > 0 else "LEARNING"
    assert current_policy(session, "EQUITY")["policy"] in (expected, "FROZEN_V1")
    from sklearn.linear_model import LogisticRegression

    monkeypatch.setattr(LogisticRegression, "fit", lambda *_: pytest.fail("refit"))
    assert learning_v3.run_exam_v3(session, tmp_path, NOW).record_id == exam.record_id


def test_champion_follows_v3_policy(session, tmp_path, universe):
    fit_model(session, "EQUITY", dict(universe), {}, tmp_path, now=NOW)
    run_exam(session, "EQUITY", tmp_path, NOW)
    learning_v3.run_exam_v3(session, tmp_path, NOW)
    refit = learning_v3.monthly_refit_v3(session, tmp_path, NOW)
    set_policy(session, "EQUITY", "LEARNING_V3", "TEST", {}, NOW + timedelta(seconds=5))
    assert champion(session, "EQUITY").record_id == refit.record_id


@pytest.mark.parametrize(
    "policy,low,high,expected",
    [("LEARNING", 0.01, 0.02, "LEARNING_V3"), ("LEARNING", -0.01, 0.02, None),
     ("LEARNING_V3", -0.02, -0.01, "LEARNING"), ("FROZEN_V1", 0.01, 0.02, None)],
)  # fmt: skip
def test_forward_switch_v2_v3(session, monkeypatch, policy, low, high, expected):
    set_policy(session, "EQUITY", policy, "TEST", {}, NOW)
    cmp = {"pairs": 300, "dates": 30, "v3_gain": {"low90": low, "high90": high}}
    monkeypatch.setattr(learning_v3, "forward_comparison_v3", lambda *_: cmp)
    out = learning_v3.review_policy_v3(session, NOW + timedelta(seconds=1))
    assert out["switched"] is (expected is not None)
    assert current_policy(session, "EQUITY")["policy"] == (expected or policy)


def test_v2_and_v3_refits_same_month_do_not_collide(session, tmp_path):
    frame = attach(bars(), table(bars()))
    kw = dict(now=NOW, cutoff=date(2026, 10, 1), label="2026-11")
    v2 = fit_model(session, "EQUITY", {"SYN": frame}, {}, tmp_path, family=learning.LEARNING, **kw)
    v3 = fit_model(session, "EQUITY", {"SYN": frame}, {}, tmp_path, family=learning_v3.V3,
                   extra_features=tuple(FUND_FEATURES), **kw)  # fmt: skip
    assert v2.record_id != v3.record_id
    assert v3.payload["dataset_file"] != v2.payload["dataset_file"]
