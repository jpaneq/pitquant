# ruff: noqa: E501
"""Predefined baseline MODEL SPECS per horizon (ADR-0038). Nothing here is trained unless every data gate is open.

* ``EQUITY_6M_BASELINE`` / ``EQUITY_12M_BASELINE``: Elastic Net (excess total return vs SPY_TOTAL_RETURN_PROXY) + Logistic Regression (P(outperform)), one model PER
  horizon (never shared coefficients), with the 51 Feature Engine v0.2 features. A Gradient Boosting challenger is configured, to be tried only after the baselines.
* ``evaluate_training_gates`` reads ``research_readiness`` ONCE (it rebuilds the whole anchor graph: never call it in a hot path).
* ``attempt_training``: gates closed ⇒ a BLOCKED experiment is registered through the existing ``define_experiment`` and NOTHING is fitted. The walk-forward flow
  (``fit_walk_forward``) exists and is exercised only with an INJECTED estimator (a labelled fake in tests); sklearn is not a dependency of this build.
* Validation is walk-forward OOS only (purge, embargo, train_min=60, sealed holdout): no random split, no shuffle.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Protocol

import numpy as np
from sqlalchemy.orm import Session

from pitquant.config.settings import Settings
from pitquant.features.v0.engine import FEATURE_NAMES
from pitquant.research.baselines import ELASTIC_NET, GRADIENT_BOOSTING, LOGISTIC, BaselineConfig
from pitquant.research.metrics import (
    ClassificationMetrics,
    RankingMetrics,
    RegressionMetrics,
    classification_metrics,
    ranking_metrics,
    regression_metrics,
)
from pitquant.research.walkforward import Fold, WalkForwardConfig, plan_folds

TRAINING_GATES = (
    "D02_MONTHLY_RESEARCH_READY",
    "US_D05_RESEARCH_READY",
    "US_SECURITY_IDENTITY_READY",
    "US_FUNDAMENTALS_READY",
)


@dataclass(frozen=True)
class HorizonModelSpec:
    model_id: str
    horizon_months: int
    regressor: BaselineConfig
    classifier: BaselineConfig
    challenger: BaselineConfig
    feature_names: tuple[str, ...] = FEATURE_NAMES
    status: str = "NOT_TRAINED"


def _spec(h: int) -> HorizonModelSpec:
    return HorizonModelSpec(
        f"EQUITY_{h}M_BASELINE", h, replace(ELASTIC_NET, name=f"equity_{h}m_elastic_net_excess", horizons=(h,)), replace(LOGISTIC, name=f"equity_{h}m_logistic_outperform", horizons=(h,)),
        replace(GRADIENT_BOOSTING, name=f"equity_{h}m_gradient_boosting_challenger", horizons=(h,)),
    )  # fmt: skip


MODEL_SPECS: dict[str, HorizonModelSpec] = {s.model_id: s for s in (_spec(6), _spec(12))}


@dataclass
class TrainingGates:
    flags: dict[str, bool]
    reasons: list[str] = field(default_factory=list)

    @property
    def open(self) -> bool:
        return all(self.flags.get(g, False) for g in TRAINING_GATES)


def evaluate_training_gates(
    session: Session, settings: Settings, flags: dict[str, bool] | None = None
) -> TrainingGates:
    """The four data gates. ``flags`` lets a caller that already holds a readiness evaluation (one per run) avoid recomputing it."""
    if flags is None:
        from pitquant.research_readiness import research_readiness

        rf = research_readiness(session, settings)
        flags = {g: bool(rf.flags.get(g, False)) for g in TRAINING_GATES}
    return TrainingGates(
        {g: bool(flags.get(g, False)) for g in TRAINING_GATES},
        [f"gate {g} = false" for g in TRAINING_GATES if not flags.get(g, False)],
    )


@dataclass
class TrainingAttempt:
    model_id: str
    status: str  # BLOCKED | NOT_IMPLEMENTED_WITHOUT_DATASET
    trained: bool
    experiment_id: str | None
    blocked_reasons: list[str]


def attempt_training(
    session: Session, settings: Settings, model_id: str, gates: TrainingGates | None = None
) -> TrainingAttempt:
    """Closed gates ⇒ register the experiment as BLOCKED (idempotent) and return. Never fits, never improvises a dataset."""
    from pitquant.research.registry import ExperimentSpec, define_experiment

    spec = MODEL_SPECS[model_id]
    gates = gates or evaluate_training_gates(session, settings)
    if not gates.open:
        ex = define_experiment(
            session,
            ExperimentSpec(
                model_id, spec.regressor, WalkForwardConfig(train_min_months=60, purge_months=1, embargo_months=1, label_horizon_months=spec.horizon_months), spec.horizon_months,
                "SP500@FEATURE_V0_51", "SPY_TOTAL_RETURN_PROXY", horizons=(spec.horizon_months,), extra_models=(spec.classifier,),
            ),
            None,
            {g: False for g in TRAINING_GATES if not gates.flags.get(g, False)},
        )  # fmt: skip
        return TrainingAttempt(model_id, "BLOCKED", False, ex.experiment_id, ex.blocked_reasons)
    return TrainingAttempt(
        model_id,
        "NOT_IMPLEMENTED_WITHOUT_DATASET",
        False,
        None,
        [
            "gates are open but no persisted dataset version was supplied: build it with the Dataset Builder first"
        ],
    )


# ───────────────────────────────────────────── walk-forward fit/predict flow (estimator INJECTED)
class Estimator(Protocol):
    def fit(self, x: np.ndarray, y: np.ndarray) -> Any: ...
    def predict(self, x: np.ndarray) -> np.ndarray: ...


EstimatorFactory = Callable[[BaselineConfig, dict[str, object]], Estimator]


def sklearn_factory(
    cfg: BaselineConfig, params: dict[str, object]
) -> Estimator:  # pragma: no cover - sklearn is not installed in this build
    try:
        import sklearn.ensemble as ens
        import sklearn.linear_model as lm
    except ImportError as e:
        raise RuntimeError(
            "scikit-learn is not installed: install the research extra before training (the gates must be open first)"
        ) from e
    kinds: dict[str, Any] = {
        "ELASTIC_NET": lm.ElasticNet,
        "LOGISTIC_REGRESSION": lm.LogisticRegression,
        "GRADIENT_BOOSTING": ens.GradientBoostingRegressor,
    }
    return kinds[cfg.kind](**{**cfg.params, **params})  # type: ignore[no-any-return]


@dataclass(frozen=True)
class Row:
    decision_date: date
    x: tuple[float | None, ...]
    y_excess: float
    y_outperform: int


@dataclass
class TrainFit:
    medians: np.ndarray
    lo: np.ndarray
    hi: np.ndarray
    mean: np.ndarray
    std: np.ndarray

    @classmethod
    def fit(cls, x: np.ndarray) -> TrainFit:
        """Transformers are fitted on the TRAIN rows only (median imputation, 1/99 winsorisation, standardisation)."""
        med = np.nanmedian(x, axis=0)
        med = np.where(np.isnan(med), 0.0, med)
        xi = np.where(np.isnan(x), med, x)
        lo, hi = np.quantile(xi, 0.01, axis=0), np.quantile(xi, 0.99, axis=0)
        xw = np.clip(xi, lo, hi)
        sd = xw.std(axis=0)
        return cls(med, lo, hi, xw.mean(axis=0), np.where(sd == 0, 1.0, sd))

    def apply(self, x: np.ndarray) -> np.ndarray:
        xi = np.where(np.isnan(x), self.medians, x)
        out: np.ndarray = (np.clip(xi, self.lo, self.hi) - self.mean) / self.std
        return out


@dataclass
class FoldResult:
    fold: Fold
    regression: RegressionMetrics
    classification: ClassificationMetrics
    ranking: RankingMetrics


def fit_walk_forward(
    rows: Sequence[Row],
    cfg: WalkForwardConfig,
    holdout: tuple[date, date],
    regressor: EstimatorFactory,
    classifier: EstimatorFactory,
    spec: HorizonModelSpec,
) -> list[FoldResult]:
    """Walk-forward OOS over ``rows``: folds from ``plan_folds`` (purge, embargo, train_min, label windows clear of the holdout); transformers fitted per
    fold on train only; metrics on the validation rows only. No random split, no shuffling."""
    folds = plan_folds(sorted({r.decision_date for r in rows}), cfg, holdout)
    out: list[FoldResult] = []
    for f in folds:
        tr = [r for r in rows if f.train_start <= r.decision_date <= f.train_end]
        va = [r for r in rows if f.validation_start <= r.decision_date <= f.validation_end]
        if not tr or not va:
            continue
        xt = np.array([[np.nan if v is None else v for v in r.x] for r in tr], float)
        xv = np.array([[np.nan if v is None else v for v in r.x] for r in va], float)
        tf = TrainFit.fit(xt)
        xt, xv = tf.apply(xt), tf.apply(xv)
        reg = regressor(spec.regressor, {}).fit(xt, np.array([r.y_excess for r in tr]))
        clf = classifier(spec.classifier, {}).fit(xt, np.array([r.y_outperform for r in tr]))
        pr, pc = np.asarray(reg.predict(xv), float), np.asarray(clf.predict(xv), float)
        y = np.array([r.y_excess for r in va])
        out.append(
            FoldResult(
                f,
                regression_metrics(y, pr),
                classification_metrics(np.array([r.y_outperform for r in va]), pc),
                ranking_metrics(pr, y),
            )
        )
    return out


# ───────────────────────────────────────────── model availability at a decision date (anti look-ahead)
@dataclass(frozen=True)
class TrainedModelRecord:
    """What a historical replay may select. ``label_known_by`` = the latest ``label_available_at`` among ALL its training labels."""

    model_id: str
    model_version: str
    horizon_months: int
    label_known_by: Any  # datetime
    frozen: bool = True


def model_eligible_at(
    rec: TrainedModelRecord, decision_at: Any, purge_embargo_months: int = 2
) -> tuple[bool, str]:
    """A model may serve decision T only if it is frozen and EVERY training label was already known at T (plus purge + embargo): ``trained_until < T`` alone is not enough."""
    from dateutil.relativedelta import relativedelta

    if not rec.frozen:
        return False, "model is not frozen"
    if rec.label_known_by + relativedelta(months=purge_embargo_months) > decision_at:
        return (
            False,
            f"a training label was only known at {rec.label_known_by.isoformat()} (+{purge_embargo_months}M purge/embargo), after the decision {decision_at.isoformat()}",
        )
    return True, "all training labels were known at the decision date"
