"""API integration on the SYNTHETIC market (§75, §102 Time Machine skeleton)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from pitquant.api.app import create_app
from pitquant.config.settings import Settings


@pytest.fixture(scope="module")
def client(market_factory: sessionmaker[Session], settings: Settings) -> TestClient:
    return TestClient(create_app(market_factory, settings))


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_ticker_reuse_via_api(client: TestClient) -> None:
    a = client.get("/securities/SYNX", params={"as_of": "2002-06-03"}).json()
    b = client.get("/securities/SYNX", params={"as_of": "2013-06-03"}).json()
    assert a["security_id"] != b["security_id"]
    assert a["synthetic_data"] is True
    assert client.get("/securities/SYNX", params={"as_of": "2008-01-02"}).status_code == 404


def test_universe_endpoint(client: TestClient) -> None:
    r = client.get("/universes/SYN_SP500/2008-01-02").json()
    assert r["count"] == 4
    assert {m["ticker"] for m in r["members"]} == {"SYNA", "SYNB", "SYNC", "SYNE"}


@pytest.mark.pit
def test_analysis_time_machine_reconstruction(client: TestClient) -> None:
    r = client.post("/analysis", json={"ticker": "SYNA", "as_of": "2020-10-30"})
    assert r.status_code == 200
    body = r.json()
    assert body["signal"] is None  # no fabricated signal before Phase 5
    assert body["synthetic_data"] is True
    info = body["information_available"]
    assert info["last_bar_session"] == "2020-10-30"
    assert info["latest_fact_available_at"] < body["as_of"]
    w = body["label_windows"]["12m"]
    assert w["t_exec"].startswith("2020-11-02 14:30")  # Monday open, EST


def test_naive_datetime_rejected_by_api(client: TestClient) -> None:
    r = client.post("/analysis", json={"ticker": "SYNA", "as_of": "2020-10-30T16:00:00"})
    assert r.status_code == 422
