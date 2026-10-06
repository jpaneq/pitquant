"""Adaptive DEV regularization and causal monotonic Platt; V0 stays frozen."""

from __future__ import annotations

import warnings
from datetime import datetime
from typing import Any

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit
from scipy.stats import rankdata
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from threadpoolctl import threadpool_limits

from pitquant.research import equity_baseline as E

EXPERIMENT = "FIRST_EQUITY_ML_12M_V1"
GRID = (0.01, 0.03, 0.1, 0.3, 1.0)
STATUS = ["RESEARCH_DEV_ONLY", "ADAPTIVE_DEV", "RETROSPECTIVE_UNVALIDATED"]
DATA_HASH = "5d31e90b0026b222db01068364fa9a19c04ccb2b7c2fa497d0c489ce09fc3833"
FOLD_HASH = "f33b4daffb1dc2e1cbb32fe740178533a14f289df33612d567c447eafac99944"
PAIRS = (
    ("M3R", "M3"),
    ("M3RC", "M3R"),
    ("M4R", "M4"),
    ("M4RC", "M4R"),
    ("M4R", "M3R"),
    ("M4RC", "M3RC"),
)
DESIGN: dict[str, Any] = {
    "minimum_train_calendar_months": 18,
    "validation_months": 6,
    "step_months": 6,
    "purge_plus_embargo_months": 13,
    "partial_validation_blocks": "EXCLUDED",
    "maturity": "target_end and label_available_at strictly before inner fit_at",
    "selection": "minimum row-weighted inner OOF LogLoss; tie atol=1e-12 chooses smaller C",
    "calibration": "positive-slope Platt binomial MLE on selected-C inner OOF only",
    "slope_bounds": [1e-6, None],
    "probability_clip": 1e-12,
    "ranking_invariance": (
        "within outer fold and monthly cross-section; "
        "pooled may change with different fold calibrators"
    ),
    "minimum_calibration_rows": 2,
    "calibration_identifiability": "both classes and nonconstant logits required",
}


def month_index(at: str) -> int:
    return int(at[:4]) * 12 + int(at[5:7]) - 1


def key(row: dict[str, Any]) -> tuple[str, str]:
    return row["security_id"], row["decision_at"]


def inner_folds(fold: dict[str, Any]) -> list[dict[str, Any]]:
    rows = fold["TRAIN"]
    outer_keys = {key(r) for r in fold["TEST"]}
    if outer_keys & {key(r) for r in rows}:
        raise ValueError("outer TEST contamination")
    for r in rows:
        E.assert_row(r, "TRAIN", fold["fit_at"])
    first, last = (
        min(month_index(r["decision_at"]) for r in rows),
        max(month_index(r["decision_at"]) for r in rows),
    )
    start = (
        first + DESIGN["minimum_train_calendar_months"] - 1 + DESIGN["purge_plus_embargo_months"]
    )
    result = []
    while start + 5 <= last:
        validation = [r for r in rows if start <= month_index(r["decision_at"]) <= start + 5]
        if len({month_index(r["decision_at"]) for r in validation}) != 6:
            raise ValueError("missing complete inner validation month")
        fit_at = min(r["decision_at"] for r in validation)
        fit = datetime.fromisoformat(fit_at)
        train = [
            r
            for r in rows
            if month_index(r["decision_at"]) + 13 <= start
            and datetime.fromisoformat(r["target_end"]) < fit
            and datetime.fromisoformat(r["label_available_at"]) < fit
        ]
        if len({month_index(r["decision_at"]) for r in train}) < 18:
            raise ValueError("insufficient causal inner TRAIN history")
        for r in train:
            E.assert_row(r, "TRAIN", fit_at)
        for r in validation:
            E.assert_row(r, "TEST", fit_at)
        result.append(
            {
                "fit_at": fit_at,
                "train": train,
                "validation": validation,
                "train_keys_hash": E.digest([key(r) for r in train]),
                "validation_keys_hash": E.digest([key(r) for r in validation]),
            }
        )
        start += 6
    return result


def select_c(scores: dict[float, float]) -> float:
    if set(scores) != set(GRID) or not all(np.isfinite(v) for v in scores.values()):
        raise ValueError("invalid frozen grid scores")
    best = min(scores.values())
    return min(c for c, value in scores.items() if value <= best + 1e-12)


def fit_base(
    train: list[dict[str, Any]], test: list[dict[str, Any]], names: tuple[str, ...], c: float
) -> tuple[np.ndarray, dict[str, Any]]:
    if c not in GRID:
        raise ValueError("unregistered C")
    processor = E.TrainPreprocessor(E.matrix(train, names))
    x, xt = processor.transform(E.matrix(train, names)), processor.transform(E.matrix(test, names))
    y = np.array([r["actual_target"] for r in train])
    params = {**E.PARAMS, "C": c}
    with threadpool_limits(limits=1), warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model = LogisticRegression(**params).fit(x, y)
        p = model.predict_proba(xt)[:, 1]
        repeated = LogisticRegression(**params).fit(x, y).predict_proba(xt)[:, 1]
    if (
        any(issubclass(w.category, ConvergenceWarning) for w in caught)
        or max(model.n_iter_) >= params["max_iter"]
    ):
        raise ValueError("convergence failure STOP")
    if not np.allclose(p, repeated, rtol=0, atol=1e-12):
        raise ValueError("nondeterministic fit STOP")
    return p, {
        "params": params,
        "features": names,
        "transformed_features": list(names) + [n + "__missing" for n in names],
        "preprocessing": processor.parameters(),
        "coefficients": model.coef_[0].tolist(),
        "intercept": float(model.intercept_[0]),
        "n_iter": model.n_iter_.tolist(),
        "warnings": [str(w.message) for w in caught],
        "train_keys_hash": E.digest([key(r) for r in train]),
        "reproduction_max_abs_difference": float(np.max(np.abs(p - repeated))),
        "status": STATUS,
    }


def logits(p: np.ndarray) -> np.ndarray:
    bounded = np.clip(p, 1e-12, 1 - 1e-12)
    return np.asarray(np.log(bounded / (1 - bounded)))


def fit_platt(
    oof: list[dict[str, Any]],
    outer_fit: str,
    training_keys: dict[str, list[tuple[str, str]]],
) -> dict[str, Any]:
    for r in oof:
        if r["prediction_kind"] != "CAUSAL_INNER_OOF" or key(r) in set(
            training_keys[r["base_train_keys_hash"]]
        ):
            raise ValueError("calibrator requires causal OOF; in-sample rejected")
        if month_index(r["decision_at"]) < month_index(r["inner_fit_at"]):
            raise ValueError("prediction precedes fit")
        if datetime.fromisoformat(r["label_available_at"]) >= datetime.fromisoformat(outer_fit):
            raise ValueError("calibration label unavailable at outer fit")
    p = np.array([r["p"] for r in oof])
    y = np.array([r["actual_target"] for r in oof])
    if len(y) < 2 or len(set(y)) != 2 or np.std(logits(p)) < 1e-12:
        return {"status": "CALIBRATION_NOT_AVAILABLE_INSUFFICIENT_CAUSAL_INNER_HISTORY"}
    x = logits(p)

    def objective(v: np.ndarray) -> tuple[float, np.ndarray]:
        z = v[0] + v[1] * x
        residual = expit(z) - y
        return float(np.mean(np.logaddexp(0, z) - y * z)), np.array(
            [residual.mean(), np.mean(residual * x)]
        )

    opt = minimize(
        objective,
        [0.0, 1.0],
        jac=True,
        method="L-BFGS-B",
        bounds=[(None, None), (1e-6, None)],
        options={"ftol": 1e-12, "gtol": 1e-9, "maxiter": 5000},
    )
    if not opt.success or not np.isfinite(opt.x).all():
        raise ValueError("Platt convergence failure STOP")
    return {
        "status": "AVAILABLE",
        "intercept": float(opt.x[0]),
        "slope": float(opt.x[1]),
        "positive_boundary_active": bool(opt.x[1] <= 1e-6 + 1e-12),
        "inner_oof_hash": E.digest(oof),
        "n": len(y),
        "fit_log_loss": float(opt.fun),
        "iterations": int(opt.nit),
        "method": DESIGN["calibration"],
    }


def apply_platt(p: np.ndarray, calibrator: dict[str, Any]) -> np.ndarray:
    calibrated = expit(calibrator["intercept"] + calibrator["slope"] * logits(p))
    if not np.array_equal(rankdata(p), rankdata(calibrated)):
        raise ValueError("monotonic ranking changed STOP")
    return np.asarray(calibrated)


def evaluate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        **E.metrics(rows),
        "quintiles": E.buckets(rows, 5),
        "probability_distribution": dict(
            zip(
                ("min", "p05", "p25", "median", "p75", "p95", "max"),
                np.quantile(
                    [r["predicted_probability"] for r in rows], [0, 0.05, 0.25, 0.5, 0.75, 0.95, 1]
                ).tolist(),
                strict=True,
            )
        ),
        "mean_probability": float(np.mean([r["predicted_probability"] for r in rows])),
    }


def bootstrap(
    predictions: dict[str, list[dict[str, Any]]], repetitions: int = 1000
) -> dict[str, Any]:
    months = sorted({r["decision_at"][:7] for r in predictions["M3R"]})
    groups = {
        m: {month: [r for r in rs if r["decision_at"][:7] == month] for month in months}
        for m, rs in predictions.items()
    }
    spreads = {
        m: {
            r["month"]: r["excess_spread"]
            for r in E.buckets(rs, 5)["monthly"]
            if r["status"] == "AVAILABLE"
        }
        for m, rs in predictions.items()
    }
    deltas: dict[str, dict[str, list[float]]] = {
        a + "-" + b: {k: [] for k in ("log_loss", "brier", "auc", "spread")} for a, b in PAIRS
    }
    rng = np.random.default_rng(E.SEED)
    draws = rng.integers(0, len(months), size=(repetitions, len(months)))
    for draw in draws:
        sampled = [months[i] for i in draw]
        values = {}
        for m, grouped in groups.items():
            rs = [r for month in sampled for r in grouped[month]]
            y, p = (
                np.array([r["actual_target"] for r in rs]),
                np.array([r["predicted_probability"] for r in rs]),
            )
            values[m] = {
                "log_loss": float(log_loss(y, p, labels=[0, 1])),
                "brier": float(brier_score_loss(y, p)),
                "auc": float(roc_auc_score(y, p)),
                "spread": float(np.mean([spreads[m][month] for month in sampled])),
            }
        for a, b in PAIRS:
            for k in deltas[a + "-" + b]:
                deltas[a + "-" + b][k].append(values[a][k] - values[b][k])
    return {
        "status": "ADAPTIVE_DEV_EXPLORATORY",
        "repetitions": repetitions,
        "seed": E.SEED,
        "draws_hash": E.digest(draws.tolist()),
        "paired_deltas": {
            pair: {
                k: {
                    "low": float(np.quantile(v, 0.025)),
                    "high": float(np.quantile(v, 0.975)),
                    "n": len(v),
                }
                for k, v in metrics.items()
            }
            for pair, metrics in deltas.items()
        },
        "limitation": (
            "Complete-month resampling preserves cross-sectional dependence, "
            "not serial dependence of overlapping H12 labels. "
            "Adaptive observed DEV; not independent confirmation."
        ),
    }
