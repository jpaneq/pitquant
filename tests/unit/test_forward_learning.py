"""Forward learning (ADR-0064): exam once, no leakage into refits, pre-registered policy rules."""

from datetime import UTC, date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from pitquant.forward import learning
from pitquant.forward.engine import fit_model, records
from pitquant.forward.learning import (
    LEARNING,
    champion,
    cluster_interval,
    current_policy,
    monthly_refit,
    review_policy,
    run_exam,
    set_policy,
)

NOW = datetime(2026, 11, 8, 12, tzinfo=UTC)


def bars(start=date(2022, 1, 1), end=date(2026, 11, 7), seed=7):
    index = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.03, len(index))))
    return pd.DataFrame(
        dict(
            close=close, high=close * 1.02, low=close * 0.98, volume=rng.uniform(1, 3, len(index))
        ),
        index=index,
    )


@pytest.fixture
def btc(monkeypatch):
    frame = bars()
    monkeypatch.setattr(learning, "training_frames", lambda *a, **k: ({"BTC": frame.copy()}, {}))
    return frame


def v1(session, tmp_path, frame):
    return fit_model(session, "BTC", {"BTC": frame}, {}, tmp_path, now=NOW)


def test_cluster_interval_resamples_whole_clusters():
    values = np.array([1.0, 1.0, -1.0, -1.0])
    out = cluster_interval(values, ["a", "a", "b", "b"])
    assert out["clusters"] == 2 and out["mean"] == 0
    assert out["low90"] == -1 and out["high90"] == 1
    assert cluster_interval(np.ones(10), range(10))["low90"] == 1


@pytest.mark.pit
def test_exam_is_preregistered_frozen_and_run_once(session, tmp_path, btc, monkeypatch):
    with pytest.raises(ValueError, match="V1_REQUIRED"):
        run_exam(session, "BTC", tmp_path, NOW)
    model = v1(session, tmp_path, btc)
    exam = run_exam(session, "BTC", tmp_path, NOW)
    kinds = [
        r.kind for r in records(session, "EXAM_PROTOCOL") + records(session, "EXAM_PREDICTIONS")
    ]
    assert kinds == ["EXAM_PROTOCOL", "EXAM_PREDICTIONS"]
    protocol = records(session, "EXAM_PROTOCOL")[0]
    assert protocol.created_at <= records(session, "EXAM_PREDICTIONS")[0].created_at
    assert protocol.created_at <= exam.created_at
    p = exam.payload
    assert p["window"]["first_decision"] >= "2025-10-01"
    assert p["window"]["last_target"] <= str(btc.index[-1])
    assert p["arms"]["A_FROZEN_V1"]["n"] == p["arms"]["B_LEARNING"]["n"] == p["n"] > 0
    assert p["policy"] in ("LEARNING", "FROZEN_V1")
    assert current_policy(session, "BTC")["policy"] == p["policy"]
    assert p["base_rate_p"] == model.payload["train_up_rate"]
    # Second call: same record, no new fits.
    from sklearn.linear_model import LogisticRegression

    monkeypatch.setattr(LogisticRegression, "fit", lambda *_: pytest.fail("refit"))
    assert run_exam(session, "BTC", tmp_path, NOW).record_id == exam.record_id


@pytest.mark.pit
def test_exam_refits_only_use_labels_matured_before_their_month(session, tmp_path, btc):
    v1(session, tmp_path, btc)
    run_exam(session, "BTC", tmp_path, NOW)
    refits = [r for r in records(session, "REPLAY_MODEL") if r.payload.get("family") == LEARNING]
    assert refits
    for r in refits:
        month = r.payload["version"].removeprefix("exam-") + "-01"
        assert r.payload["train_target_end"] < month
        assert r.payload["train_feature_end"] < month


@pytest.mark.pit
def test_exam_predictions_do_not_depend_on_future_prices(tmp_path, monkeypatch):
    from pitquant.db.session import create_all, make_engine, make_session_factory

    a, b = bars(), bars()
    b.loc[b.index >= date(2026, 6, 1), "close"] *= 50  # distort the future only
    results = []
    for frame in (a, b):
        engine = make_engine("sqlite+pysqlite:///:memory:")
        create_all(engine)
        session = make_session_factory(engine)()  # fresh journal: records are immutable
        monkeypatch.setattr(learning, "training_frames", lambda *x, f=frame, **k: ({"BTC": f}, {}))
        v1(session, tmp_path / str(len(results)), frame)
        run_exam(session, "BTC", tmp_path / str(len(results)), NOW)
        with np.load(records(session, "EXAM_PREDICTIONS")[0].payload["file"]) as z:
            keep = z["feature_date"] < "2026-05-01"
            results.append((z["p_v1"][keep], z["p_learning"][keep]))
        session.close()
    np.testing.assert_allclose(results[0][0], results[1][0])
    np.testing.assert_allclose(results[0][1], results[1][1])


def test_monthly_refit_requires_exam_and_is_monthly(session, tmp_path, btc):
    v1(session, tmp_path, btc)
    with pytest.raises(ValueError, match="EXAM_REQUIRED"):
        monthly_refit(session, "BTC", tmp_path, NOW)
    run_exam(session, "BTC", tmp_path, NOW)
    first = monthly_refit(session, "BTC", tmp_path, NOW)
    assert first.kind == "MODEL" and first.payload["family"] == LEARNING
    assert first.payload["baseline"] is False
    assert first.payload["train_target_end"] < str(NOW.date())
    again = monthly_refit(session, "BTC", tmp_path, NOW + timedelta(days=3))
    assert again.record_id == first.record_id
    nxt = monthly_refit(session, "BTC", tmp_path, datetime(2026, 12, 2, tzinfo=UTC))
    assert nxt.record_id != first.record_id


def test_champion_follows_policy(session, tmp_path, btc):
    base = v1(session, tmp_path, btc)
    run_exam(session, "BTC", tmp_path, NOW)
    refit = monthly_refit(session, "BTC", tmp_path, NOW)
    set_policy(session, "BTC", "FROZEN_V1", "TEST", {}, NOW)
    assert champion(session, "BTC").record_id == base.record_id
    set_policy(session, "BTC", "LEARNING", "TEST", {}, NOW + timedelta(seconds=1))
    assert champion(session, "BTC").record_id == refit.record_id


@pytest.mark.parametrize(
    "policy,pairs,low,high,expected",
    [
        ("FROZEN_V1", 250, 0.01, 0.03, "LEARNING"),
        ("FROZEN_V1", 150, 0.01, 0.03, None),  # not enough matured pairs
        ("FROZEN_V1", 250, -0.01, 0.03, None),  # interval touches zero
        ("LEARNING", 250, -0.03, -0.01, "FROZEN_V1"),
        ("LEARNING", 250, 0.01, 0.03, None),
    ],
)
def test_forward_switch_rule(session, monkeypatch, policy, pairs, low, high, expected):
    set_policy(session, "BTC", policy, "TEST", {}, NOW)
    cmp = {"pairs": pairs, "dates": 40, "learning_gain": {"low90": low, "high90": high}}
    monkeypatch.setattr(learning, "forward_comparison", lambda *_: cmp)
    out = review_policy(session, "BTC", NOW + timedelta(seconds=1))
    assert out["switched"] is (expected is not None)
    assert current_policy(session, "BTC")["policy"] == (expected or policy)


def test_exam_series_matches_exam_and_is_derived_once(session, tmp_path, btc, monkeypatch):
    from pitquant.forward.learning import exam_series, learning_dashboard

    v1(session, tmp_path, btc)
    exam = run_exam(session, "BTC", tmp_path, NOW)
    series = exam_series(session, "BTC", NOW)
    p = series.payload
    assert sum(m["n"] for m in p["monthly"]) == exam.payload["n"]
    total = sum(m["acc_learning"] * m["n"] for m in p["monthly"]) / exam.payload["n"]
    assert total == pytest.approx(exam.payload["arms"]["B_LEARNING"]["accuracy"])
    assert sum(c["n"] for c in p["calibration"]["learning"]) <= exam.payload["n"]
    monkeypatch.setattr(learning, "training_frames", lambda *a, **k: pytest.fail("recomputed"))
    assert exam_series(session, "BTC", NOW).record_id == series.record_id
    board = {b["market"]: b for b in learning_dashboard(session)}["BTC"]
    assert board["exam_series"]["monthly"] == p["monthly"]
    assert board["live"]["matured"] == 0
    assert board["live"]["series"] == {"v1": [], "learning": [], "v3": []}
