# ruff: noqa: E501, F811, F401
"""Simulated positions API (SYNTHETIC SYNF): buy, add, reduce, close, rule-based review, BTC without real data."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from tests.integration.test_analyzer_api import client


def buy(c: TestClient, **kw):
    body = {
        "asset_type": "EQUITY",
        "security": "SYNF",
        "horizon_months": 6,
        "notional": 10_000,
        **kw,
    }
    return c.post("/positions", json=body)


def test_buy_creates_a_position_with_a_stop_and_a_reviewed_recommendation(
    client: TestClient,
) -> None:
    r = buy(client)
    assert r.status_code == 200
    v = r.json()
    assert (
        v["status"] == "OPEN"
        and v["asset_type"] == "EQUITY"
        and v["quantity"] > 0
        and v["avg_cost"] > 0
        and v["stop_rule"] == "ATR14_2X_AT_OPEN"
        and v["stop_price"] < v["avg_cost"]
    )
    rv = v["review"]
    assert (
        rv["recommendation"] in ("ADD", "HOLD", "SELL")
        and rv["engine_version"] == "position-review-v0"
        and "NOT A PREDICTION" in rv["label"]
        and rv["horizon_bucket"] == "MEDIUM"
        and rv["rules"]
    )
    assert v["events"][0]["type"] == "OPEN" and v["events"][0]["price_source"] == "EOD_CLOSE"


def test_add_reduce_and_close_update_the_average_cost_and_quantity(client: TestClient) -> None:
    v = buy(client, quantity=10).json()
    pid, px = v["position_id"], v["avg_cost"]
    added = client.post(
        f"/positions/{pid}/events", json={"type": "ADD", "quantity": 10, "price": px * 1.2}
    ).json()
    assert added["quantity"] == 20 and added["avg_cost"] == pytest.approx(px * 1.1)
    reduced = client.post(
        f"/positions/{pid}/events", json={"type": "REDUCE", "quantity": 5, "price": px * 1.3}
    ).json()
    assert (
        reduced["quantity"] == 15
        and reduced["avg_cost"] == pytest.approx(px * 1.1)
        and reduced["realized_pnl"] == pytest.approx((px * 1.3 - px * 1.1) * 5)
    )
    assert (
        client.post(
            f"/positions/{pid}/events", json={"type": "REDUCE", "quantity": 99, "price": px}
        ).status_code
        == 422
    )
    closed = client.post(
        f"/positions/{pid}/events", json={"type": "CLOSE", "price": px * 1.05}
    ).json()
    assert closed["status"] == "CLOSED" and closed["review"] is None and closed["quantity"] == 0
    assert (
        client.post(
            f"/positions/{pid}/events", json={"type": "ADD", "quantity": 1, "price": px}
        ).status_code
        == 422
    )  # a closed position cannot be reopened
    assert all(
        p["position_id"] != pid
        for p in client.get(
            "/positions", params={"asset_type": "EQUITY", "security": "SYNF"}
        ).json()
    )


def test_horizon_and_inputs_are_validated(client: TestClient) -> None:
    assert buy(client, horizon_months=0).status_code == 422
    assert buy(client, horizon_months=61).status_code == 422
    assert buy(client, notional=None, quantity=None).status_code == 422
    assert buy(client, notional=1).status_code == 422  # does not buy one share
    assert buy(client, stop_price=1e9).status_code == 422
    assert buy(client, target_return=-0.1).status_code == 422
    assert (
        client.post(
            "/positions",
            json={
                "asset_type": "EQUITY",
                "security": "NOPE",
                "horizon_months": 6,
                "notional": 1000,
            },
        ).status_code
        == 404
    )


def test_the_same_position_gets_a_different_weighting_for_a_short_and_a_long_horizon(
    client: TestClient,
) -> None:
    short = buy(client, horizon_months=1).json()["review"]
    long_ = buy(client, horizon_months=24).json()["review"]
    assert (
        short["horizon_bucket"] == "SHORT"
        and long_["horizon_bucket"] == "LONG"
        and short["weights"] != long_["weights"]
    )


def test_keeping_a_review_is_explicit_and_listed(client: TestClient) -> None:
    pid = buy(client).json()["position_id"]
    assert client.get(f"/positions/{pid}/reviews").json() == []  # viewing never stores anything
    kept = client.post(f"/positions/{pid}/review").json()
    assert kept["recommendation"] in ("ADD", "HOLD", "SELL")
    rows = client.get(f"/positions/{pid}/reviews").json()
    assert len(rows) == 1 and rows[0]["engine_version"] == "position-review-v0"


def test_btc_position_needs_a_real_quote_and_never_falls_back_to_synthetic(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("PITQUANT_E2E_FIXTURE", raising=False)
    from pitquant.api import btc as btc_api

    def down(db):  # no network and no archive
        return {
            "quote": {
                "price": None,
                "retrieved_at": None,
                "status": "UNAVAILABLE",
                "source": "BINANCE_SPOT",
            },
            "data_mode": "REAL",
        }

    monkeypatch.setattr(btc_api, "_market", down)
    r = client.post("/positions", json={"asset_type": "BTC", "horizon_months": 6, "notional": 1000})
    assert r.status_code == 422 and "PRICE_UNAVAILABLE" in r.json()["detail"]


def test_positions_are_append_only_tables() -> None:
    from pitquant.db.models import IMMUTABLE_TABLES

    assert {"paper_positions", "paper_position_events", "position_reviews"} <= set(IMMUTABLE_TABLES)
