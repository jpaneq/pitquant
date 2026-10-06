"""Read-only diagnostics of archived models. No estimators, fits, or database access."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from itertools import pairwise
from typing import Any

import numpy as np
from numpy.typing import NDArray

from pitquant.research import equity_baseline as E
from pitquant.research import equity_return as R
from pitquant.research import equity_v1 as V
from pitquant.research import first_ml_contract as C
from pitquant.research.metrics import spearman

Array = NDArray[np.float64]


def correlation(x: Array, y: Array) -> float | None:
    if len(x) < 3 or np.ptp(x) == 0 or np.ptp(y) == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def replay(parameters: dict[str, Any], rows: list[dict[str, Any]]) -> tuple[Array, Array]:
    raw = E.matrix(rows, tuple(parameters["features"]))
    missing = np.isnan(raw)
    p = parameters["preprocessing"]
    filled = np.where(missing, np.asarray(p["median"]), raw)
    scaled = (np.clip(filled, p["low"], p["high"]) - p["mean"]) / p["scale"]
    x = np.column_stack((scaled, missing.astype(float)))
    return x, np.asarray(x @ np.asarray(parameters["coefficients"]) + parameters["intercept"])


def metrics(y: Array, prediction: Array) -> dict[str, Any]:
    residual = prediction - y
    return {
        "n": len(y),
        "mae": float(np.mean(np.abs(residual))),
        "mse": float(np.mean(residual**2)),
        "rmse": float(np.sqrt(np.mean(residual**2))),
        "pearson": correlation(prediction, y),
        "spearman": spearman(prediction, y),
    }


def distribution(values: list[float] | Array) -> dict[str, Any]:
    y = np.asarray(values, dtype=float)
    if len(y) == 0:
        return {"n": 0}
    mean, std = float(np.mean(y)), float(np.std(y))
    z = (y - mean) / std if std else np.zeros(len(y))
    q = np.quantile(y, [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95])
    return {
        "n": len(y),
        "mean": mean,
        "median": float(q[3]),
        "std": std,
        "iqr": float(q[4] - q[2]),
        "p90_p10": float(q[5] - q[1]),
        "p05": float(q[0]),
        "p95": float(q[6]),
        "skew": float(np.mean(z**3)) if std else None,
        "excess_kurtosis": float(np.mean(z**4) - 3) if std else None,
    }


def loss_decomposition(y: Array, pred: Array, rows: list[dict[str, Any]]) -> dict[str, Any]:
    order = sorted(
        range(len(y)), key=lambda i: (abs(y[i]), rows[i]["security_id"], rows[i]["decision_at"])
    )
    absolute, squared = np.abs(pred - y), (pred - y) ** 2
    bounds = [0, int(0.90 * len(y)), int(0.95 * len(y)), int(0.99 * len(y)), len(y)]
    bins = []
    for start, end in pairwise(bounds):
        indices = order[start:end]
        bins.append(
            {
                "n": len(indices),
                "absolute_error_share": float(absolute[indices].sum() / absolute.sum())
                if absolute.sum()
                else None,
                "squared_error_share": float(squared[indices].sum() / squared.sum())
                if squared.sum()
                else None,
            }
        )
    return {
        "bins_0_90_90_95_95_99_99_100": bins,
        "top_tail_squared_share": {
            str(p): float(squared[order[int((1 - p) * len(y)) :]].sum() / squared.sum())
            if squared.sum()
            else None
            for p in (0.10, 0.05, 0.01)
        },
    }


def monthly_ic(rows: list[dict[str, Any]], pred: Array) -> dict[str, Any]:
    groups: dict[str, list[int]] = defaultdict(list)
    for i, row in enumerate(rows):
        groups[row["decision_at"][:7]].append(i)
    result: list[dict[str, Any]] = []
    for month, idx in sorted(groups.items()):
        y = np.asarray([rows[i]["excess_return"] for i in idx], dtype=float)
        result.append(
            {"month": month, "n": len(idx), "ic": spearman(pred[idx], y) if len(idx) >= 5 else None}
        )
    return {
        "months": result,
        "by_year": {
            year: R.summary(
                [r["ic"] for r in result if r["month"][:4] == year and r["ic"] is not None]
            )
            for year in sorted({r["month"][:4] for r in result})
        },
        "summary": R.summary([r["ic"] for r in result if r["ic"] is not None]),
    }


def margin(scores: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(scores, key=lambda s: (s["mae"], s["alpha"], s["l1_ratio"]))
    difference = ordered[1]["mae"] - ordered[0]["mae"]
    return {
        "top_three_raw_mae": ordered[:3],
        "absolute": difference,
        "relative_percent": 100 * difference / ordered[0]["mae"],
        "numeric_tie_1e_12": difference <= 1e-12,
    }


def pareto(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [c for c in candidates if c["validation"]["spearman"] is not None]
    front = []
    for c in eligible:
        a, b = c["validation"]["mae"], c["validation"]["spearman"]
        dominated = any(
            d["validation"]["mae"] <= a
            and d["validation"]["spearman"] >= b
            and (d["validation"]["mae"] < a or d["validation"]["spearman"] > b)
            for d in eligible
        )
        if not dominated:
            front.append(c["candidate"])
    return {
        "non_dominated": front,
        "dominated": [c["candidate"] for c in eligible if c["candidate"] not in front],
        "undefined_ic": [c["candidate"] for c in candidates if c["validation"]["spearman"] is None],
    }


def kkt(parameters: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    x, _ = replay(parameters, rows)
    y = R.target(rows)
    gradients = np.abs((x - x.mean(axis=0)).T @ (y - y.mean()) / len(y))
    penalty = parameters["alpha"] * parameters["l1_ratio"]
    return {
        "max_gradient": float(gradients.max()),
        "l1_threshold": penalty,
        "zero_optimum_condition": bool(gradients.max() <= penalty + 1e-12),
        "threshold_minus_gradient": float(penalty - gradients.max()),
        "transformed_features": parameters["transformed_features"],
        "feature_std": np.std(x, axis=0).tolist(),
        "abs_gradient": gradients.tolist(),
        "nonzero_count": parameters["nonzero_count"],
    }


def candidate_surface(fold: dict[str, Any], models: dict[str, Any]) -> dict[str, Any]:
    fid = "F" + str(fold["index"])
    inners = V.inner_folds(fold)
    result = {}
    for model in ("R2", "R3", "R4"):
        archived = models[fid + "-" + model]
        if len(archived["candidates"]) != 35:
            raise ValueError("candidate grid incomplete")
        candidates = []
        for name, candidate in sorted(archived["candidates"].items()):
            if len(candidate["inner_models"]) != len(inners):
                raise ValueError("inner grid incomplete")
            rows = [fold["TRAIN"][r["row_index"]] for r in candidate["oof"]]
            expected = {V.key(r) for inner in inners for r in inner["validation"]}
            if {V.key(r) for r in rows} != expected or len(rows) != len(expected):
                raise ValueError("inner OOF coverage mismatch")
            pred = np.asarray([r["prediction"] for r in candidate["oof"]], dtype=float)
            inner_details = []
            for parameters, inner in zip(candidate["inner_models"], inners, strict=True):
                if (
                    parameters["train_keys_hash"] != inner["train_keys_hash"]
                    or parameters["validation_keys_hash"] != inner["validation_keys_hash"]
                ):
                    raise ValueError("causal inner hashes mismatch")
                for record in candidate["oof"]:
                    if (
                        record["inner_fit_at"] == inner["fit_at"]
                        and record["base_train_keys_hash"] != parameters["train_keys_hash"]
                    ):
                        raise ValueError("OOF base lineage mismatch")
                _, train_pred = replay(parameters, inner["train"])
                _, val_pred = replay(parameters, inner["validation"])
                lookup = {
                    V.key(fold["TRAIN"][r["row_index"]]): r["prediction"]
                    for r in candidate["oof"]
                    if r["inner_fit_at"] == inner["fit_at"]
                }
                if any(
                    abs(lookup[V.key(row)] - p) > 1e-10
                    for row, p in zip(inner["validation"], val_pred, strict=True)
                ):
                    raise ValueError("archived replay mismatch STOP")
                inner_details.append(
                    {
                        "fit_at": inner["fit_at"],
                        "alpha": parameters["alpha"],
                        "l1_ratio": parameters["l1_ratio"],
                        "nonzero_features": parameters["nonzero_count"],
                        "l1_norm": parameters["l1_norm"],
                        "l2_norm": parameters["l2_norm"],
                        "train_in_sample": metrics(R.target(inner["train"]), train_pred),
                        "validation": metrics(R.target(inner["validation"]), val_pred),
                        "train_loss": loss_decomposition(
                            R.target(inner["train"]), train_pred, inner["train"]
                        ),
                        "validation_loss": loss_decomposition(
                            R.target(inner["validation"]), val_pred, inner["validation"]
                        ),
                        "train_monthly_ic": monthly_ic(inner["train"], train_pred),
                        "validation_monthly_ic": monthly_ic(inner["validation"], val_pred),
                    }
                )
            met = metrics(R.target(rows), pred)
            if abs(met["mae"] - candidate["score"]["mae"]) > 1e-12:
                raise ValueError("archived selection MAE mismatch")
            candidates.append(
                {
                    "candidate": name,
                    "alpha": candidate["score"]["alpha"],
                    "l1_ratio": candidate["score"]["l1_ratio"],
                    "mean_nonzero_count": candidate["score"]["mean_nonzero_count"],
                    "validation": met,
                    "delta_mae_selected": met["mae"]
                    - next(
                        s["mae"]
                        for s in archived["scores"]
                        if s["alpha"] == archived["selected_alpha"]
                        and s["l1_ratio"] == archived["selected_l1_ratio"]
                    ),
                    "monthly_ic": monthly_ic(rows, pred),
                    "validation_loss": loss_decomposition(R.target(rows), pred, rows),
                    "inners": inner_details,
                }
            )
        winner = f"{archived['selected_alpha']}/{archived['selected_l1_ratio']}"
        chosen = next(
            c
            for c in candidates
            if c["alpha"] == archived["selected_alpha"]
            and c["l1_ratio"] == archived["selected_l1_ratio"]
        )
        zero = [c for c in candidates if c["mean_nonzero_count"] == 0]
        nonzero = [c for c in candidates if c["mean_nonzero_count"] > 0]
        defined = [c for c in candidates if c["validation"]["spearman"] is not None]
        summary_keys = (
            "candidate",
            "validation",
            "monthly_ic",
            "mean_nonzero_count",
            "delta_mae_selected",
        )

        def brief(c: dict[str, Any], keys: tuple[str, ...] = summary_keys) -> dict[str, Any]:
            return {k: c[k] for k in keys}

        result[model] = {
            "selected": winner,
            "selection_margin": margin(archived["scores"]),
            "selected_inner": brief(chosen),
            "selected_inner_loss": chosen["validation_loss"],
            "best_zero": brief(min(zero, key=lambda c: c["validation"]["mae"])) if zero else None,
            "best_nonzero": brief(min(nonzero, key=lambda c: c["validation"]["mae"]))
            if nonzero
            else None,
            "nonzero_candidates": [c["candidate"] for c in nonzero],
            "ranking_positive_majority": [
                c["candidate"]
                for c in nonzero
                if c["monthly_ic"]["summary"]["mean"] is not None
                and c["monthly_ic"]["summary"]["mean"] > 0
                and c["monthly_ic"]["summary"]["positive_fraction"] > 0.5
            ],
            "candidate_correlations": {
                "n": len(defined),
                "mae_vs_pooled_ic": correlation(
                    np.asarray([c["validation"]["mae"] for c in defined]),
                    np.asarray([c["validation"]["spearman"] for c in defined]),
                ),
                "rmse_vs_pooled_ic": correlation(
                    np.asarray([c["validation"]["rmse"] for c in defined]),
                    np.asarray([c["validation"]["spearman"] for c in defined]),
                ),
            },
            "pareto": pareto(candidates),
            "pareto_monthly": pareto(
                [
                    {
                        "candidate": c["candidate"],
                        "validation": {
                            "mae": c["validation"]["mae"],
                            "spearman": c["monthly_ic"]["summary"]["mean"],
                        },
                    }
                    for c in candidates
                ]
            ),
            "candidate_monthly_correlations": {
                "n": sum(c["monthly_ic"]["summary"]["mean"] is not None for c in candidates),
                "mae_vs_mean_monthly_ic": correlation(
                    np.asarray(
                        [
                            c["validation"]["mae"]
                            for c in candidates
                            if c["monthly_ic"]["summary"]["mean"] is not None
                        ]
                    ),
                    np.asarray(
                        [
                            c["monthly_ic"]["summary"]["mean"]
                            for c in candidates
                            if c["monthly_ic"]["summary"]["mean"] is not None
                        ]
                    ),
                ),
                "rmse_vs_mean_monthly_ic": correlation(
                    np.asarray(
                        [
                            c["validation"]["rmse"]
                            for c in candidates
                            if c["monthly_ic"]["summary"]["mean"] is not None
                        ]
                    ),
                    np.asarray(
                        [
                            c["monthly_ic"]["summary"]["mean"]
                            for c in candidates
                            if c["monthly_ic"]["summary"]["mean"] is not None
                        ]
                    ),
                ),
            },
            "pooled_ic_warning": (
                "Constant within each inner period can have pooled IC from changing TRAIN means. "
                "Monthly IC is primary ranking evidence; pooled Pareto is descriptive only."
            ),
            "minimum_archived_rmse_candidate": brief(
                min(candidates, key=lambda c: c["validation"]["rmse"])
            ),
            "ridge_diagnostics": [brief(c) for c in candidates if c["l1_ratio"] == 0],
            "selected_outer_zeroing": kkt(archived["base"], fold["TRAIN"]),
            "selected_inner_zeroing": [
                kkt(p, i["train"])
                for p, i in zip(
                    archived["candidates"][chosen["candidate"]]["inner_models"], inners, strict=True
                )
            ],
            "candidates": candidates,
        }
    return result


def safe_rows(data: dict[str, Any]) -> None:
    if data["holdout_outcome_rows_accessed"] or data["oot_outcome_rows_accessed"]:
        raise ValueError("sealed outcomes accessed STOP")
    if [f["index"] for f in data["folds"]] != [1, 2, 3]:
        raise ValueError("unexpected DEV folds")
    for fold in data["folds"]:
        for role in ("TRAIN", "TEST"):
            for row in fold[role]:
                E.assert_row(row, role, fold["fit_at"])
                if (
                    row["source_meta"]["currency"] != "USD"
                    or row["source_meta"]["return_type"] != "TOTAL_RETURN"
                    or row["source_meta"]["benchmark"] != "SPY"
                ):
                    raise ValueError("benchmark/FX contract mismatch STOP")
                if row["actual_target"] != int(row["excess_return"] > 0):
                    raise ValueError("binary/continuous target mismatch STOP")


def raw_features(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["decision_at"][:7]].append(row)
    for feature in C.M4.features:
        months: list[dict[str, Any]] = []
        for month, group in sorted(groups.items()):
            pairs = [
                (r["features"][feature]["value"], r["excess_return"])
                for r in group
                if r["features"][feature]["value"] is not None
            ]
            ic = (
                spearman(np.asarray([p[0] for p in pairs]), np.asarray([p[1] for p in pairs]))
                if len(pairs) >= 5
                else None
            )
            months.append({"month": month, "n": len(pairs), "ic": ic})
        result[feature] = {
            "months": months,
            "by_year": {
                year: R.summary(
                    [r["ic"] for r in months if r["month"][:4] == year and r["ic"] is not None]
                )
                for year in sorted({r["month"][:4] for r in months})
            },
            "summary": R.summary([m["ic"] for m in months if m["ic"] is not None]),
        }
    return result


def sector_diagnostics(rows: list[dict[str, Any]], scores: dict[str, Array]) -> dict[str, Any]:
    sectors: dict[str, list[int]] = defaultdict(list)
    groups: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for i, row in enumerate(rows):
        sector = row["source_meta"].get("sector_group") or "UNKNOWN"
        sectors[sector].append(i)
        groups[row["decision_at"][:7]][sector].append(i)
    y = R.target(rows)
    target = {s: distribution(y[idx]) for s, idx in sorted(sectors.items())}
    models = {}
    for name, pred in scores.items():
        months: list[dict[str, Any]] = []
        for month, group in sorted(groups.items()):
            pairs: list[dict[str, Any]] = [
                {
                    "sector": s,
                    "n": len(idx),
                    "ic": spearman(pred[idx], y[idx]) if len(idx) >= 5 else None,
                }
                for s, idx in sorted(group.items())
            ]
            valid = [p for p in pairs if p["ic"] is not None]
            months.append(
                {
                    "month": month,
                    "sectors": pairs,
                    "eligible_n": sum(p["n"] for p in valid),
                    "within_sector_ic": sum(p["n"] * p["ic"] for p in valid)
                    / sum(p["n"] for p in valid)
                    if valid
                    else None,
                }
            )
        models[name] = {
            "global_monthly_ic": monthly_ic(rows, pred),
            "within_sector_months": months,
            "within_sector_summary": R.summary(
                [m["within_sector_ic"] for m in months if m["within_sector_ic"] is not None]
            ),
            "residuals": {s: distribution(pred[idx] - y[idx]) for s, idx in sorted(sectors.items())}
            if name != "M4R"
            else None,
            "residual_units": "excess return"
            if name != "M4R"
            else "NA: Direction probability is not a return forecast",
        }
    return {"target_by_sector": target, "models": models}


def age(rows: list[dict[str, Any]], reference: str) -> dict[str, Any]:
    anchor = datetime.fromisoformat(reference)
    return {
        "reference": reference,
        "days": distribution(
            [
                (anchor - datetime.fromisoformat(r["decision_at"])).total_seconds() / 86400
                for r in rows
            ]
        ),
    }
