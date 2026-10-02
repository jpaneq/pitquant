"""Research Lab HTTP contract: real rows or empty lists, holdout always SEALED, flags separated."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from pitquant.api.app import create_app
from pitquant.config.settings import Settings


@pytest.fixture
def client(factory: sessionmaker[Session], settings: Settings) -> TestClient:
    return TestClient(create_app(factory, settings))


def test_status_separates_lab_from_data(client: TestClient) -> None:
    j = client.get("/research/status").json()
    assert j["holdout"] == "SEALED"
    assert j["flags"]["RESEARCH_LAB_IMPLEMENTED"] is True
    assert j["flags"]["RESEARCH_DATA_READY"] is False
    assert j["flags"]["FEATURE_RESEARCH_READY_US"] is False


def test_no_fake_results(client: TestClient) -> None:
    assert client.get("/research/experiments").json() == []
    assert client.get("/research/datasets").json() == []
    bt = client.get("/research/backtests").json()
    assert bt == {"folds": [], "metric_sets": []}
    models = client.get("/research/models").json()
    assert all(not m["trained"] for m in models["predefined_baselines"])
    assert models["registered"] == []
    assert len(client.get("/research/features").json()["catalog"]) == 51


def test_audit_states_holdout(client: TestClient) -> None:
    j = client.get("/research/audit").json()
    assert j["holdout"] == "SEALED" and j["holdout_range"] == ["2022-10-01", "2025-09-30"]
