# ruff: noqa: E501
"""Position review V0 (pure rules, SYNTHETIC contexts): add / hold / sell by horizon. Not a prediction."""

from datetime import UTC, datetime, timedelta

import pytest

from pitquant.positions.review import Context, Position, horizon_bucket, review

T0 = datetime(2026, 1, 5, tzinfo=UTC)


def pos(months=6, avg=100.0, days=30, **kw) -> tuple[Position, datetime]:
    return Position(avg, 10.0, T0, months, **kw), T0 + timedelta(days=days)


def ctx(**kw) -> Context:
    base = dict(
        price=110.0,
        atr14=2.0,
        trend_state="UPTREND",
        close_vs_sma200=0.10,
        close_vs_sma50=0.03,
        ret_6m=0.20,
        rsi14=60.0,
        valuation_label="Fair",
        fundamentals_label="Strong",
        support_lower=100.0,
    )
    return Context(**{**base, **kw})


def test_buckets() -> None:
    assert [horizon_bucket(m) for m in (1, 3, 4, 8, 9, 24)] == [
        "SHORT",
        "SHORT",
        "MEDIUM",
        "MEDIUM",
        "LONG",
        "LONG",
    ]


def test_strong_picture_with_room_to_run_suggests_adding() -> None:
    p, now = pos(12)
    r = review(p, ctx(trend_state="STRONG_UPTREND", valuation_label="Cheap"), now)
    assert r["recommendation"] == "ADD" and r["score"] >= 2.5 and r["horizon_bucket"] == "LONG"
    assert r["label"].startswith("RULE_BASED") and "NOT A PREDICTION" in r["label"] and r["rules"]


def test_overextended_price_blocks_adding_but_does_not_sell() -> None:
    p, now = pos(12)
    r = review(
        p,
        ctx(trend_state="STRONG_UPTREND", valuation_label="Cheap", close_vs_sma50=0.20, rsi14=78.0),
        now,
    )
    assert r["recommendation"] == "HOLD" and "no se amplía" in r["reason"]


def test_horizon_changes_the_answer_for_the_same_facts() -> None:
    # expensive valuation and weak fundamentals matter for a 24-month view, hardly for a 1-month one
    facts = ctx(
        valuation_label="Expensive",
        fundamentals_label="Weak",
        trend_state="UPTREND",
        close_vs_sma200=0.05,
    )
    short, now_s = pos(1, days=5)
    long_, now_l = pos(24, days=5)
    rs, rl = review(short, facts, now_s), review(long_, facts, now_l)
    assert (
        rs["horizon_bucket"] == "SHORT"
        and rl["horizon_bucket"] == "LONG"
        and rs["score"] > rl["score"]
    )


def test_stop_hit_overrides_everything() -> None:
    p, now = pos(12, stop_price=105.0)
    r = review(p, ctx(price=104.0, trend_state="STRONG_UPTREND"), now)
    assert r["recommendation"] == "SELL" and r["hard_rules"][0]["id"] == "STOP_HIT"


def test_bearish_picture_suggests_selling_for_a_medium_horizon() -> None:
    p, now = pos(6)
    r = review(
        p,
        ctx(
            trend_state="STRONG_DOWNTREND",
            close_vs_sma200=-0.12,
            ret_6m=-0.25,
            valuation_label="Expensive",
            fundamentals_label="Weak",
            price=90.0,
            support_lower=95.0,
        ),
        now,
    )
    assert r["recommendation"] == "SELL" and r["score"] <= -2.0


def test_target_met_sells_unless_the_signal_is_still_strong() -> None:
    p, now = pos(12, target_return=0.10)
    weak = review(p, ctx(trend_state="SIDEWAYS", close_vs_sma200=-0.01, ret_6m=-0.02), now)
    strong = review(p, ctx(trend_state="STRONG_UPTREND", valuation_label="Cheap"), now)
    assert (
        weak["recommendation"] == "SELL"
        and "Objetivo" in weak["reason"]
        and strong["recommendation"] == "HOLD"
        and strong["position"]["target_met"] is True
    )


def test_horizon_reached_with_a_profit_and_a_weak_signal_sells_and_with_a_strong_one_holds() -> (
    None
):
    p, now = pos(3, days=100)
    assert (
        review(p, ctx(trend_state="SIDEWAYS", close_vs_sma200=-0.02, ret_6m=-0.01), now)[
            "recommendation"
        ]
        == "SELL"
    )
    assert (
        review(p, ctx(trend_state="STRONG_UPTREND", valuation_label="Cheap"), now)["recommendation"]
        == "HOLD"
    )
    assert review(p, ctx(), now)["position"]["months_remaining"] < 0


def test_missing_facts_are_skipped_not_guessed() -> None:
    p, now = pos(6)
    r = review(p, Context(price=110.0), now)
    assert (
        r["rules"] == []
        and r["recommendation"] == "HOLD"
        and set(r["missing_rules"])
        == {"trend", "long_trend", "momentum", "valuation", "fundamentals", "support"}
    )


def test_pnl_and_months_are_reported() -> None:
    p, now = pos(6, avg=100.0, days=61)
    r = review(p, ctx(price=125.0), now)["position"]
    assert (
        r["pnl_pct"] == pytest.approx(0.25)
        and r["pnl_value"] == pytest.approx(250.0)
        and r["months_elapsed"] == pytest.approx(2.0, abs=0.05)
    )
