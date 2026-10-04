# ruff: noqa: E501
"""Predefined baseline configurations (NOT trained here; ADR-0030). No XGBoost.

Transformers (imputation, winsorisation, standardisation) are fitted on the TRAIN fold only. The grids are
small and fixed in advance: no hyper-parameter fishing, no model selection on accuracy/AUC alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pitquant.core.hashing import content_hash

BASELINE_VERSION = "baselines-v1"


@dataclass(frozen=True)
class BaselineConfig:
    kind: str
    name: str
    target: str
    horizons: tuple[int, ...]
    params: dict[str, object]
    grid: dict[str, tuple[object, ...]]
    transformers: tuple[str, ...] = (
        "impute_median_train_only",
        "winsorize_train_quantiles_only",
        "standardize_train_only",
    )
    selection_metrics: tuple[str, ...] = field(default_factory=tuple)
    version: str = BASELINE_VERSION

    @property
    def config_hash(self) -> str:
        return content_hash(
            {
                "kind": self.kind,
                "name": self.name,
                "target": self.target,
                "horizons": list(self.horizons),
                "params": self.params,
                "grid": {k: list(v) for k, v in self.grid.items()},
                "transformers": list(self.transformers),
                "version": self.version,
            }
        )


ELASTIC_NET = BaselineConfig(
    "ELASTIC_NET",
    "elastic_net_excess_return",
    "future_excess_total_return",
    (6, 12),
    {"max_iter": 10000, "fit_intercept": True, "random_state": 20261001},
    {"alpha": (0.001, 0.01, 0.1, 1.0), "l1_ratio": (0.0, 0.25, 0.5, 0.75, 1.0)},
    selection_metrics=("spearman_ic", "mae", "rmse", "d10_d1_spread"),
)
LOGISTIC = BaselineConfig(
    "LOGISTIC_REGRESSION",
    "logistic_outperform",
    "outperform",
    (6, 12),
    {"penalty": "l2", "max_iter": 5000, "random_state": 20261001},
    {"C": (0.1, 1.0, 10.0)},
    selection_metrics=("brier", "log_loss", "calibration", "roc_auc"),
)
GRADIENT_BOOSTING = BaselineConfig(
    "GRADIENT_BOOSTING",
    "gradient_boosting_excess_return",
    "future_excess_total_return",
    (6, 12),
    {"loss": "squared_error", "random_state": 20261001, "subsample": 1.0},
    {"n_estimators": (100, 300), "max_depth": (2, 3), "learning_rate": (0.03, 0.1)},
    selection_metrics=("spearman_ic", "mae", "rmse", "d10_d1_spread"),
)  # CHALLENGER only, after the baselines (ADR-0038); no deep learning, no ensembles, no feature zoo
BASELINES = {
    c.kind: c for c in (ELASTIC_NET, LOGISTIC)
}  # the registered baselines (the challenger is registered separately)
FORBIDDEN_TARGETS = frozenset(
    {"human_label", "trend_state", "valuation_label", "analysis_label"}
)  # human analysis is never a target
