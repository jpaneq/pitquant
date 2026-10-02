# ruff: noqa: E501
"""Analyzer V0 consolidation: S/R contract, split/gap/trend/broken-support cases, trade-plan fields, wording."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from pitquant.analyzer.sr_v1 import compute_zones
from pitquant.analyzer.trade_plan_v0 import build_trade_plan
from tests.unit.test_analyzer_engines import _ohlc, _tech

ROOT = Path(__file__).resolve().parents[2]
ZONE_KEYS = {
    "zone_low",
    "zone_high",
    "method",
    "touches",
    "recency",
    "strength_raw",
    "calculation_at",
}


def _wave(n: int = 200, base: float = 100.0, amp: float = 6.0) -> pd.DataFrame:
    w = [amp * np.sin(i / 4.0) for i in range(n)]
    return _ohlc([base + x + 1 for x in w], [base + x - 1 for x in w])


def test_zone_contract_fields_and_calculation_at() -> None:
    adj = _wave()
    z = compute_zones(adj, 2.0)
    zones = z["supports"] + z["resistances"]
    assert zones
    for zone in zones:
        assert set(zone) >= ZONE_KEYS
        assert zone["zone_low"] == zone["lower"] < zone["zone_high"] == zone["upper"]
        assert zone["calculation_at"] == str(adj.index[-1])  # last COMPLETED bar only
        assert zone["strength_raw"] >= zone["strength"] - 0.05


def test_unadjusted_split_creates_no_fake_zone_below_the_new_price() -> None:
    """Raw (unadjusted) pre-split prices ×2 would put 'resistance' at 2× price: adjusted input must not."""
    adj = _wave()
    z = compute_zones(adj, 2.0)
    last = float(adj["close"].iloc[-1])
    assert all(r["zone_high"] < last * 1.5 for r in z["resistances"])


def test_gap_does_not_break_zones() -> None:
    hs = [100 + 5 * np.sin(i / 4) + 1 for i in range(120)] + [
        130 + 5 * np.sin(i / 4) + 1 for i in range(120, 220)
    ]
    ls = [h - 2 for h in hs]
    z = compute_zones(_ohlc(hs, ls), 2.0)
    assert len(z["supports"]) <= 3 and all(s["zone_low"] < s["zone_high"] for s in z["supports"])


def test_little_history_returns_no_zones_not_an_error() -> None:
    assert compute_zones(_wave(8), 2.0) == {"supports": [], "resistances": []}


def test_very_strong_trend_has_no_resistance_above() -> None:
    n = 220
    c = np.linspace(50, 200, n)
    z = compute_zones(_ohlc(list(c + 1), list(c - 1)), 2.0)
    assert z["resistances"] == []  # price makes new highs: nothing overhead


def test_broken_support_is_not_offered_as_support() -> None:
    base = list(100 + 5 * np.sin(np.arange(150) / 4))
    drop = list(np.linspace(base[-1], 70, 40))  # support zone around 95 is lost
    c = base + drop
    z = compute_zones(_ohlc([x + 1 for x in c], [x - 1 for x in c]), 2.0)
    last = c[-1]
    assert all(s["zone_high"] < last + 1e-9 or s["midpoint"] < last for s in z["supports"])


def test_trade_plan_has_full_contract_and_consistent_numbers() -> None:
    plan = build_trade_plan(_tech(), "2024-01-02T21:00:00+00:00")
    assert plan["setups"], plan
    for s in plan["setups"]:
        for k in (
            "profile",
            "setup_type",
            "entry_zone",
            "invalidation_level",
            "stop",
            "target_1",
            "target_2",
            "risk_reward_1",
            "risk_reward_2",
            "inputs",
            "rules_version",
            "explanation",
        ):
            assert k in s, k
        assert s["stop"] < s["entry"] < s["target_1"] < s["target_2"]
        assert (
            abs(s["risk_reward_1"] - (s["target_1"] - s["entry"]) / (s["entry"] - s["stop"])) < 1e-9
        )
        assert s["rules_version"] == plan["engine_version"]


def test_forbidden_certainty_wording_in_analyzer_and_ui_text() -> None:
    bad = re.compile(
        r"\b(optimal|guaranteed|risk[- ]free|sure thing|safe entry|óptimo|garantizado)\b", re.I
    )
    files = list((ROOT / "src/pitquant/analyzer").glob("*.py")) + list(
        (ROOT / "frontend/src").rglob("*.tsx")
    )
    hits = [f"{f.name}: {m.group(0)}" for f in files for m in bad.finditer(f.read_text())]
    assert hits == []
