# ruff: noqa: E501
"""Analyzer HTTP contract (SYNTHETIC data). Panels are independent endpoints; a missing family degrades only
its own panel; the holdout is sealed; no secrets leave the process."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from pitquant.analyzer.service import clear_cache
from pitquant.api.app import create_app
from pitquant.config.settings import Settings
from pitquant.security_master.service import SecurityMaster
from tests.unit.test_feature_engine_v0 import SESSIONS, add_fact, closes_path, load_bars


@pytest.fixture
def client(factory: sessionmaker[Session], settings: Settings) -> TestClient:
    clear_cache()
    with factory() as s:
        sm = SecurityMaster(s)
        a = sm.register(name="SYN FULL CO", exchange="XNYS", currency="USD").security_id
        sm.add_ticker(a, "SYNF", "XNYS", date(2010, 1, 4))
        load_bars(
            s,
            a,
            "F",
            closes_path(SESSIONS, 100.0, 0.0006),
            splits={date(2016, 3, 15): 2.0},
            dividends={date(2016, 5, 12): 0.5},
        )
        for y, rev in ((2014, 1000.0), (2015, 1200.0)):
            for tag, v in (
                ("Revenues", rev),
                ("NetIncomeLoss", rev * 0.1),
                ("OperatingIncomeLoss", rev * 0.2),
                ("NetCashProvidedByUsedInOperatingActivities", rev * 0.15),
                ("PaymentsToAcquirePropertyPlantAndEquipment", rev * 0.03),
            ):
                add_fact(
                    s,
                    a,
                    tag,
                    date(y, 1, 1),
                    date(y, 12, 31),
                    v,
                    datetime(y + 1, 2, 20, 21, tzinfo=UTC),
                    form="10-K",
                )
        add_fact(
            s,
            a,
            "EntityCommonStockSharesOutstanding",
            None,
            date(2016, 2, 10),
            100.0,
            datetime(2016, 2, 20, tzinfo=UTC),
            unit="shares",
        )
        b = sm.register(name="SYN FUND ONLY", exchange="XNYS", currency="USD").security_id
        sm.add_ticker(b, "SYNO", "XNYS", date(2010, 1, 4))
        add_fact(
            s,
            b,
            "Revenues",
            date(2015, 1, 1),
            date(2015, 12, 31),
            500.0,
            datetime(2016, 2, 20, tzinfo=UTC),
            form="10-K",
        )
        s.commit()
    return TestClient(create_app(factory, settings))


AS_OF = "2016-12-31T23:00:00+00:00"


def test_search_exact_and_suggestion(client: TestClient) -> None:
    r = client.get("/search", params={"q": "synf"}).json()
    assert r["exact"] and r["results"][0]["ticker"] == "SYNF"
    sug = client.get("/search", params={"q": "SYNX"}).json()
    assert not sug["exact"] and all(h["match_type"] != "EXACT" for h in sug["results"])


def test_summary_contract_and_engine_versions(client: TestClient) -> None:
    d = client.get("/analyzer/SYNF/summary", params={"as_of": AS_OF}).json()
    assert (
        d["security"]["ticker"] == "SYNF"
        and d["quote"]["status"] == "OK"
        and d["quote"]["currency"] == "USD"
    )
    assert d["quote"]["timestamp"] and d["quote"]["badge"] in (
        "EOD",
        "STALE",
    )  # a quote is NEVER shown without a timestamp / badge
    assert (
        d["availability"]["analyzer_eligibility"] in ("FULL", "PARTIAL")
        and d["availability"]["prediction"] == "NOT_YET_VALIDATED"
    )
    assert set(d["summary"]) == {
        "fundamentals",
        "growth",
        "valuation",
        "trend",
        "momentum",
        "relative_strength",
        "risk",
        "data_quality",
    }
    assert {
        "technical_engine_version",
        "fundamental_engine_version",
        "support_resistance_version",
        "trade_plan_version",
        "analysis_score_version",
        "feature_engine_version",
        "model_version",
    } <= set(d["engine_versions"])
    assert d["engine_versions"]["model_version"] == "none"
    assert d["data_notice"]["live_reference"] in ("CONFIGURED", "DATA SOURCE NOT CONFIGURED")


def test_panels_are_independent_and_dtos_carry_as_of_and_version(client: TestClient) -> None:
    for panel in (
        "technicals",
        "fundamentals",
        "valuation",
        "analysis",
        "trade-plan",
        "prediction",
        "filings",
        "data-quality",
        "quote",
    ):
        r = client.get(f"/analyzer/SYNF/{panel}", params={"as_of": AS_OF})
        assert r.status_code == 200, panel
        assert "as_of" in r.json(), panel
    t = client.get("/analyzer/SYNF/technicals", params={"as_of": AS_OF}).json()
    assert t["engine_version"].startswith("technical-v") and t["trend"]["state"] in (
        "STRONG_UPTREND",
        "UPTREND",
        "NEUTRAL",
        "DOWNTREND",
        "STRONG_DOWNTREND",
    )
    assert set(t["indicators"]) >= {
        "sma20",
        "sma50",
        "sma200",
        "ema20",
        "ema50",
        "rsi14",
        "macd",
        "macd_signal",
        "macd_hist",
        "atr14",
        "adx14",
        "bollinger_upper",
        "bollinger_mid",
        "bollinger_lower",
    }
    assert set(t["support_resistance"]) >= {"supports", "resistances"}
    f = client.get("/analyzer/SYNF/fundamentals", params={"as_of": AS_OF}).json()
    assert f["ttm"]["revenue"]["value"] == 1200.0 and f["ttm"]["fcf"]["value"] == pytest.approx(
        1200 * 0.12
    )
    p = client.get("/analyzer/SYNF/prediction", params={"as_of": AS_OF}).json()
    assert (
        p["model_status"] == "NOT_YET_VALIDATED"
        and p["horizons"]["6M"]["p_outperform"] is None
        and p["horizons"]["12M"]["expected_excess_return"] is None
    )


def test_chart_ranges_and_validation(client: TestClient) -> None:
    c = client.get("/analyzer/SYNF/chart", params={"range": "3M", "as_of": AS_OF}).json()
    assert (
        c["status"] == "OK" and c["n_bars"] == 63 and c["price_basis"].startswith("SPLIT_ADJUSTED")
    )
    assert {"time", "open", "high", "low", "close", "volume"} <= set(
        c["candles"][0]
    ) and "sma200" in c["overlays"]
    assert (
        client.get("/analyzer/SYNF/chart", params={"range": "1D"}).status_code == 422
    )  # no intraday is synthesised
    assert client.get("/analyzer/SYNF/chart", params={"range": "MAX", "as_of": AS_OF}).json()[
        "n_bars"
    ] == len(SESSIONS)


def test_fundamental_only_security_degrades_only_its_price_panels(client: TestClient) -> None:
    s = client.get("/analyzer/SYNO/summary", params={"as_of": AS_OF}).json()
    assert s["quote"]["status"] == "NO_DATA" and s["quote"]["badge"] == "NO_DATA"
    assert s["availability"]["analyzer_eligibility"] in (
        "FUNDAMENTAL_ONLY",
        "PARTIAL",
        "INSUFFICIENT",
    )
    assert (
        client.get("/analyzer/SYNO/technicals", params={"as_of": AS_OF}).json()["status"]
        == "NO_DATA"
    )
    assert (
        client.get("/analyzer/SYNO/trade-plan", params={"as_of": AS_OF}).json()["status"]
        == "NO_DATA"
    )
    assert (
        client.get("/analyzer/SYNO/fundamentals", params={"as_of": AS_OF}).json()["status"] == "OK"
    )
    assert client.get("/analyzer/SYNO/chart", params={"as_of": AS_OF}).json()["candles"] == []


def test_holdout_unknown_security_position_size_and_secrets(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert (
        client.get(
            "/analyzer/SYNF/summary", params={"as_of": "2023-01-05T15:00:00+00:00"}
        ).status_code
        == 403
    )  # sealed holdout
    assert (
        client.get("/analyzer/SYNF/summary", params={"as_of": "2016-12-31T23:00:00"}).status_code
        == 422
    )  # naive datetime refused
    nf = client.get("/analyzer/NOPE/summary")
    assert nf.status_code == 404
    ps = client.get(
        "/analyzer/SYNF/position-size",
        params={"capital": 100000, "risk_pct": 1, "entry": 100, "stop": 95},
    ).json()
    assert ps["shares"] == 200
    monkeypatch.setenv("PITQUANT_TIINGO_API_KEY", "SUPERSECRETVALUE")
    r = client.get("/analyzer/status")
    assert "SUPERSECRETVALUE" not in r.text and any(
        p["env_var"] == "PITQUANT_TIINGO_API_KEY" and p["configured"] for p in r.json()["providers"]
    )
    rep = client.get("/analyzer/SYNF/report", params={"as_of": AS_OF, "format": "markdown"})
    assert (
        rep.status_code == 200 and "RULE_BASED" in rep.text and "SUPERSECRETVALUE" not in rep.text
    )
    js = client.get("/analyzer/SYNF/report", params={"as_of": AS_OF}).json()
    assert {
        "security",
        "quote",
        "fundamentals",
        "valuation",
        "technicals",
        "analysis",
        "trade_plan",
        "prediction",
        "data_quality",
        "engine_versions",
    } <= set(js)


def test_same_inputs_same_output_and_historical_call_ignores_later_data(client: TestClient) -> None:
    a = client.get("/analyzer/SYNF/technicals", params={"as_of": AS_OF}).json()
    b = client.get("/analyzer/SYNF/technicals", params={"as_of": AS_OF}).json()
    assert a == b  # determinism
    early = client.get(
        "/analyzer/SYNF/technicals", params={"as_of": "2015-12-31T23:00:00+00:00"}
    ).json()
    assert (
        early["last_session"] < a["last_session"] and early["n_bars"] < a["n_bars"]
    )  # decision_at is honoured
    mid = client.get(
        "/analyzer/SYNF/fundamentals", params={"as_of": "2015-06-01T00:00:00+00:00"}
    ).json()
    assert (
        mid["ttm"]["revenue"]["value"] == 1000.0
    )  # FY2015 is filed in 2016: invisible in mid-2015, FY2014 is the latest known
