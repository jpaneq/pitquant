# ruff: noqa: E501
"""Analyzer golden path on the REAL local database (AAPL, MSFT, KO). Skipped when ``data/pitquant.db`` or the
golden securities are absent (CI). When the data IS present every failure is a failure."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from pitquant.analyzer.service import clear_cache
from pitquant.api.app import create_app
from pitquant.config.settings import get_settings
from pitquant.db.models import Price, SecurityProfile
from pitquant.db.session import make_engine, make_session_factory

DB = Path("data/pitquant.db")
pytestmark = pytest.mark.skipif(not DB.exists(), reason="no local real database")


@pytest.fixture(scope="module")
def client() -> TestClient:
    clear_cache()
    s = get_settings()
    f = make_session_factory(make_engine("sqlite:///" + str(DB)))
    with f() as ses:
        have = set(ses.scalars(select(SecurityProfile.current_ticker)))
        if not {"AAPL", "MSFT", "KO"} <= have or not ses.scalars(select(Price.security_id)).first():
            pytest.skip("golden securities not ingested locally")
    return TestClient(create_app(f, s))


# KO was FUNDAMENTAL_ONLY while no price source covered it; since the free Yahoo daily bars were ingested (ADR-0043) it has real prices, so FULL is the correct state.
# The FUNDAMENTAL_ONLY path stays covered by the synthetic SYNO security (tests/integration/test_analyzer_api.py).
@pytest.mark.parametrize("t,elig", [("AAPL", "FULL"), ("MSFT", "FULL"), ("KO", "FULL")])
def test_golden_securities(client: TestClient, t: str, elig: str) -> None:
    d = client.get(f"/analyzer/{t}/summary").json()
    assert d["security"]["ticker"] == t and d["availability"]["analyzer_eligibility"] == elig
    f = client.get(f"/analyzer/{t}/fundamentals").json()
    assert (
        f["status"] == "OK" and f["ttm"]["revenue"]["value"] > 1e9
    )  # real SEC data, no hard-coded values
    pred = client.get(f"/analyzer/{t}/prediction").json()
    assert (
        pred["model_status"] == "NOT_YET_VALIDATED"
        and pred["horizons"]["6M"]["p_outperform"] is None
    )
    if elig == "FULL":
        q = d["quote"]
        assert (
            q["status"] == "OK"
            and q["timestamp"]
            and q["badge"] in ("EOD", "STALE")
            and q["source"]
        )
        min_bars = (
            3500 if t == "KO" else 5000
        )  # KO comes from the Yahoo daily source since 2011 (canonical V1 start); AAPL/MSFT carry the 1995+ vendor history
        tech = client.get(f"/analyzer/{t}/technicals").json()
        assert (
            tech["n_bars"] > min_bars
            and tech["indicators"]["sma200"] > 0
            and tech["relative_strength"]["benchmark"] in ("SPY", "VTI")
        )
        assert (
            client.get(f"/analyzer/{t}/chart", params={"range": "MAX"}).json()["n_bars"] > min_bars
        )
    else:
        assert (
            d["quote"]["status"] == "NO_DATA"
            and client.get(f"/analyzer/{t}/technicals").json()["status"] == "NO_DATA"
        )


def test_apple_split_2020_is_continuous_on_the_chart(client: TestClient) -> None:
    c = client.get("/analyzer/AAPL/chart", params={"range": "MAX"}).json()
    px = {k["time"]: k["close"] for k in c["candles"]}
    assert (
        0.9 < px["2020-08-31"] / px["2020-08-28"] < 1.2
    )  # 4:1 split: raw 499.23 -> 129.04 would be -74 %; adjusted is continuous
    assert any(
        a["kind"] == "SPLIT" and a["date"] == "2020-08-31" and a["ratio"] == 4.0
        for a in c["corporate_actions"]
    )
