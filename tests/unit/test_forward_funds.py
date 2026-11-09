"""Owner's fund watch list (ADR-0065): ISIN checks, append-only list, frozen forecasts, apart."""

from datetime import UTC, date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from pitquant.forward import funds
from pitquant.forward.engine import fit_model, records

NOW = datetime(2026, 11, 8, 22, tzinfo=UTC)


def nav(end=date(2026, 11, 6), n=400, seed=3):
    days = pd.bdate_range(end=end, periods=n).date
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.008, n)))
    frame = pd.DataFrame({"close": close}, index=list(days))
    frame["high"] = frame["low"] = frame["signal_close"] = frame["close"]
    frame["volume"] = np.nan
    return frame


@pytest.fixture
def model(session, tmp_path):
    train = nav(date(2025, 9, 1), 800)
    train["volume"] = np.random.default_rng(5).uniform(1, 3, len(train))  # equities have volume
    return fit_model(session, "BTC", {"SYN": train}, {}, tmp_path, now=NOW)


@pytest.mark.parametrize(
    "code,ok",
    [
        ("ES0119199000", True),
        ("IE00B03HD191", True),
        ("US0378331005", True),
        ("ES0119199001", False),
        ("ES011919900", False),
        ("es0119199000", True),
    ],
)
def test_isin_check_digit(code, ok):
    assert funds.valid_isin(code) is ok


def test_watch_list_is_append_only_replay(session):
    funds.add(session, "ES0119199000", "0P00019W2R.F", "Cobas", "EUR", NOW)
    funds.add(
        session, "IE00B03HD191", "0P00000WLG.F", "Vanguard", "EUR", NOW + timedelta(seconds=1)
    )
    funds.remove(session, "ES0119199000", NOW + timedelta(seconds=2))
    assert list(funds.watched(session)) == ["IE00B03HD191"]
    funds.add(session, "ES0119199000", "0P00019W2R.F", "Cobas", "EUR", NOW + timedelta(seconds=3))
    assert set(funds.watched(session)) == {"ES0119199000", "IE00B03HD191"}
    assert len(records(session, "FUND_WATCH")) == 3  # nothing deleted
    with pytest.raises(ValueError, match="INVALID_FUND"):
        funds.add(session, "ES0119199001", "X.F", "bad", None, NOW)


@pytest.mark.pit
def test_forecast_frozen_reviewed_at_maturity_and_kept_apart(session, model):
    series = nav()
    pred = funds.predict(session, model, "ES0119199000", series, NOW)
    session.commit()
    assert pred.kind == "FUND_PREDICTION" and pred.market == "FUNDS"
    assert 0 < pred.payload["p_up"] < 1
    assert funds.predict(session, model, "ES0119199000", series, NOW).record_id == pred.record_id
    assert funds.review(session, pred, series, NOW) == []  # no NAV after the forecast yet
    future = pd.bdate_range(start=date(2026, 11, 9), periods=30).date
    more = pd.DataFrame(
        {"close": np.linspace(series.close.iloc[-1], series.close.iloc[-1] * 1.05, 30)},
        index=list(future),
    )
    more["high"] = more["low"] = more["signal_close"] = more["close"]
    more["volume"] = np.nan
    full = pd.concat([series, more])
    later = NOW + timedelta(days=40)
    rows = funds.review(session, pred, full, later)
    assert [r.payload["step"] for r in rows] == funds.REVIEWS
    final = rows[-1].payload
    assert final["final"] and final["actual_return"] > 0
    assert final["hit"] is (pred.payload["p_up"] >= 0.5)
    assert funds.review(session, pred, full, later) == []  # idempotent
    assert not records(session, "PREDICTION") and not records(session, "OUTCOME")  # apart


def test_stale_or_short_nav_never_forecast(session, model):
    with pytest.raises(ValueError, match="STALE_NAV"):
        funds.predict(session, model, "ES0119199000", nav(date(2026, 10, 1)), NOW)
    with pytest.raises(ValueError, match="TOO_SHORT"):
        funds.predict(session, model, "ES0119199000", nav(n=150), NOW)


def test_board_scorecard(session, model, monkeypatch):
    funds.add(session, "ES0119199000", "0P00019W2R.F", "Cobas", "EUR", NOW)
    series = nav()
    monkeypatch.setattr(funds, "load_nav", lambda *a: series)
    monkeypatch.setattr("pitquant.forward.learning.champion", lambda *a: model)
    out = funds.cycle(session, NOW)
    assert out == {"forecasts": 1, "reviews": 0, "gaps": {}}
    card = funds.board(session)[0]
    assert card["name"] == "Cobas" and card["forecasts"] == 1 and card["matured"] == 0
    assert card["latest"]["last_step"] == 0 and card["accuracy"] is None
