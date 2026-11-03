"""Pilot API cannot fit or create trades through the review operation."""

from fastapi.testclient import TestClient

from pitquant.api.app import create_app


def test_review_passes_no_training_flags_and_manual_requires_valid_forecast(
    factory, settings, monkeypatch
):
    import pitquant.api.forward as route

    calls = []

    def cycle(*args, **kwargs):
        calls.append(kwargs)
        return {"orders_opened": 0, "fits": []}

    monkeypatch.setattr(route, "run_cycle", cycle)
    with TestClient(create_app(settings=settings, factory=factory)) as c:
        assert c.get("/forward-pilots").json()["markets"] == []
        assert c.post("/forward-pilots/review", json={}).json()["orders_opened"] == 0
        assert len(calls) == 1
        assert not calls[0].get("train") and not calls[0].get("candidate")
        assert (
            c.post(
                "/forward-pilots/simulate", json={"prediction_id": "missing", "notional": 1000}
            ).status_code
            == 409
        )
        assert (
            c.post(
                "/forward-pilots/simulate", json={"prediction_id": "missing", "notional": -1}
            ).status_code
            == 422
        )
