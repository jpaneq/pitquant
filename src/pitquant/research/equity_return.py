# ruff: noqa: E501
"""Frozen adaptive DEV continuous-return research, without target transformation."""

from __future__ import annotations

import gzip
import warnings
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import rankdata
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import ElasticNet, Ridge
from threadpoolctl import threadpool_limits

from pitquant.research import equity_baseline as E
from pitquant.research import equity_v1 as V
from pitquant.research.metrics import spearman

EXPERIMENT = "FIRST_EQUITY_RETURN_12M_V0"
STATUS = ["RESEARCH_DEV_ONLY", "ADAPTIVE_DEV", "RETROSPECTIVE_UNVALIDATED"]
ALPHAS = (0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1.0)
RATIOS = (0.0, 0.25, 0.5, 0.75, 1.0)
GRID = tuple((alpha, ratio) for alpha in ALPHAS for ratio in RATIOS)
PAIRS = (("R2", "R0"), ("R3", "R0"), ("R4", "R0"), ("R4", "R2"), ("R4", "R3"))
SPEC: dict[str, Any] = {
    "fit_intercept": True,
    "copy_X": True,
    "positive": False,
    "precompute": False,
    "warm_start": False,
    "ridge_fixed_parameters": {
        "fit_intercept": True,
        "solver": "svd",
        "copy_X": True,
        "positive": False,
        "tol": 1e-8,
        "random_state": E.SEED,
    },
    "max_iter": 100000,
    "tol": 1e-8,
    "selection": "cyclic",
    "random_state": E.SEED,
    "primary_selection_metric": "row_weighted_inner_OOF_MAE",
    "secondary_metric": "RMSE_DIAGNOSTIC_ONLY",
    "mae_tie_atol": 1e-12,
    "tie_order": ["larger alpha", "smaller mean inner nonzero count", "smaller l1_ratio"],
    "nonzero_atol": 1e-12,
    "ridge_equivalence": "l1_ratio=0: Ridge(solver=svd, alpha=n_train*elastic_net_alpha)",
    "target_transform": "NONE; no scaling/clipping/winsorization",
    "bootstrap": "1000 paired complete-month resamples; same draws for every model",
    "undefined_ranking": "NA, never zero; pairwise month intersection for ranking deltas",
}
RULES = {
    "ROBUST_RETURN_SIGNAL": "Any R2/R3/R4 improves MAE and RMSE vs R0 in every fold, has positive mean monthly IC and spread with all 12 months defined in every fold, and pooled MAE/RMSE delta IC95 wholly negative",
    "PROMISING_RETURN_RANKING": "Otherwise any candidate has positive mean monthly IC and spread with all 12 months defined in every fold",
    "RETURN_SIGNAL_UNSTABLE": "Otherwise any candidate has positive pooled mean monthly IC and spread, with at least one fold not both positive",
    "WEAK_RETURN_SIGNAL": "Otherwise any candidate has positive pooled mean monthly IC or spread",
    "NO_RETURN_SIGNAL": "Otherwise",
    "scope": "Ordered descriptive rules; adaptive exploratory evidence, not production validation",
}


def immutable_gzip(path: Path, obj: Any) -> str:
    raw = E.encoded(obj)
    compressed = gzip.compress(raw, mtime=0)
    if path.exists():
        if path.read_bytes() != compressed:
            raise ValueError("immutable artifact differs")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as f:
            f.write(compressed)
    return E.digest(obj)


def target(rows: list[dict[str, Any]]) -> np.ndarray:
    values = np.array([r["excess_return"] for r in rows], dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("invalid continuous target STOP")
    return values


def distribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    y = target(rows)
    names = ("min", "p01", "p05", "p25", "median", "p75", "p95", "p99", "max")
    qs = np.quantile(y, [0, 0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99, 1])
    low, high = qs[3] - 3 * (qs[5] - qs[3]), qs[5] + 3 * (qs[5] - qs[3])
    return {
        "n": len(y),
        "mean": float(y.mean()),
        "std_ddof0": float(y.std()),
        **dict(zip(names, qs.tolist(), strict=True)),
        "outlier_rule": "outside Q1-3*IQR / Q3+3*IQR; descriptive only, all retained",
        "outliers": [
            {"security_id": r["security_id"], "decision_at": r["decision_at"], "value": float(v)}
            for r, v in zip(rows, y, strict=True)
            if v < low or v > high
        ],
        "target_transform": "NONE",
    }


def train_mean(rows: list[dict[str, Any]]) -> float:
    return float(target(rows).mean())


def fit_model(
    train: list[dict[str, Any]],
    test: list[dict[str, Any]],
    names: tuple[str, ...],
    alpha: float,
    ratio: float,
) -> tuple[np.ndarray, dict[str, Any]]:
    if (alpha, ratio) not in GRID:
        raise ValueError("hyperparameters outside frozen grid")
    processor = E.TrainPreprocessor(E.matrix(train, names))
    x = processor.transform(E.matrix(train, names))
    xt = processor.transform(E.matrix(test, names))
    y = target(train)
    params = {
        k: SPEC[k]
        for k in (
            "fit_intercept",
            "max_iter",
            "tol",
            "selection",
            "random_state",
            "copy_X",
            "positive",
            "precompute",
            "warm_start",
        )
    }

    def estimator() -> Any:
        return (
            Ridge(alpha=len(y) * alpha, **SPEC["ridge_fixed_parameters"])
            if ratio == 0
            else ElasticNet(alpha=alpha, l1_ratio=ratio, **params)
        )

    with threadpool_limits(limits=1), warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model = estimator().fit(x, y)
        p = model.predict(xt)
        repeated = estimator().fit(x, y).predict(xt)
    if any(issubclass(w.category, ConvergenceWarning) for w in caught) or (
        ratio > 0 and model.n_iter_ >= SPEC["max_iter"]
    ):
        raise ValueError("nonconvergent regression STOP")
    if not np.isfinite(p).all() or not np.allclose(p, repeated, rtol=0, atol=1e-12):
        raise ValueError("invalid/nondeterministic regression STOP")
    coefficients = np.asarray(model.coef_)
    return np.asarray(p), {
        "alpha": alpha,
        "l1_ratio": ratio,
        "estimator": "RidgeEquivalent" if ratio == 0 else "ElasticNet",
        "estimator_params": model.get_params(),
        "features": names,
        "transformed_features": list(names) + [n + "__missing" for n in names],
        "preprocessing": processor.parameters(),
        "coefficients": coefficients.tolist(),
        "intercept": float(model.intercept_),
        "n_iter": int(model.n_iter_) if ratio > 0 else None,
        "nonzero_count": int(np.sum(np.abs(coefficients) > 1e-12)),
        "l1_norm": float(np.linalg.norm(coefficients, ord=1)),
        "l2_norm": float(np.linalg.norm(coefficients)),
        "warnings": [str(w.message) for w in caught],
        "train_keys_hash": E.digest([V.key(r) for r in train]),
        "target_values_hash": E.digest(y.tolist()),
        "target_transform": "NONE",
        "reproduction_max_abs_difference": float(np.max(np.abs(p - repeated))),
        "status": STATUS,
    }


def choose(scores: list[dict[str, Any]]) -> tuple[float, float]:
    if {(s["alpha"], s["l1_ratio"]) for s in scores} != set(GRID) or not all(
        np.isfinite(s["mae"]) for s in scores
    ):
        raise ValueError("invalid frozen candidate scores")
    best = min(s["mae"] for s in scores)
    tied = [s for s in scores if s["mae"] <= best + SPEC["mae_tie_atol"]]
    winner = min(tied, key=lambda s: (-s["alpha"], s["mean_nonzero_count"], s["l1_ratio"]))
    return float(winner["alpha"]), float(winner["l1_ratio"])


def summary(values: list[float]) -> dict[str, Any]:
    return {
        "n_available": len(values),
        "mean": float(np.mean(values)) if values else None,
        "median": float(np.median(values)) if values else None,
        "positive_fraction": float(np.mean(np.array(values) > 0)) if values else None,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
        "std_ddof0": float(np.std(values)) if values else None,
    }


def ranking(rows: list[dict[str, Any]]) -> dict[str, Any]:
    months = sorted({r["decision_at"][:7] for r in rows})
    monthly = []
    for month in months:
        rs = [r for r in rows if r["decision_at"][:7] == month]
        p = np.array([r["raw_score"] for r in rs])
        y = np.array([r["future_excess_return_12m"] for r in rs])
        monthly.append({"month": month, "n": len(rs), "rank_ic": spearman(p, y)})
    buckets = E.buckets(rows, 5)
    return {
        "pooled_observation_ic": spearman(
            np.array([r["raw_score"] for r in rows]),
            np.array([r["future_excess_return_12m"] for r in rows]),
        ),
        "monthly_ic": monthly,
        "mean_monthly_cross_sectional_ic": summary(
            [r["rank_ic"] for r in monthly if r["rank_ic"] is not None]
        ),
        "quintiles": buckets,
        "monthly_spread": summary(
            [r["excess_spread"] for r in buckets["monthly"] if r["status"] == "AVAILABLE"]
        ),
        "ranking_warning": "Constant predictions have undefined IC/spread; no artificial zero baseline.",
    }


def metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    y = np.array([r["realized_excess_return"] for r in rows])
    p = np.array([r["predicted_excess_return"] for r in rows])
    error = y - p
    variation = float(np.sum((y - y.mean()) ** 2))
    return {
        "n": len(rows),
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "r2": 1 - float(np.sum(error**2)) / variation if variation > 0 else None,
        "pearson": float(np.corrcoef(y, p)[0, 1]) if np.std(y) > 0 and np.std(p) > 1e-12 else None,
        **ranking(rows),
    }


def assign_ranks(rows: list[dict[str, Any]]) -> None:
    for month in sorted({r["decision_at"][:7] for r in rows}):
        rs = [r for r in rows if r["decision_at"][:7] == month]
        ranks = rankdata([r["predicted_excess_return"] for r in rs], method="average")
        for row, rank in zip(rs, ranks, strict=True):
            row["rank"] = float(rank)


def bootstrap(
    predictions: dict[str, list[dict[str, Any]]], repetitions: int = 1000
) -> dict[str, Any]:
    months = sorted({r["decision_at"][:7] for r in predictions["R0"]})
    grouped = {
        m: {month: [r for r in rs if r["decision_at"][:7] == month] for month in months}
        for m, rs in predictions.items()
    }
    ranks = {m: ranking(rs) for m, rs in predictions.items()}
    ic = {
        m: {r["month"]: r["rank_ic"] for r in v["monthly_ic"] if r["rank_ic"] is not None}
        for m, v in ranks.items()
    }
    spread = {
        m: {
            r["month"]: r["excess_spread"]
            for r in v["quintiles"]["monthly"]
            if r["status"] == "AVAILABLE"
        }
        for m, v in ranks.items()
    }
    deltas: dict[str, dict[str, list[float]]] = {
        a + "-" + b: {k: [] for k in ("mae", "rmse", "monthly_rank_ic", "spread")} for a, b in PAIRS
    }
    draws = np.random.default_rng(E.SEED).integers(0, len(months), size=(repetitions, len(months)))
    for draw in draws:
        sampled = [months[i] for i in draw]
        errors = {}
        for m, groups in grouped.items():
            rs = [r for month in sampled for r in groups[month]]
            e = np.array([r["predicted_excess_return"] - r["realized_excess_return"] for r in rs])
            errors[m] = {"mae": float(np.mean(np.abs(e))), "rmse": float(np.sqrt(np.mean(e**2)))}
        for a, b in PAIRS:
            for metric in ("mae", "rmse"):
                deltas[a + "-" + b][metric].append(errors[a][metric] - errors[b][metric])
            for metric, available in (("monthly_rank_ic", ic), ("spread", spread)):
                differences = [
                    available[a][month] - available[b][month]
                    for month in sampled
                    if month in available[a] and month in available[b]
                ]
                if differences:
                    deltas[a + "-" + b][metric].append(float(np.mean(differences)))
    return {
        "status": "ADAPTIVE_DEV_EXPLORATORY_INTERVAL",
        "repetitions": repetitions,
        "seed": E.SEED,
        "draws_hash": E.digest(draws.tolist()),
        "paired_deltas": {
            pair: {
                k: {
                    "n": len(values),
                    "low": float(np.quantile(values, 0.025)) if values else None,
                    "high": float(np.quantile(values, 0.975)) if values else None,
                    "status": "AVAILABLE" if values else "NOT_IDENTIFIABLE_CONSTANT_BASELINE",
                }
                for k, values in v.items()
            }
            for pair, v in deltas.items()
        },
        "paired_ranking_month_counts": {
            a + "-" + b: {
                "ic": len(set(ic[a]) & set(ic[b])),
                "spread": len(set(spread[a]) & set(spread[b])),
            }
            for a, b in PAIRS
        },
        "limitation": "Paired complete months preserve within-month dependence, not all H12 serial dependence. Undefined ranking remains NA; rank deltas use paired available months only. Adaptive DEV, not independent confirmation.",
    }
