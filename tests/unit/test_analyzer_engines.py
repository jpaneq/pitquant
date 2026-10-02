# ruff: noqa: E501
"""Analyzer engines (technical V1, support/resistance V1, fundamental V1, valuation V1, trade plan V0,
corporate-action resolution, search). SYNTHETIC data (SYN*) except where noted; no network."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest
from sqlalchemy.orm import Session

from pitquant.analyzer import indicators as I
from pitquant.analyzer.analysis_v0 import build_analysis, positives_and_risks
from pitquant.analyzer.fundamental_v1 import compute_fundamentals, discrete_quarters
from pitquant.analyzer.market import load_market
from pitquant.analyzer.search import search
from pitquant.analyzer.sr_v1 import compute_zones, pivots
from pitquant.analyzer.technical_v1 import chart_payload, classify_trend, compute_technicals
from pitquant.analyzer.trade_plan_v0 import build_trade_plan, position_size
from pitquant.analyzer.valuation_v1 import compute_valuation, valuation_point
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.features.v0 import fundamentals as F
from pitquant.features.v0.engine import load_facts
from pitquant.market.ca_resolve import collapse_equivalent
from pitquant.market.normalized import CorporateAction, CorporateActionKind, Provenance, SourceTier
from tests.unit.test_feature_engine_v0 import (
    CAL,
    SESSIONS,
    add_fact,
    closes_path,
    load_bars,
    make_security,
)

K = CorporateActionKind
AT = datetime(2016, 12, 31, 23, tzinfo=UTC)  # after the last synthetic bar


# ───────────────────────────── indicators (exact / known values) ─────────────────────────────────
def test_sma_ema_exact_and_wilder_seed() -> None:
    c = pd.Series(np.arange(1.0, 31.0))
    assert I.sma(c, 5).iloc[-1] == pytest.approx(28.0) and np.isnan(I.sma(c, 5).iloc[3])
    e = I.ema(c, 10)
    assert np.isnan(e.iloc[8]) and e.iloc[-1] == pytest.approx(
        c.ewm(span=10, adjust=False).mean().iloc[-1]
    )
    w = I.wilder(pd.Series([2.0] * 3 + [4.0] * 10), 3)
    assert w.iloc[2] == pytest.approx(2.0) and w.iloc[3] == pytest.approx(
        (2.0 * 2 + 4.0) / 3
    )  # seeded with the mean of the first n


def test_rsi_wilder_matches_reference_values_and_extremes() -> None:
    close = pd.Series(
        [
            44.34,
            44.09,
            44.15,
            43.61,
            44.33,
            44.83,
            45.10,
            45.42,
            45.84,
            46.08,
            45.89,
            46.03,
            45.61,
            46.28,
            46.28,
            46.00,
            46.03,
            46.41,
            46.22,
            45.64,
        ]
    )
    r = I.rsi(close, 14)
    assert r.iloc[14] == pytest.approx(70.46, abs=0.1)  # Wilder's classic worked example
    assert I.rsi(pd.Series(np.arange(1.0, 40.0)), 14).iloc[-1] == 100.0  # no losses
    assert I.rsi(pd.Series(np.arange(40.0, 1.0, -1.0)), 14).iloc[-1] == pytest.approx(0.0, abs=1e-9)


def test_macd_atr_adx_bollinger_shapes_and_identities() -> None:
    n = 120
    idx = pd.RangeIndex(n)
    c = pd.Series(100 + np.cumsum(np.sin(np.arange(n) / 5.0)), index=idx)
    h, lo = c + 1.0, c - 1.0
    m = I.macd(c)
    assert m["hist"].dropna().iloc[-1] == pytest.approx(m["macd"].iloc[-1] - m["signal"].iloc[-1])
    assert (
        m["macd"].first_valid_index() == 25 and m["signal"].first_valid_index() == 33
    )  # 26-1 and 26-1+9-1
    a = I.atr(h, lo, c, 14)
    assert a.first_valid_index() == 14 and (a.dropna() > 0).all()
    d = I.adx(h, lo, c, 14)
    assert d["adx"].dropna().min() >= 0 and d["adx"].dropna().max() <= 100
    b = I.bollinger(c)
    assert (b["upper"] - b["mid"]).iloc[-1] == pytest.approx((b["mid"] - b["lower"]).iloc[-1])
    flat = I.adx(pd.Series([10.0] * 60) + 1, pd.Series([10.0] * 60) - 1, pd.Series([10.0] * 60), 14)
    assert (
        flat["adx"].dropna().empty or (flat["adx"].dropna() == 0).all() or flat["adx"].isna().all()
    )  # no trend -> no strength


def test_downside_vol_and_trend_classification_rules() -> None:
    assert I.downside_vol(pd.Series([0.01] * 63), 63) == 0.0
    assert I.downside_vol(pd.Series([-0.01] * 63), 63) == pytest.approx(0.01 * np.sqrt(252))
    up = classify_trend(
        {"close": 110.0, "sma20": 105.0, "sma50": 100.0, "sma200": 90.0, "sma200_slope_20": 0.02}
    )
    assert up["state"] == "STRONG_UPTREND" and up["score"] == 5
    mixed = classify_trend(
        {"close": 99.0, "sma20": 100.0, "sma50": 98.0, "sma200": 90.0, "sma200_slope_20": 0.01}
    )
    assert mixed["state"] == "UPTREND" and any(
        not e["positive"] for e in mixed["evidence"] if e["available"]
    )
    assert (
        classify_trend(
            {"close": 80.0, "sma20": 90.0, "sma50": 95.0, "sma200": 100.0, "sma200_slope_20": -0.05}
        )["state"]
        == "STRONG_DOWNTREND"
    )
    few = classify_trend(
        {"close": 1.0, "sma20": None, "sma50": None, "sma200": None, "sma200_slope_20": None}
    )
    assert (
        few["state"] == "INSUFFICIENT_HISTORY"
    )  # state is NOT a return prediction and never invented


# ───────────────────────────── market series: split boundary, completed bars only ─────────────────
@pytest.fixture
def mk(session: Session) -> str:
    sid = make_security(session, "SYN TECH")
    load_bars(
        session,
        sid,
        "T",
        closes_path(SESSIONS),
        splits={date(2016, 3, 15): 2.0},
        dividends={date(2016, 5, 12): 0.5},
    )
    return sid


def test_split_boundary_keeps_candles_continuous_and_volume_consistent(
    session: Session, mk: str
) -> None:
    md = load_market(session, mk, AT)
    adj, raw = md.series.split_adjusted, md.bars
    day, prev = date(2016, 3, 15), CAL.previous_session(date(2016, 3, 15))
    assert raw.loc[prev, "close"] == pytest.approx(
        2 * raw.loc[day, "close"], rel=0.05
    )  # raw halves...
    assert (
        abs(adj.loc[day, "close"] / adj.loc[prev, "close"] - 1) < 0.05
    )  # ...adjusted does not jump
    assert adj.loc[prev, "volume"] == pytest.approx(
        raw.loc[prev, "volume"] * 2
    )  # volume on the post-split share basis
    ch = chart_payload(md, "MAX")
    assert ch["price_basis"] == "SPLIT_ADJUSTED_NOT_DIVIDEND_ADJUSTED" and ch["n_bars"] == len(adj)
    assert [a["kind"] for a in ch["corporate_actions"]] == ["SPLIT", "CASH_DIVIDEND"]
    # SMA over a window spanning the split equals SMA of the adjusted series (no raw mixing)
    t = compute_technicals(md)
    assert t["indicators"]["sma50"] == pytest.approx(float(adj["close"].iloc[-50:].mean()))


def test_only_completed_bars_known_at_decision_at_are_used(session: Session, mk: str) -> None:
    cal = get_calendar("XNYS")
    d = SESSIONS[300]
    before_close = cal.session_close(d) - timedelta(minutes=1)
    md = load_market(session, mk, before_close)
    assert md.last_session == SESSIONS[299]  # the session in progress is excluded
    md2 = load_market(session, mk, cal.session_close(d))
    assert md2.last_session == d
    t1, t2 = compute_technicals(md), compute_technicals(md)
    assert t1 == t2  # deterministic
    assert compute_technicals(load_market(session, mk, before_close))["last_session"] == str(
        SESSIONS[299]
    )


def test_insufficient_history_is_explicit(session: Session) -> None:
    sid = make_security(session, "SYN SHORT")
    load_bars(session, sid, "S", closes_path(SESSIONS[:20]))
    t = compute_technicals(load_market(session, sid, datetime(2015, 6, 1, tzinfo=UTC)))
    assert t["indicators"]["sma200"] is None and t["indicators"]["adx14"] is None
    assert (
        any("sma200" in w for w in t["warnings"]) and t["trend"]["state"] == "INSUFFICIENT_HISTORY"
    )
    assert (
        compute_technicals(load_market(session, make_security(session, "SYN EMPTY"), AT))["status"]
        == "NO_DATA"
    )


# ───────────────────────────── support / resistance ──────────────────────────────────────────────
def _ohlc(highs: list[float], lows: list[float]) -> pd.DataFrame:
    n = len(highs)
    idx = pd.date_range("2020-01-01", periods=n, freq="B").date
    c = [(h + lo) / 2 for h, lo in zip(highs, lows, strict=True)]
    return pd.DataFrame(
        {"open": c, "high": highs, "low": lows, "close": c, "volume": 1000.0}, index=idx
    )


def test_pivot_needs_five_later_bars_and_has_no_lookahead() -> None:
    highs = [10, 10, 10, 10, 10, 10, 11, 12, 13, 14, 20, 14, 13, 12, 11, 10, 10, 10, 10, 10, 10.0]
    lows = [h - 1 for h in highs]
    hi, _ = pivots(pd.Series(highs), pd.Series(lows))
    assert hi == [10]
    # the SAME pivot is invisible while fewer than 5 bars follow it: truncating the series drops it
    hi_trunc, _ = pivots(pd.Series(highs[:14]), pd.Series(lows[:14]))
    assert hi_trunc == []


def test_zones_cluster_by_atr_and_split_into_supports_and_resistances() -> None:
    base = 100.0
    hs, ls = [], []
    for i in range(160):
        wave = 6 * np.sin(i / 4.0)
        hs.append(base + wave + 1.0)
        ls.append(base + wave - 1.0)
    adj = _ohlc(hs, ls)
    z = compute_zones(adj, atr14=2.0)
    assert len(z["supports"]) <= 3 and len(z["resistances"]) <= 3
    last = float(adj["close"].iloc[-1])
    assert all(s["midpoint"] < last for s in z["supports"]) and all(
        r["midpoint"] > last for r in z["resistances"]
    )
    for zone in z["supports"] + z["resistances"]:
        assert (
            zone["lower"] < zone["upper"] and zone["touches"] >= 1 and 0 <= zone["strength"] <= 100
        )
        assert {"first_touch", "last_touch", "distance_pct", "distance_atr", "reasons"} <= set(zone)
    assert compute_zones(adj.iloc[:8], 2.0) == {
        "supports": [],
        "resistances": [],
    }  # not enough bars
    assert compute_zones(adj, None) == {"supports": [], "resistances": []}


# ───────────────────────────── fundamentals V1 ───────────────────────────────────────────────────
def _fy(session: Session, sid: str, concept: str, y: int, v: float, form: str = "10-K") -> None:
    add_fact(
        session,
        sid,
        concept,
        date(y, 1, 1),
        date(y, 12, 31),
        v,
        datetime(y + 1, 2, 20, 21, tzinfo=UTC),
        form=form,
    )


def test_discrete_quarters_derive_from_ytd_and_never_sum_ytd(session: Session) -> None:
    sid = make_security(session, "SYN Q")
    d = lambda y, m, dd: date(y, m, dd)  # noqa: E731
    R = "Revenues"
    add_fact(
        session, sid, R, d(2015, 1, 1), d(2015, 3, 31), 100.0, datetime(2015, 5, 1, tzinfo=UTC)
    )
    add_fact(
        session, sid, R, d(2015, 1, 1), d(2015, 6, 30), 210.0, datetime(2015, 8, 1, tzinfo=UTC)
    )  # YTD only, no discrete Q2
    add_fact(
        session, sid, R, d(2015, 1, 1), d(2015, 9, 30), 330.0, datetime(2015, 11, 1, tzinfo=UTC)
    )
    add_fact(
        session,
        sid,
        R,
        d(2015, 1, 1),
        d(2015, 12, 31),
        460.0,
        datetime(2016, 2, 1, tzinfo=UTC),
        form="10-K",
    )
    at = datetime(2016, 3, 1, tzinfo=UTC)
    q = {
        e: (v, how)
        for e, v, how in discrete_quarters(
            F.visible(load_facts(session, sid, at), at), ("Revenues",)
        )
    }
    assert [round(q[d(2015, m, dd)][0]) for m, dd in ((3, 31), (6, 30), (9, 30), (12, 31))] == [
        100,
        110,
        120,
        130,
    ]
    assert q[d(2015, 6, 30)][1] == "6M - 3M" and q[d(2015, 12, 31)][1] == "12M - 9M"
    assert sum(v for v, _ in q.values()) == pytest.approx(
        460.0
    )  # quarters add up to the fiscal year


def test_growth_cagr_not_meaningful_capex_sign_and_missing_values(session: Session) -> None:
    sid = make_security(session, "SYN GROW")
    for y, rev, ni, cfo, cap in (
        (2012, 100.0, -5.0, 10.0, 3.0),
        (2013, 110.0, 4.0, 12.0, 3.5),
        (2014, 120.0, 8.0, 14.0, 4.0),
        (2015, 150.0, 10.0, 20.0, 5.0),
    ):
        _fy(session, sid, "Revenues", y, rev)
        _fy(session, sid, "NetIncomeLoss", y, ni)
        _fy(session, sid, "NetCashProvidedByUsedInOperatingActivities", y, cfo)
        _fy(session, sid, "PaymentsToAcquirePropertyPlantAndEquipment", y, cap)
    at = datetime(2016, 3, 1, tzinfo=UTC)
    f = compute_fundamentals(session, sid, at)
    assert f["growth"]["revenue_yoy"]["value"] == pytest.approx(150 / 120 - 1)
    assert f["growth"]["revenue_cagr3"]["value"] == pytest.approx((150 / 100) ** (1 / 3) - 1)
    assert f["ttm"]["fcf"]["value"] == 15.0 and f["profitability"]["fcf_margin"][
        "value"
    ] == pytest.approx(0.1)
    # earnings that were negative 3 years earlier: a ratio CAGR is NOT_MEANINGFUL, never computed with abs()
    assert f["growth"]["operating_income_yoy"]["value"] is None  # no operating income tag at all
    sid2 = make_security(session, "SYN NEG")
    _fy(session, sid2, "Revenues", 2014, 100.0)
    _fy(session, sid2, "Revenues", 2015, 120.0)
    _fy(session, sid2, "NetIncomeLoss", 2014, -10.0)
    _fy(session, sid2, "NetIncomeLoss", 2015, 5.0)
    f2 = compute_fundamentals(session, sid2, at)
    assert (
        f2["growth"]["net_income_yoy"]["reason"] == "NOT_MEANINGFUL"
        and f2["growth"]["net_income_yoy"]["value"] is None
    )
    sid3 = make_security(session, "SYN CAPEX")
    _fy(session, sid3, "Revenues", 2015, 100.0)
    _fy(session, sid3, "NetCashProvidedByUsedInOperatingActivities", 2015, 20.0)
    _fy(session, sid3, "PaymentsToAcquirePropertyPlantAndEquipment", 2015, -5.0)  # unexpected sign
    f3 = compute_fundamentals(session, sid3, at)
    assert f3["ttm"]["fcf"]["value"] is None and f3["ttm"]["capex"]["reason"] == "sign_unexpected"
    assert any("capex" in w for w in f3["warnings"])


def test_balance_shares_split_alignment_and_materiality(session: Session) -> None:
    sid = make_security(session, "SYN BAL")
    _fy(session, sid, "Revenues", 2015, 1000.0)
    _fy(session, sid, "NetIncomeLoss", 2015, 0.5)  # |NI| below materiality: CFO/NI is meaningless
    _fy(session, sid, "NetCashProvidedByUsedInOperatingActivities", 2015, 100.0)
    av = datetime(2016, 2, 20, 21, tzinfo=UTC)
    add_fact(
        session,
        sid,
        "EntityCommonStockSharesOutstanding",
        None,
        date(2016, 2, 10),
        2000.0,
        av,
        unit="shares",
    )
    add_fact(
        session,
        sid,
        "EntityCommonStockSharesOutstanding",
        None,
        date(2015, 2, 10),
        1000.0,
        datetime(2015, 2, 20, tzinfo=UTC),
        unit="shares",
    )
    for tag, v in (
        ("Assets", 500.0),
        ("AssetsCurrent", 200.0),
        ("LiabilitiesCurrent", 100.0),
        ("CashAndCashEquivalentsAtCarryingValue", 50.0),
        ("LongTermDebt", 120.0),
        ("StockholdersEquity", 300.0),
    ):
        add_fact(session, sid, tag, None, date(2015, 12, 31), v, av, form="10-K")
    split = CorporateAction(
        "X",
        K.SPLIT,
        datetime(2015, 6, 1, tzinfo=UTC),
        Provenance("SYN", SourceTier.FIXTURE, "s", "0" * 64, "t"),
        ex_date=date(2015, 9, 1),
        ratio=2.0,
    )
    f = compute_fundamentals(session, sid, datetime(2016, 3, 1, tzinfo=UTC), actions=[split])
    assert f["quality"]["cfo_to_net_income"]["reason"] == "NOT_MEANINGFUL"
    assert f["capital_allocation"]["shares_growth1"]["value"] == pytest.approx(
        0.0
    )  # 2000 now vs 1000 * 2 (split) one year ago: NO dilution
    b = f["balance"]
    assert (
        b["net_debt"]["value"] == pytest.approx(70.0)
        and b["current_ratio"]["value"] == pytest.approx(2.0)
        and b["debt_to_equity"]["value"] == pytest.approx(0.4)
    )
    assert (
        b["interest_coverage"]["value"] is None
    )  # interest expense not reported: no ratio invented
    assert "weighted" in f["capital_allocation"]["note"].lower()


# ───────────────────────────── valuation V1 ──────────────────────────────────────────────────────
def test_valuation_nulls_negative_denominators_and_keeps_negative_fcf_yield(
    session: Session,
) -> None:
    sid = make_security(session, "SYN VAL")
    av = datetime(2016, 2, 20, 21, tzinfo=UTC)
    add_fact(
        session,
        sid,
        "EntityCommonStockSharesOutstanding",
        None,
        date(2016, 2, 10),
        1_000.0,
        av,
        unit="shares",
    )
    _fy(session, sid, "Revenues", 2015, 5_000.0)
    _fy(session, sid, "NetIncomeLoss", 2015, -100.0)
    add_fact(session, sid, "StockholdersEquity", None, date(2015, 12, 31), -50.0, av, form="10-K")
    _fy(session, sid, "NetCashProvidedByUsedInOperatingActivities", 2015, 300.0)
    _fy(session, sid, "PaymentsToAcquirePropertyPlantAndEquipment", 2015, 500.0)
    vis = F.visible(
        load_facts(session, sid, datetime(2016, 3, 1, tzinfo=UTC)), datetime(2016, 3, 1, tzinfo=UTC)
    )
    v = valuation_point(vis, 10.0, date(2016, 2, 29), [])
    assert (
        v["market_cap"] == 10_000.0 and v["pe"] is None and v["price_to_book"] is None
    )  # NI <= 0, equity <= 0
    assert v["earnings_yield"] == pytest.approx(-0.01) and v["price_to_sales"] == pytest.approx(2.0)
    assert v["fcf_yield"] == pytest.approx(-0.02)  # negative FCF yield is valid and not truncated
    assert v["ev"] is None  # no debt/cash facts: EV withheld, no EBITDA invented
    stale = valuation_point(vis, 10.0, date(2018, 6, 1), [])
    assert stale["market_cap"] is None and stale["reason"] == "stale_data"


def test_own_history_uses_only_information_known_at_each_date(session: Session, mk: str) -> None:
    # fundamentals appear only at the end: earlier history points must NOT see them
    av = datetime(2016, 12, 1, tzinfo=UTC)
    add_fact(
        session,
        mk,
        "EntityCommonStockSharesOutstanding",
        None,
        date(2016, 11, 20),
        1_000.0,
        av,
        unit="shares",
    )
    for y in (2015,):
        add_fact(session, mk, "NetIncomeLoss", date(y, 1, 1), date(y, 12, 31), 5_000.0, av)
        add_fact(session, mk, "Revenues", date(y, 1, 1), date(y, 12, 31), 50_000.0, av)
    md = load_market(session, mk, AT)
    v = compute_valuation(md, load_facts(session, mk, AT), AT, years=2, min_points=1)
    assert v["status"] == "OK" and v["current"]["pe"] is not None
    assert (
        v["own_history_points"] == 0
    )  # no earlier date had a known share count: nothing is back-filled


# ───────────────────────────── trade plan ────────────────────────────────────────────────────────
def _tech(**over: object) -> dict:
    t = {
        "status": "OK",
        "indicators": {"atr14": 2.0, "ema20": 100.0, "sma20": 101.0, "sma50": 99.0, "sma200": 90.0},
        "trend": {"state": "UPTREND"},
        "last_close_split_adjusted": 105.0,
        "support_resistance": {
            "supports": [
                {
                    "kind": "SUPPORT",
                    "lower": 98.0,
                    "upper": 100.0,
                    "midpoint": 99.0,
                    "touches": 3,
                    "strength": 70.0,
                    "distance_atr": 3.0,
                    "distance_pct": -0.057,
                }
            ],
            "resistances": [
                {
                    "kind": "RESISTANCE",
                    "lower": 112.0,
                    "upper": 113.0,
                    "midpoint": 112.5,
                    "touches": 2,
                    "strength": 60.0,
                    "distance_atr": 3.7,
                }
            ],
            "broken_resistances": [],
        },
    }
    t.update(over)
    return t  # type: ignore[return-value]


def test_pullback_geometry_atr_buffer_and_targets() -> None:
    p = build_trade_plan(_tech(), "2026-10-02T00:00:00+00:00")
    assert (
        p["status"] == "SETUPS_AVAILABLE"
        and p["validation_status"] == "RULE_BASED_NOT_BACKTEST_VALIDATED"
    )
    base = next(s for s in p["setups"] if s["type"] == "PULLBACK" and s["profile"] == "BASE")
    assert base["stop"] == pytest.approx(
        98.0 - 0.5 * 2.0
    )  # support.lower - 0.5 ATR, never a % stop
    assert base["entry"] == pytest.approx(100.0 + 0.25 * 2.0) and base["invalidation_level"] == 98.0
    r = base["entry"] - base["stop"]
    assert [t["price"] for t in base["r_targets"]] == pytest.approx(
        [base["entry"] + m * r for m in (1.5, 2.0, 3.0)]
    )
    assert base["structural_target"]["price"] == 112.0  # next resistance above entry
    assert {s["profile"] for s in p["setups"]} == {"AGGRESSIVE", "BASE", "CONSERVATIVE"} and len(
        {round(s["stop"], 6) for s in p["setups"]}
    ) == 1  # profiles never move the stop
    assert any("EMA20" in c or "SMA20" in c for c in base["confluence"])


def test_no_setup_without_structure_or_against_trend() -> None:
    none = build_trade_plan(
        _tech(support_resistance={"supports": [], "resistances": [], "broken_resistances": []}), "x"
    )
    assert none["status"] == "NO_VALID_SETUP" and none["setups"] == []
    down = build_trade_plan(_tech(trend={"state": "DOWNTREND"}), "x")
    assert down["status"] == "NO_VALID_SETUP" and "DOWNTREND" in down["reason"]
    assert build_trade_plan({"status": "NO_DATA"}, "x")["status"] == "NO_DATA"
    far = _tech()
    far["support_resistance"]["supports"][0]["distance_atr"] = 6.0
    assert build_trade_plan(far, "x")["status"] == "NO_VALID_SETUP"  # support too far away


def test_breakout_retest_needs_a_confirmed_close_above_the_zone() -> None:
    broken = {
        "lower": 103.0,
        "upper": 104.0,
        "midpoint": 103.5,
        "touches": 3,
        "trigger": 104.5,
        "broke_on": "2026-09-20",
        "distance_atr": 0.5,
    }
    t = _tech(
        support_resistance={"supports": [], "resistances": [], "broken_resistances": [broken]}
    )
    p = build_trade_plan(t, "x")
    s = next(
        x for x in p["setups"] if x["type"] == "BREAKOUT_RETEST" and x["profile"] == "AGGRESSIVE"
    )
    assert (
        s["entry"] == 104.0
        and s["stop"] == pytest.approx(103.0 - 1.0)
        and "breakout confirmed" in s["conditions"][0]
    )
    far = dict(broken, distance_atr=3.5)  # price already too far above: retest not plausible
    assert (
        build_trade_plan(
            _tech(
                support_resistance={"supports": [], "resistances": [], "broken_resistances": [far]}
            ),
            "x",
        )["status"]
        == "NO_VALID_SETUP"
    )


def test_breakout_detection_ignores_unconfirmed_and_incomplete_moves() -> None:
    lows = [99.0] * 50
    highs = [101.0] * 50
    for i in (10, 25):  # two swing highs at ~110 (a resistance zone)
        highs[i] = 110.0
    adj = _ohlc(highs, lows)
    adj.loc[adj.index[-1], "close"] = (
        110.2  # a last close only 0.2 above the zone: NOT > upper + 0.25 ATR
    )
    z = compute_zones(adj, atr14=2.0, last_close=110.2)
    assert z["broken_resistances"] == []
    adj2 = adj.copy()
    adj2.iloc[-6:, adj2.columns.get_loc("close")] = (
        113.0  # a completed close beyond upper + 0.25*ATR, after trading below
    )
    adj2.iloc[-6:, adj2.columns.get_loc("high")] = 113.5
    z2 = compute_zones(adj2, atr14=2.0, last_close=113.0)
    assert z2["broken_resistances"] and z2["broken_resistances"][0]["trigger"] == pytest.approx(
        110.0 + 0.5 + 0.0, abs=0.6
    )


def test_position_size_floor_no_leverage_and_validation() -> None:
    p = position_size(capital=100_000, risk_pct=1.0, entry=100.0, stop=95.0)
    assert (
        p["status"] == "OK"
        and p["risk_amount"] == 1_000.0
        and p["shares"] == 200
        and p["notional"] == 20_000.0
        and p["actual_risk"] == 1_000.0
    )
    cap = position_size(capital=1_000, risk_pct=5.0, entry=100.0, stop=99.0)
    assert (
        cap["shares"] == 10 and cap["capped_by_capital_no_leverage"] is True
    )  # 50 shares would need leverage
    assert (
        position_size(0, 1, 100, 95)["status"] == "INVALID_INPUT"
        and position_size(1000, 1, 100, 100)["status"] == "INVALID_INPUT"
    )


# ───────────────────────────── analysis engine ───────────────────────────────────────────────────
def test_analysis_labels_never_strong_with_poor_coverage_and_missing_is_not_50() -> None:
    thin = {"profitability": {"operating_margin": {"value": 0.4}}}
    a = build_analysis(
        {"status": "OK", "trend": {"state": "UPTREND"}},
        thin,
        {"own_history": {}},
        {"status": "EOD"},
        "STANDARD_CORPORATE",
    )
    assert (
        a["labels"]["fundamentals"]["label"] == "Insufficient"
        and a["labels"]["valuation"]["label"] == "Insufficient"
    )
    assert (
        a["labels"]["trend"]["label"] == "Uptrend"
        and a["not_a_prediction"] is True
        and a["status"] == "AVAILABLE"
    )
    bank = build_analysis({"status": "OK"}, {}, {}, {"status": "EOD"}, "BANK")
    assert (
        "NOT YET SUPPORTED" in bank["labels"]["fundamentals"]["note"]
        and bank["labels"]["growth"]["label"] == "Insufficient"
    )
    pr = positives_and_risks(
        {"profitability": {"operating_margin": {"value": 0.35}, "net_margin": {"value": -0.1}}},
        {"own_history": {"pe": {"percentile": 95.0}}},
        {"trend": {"state": "UPTREND", "score": 4}},
    )
    codes = {x["reason_code"] for x in pr["positives"]} | {x["reason_code"] for x in pr["risks"]}
    assert {
        "HIGH_OPERATING_MARGIN",
        "UPTREND",
        "NEGATIVE_EARNINGS",
        "EXPENSIVE_VS_OWN_HISTORY",
    } <= codes
    assert all(
        {"reason_code", "metric", "value", "reference", "rendered_text"} <= set(x)
        for x in pr["positives"] + pr["risks"]
    )  # structured, not free text


# ───────────────────────────── corporate actions: one economic event, one action ─────────────────
def _ca(
    kind: K,
    tier: SourceTier,
    raw: str,
    anchor: date,
    ratio: float | None = None,
    cash: float | None = None,
    at: datetime = datetime(2020, 1, 1, tzinfo=UTC),
) -> CorporateAction:
    return CorporateAction(
        "X",
        kind,
        at,
        Provenance(f"P-{tier}", tier, raw, "0" * 64, "t"),
        ex_date=anchor if True else None,
        ratio=ratio,
        cash_amount=cash,
        currency="USD" if cash else None,
    )


def test_collapse_keeps_official_over_vendor_and_flags_nothing_silent() -> None:
    off = _ca(K.SPLIT, SourceTier.OFFICIAL, "o", date(2020, 8, 31), ratio=4.0)
    ven = _ca(K.SPLIT, SourceTier.VENDOR, "v", date(2020, 8, 31), ratio=4.0)
    assert [a.provenance.tier for a in collapse_equivalent([ven, off])] == [SourceTier.OFFICIAL]
    contradiction = _ca(K.SPLIT, SourceTier.VENDOR, "v2", date(2020, 8, 31), ratio=2.0)
    assert (
        len(collapse_equivalent([off, contradiction])) == 2
    )  # a contradicting ratio stays visible
    d_off = _ca(K.SPECIAL_DIVIDEND, SourceTier.OFFICIAL, "o", date(2004, 11, 15), cash=3.00)
    d_ven = _ca(K.CASH_DIVIDEND, SourceTier.VENDOR, "v", date(2004, 11, 15), cash=3.08)
    kept = collapse_equivalent([d_ven, d_off])
    assert (
        len(kept) == 1 and kept[0].cash_amount == 3.00
    )  # MSFT 2004: official 3.00 wins; the vendor 3.08 is not added
    other_day = _ca(K.CASH_DIVIDEND, SourceTier.VENDOR, "v3", date(2004, 11, 16), cash=0.08)
    assert len(collapse_equivalent([d_off, other_day])) == 2


# ───────────────────────────── search ────────────────────────────────────────────────────────────
def test_search_exact_name_fuzzy_and_unknown(session: Session) -> None:
    from pitquant.security_master.service import SecurityMaster

    sm = SecurityMaster(session)
    for name, tick in (("SYN APPLE INC", "SYNA"), ("SYN COCA COLA CO", "SYNC")):
        sid = sm.register(name=name, exchange="XNYS", currency="USD").security_id
        sm.add_ticker(sid, tick, "XNYS", date(2010, 1, 4))
    ex = search(session, "SYNA")
    assert (
        ex["exact"] is True
        and ex["results"][0]["ticker"] == "SYNA"
        and ex["results"][0]["match_type"] == "EXACT"
    )
    by_name = search(session, "coca")
    assert by_name["results"][0]["ticker"] == "SYNC" and by_name["exact"] is False
    fuzzy = search(session, "SYNB")
    assert fuzzy["exact"] is False and all(
        r["match_type"] != "EXACT" for r in fuzzy["results"]
    )  # never silently resolved
    assert search(session, "zzzzzz")["results"] == [] and search(session, "")["results"] == []
