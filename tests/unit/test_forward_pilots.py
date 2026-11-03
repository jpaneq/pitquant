"""Synthetic temporal and persistence tests for independent forward pilots."""

from datetime import UTC, date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import select

from pitquant.core.errors import ImmutableRecordError
from pitquant.db.models_forward import ForwardPilotRecord as Record
from pitquant.forward.engine import (
    FEATURES,
    append,
    dashboard,
    features,
    fit_model,
    predict,
    probability,
    records,
    review,
    training_rows,
)
from pitquant.forward.replay import replay_window
from pitquant.forward.storage import publish
from pitquant.positions.audit import summarize


def bars(end=date(2025, 9, 30), n=650):
    index = [end - timedelta(days=i) for i in reversed(range(n))]
    rng = np.random.default_rng(71)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.025, n)))
    return pd.DataFrame(
        dict(close=close, high=close * 1.02, low=close * 0.98, volume=rng.uniform(100, 300, n)),
        index=index,
    )


@pytest.mark.pit
def test_features_causal_and_holes_not_filled():
    b = bars()
    before = features(b.iloc[:400])
    b.iloc[400:, b.columns.get_loc("close")] *= 100
    pd.testing.assert_frame_equal(before, features(b).iloc[:400])
    b.iloc[300, b.columns.get_loc("close")] = np.nan
    assert features(b).iloc[300:501].isna().all().all()


@pytest.mark.pit
@pytest.mark.parametrize(
    "market,cutoff", [("BTC", date(2025, 10, 1)), ("EQUITY", date(2022, 10, 1))]
)
def test_reserved_prices_cannot_enter_labels(market, cutoff):
    b = bars(cutoff + timedelta(days=100))
    a = training_rows(b, market, "SYNTHETIC")
    b.loc[b.index >= cutoff, "close"] = 1e20
    pd.testing.assert_frame_equal(a, training_rows(b, market, "SYNTHETIC"))
    assert (a.target_date < cutoff).all()


def test_fit_archived_and_idempotent(session, tmp_path, monkeypatch):
    now = datetime(2026, 11, 3, tzinfo=UTC)
    model = fit_model(session, "BTC", {"SYNTHETIC": bars()}, {}, tmp_path, now=now)
    assert model.payload["train_target_end"] < "2025-10-01"
    assert len(records(session, "PROTOCOL")) == 1
    assert list(tmp_path.glob("*.npz"))
    from sklearn.linear_model import LogisticRegression

    monkeypatch.setattr(LogisticRegression, "fit", lambda *_: pytest.fail("Repeated fit"))
    assert fit_model(session, "BTC", {}, {}, tmp_path, now=now).record_id == model.record_id
    assert 0 <= probability(model.payload, [0.0] * len(FEATURES)) <= 1
    with pytest.raises(ValueError, match="NO_NEW_MATURE"):
        fit_model(session, "BTC", {"SYNTHETIC": bars()}, {}, tmp_path, candidate=True, now=now)


@pytest.mark.pit
def test_forward_review_only_mature_and_reference_scale_invariant(session, tmp_path):
    now = datetime(2026, 11, 3, 12, tzinfo=UTC)
    model = fit_model(session, "BTC", {"SYNTHETIC": bars()}, {}, tmp_path, now=now)
    live = bars(date(2026, 11, 2))
    pred = predict(session, model, "SYNTHETIC", live, now)
    session.commit()
    assert review(session, pred, live, now) == []
    assert predict(session, model, "SYNTHETIC", live, now).record_id == pred.record_id
    with pytest.raises(ValueError, match="STALE"):
        predict(session, model, "SYNTHETIC", live.iloc[:-1], now)
    full = pd.concat(
        [
            live,
            pd.DataFrame(
                dict(close=[120.0] * 30, high=[122.0] * 30, low=[118.0] * 30, volume=[200.0] * 30),
                index=[date(2026, 11, 3) + timedelta(days=i) for i in range(30)],
            ),
        ]
    )
    # TR indices can be rebased between observations; ratios, not the old index level, matter.
    full["signal_close"] = full.close * 7
    rows = review(session, pred, full, datetime(2026, 12, 3, 1, tzinfo=UTC))
    assert len(rows) == 4
    final = next(r for r in rows if r.kind == "OUTCOME")
    assert final.payload["actual_return"] == pytest.approx(120 / live.close.iloc[-1] - 1)
    assert review(session, pred, full, datetime(2026, 12, 3, 1, tzinfo=UTC)) == []
    d = dashboard(session)
    assert d["markets"][0]["mature"] == 1
    assert d["auto_orders"] is False
    assert pred.payload["generated_at"] == now.isoformat()


@pytest.mark.pit
@pytest.mark.parametrize("market,months", [("EQUITY", 12), ("EQUITY", 24), ("BTC", 12)])
def test_reserved_replay_does_not_load_outcomes(session, tmp_path, monkeypatch, market, months):
    import pitquant.forward.replay as module

    monkeypatch.setattr(module, "training_frames", lambda *_: pytest.fail("Reserved data read"))
    r = replay_window(session, market, months, datetime(2026, 11, 3, tzinfo=UTC), tmp_path)
    assert r["status"] == "BLOCKED_RESERVED_PERIODS"
    assert r["n"] == r["holdout_outcomes_accessed"] == r["oot_outcomes_accessed"] == 0


def test_journal_rejects_conflicting_payload_and_tamper(session):
    row = append(session, "key", "PROTOCOL", "BTC", {"a": 1})
    with pytest.raises(ValueError, match="CONFLICT"):
        append(session, "key", "PROTOCOL", "BTC", {"a": 2})
    assert session.scalar(select(Record)).record_id == row.record_id
    row.payload = {"a": 2}
    with pytest.raises(ImmutableRecordError):
        session.flush()


def test_storage_no_overwrite(tmp_path):
    p = tmp_path / "immutable.json"
    publish(p, b"first")
    publish(p, b"first")
    with pytest.raises(ValueError):
        publish(p, b"second")
    assert p.read_bytes() == b"first"


def test_audit_waiting_not_a_loss():
    rows = [
        dict(state=state, return_pct=ret, horizon_mature=False, pick_id="one")
        for state, ret in [
            ("TARGET_HIT", 0.05),
            ("STOP_HIT", -0.08),
            ("WAITING_FIRST_BAR", None),
            ("NO_DATA", None),
        ]
    ]
    r = summarize(rows)
    assert r["closed"] == 2 and r["pending"] == 1 and r["no_data"] == 1
    assert r["target_rate_closed"] == 0.5
    assert r["mean_closed_return"] == pytest.approx(-0.015)
    assert r["distinct_pick_ids"] == 1


def test_challenger_compares_only_same_mature_cohorts(session):
    baseline = append(session, "base", "MODEL", "BTC", {"baseline": True, "version": "v1"})
    challenger = append(
        session, "candidate", "MODEL", "BTC", {"baseline": False, "version": "2026-12"}
    )
    for name, model, day, prob in [
        ("old", baseline, "2026-10-01", 0.1),
        ("shared", baseline, "2026-11-01", 0.8),
        ("candidate-shared", challenger, "2026-11-01", 0.2),
    ]:
        p = append(
            session,
            name,
            "PREDICTION",
            "BTC",
            {
                "model_id": model.record_id,
                "ticker": "SYNTHETIC",
                "feature_date": day,
                "target_date": "2026-12-01",
                "p_up": prob,
                "momentum_up": True,
            },
        )
        append(
            session,
            "out-" + name,
            "OUTCOME",
            "BTC",
            {
                "prediction_id": p.record_id,
                "target_date": "2026-12-01",
                "actual_return": 0.1,
                "hit": prob >= 0.5,
            },
        )
    c = dashboard(session)["comparisons"][0]
    assert c["matched_mature_n"] == 1
    assert c["baseline_accuracy"] == 1 and c["candidate_accuracy"] == 0
    assert c["auto_promotion"] is False


def test_sqlite_migration_blocks_raw_journal_mutation(tmp_path):
    import os

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import IntegrityError

    cfg = Config("alembic.ini")
    url = "sqlite:///" + str(tmp_path / "journal.db")
    # The migration environment reads the env override, never the user's real DB.
    from unittest.mock import patch

    with patch.dict(os.environ, {"PITQUANT_DATABASE_URL": url}):
        command.upgrade(cfg, "head")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO forward_pilot_records VALUES "
                "('synthetic','synthetic','PROTOCOL','BTC','{}','hash','2026-11-03 00:00:00')"
            )
        )
    for sql in [
        "UPDATE forward_pilot_records SET market='EQUITY'",
        "DELETE FROM forward_pilot_records",
    ]:
        with engine.begin() as conn, pytest.raises(IntegrityError, match="append-only"):
            conn.execute(text(sql))


def test_paper_drawdown_uses_largest_positive_decline_and_ten_trade_gate(session, monkeypatch):
    from types import SimpleNamespace

    import pitquant.forward.paper as paper

    links = [
        SimpleNamespace(market="BTC", payload={"model_id": "m", "simulation_id": str(i)})
        for i in range(10)
    ]
    monkeypatch.setattr(paper, "records", lambda *_: links)
    monkeypatch.setattr(
        paper,
        "latest_outcome",
        lambda _, sid: SimpleNamespace(
            state="STOPPED",
            is_closed=True,
            realized_return=-0.02,
            max_drawdown=int(sid) / 100,
            excess_return_vs_benchmark=None,
        ),
    )
    result = paper.statistics(session, "m")
    assert result["worst_trade_drawdown"] == 0.09
    assert result["mean_excess_vs_benchmark"] is None
    assert result["portfolio_return"] is None
    links.pop()
    assert paper.statistics(session, "m")["worst_trade_drawdown"] is None
