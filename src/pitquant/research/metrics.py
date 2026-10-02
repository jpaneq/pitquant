# ruff: noqa: E501
"""Metric schemas and pure functions (no data is generated; the UI shows nothing until a run exists)."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class RegressionMetrics:
    mae: float | None = None
    rmse: float | None = None
    spearman_ic: float | None = None
    pearson_ic: float | None = None
    n: int = 0


@dataclass(frozen=True)
class ClassificationMetrics:
    brier: float | None = None
    log_loss: float | None = None
    roc_auc: float | None = None
    calibration: list[tuple[float, float, int]] = field(
        default_factory=list
    )  # (mean predicted, observed rate, n) per bin
    n: int = 0


@dataclass(frozen=True)
class RankingMetrics:
    decile_mean_return: list[float | None] = field(default_factory=list)  # D1..D10
    d10_minus_d1: float | None = None
    monotonicity: float | None = None  # Spearman between decile index and mean return
    hit_rate_by_decile: list[float | None] = field(default_factory=list)
    n: int = 0


def _rank(x: np.ndarray) -> np.ndarray:
    order = x.argsort(kind="mergesort")
    ranks = np.empty(len(x))
    ranks[order] = np.arange(len(x), dtype=float)
    # average ranks for ties
    for v in np.unique(x):
        m = x == v
        if m.sum() > 1:
            ranks[m] = ranks[m].mean()
    return ranks


def pearson(a: np.ndarray, b: np.ndarray) -> float | None:
    if len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def spearman(a: np.ndarray, b: np.ndarray) -> float | None:
    return pearson(_rank(np.asarray(a, float)), _rank(np.asarray(b, float)))


def regression_metrics(y: np.ndarray, p: np.ndarray) -> RegressionMetrics:
    y, p = np.asarray(y, float), np.asarray(p, float)
    if len(y) == 0:
        return RegressionMetrics()
    return RegressionMetrics(
        float(np.mean(np.abs(y - p))),
        float(np.sqrt(np.mean((y - p) ** 2))),
        spearman(y, p),
        pearson(y, p),
        len(y),
    )


def roc_auc(y: np.ndarray, p: np.ndarray) -> float | None:
    y, p = np.asarray(y, int), np.asarray(p, float)
    pos, neg = p[y == 1], p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    r = _rank(np.concatenate([pos, neg]))
    return float(
        ((r[: len(pos)] + 1).sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))
    )


def classification_metrics(y: np.ndarray, p: np.ndarray, bins: int = 10) -> ClassificationMetrics:
    y, p = np.asarray(y, float), np.clip(np.asarray(p, float), 1e-12, 1 - 1e-12)
    if len(y) == 0:
        return ClassificationMetrics()
    cal = []
    edges = np.linspace(0, 1, bins + 1)
    for lo, hi in itertools.pairwise(edges):
        m = (p >= lo) & ((p < hi) if hi < 1 else (p <= hi))
        if m.any():
            cal.append((float(p[m].mean()), float(y[m].mean()), int(m.sum())))
    ll = float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
    return ClassificationMetrics(
        float(np.mean((p - y) ** 2)), ll, roc_auc(y.astype(int), p), cal, len(y)
    )


def ranking_metrics(
    score: np.ndarray, ret: np.ndarray, hit: np.ndarray | None = None
) -> RankingMetrics:
    s, r = np.asarray(score, float), np.asarray(ret, float)
    if len(s) < 10:
        return RankingMetrics(n=len(s))
    rk = _rank(s)
    dec = np.minimum((rk / len(s) * 10).astype(int), 9)
    means = [float(r[dec == d].mean()) if (dec == d).any() else None for d in range(10)]
    hits = [
        float((np.asarray(hit)[dec == d]).mean()) if hit is not None and (dec == d).any() else None
        for d in range(10)
    ]
    ok = [(i, m) for i, m in enumerate(means) if m is not None]
    mono = (
        spearman(np.array([i for i, _ in ok], float), np.array([m for _, m in ok], float))
        if len(ok) >= 3
        else None
    )
    spread = None if means[0] is None or means[9] is None else means[9] - means[0]
    return RankingMetrics(means, spread, mono, hits, len(s))
