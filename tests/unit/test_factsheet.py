"""Expensive/cheap indicator (ADR-0067): percentiles of yields vs own history and vs peers."""

import pytest

from pitquant.analyzer.factsheet import YIELDS, _band, cheapness


def hist(value, n=60):
    return [dict.fromkeys(YIELDS, value + i * 1e-4) for i in range(n)]


def peers(value, n=20):
    return {f"P{i}": dict.fromkeys(YIELDS, value + i * 1e-3) for i in range(n)}


@pytest.mark.parametrize(
    "score,label",
    [(95, "MUY_BARATA"), (80, "MUY_BARATA"), (65, "BARATA"), (50, "PRECIO_NORMAL"),
     (25, "CARA"), (5, "MUY_CARA"), (0, "MUY_CARA")],
)  # fmt: skip
def test_bands(score, label):
    assert _band(score) == label


def test_cheaper_than_own_history_and_peers_scores_high():
    out = cheapness(dict.fromkeys(YIELDS, 0.20), hist(0.03), peers(0.03), "X")
    assert out["label"] == "MUY_BARATA" and out["score"] == 100
    assert out["vs_own_history"] == 100 and out["vs_peers"] == 100 and out["peers_n"] == 20


def test_expensive_and_mixed_cases():
    pricey = cheapness(dict.fromkeys(YIELDS, 0.001), hist(0.03), peers(0.03), "X")
    assert pricey["label"] == "MUY_CARA" and pricey["score"] == 0
    mixed = cheapness(dict.fromkeys(YIELDS, 0.04), hist(0.03), peers(0.05), "X")
    assert mixed["vs_own_history"] == 100 and mixed["vs_peers"] == 0
    assert mixed["label"] == "PRECIO_NORMAL"


def test_short_history_and_missing_metrics_are_not_guessed():
    current = {**dict.fromkeys(YIELDS, 0.05), "fcf_yield": None}
    out = cheapness(current, hist(0.03, n=10), peers(0.03), "X")
    assert out["vs_own_history"] is None  # < 24 monthly points: no own percentile
    fcf = next(c for c in out["components"] if c["metric"] == "fcf_yield")
    assert fcf["own_pct"] is None and fcf["peer_pct"] is None
    empty = cheapness(dict.fromkeys(YIELDS), [], {}, "X")
    assert empty["label"] == "SIN_DATOS" and empty["score"] is None


def test_company_excluded_from_its_own_peer_group():
    group = {**peers(0.03), "X": dict.fromkeys(YIELDS, 0.5)}
    out = cheapness(dict.fromkeys(YIELDS, 0.5), hist(0.03), group, "X")
    assert out["peers_n"] == 20 and out["vs_peers"] == 100
