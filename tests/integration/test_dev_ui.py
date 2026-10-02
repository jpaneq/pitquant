"""Developer UI V0.1 backend: read-only, holdout-sealed, no signals."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from pitquant.api.app import create_app
from pitquant.config.settings import Settings


def client(factory: sessionmaker[Session], settings: Settings) -> TestClient:
    return TestClient(create_app(factory, settings))


def test_status_has_every_component_and_a_sealed_holdout(
    factory: sessionmaker[Session], settings: Settings
) -> None:
    r = client(factory, settings).get("/dev/status")
    assert r.status_code == 200
    d = r.json()
    assert d["holdout"]["state"] == "SEALED" and d["holdout"]["outcomes_exposed"] is False
    flags = d["research"]["flags"]
    for k in (
        "D02_RESEARCH_READY",
        "US_D05_RESEARCH_READY",
        "ES_D05_RESEARCH_READY",
        "FEATURE_ENGINE_IMPLEMENTED",
        "FEATURE_RESEARCH_READY_US",
        "FEATURE_RESEARCH_READY_ES",
        "FEATURE_RESEARCH_READY",
        "LABEL_ENGINE_READY_US",
        "BASELINE_MODEL_READY",
    ):
        assert k in flags
    assert flags["FEATURE_ENGINE_IMPLEMENTED"] is True and flags["FEATURE_RESEARCH_READY"] is False
    assert "BUY" not in r.text.replace("No signals, no BUY/HOLD/SELL", "")


def test_holdout_dates_are_refused(factory: sessionmaker[Session], settings: Settings) -> None:
    c = client(factory, settings)
    assert c.get("/dev/time-machine/XYZ/2023-01-03").status_code == 403
    assert c.get("/dev/features/XYZ/2023-01-03").status_code in (
        403,
        404,
    )  # unknown security is checked first
    assert c.get("/dev/security/search", params={"q": "nothing-here"}).json() == []


def test_page_is_served(factory: sessionmaker[Session], settings: Settings) -> None:
    r = client(factory, settings).get("/dev/")
    assert r.status_code == 200 and "Developer UI" in r.text and "Time Machine" in r.text
