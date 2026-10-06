"""Frozen DEV-only equity baseline, independent of product/promotion services."""

from __future__ import annotations

import hashlib
import json
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import minimize
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from threadpoolctl import threadpool_limits

from pitquant.research import first_ml_contract as C
from pitquant.research.metrics import spearman

SEED = 20261006
STATUS = ["RESEARCH_DEV_ONLY", "RETROSPECTIVE_UNVALIDATED"]
PARAMS: dict[str, Any] = {
    "penalty": "l2",
    "C": 1.0,
    "solver": "lbfgs",
    "class_weight": None,
    "max_iter": 5000,
    "tol": 1e-4,
    "fit_intercept": True,
    "random_state": SEED,
}
PREPROCESSING: dict[str, Any] = {
    "order": ["train_median", "train_quantile_clip", "train_standardize", "missing_indicators"],
    "quantiles": [0.01, 0.99],
    "indicators": "one_per_predeclared_feature",
    "inputs": "RAW predeclared family; no extra rank columns or selection",
    "empty_train_column": "FAIL",
    "classification_threshold": 0.5,
}
NA = "NOT_APPLICABLE_NO_FROZEN_PROBABILITY_MAPPING"


def encoded(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(encoded(value)).hexdigest()


def immutable_json(path: Path, value: Any) -> str:
    """Same bytes are a no-op; different bytes require a new experiment identity."""
    raw = encoded(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as f:
            f.write(raw)
    except FileExistsError:
        if path.read_bytes() != raw:
            raise ValueError(f"immutable artifact conflict: {path}") from None
    return hashlib.sha256(raw).hexdigest()


def assert_row(row: dict[str, Any], role: str, fit_at: str) -> None:
    at = datetime.fromisoformat(row["decision_at"])
    end = datetime.fromisoformat(row["target_end"])
    mature = datetime.fromisoformat(row["label_available_at"])
    if at.tzinfo is None or end.tzinfo is None or mature.tzinfo is None:
        raise ValueError("naive provenance timestamp")
    if at.date() >= C.HOLDOUT[0] or end.date() >= C.HOLDOUT[0]:
        raise ValueError("holdout/OOT outcome prohibited")
    if role == "TRAIN" and (
        mature >= datetime.fromisoformat(fit_at) or end >= datetime.fromisoformat(fit_at)
    ):
        raise ValueError("training target overlaps fit/test")
    for name, feature in row["features"].items():
        if feature.get("value") is not None:
            available = datetime.fromisoformat(feature["available_at"])
            if available.tzinfo is None or available > at:
                raise ValueError(f"future feature {name}")
            for fact in feature.get("provenance", []):
                if fact.get("available_at") and datetime.fromisoformat(fact["available_at"]) > at:
                    raise ValueError("future filing")
    if row["actual_target"] not in (0, 1) or not np.isfinite(row["excess_return"]):
        raise ValueError("invalid DEV target")


def matrix(rows: list[dict[str, Any]], names: tuple[str, ...]) -> np.ndarray:
    result = np.array([[r["features"][n]["value"] for n in names] for r in rows], dtype=float)
    if np.isinf(result).any():
        raise ValueError("infinite feature")
    return result


class TrainPreprocessor:
    """Fit once on TRAIN; TEST can never update parameters or select columns."""

    def __init__(self, train: np.ndarray) -> None:
        if np.isnan(train).all(axis=0).any():
            raise ValueError("all-missing TRAIN feature; no silent removal or zero filling")
        self.median = np.nanmedian(train, axis=0)
        filled = np.where(np.isnan(train), self.median, train)
        self.low, self.high = np.quantile(filled, PREPROCESSING["quantiles"], axis=0)
        clipped = np.clip(filled, self.low, self.high)
        self.mean = clipped.mean(axis=0)
        self.scale = clipped.std(axis=0)
        self.scale[self.scale == 0] = 1.0

    def transform(self, values: np.ndarray) -> np.ndarray:
        missing = np.isnan(values)
        filled = np.where(missing, self.median, values)
        standardized = (np.clip(filled, self.low, self.high) - self.mean) / self.scale
        return np.column_stack([standardized, missing.astype(float)])

    def parameters(self) -> dict[str, Any]:
        return {n: getattr(self, n).tolist() for n in ("median", "low", "high", "mean", "scale")}


def fit_logistic(
    train: list[dict[str, Any]],
    test: list[dict[str, Any]],
    names: tuple[str, ...],
) -> tuple[np.ndarray, dict[str, Any]]:
    processor = TrainPreprocessor(matrix(train, names))
    x, xt = processor.transform(matrix(train, names)), processor.transform(matrix(test, names))
    y = np.array([r["actual_target"] for r in train])
    with threadpool_limits(limits=1), warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model = LogisticRegression(**PARAMS).fit(x, y)
        p = model.predict_proba(xt)[:, 1]
    if (
        any(issubclass(w.category, ConvergenceWarning) for w in caught)
        or max(model.n_iter_) >= PARAMS["max_iter"]
    ):
        raise ValueError("nonconvergent model: STOP, no results accepted")
    artifact = {
        "status": STATUS,
        "params": PARAMS,
        "features": list(names),
        "transformed_features": list(names) + [n + "__missing" for n in names],
        "preprocessing": processor.parameters(),
        "coefficients": model.coef_[0].tolist(),
        "intercept": float(model.intercept_[0]),
        "n_iter": model.n_iter_.tolist(),
        "warnings": [str(w.message) for w in caught],
        "converged": True,
        "train_rows_hash": digest([[r["security_id"], r["decision_at"]] for r in train]),
    }
    varying = np.std(x[:, : len(names)], axis=0) > 0
    selected = x[:, : len(names)][:, varying]
    corr = np.corrcoef(selected, rowvar=False)
    artifact["train_correlation"] = {
        "features": [n for n, keep in zip(names, varying, strict=True) if keep],
        "matrix": corr.tolist(),
        "constant_features_retained": [
            n for n, keep in zip(names, varying, strict=True) if not keep
        ],
        "condition_number": (
            float(np.linalg.cond(selected)) if np.isfinite(np.linalg.cond(selected)) else None
        ),
        "no_selection_applied": True,
    }
    # Independent fit is mandatory; tolerance is predeclared, never outcome tuned.
    with threadpool_limits(limits=1):
        repeated = LogisticRegression(**PARAMS).fit(x, y).predict_proba(xt)[:, 1]
    if not np.allclose(p, repeated, rtol=0, atol=1e-12):
        raise ValueError("prediction determinism failed")
    artifact["reproduction_max_abs_difference"] = float(np.max(np.abs(p - repeated)))
    return p, artifact


def calibration(y: np.ndarray, p: np.ndarray) -> dict[str, Any]:
    curve = []
    for i in range(10):
        selected = (p >= i / 10) & ((p < (i + 1) / 10) if i < 9 else (p <= 1))
        if selected.any():
            curve.append(
                {
                    "bin": i,
                    "n": int(selected.sum()),
                    "mean_prediction": float(p[selected].mean()),
                    "observed": float(y[selected].mean()),
                }
            )
    result: dict[str, Any] = {
        "curve": curve,
        "ece": sum(b["n"] * abs(b["mean_prediction"] - b["observed"]) for b in curve) / len(y),
    }
    logits = np.log(np.clip(p, 1e-12, 1 - 1e-12) / np.clip(1 - p, 1e-12, 1))
    if np.std(logits) < 1e-12:
        result.update(intercept=None, slope=None, status="NOT_IDENTIFIABLE_CONSTANT_PREDICTION")
    else:

        def objective(v: np.ndarray) -> float:
            z = v[0] + v[1] * logits
            return float(np.mean(np.logaddexp(0, z) - y * z))

        diagnostic = minimize(objective, [0.0, 1.0], method="BFGS")
        result.update(
            intercept=float(diagnostic.x[0]),
            slope=float(diagnostic.x[1]),
            status="DIAGNOSTIC_ONLY" if diagnostic.success else "DIAGNOSTIC_OPTIMIZER_WARNING",
        )
    result["recalibration_applied"] = False
    return result


def metrics(rows: list[dict[str, Any]], probability: bool = True) -> dict[str, Any]:
    y = np.array([r["actual_target"] for r in rows])
    p = np.array([r["predicted_probability"] if probability else r["raw_score"] for r in rows])
    ret = np.array([r["future_excess_return_12m"] for r in rows])
    result: dict[str, Any] = {
        "n": len(y),
        "base_rate": float(y.mean()),
        "auc": float(roc_auc_score(y, p)) if len(set(y)) == 2 else None,
        "ap": float(average_precision_score(y, p)),
        "rank_ic": spearman(p, ret),
    }
    if not probability:
        result.update(
            {
                n: None
                for n in (
                    "brier",
                    "log_loss",
                    "accuracy",
                    "balanced_accuracy",
                    "precision",
                    "recall",
                    "f1",
                    "confusion_matrix",
                    "calibration",
                )
            }
        )
        result["probability_metric_status"] = NA
        return result
    calls = p >= 0.5
    result.update(
        brier=float(brier_score_loss(y, p)),
        log_loss=float(log_loss(y, p, labels=[0, 1])),
        accuracy=float(accuracy_score(y, calls)),
        balanced_accuracy=float(balanced_accuracy_score(y, calls)),
        precision=float(precision_score(y, calls, zero_division=0)),
        recall=float(recall_score(y, calls, zero_division=0)),
        f1=float(f1_score(y, calls, zero_division=0)),
        confusion_matrix=confusion_matrix(y, calls, labels=[0, 1]).tolist(),
        calibration=calibration(y, p),
        probability_metric_status="AVAILABLE",
    )
    return result


def buckets(rows: list[dict[str, Any]], number: int) -> dict[str, Any]:
    """Ties never split by issuer/outcome. Constant M0 has no ranking spread."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        groups.setdefault(r["decision_at"][:7], []).append(r)
    collected: dict[int, list[dict[str, Any]]] = {i: [] for i in range(number)}
    monthly: list[dict[str, Any]] = []
    for month, rs in sorted(groups.items()):
        score = np.array([r["raw_score"] for r in rs])
        from scipy.stats import rankdata

        percentile = (rankdata(score, method="average") - 0.5) / len(score)
        assignment = np.minimum((percentile * number).astype(int), number - 1)
        if (
            len(rs) < 3 * number
            or not (assignment == 0).any()
            or not (assignment == number - 1).any()
        ):
            monthly.append({"month": month, "status": "INSUFFICIENT_N_OR_TIED_EXTREMES"})
            continue
        for i in range(number):
            collected[i].extend(r for r, a in zip(rs, assignment, strict=True) if a == i)
        top = [r for r, a in zip(rs, assignment, strict=True) if a == number - 1]
        bottom = [r for r, a in zip(rs, assignment, strict=True) if a == 0]
        monthly.append(
            {
                "month": month,
                "status": "AVAILABLE",
                "excess_spread": float(
                    np.mean([r["future_excess_return_12m"] for r in top])
                    - np.mean([r["future_excess_return_12m"] for r in bottom])
                ),
                "outperform_spread": float(
                    np.mean([r["actual_target"] for r in top])
                    - np.mean([r["actual_target"] for r in bottom])
                ),
            }
        )
    table = []
    for i, rs in collected.items():
        table.append(
            {
                "bucket": i + 1,
                "n": len(rs),
                "mean_excess_return": float(np.mean([r["future_excess_return_12m"] for r in rs]))
                if rs
                else None,
                "median_excess_return": float(
                    np.median([r["future_excess_return_12m"] for r in rs])
                )
                if rs
                else None,
                "outperform_rate": float(np.mean([r["actual_target"] for r in rs])) if rs else None,
            }
        )
    available = [r for r in monthly if r["status"] == "AVAILABLE"]
    return {
        "table": table,
        "monthly": monthly,
        "mean_month_spread": float(np.mean([r["excess_spread"] for r in available]))
        if available
        else None,
        "mean_month_outperform_spread": float(np.mean([r["outperform_spread"] for r in available]))
        if available
        else None,
        "monotonicity": "TABLE_ONLY_NO_PREDEFINED_PASS_FAIL_RULE",
    }


def bootstrap(
    predictions: dict[str, list[dict[str, Any]]], repetitions: int = 1000
) -> dict[str, Any]:
    months = sorted({r["decision_at"][:7] for r in predictions["M0"]})
    groups = {
        m: {month: [r for r in rs if r["decision_at"][:7] == month] for month in months}
        for m, rs in predictions.items()
    }
    # Bucket spreads calculated within original months before paired resampling.
    spreads = {
        m: {
            x["month"]: x["excess_spread"]
            for x in buckets(rs, 5)["monthly"]
            if x["status"] == "AVAILABLE"
        }
        for m, rs in predictions.items()
    }
    results: dict[str, dict[str, list[float]]] = {
        m: {k: [] for k in ("auc", "brier", "spread")} for m in predictions
    }
    deltas: dict[str, dict[str, list[float]]] = {
        a + "-" + b: {k: [] for k in ("auc", "brier", "spread")}
        for a, b in (("M2", "M0"), ("M3", "M0"), ("M4", "M0"), ("M4", "M2"), ("M4", "M3"))
    }
    rng = np.random.default_rng(SEED)
    for _ in range(repetitions):
        sampled = rng.choice(months, len(months), replace=True).tolist()
        values: dict[str, dict[str, float | None]] = {}
        for m, by_month in groups.items():
            rs = [r for month in sampled for r in by_month[month]]
            y = np.array([r["actual_target"] for r in rs])
            p = np.array([r["raw_score"] for r in rs])
            s = [spreads[m][month] for month in sampled if month in spreads[m]]
            values[m] = {
                "auc": float(roc_auc_score(y, p)) if len(set(y)) == 2 else None,
                "brier": float(brier_score_loss(y, p)) if m != "M1" else None,
                "spread": float(np.mean(s)) if s else None,
            }
            for k, v in values[m].items():
                if v is not None:
                    results[m][k].append(v)
        for pair, ks in deltas.items():
            a, b = pair.split("-")
            for k in ks:
                av, bv = values[a][k], values[b][k]
                if av is not None and bv is not None:
                    ks[k].append(av - bv)

    def intervals(data: dict[str, dict[str, list[float]]]) -> dict[str, Any]:
        return {
            m: {
                k: {
                    "n": len(v),
                    "low": float(np.quantile(v, 0.025)) if v else None,
                    "high": float(np.quantile(v, 0.975)) if v else None,
                }
                for k, v in ks.items()
            }
            for m, ks in data.items()
        }

    return {
        "method": "paired_complete_month_bootstrap",
        "seed": SEED,
        "repetitions": repetitions,
        "months": len(months),
        "models": intervals(results),
        "paired_deltas": intervals(deltas),
        "limitation": (
            "Preserves within-month dependence, not serial dependence of overlapping "
            "12M targets; intervals exploratory. M0 has no monthly ranking spread."
        ),
    }


def train_base_rate(train: list[dict[str, Any]]) -> float:
    return float(np.mean([r["actual_target"] for r in train]))


def run_models(
    dataset: dict[str, Any], manifest: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    per_fold, artifacts, all_predictions = [], {}, []
    for fold in dataset["folds"]:
        train, test = fold["TRAIN"], fold["TEST"]
        for role in ("TRAIN", "TEST"):
            for r in fold[role]:
                assert_row(r, role, fold["fit_at"])
        base = train_base_rate(train)
        model_scores = {
            "M0": np.full(len(test), base),
            "M1": np.array([r["v0_score"] for r in test]),
        }
        for config in (C.M2, C.M3, C.M4):
            name = config.model_id[:2]
            scores, artifact = fit_logistic(train, test, config.features)
            model_scores[name] = scores
            artifacts[f"F{fold['index']}-{name}"] = artifact
        result: dict[str, Any] = {
            "fold": fold["index"],
            "train_n": len(train),
            "test_n": len(test),
            "train_issuers": len({r["issuer_id"] for r in train}),
            "test_issuers": len({r["issuer_id"] for r in test}),
            "train_base_rate": base,
            "test_base_rate": float(np.mean([r["actual_target"] for r in test])),
            "models": {},
        }
        for name, scores in model_scores.items():
            predictions = []
            for r, score in zip(test, scores, strict=True):
                predictions.append(
                    {
                        "experiment_id": manifest["experiment_id"],
                        "model_id": name,
                        "fold_id": fold["index"],
                        "decision_at": r["decision_at"],
                        "issuer_id": r["issuer_id"],
                        "security_id": r["security_id"],
                        "actual_target": r["actual_target"],
                        "predicted_probability": float(score) if name != "M1" else None,
                        "raw_score": float(score),
                        "future_excess_return_12m": r["excess_return"],
                        "benchmark_id": r["benchmark_id"],
                        "cohort_id": fold["test_cohort_hash"],
                        "created_at": manifest["created_at"],
                        "code_sha": manifest["code_sha"],
                        "data_hash": manifest["data_snapshot_hash"],
                        "snapshot_id": r["snapshot_id"],
                        "regime": r["regime"],
                        "status": STATUS,
                    }
                )
            all_predictions.extend(predictions)
            result["models"][name] = {
                **metrics(predictions, name != "M1"),
                "quintiles": buckets(predictions, 5),
                "deciles": buckets(predictions, 10),
            }
        per_fold.append(result)
    pooled = {
        name: [r for r in all_predictions if r["model_id"] == name]
        for name in ("M0", "M1", "M2", "M3", "M4")
    }
    reference = [(r["security_id"], r["decision_at"]) for r in pooled["M0"]]
    if len(reference) != len(set(reference)) or any(
        [(r["security_id"], r["decision_at"]) for r in rs] != reference for rs in pooled.values()
    ):
        raise ValueError("TEST overlap/cohort mismatch")
    monthly: dict[str, Any] = {}
    for name, rs in pooled.items():
        monthly[name] = []
        for month in sorted({r["decision_at"][:7] for r in rs}):
            group = [r for r in rs if r["decision_at"][:7] == month]
            monthly[name].append(
                {
                    "month": month,
                    "n": len(group),
                    "base_rate": float(np.mean([r["actual_target"] for r in group])),
                    "actual_outperform_rate": float(np.mean([r["actual_target"] for r in group])),
                    "mean_prediction": float(np.mean([r["raw_score"] for r in group]))
                    if name != "M1"
                    else None,
                    **metrics(group, name != "M1"),
                }
            )
    report = {
        "manifest": manifest,
        "scope": "PRIMARY_COMMON_COHORT",
        "status": STATUS,
        "per_fold": per_fold,
        "POOLED_DEV_OOF": {
            name: {
                **metrics(rs, name != "M1"),
                "quintiles": buckets(rs, 5),
                "deciles": buckets(rs, 10),
            }
            for name, rs in pooled.items()
        },
        "monthly": monthly,
        "bootstrap": bootstrap(pooled),
        "holdout_outcome_rows_accessed": 0,
        "oot_outcome_rows_accessed": 0,
        "promoted": False,
    }
    return report, all_predictions, artifacts
