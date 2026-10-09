"""Frozen monthly ranking diagnostics; not a portfolio engine."""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.stats import rankdata, spearmanr


def ic(score: np.ndarray, target: np.ndarray) -> float | None:
    if len(score) < 2 or np.ptp(score) == 0 or np.ptp(target) == 0:
        return None
    value = float(spearmanr(score, target).statistic)
    return value if np.isfinite(value) else None


def grades(target: np.ndarray) -> np.ndarray:
    if len(target) < 2:
        raise ValueError("query N<2")
    percentile = (rankdata(target, method="average") - 1) / (len(target) - 1)
    return np.asarray(np.minimum(9, np.floor(10 * percentile)), dtype=float)


def bin_weights(score: np.ndarray, low: float, high: float) -> np.ndarray:
    """Fractional allocation at tied boundaries; constant scores cannot invent spread."""
    n = len(score)
    result = np.zeros(n)
    unique, counts = np.unique(score, return_counts=True)
    start = 0
    for value, count in zip(unique, counts, strict=True):
        overlap = max(0.0, min(start + count, high * n) - max(start, low * n))
        result[score == value] = overlap / count
        start += count
    if not np.isclose(result.sum(), (high - low) * n):
        raise ValueError("bin mass loss")
    return result


def ndcg(score: np.ndarray, relevance: np.ndarray, fraction: float) -> float | None:
    k = int(np.ceil(len(score) * fraction))
    discount = 1 / np.log2(np.arange(k) + 2)
    ideal = float(np.dot(np.sort(relevance)[::-1][:k], discount))
    if ideal == 0:
        return None
    dcg = 0.0
    pos = 0
    for value in np.unique(score)[::-1]:
        mask = score == value
        count = int(mask.sum())
        dcg += float(relevance[mask].mean()) * float(discount[pos : min(pos + count, k)].sum())
        pos += count
        if pos >= k:
            break
    return dcg / ideal


def weighted_median(y: np.ndarray, w: np.ndarray) -> float:
    order = np.argsort(y, kind="stable")
    cumulative = np.cumsum(w[order])
    return float(y[order[np.searchsorted(cumulative, w.sum() / 2, side="left")]])


def summary(values: list[float | None]) -> dict[str, Any]:
    defined = [v for v in values if v is not None]
    return {
        "mean": float(np.mean(defined)) if defined else None,
        "median": float(np.median(defined)) if defined else None,
        "sd": float(np.std(defined, ddof=1)) if len(defined) > 1 else None,
        "positive_fraction": sum(v > 0 for v in defined) / len(values) if values else None,
        "defined": len(defined),
        "undefined": len(values) - len(defined),
        "months": len(values),
    }


def monthly(rows: list[dict[str, Any]], score: np.ndarray) -> dict[str, Any]:
    y = np.array([r["excess_return"] for r in rows])
    g = grades(y)
    top = bin_weights(score, 0.8, 1.0)
    bottom = bin_weights(score, 0.0, 0.2)
    spread = (
        0.0
        if np.ptp(score) == 0
        else float(np.average(y, weights=top) - np.average(y, weights=bottom))
    )
    quintiles = []
    for i in range(5):
        w = bin_weights(score, i / 5, (i + 1) / 5)
        quintiles.append(
            {
                "quintile": i + 1,
                "mean": float(np.average(y, weights=w)),
                "median": weighted_median(y, w),
                "outperform_rate": float(np.average(y > 0, weights=w)),
                "N": int((w > 0).sum()),
                "effective_N": float(w.sum()),
            }
        )
    groups = []
    demeaned = np.full(len(rows), np.nan)
    sectors = np.array([r["sector"] for r in rows])
    counts = {str(s): int((sectors == s).sum()) for s in np.unique(sectors)}
    for sector in sorted(counts):
        mask = sectors == sector
        n = int(mask.sum())
        if n < 10:
            continue
        ss, yy = score[mask], y[mask]
        ti, bi = bin_weights(ss, 0.8, 1), bin_weights(ss, 0, 0.2)
        demeaned[mask] = yy - yy.mean()
        groups.append(
            {
                "sector": sector,
                "N": n,
                "ic": ic(ss, yy),
                "spread": (
                    0.0
                    if np.ptp(ss) == 0
                    else float(np.average(yy, weights=ti) - np.average(yy, weights=bi))
                ),
            }
        )
    valid = [r for r in groups if r["ic"] is not None]
    finite = np.isfinite(demeaned)
    shares = sorted(counts.values(), reverse=True)
    return {
        "month": rows[0]["month"],
        "N": len(rows),
        "ic": ic(score, y),
        "spread": spread,
        "ndcg10": ndcg(score, g, 0.1),
        "ndcg20": ndcg(score, g, 0.2),
        "quintiles": quintiles,
        "sector_groups": groups,
        "sector_ic": float(np.mean([r["ic"] for r in valid])) if valid else None,
        "sector_spread": float(np.mean([r["spread"] for r in groups])) if groups else None,
        "sector_demeaned_ic": ic(score[finite], demeaned[finite]) if finite.any() else None,
        "sector_counts": counts,
        "sector_count": len(counts),
        "largest_sector_share": shares[0] / len(rows),
        "top3_sector_share": sum(shares[:3]) / len(rows),
        "excluded_small_sector_groups": sum(n < 10 for n in counts.values()),
    }


def aggregate(months: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        k: summary([m[k] for m in months])
        for k in (
            "ic",
            "spread",
            "ndcg10",
            "ndcg20",
            "sector_ic",
            "sector_spread",
            "sector_demeaned_ic",
        )
    }
    groups = [g for m in months for g in m["sector_groups"] if g["ic"] is not None]
    result["within_sector_equal_group_ic"] = (
        float(np.mean([g["ic"] for g in groups])) if groups else None
    )
    result["within_sector_N_weighted_ic"] = (
        float(np.average([g["ic"] for g in groups], weights=[g["N"] for g in groups]))
        if groups
        else None
    )
    result["sector_groups_defined"] = len(groups)
    result["quintiles"] = [
        {
            "quintile": i + 1,
            "monthly_mean_excess": summary([m["quintiles"][i]["mean"] for m in months]),
            "monthly_median_excess": summary([m["quintiles"][i]["median"] for m in months]),
            "monthly_outperform_rate": summary(
                [m["quintiles"][i]["outperform_rate"] for m in months]
            ),
            "N": sum(m["quintiles"][i]["N"] for m in months),
            "effective_N": sum(m["quintiles"][i]["effective_N"] for m in months),
        }
        for i in range(5)
    ]
    return result


def bootstrap(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> dict[str, Any]:
    if [r["month"] for r in a] != [r["month"] for r in b]:
        raise ValueError("unpaired months")
    rng = np.random.Generator(np.random.PCG64(20261009))
    pooled: dict[str, list[float | None]] = {
        k: [] for k in ("ic", "spread", "sector_ic", "sector_spread")
    }
    fold_values: dict[str, dict[str, list[float | None]]] = {
        f: {k: [] for k in pooled} for f in ("F1", "F2", "F3")
    }
    valid = {
        k: [i for i in range(len(a)) if a[i][k] is not None and b[i][k] is not None] for k in pooled
    }
    for _ in range(1000):
        draws = {
            f: rng.integers(idx * 12, (idx + 1) * 12, size=12) for idx, f in enumerate(fold_values)
        }
        for k in pooled:
            all_diff = []
            for f, indices in draws.items():
                values = [a[int(i)][k] - b[int(i)][k] for i in indices if int(i) in valid[k]]
                original_valid = sum(
                    i in valid[k] for i in range((int(f[1]) - 1) * 12, int(f[1]) * 12)
                )
                fold_values[f][k].append(
                    float(np.mean(values)) if values and original_valid >= 6 else None
                )
                all_diff.extend(values)
            pooled[k].append(
                float(np.mean(all_diff))
                if all_diff
                and all(
                    sum(i in valid[k] for i in range(j * 12, (j + 1) * 12)) >= 6 for j in range(3)
                )
                else None
            )

    def interval(values: list[float | None]) -> dict[str, Any]:
        okay = [v for v in values if v is not None]
        return {
            "status": "AVAILABLE" if len(okay) == 1000 else "NOT_ESTIMABLE",
            "CI95": np.quantile(okay, [0.025, 0.975], method="linear").tolist()
            if len(okay) == 1000
            else None,
            "defined_samples": len(okay),
        }

    return {
        "status": "ADAPTIVE_DEV_EXPLORATORY",
        "samples": 1000,
        "seed": 20261009,
        "paired_month_counts": {k: len(v) for k, v in valid.items()},
        "combined": {k: interval(v) for k, v in pooled.items()},
        "folds": {
            f: {k: interval(v) for k, v in values.items()} for f, values in fold_values.items()
        },
    }


def classify(ltr: dict[str, Any], control: dict[str, Any]) -> str:
    p = ltr["combined"]
    folds = [ltr[f"F{i}"] for i in (1, 2, 3)]
    if (
        p["ic"]["defined"] != 36
        or any(p[k]["mean"] is None for k in ("ic", "spread", "sector_ic", "sector_spread"))
        or p["ic"]["mean"] <= 0
        or p["spread"]["mean"] <= 0
    ):
        return "NO_MEANINGFUL_RANKING_SIGNAL"
    if any(f["ic"]["mean"] <= 0 or f["spread"]["mean"] < -0.02 for f in folds):
        return "TEMPORALLY_UNSTABLE_SIGNAL"
    if p["within_sector_equal_group_ic"] <= 0 or p["sector_spread"]["mean"] <= 0:
        return "SECTOR_DRIVEN_SIGNAL"
    pc = control["combined"]
    global_deltas = [p[k]["mean"] - pc[k]["mean"] for k in ("ic", "spread")]
    if (
        all(
            f["ic"]["mean"] >= 0.02
            and f["ic"]["positive_fraction"] >= 0.5
            and f["spread"]["mean"] > 0
            and f["within_sector_equal_group_ic"] is not None
            and f["within_sector_equal_group_ic"] > 0
            and f["sector_spread"]["mean"] is not None
            and f["sector_spread"]["mean"] > 0
            for f in folds
        )
        and p["ic"]["mean"] >= 0.03
        and all(v >= 0 for v in global_deltas)
        and any(v > 0 for v in global_deltas)
        and p["within_sector_equal_group_ic"] >= pc["within_sector_equal_group_ic"]
        and p["sector_spread"]["mean"] >= pc["sector_spread"]["mean"]
    ):
        return "ROBUST_CROSS_SECTIONAL_SIGNAL"
    return "PROMISING_CROSS_SECTIONAL_SIGNAL"


def holdout_conditions(ltr: dict[str, Any]) -> bool:
    p = ltr["combined"]
    folds = [ltr[f"F{i}"] for i in (1, 2, 3)]
    f3 = folds[-1]
    return bool(
        p["ic"]["defined"] == 36
        and all(f["ic"]["mean"] is not None and f["ic"]["mean"] > 0 for f in folds)
        and p["ic"]["mean"] > 0
        and p["spread"]["mean"] > 0
        and all(f["spread"]["mean"] >= -0.02 for f in folds)
        and p["within_sector_equal_group_ic"] is not None
        and p["within_sector_equal_group_ic"] > 0
        and p["sector_spread"]["mean"] is not None
        and p["sector_spread"]["mean"] > 0
        and f3["within_sector_equal_group_ic"] is not None
        and f3["within_sector_equal_group_ic"] >= 0
        and f3["sector_spread"]["mean"] is not None
        and f3["sector_spread"]["mean"] >= 0
    )
