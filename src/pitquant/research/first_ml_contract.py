# ruff: noqa: E501
"""Exact contract of the FIRST equity ML experiment (ADR-0049). NOTHING is trained here: this module only fixes WHAT will be run, so the run cannot choose its own rules after seeing results.

* Experiment ``FIRST_EQUITY_ML_12M_V0``: target ``outperform_12m`` (comparable return basis only), regularised logistic regression, five configurations M0..M4 on the SAME folds, labels, dates, universe and benchmark contract.
* Features enter by PRE-DEFINED FAMILIES, never by the RUN 3 IC ranking (research-selection bias). Any feature screening happens INSIDE each training fold.
* Walk-forward: expanding window, no random split. A training decision at month t is used for a test window starting at month s only if ``t + horizon + embargo <= s`` (purge of overlapping labels + embargo).
* Preprocessing (imputation, scaling, screening, regularisation strength) is fit on the TRAIN rows of the fold and applied to the test rows. Missing: median of TRAIN + missing indicator; never 0 unless economically zero and documented.
* The sealed holdout (2022-10-01 -> 2025-09-30) and the OOT period (>= 2025-10) contribute 0 rows to training, selection, preprocessing, benchmark tuning or feature selection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

EXPERIMENT_ID = "FIRST_EQUITY_ML_12M_V0"
HORIZON_MONTHS = 12
TRAIN_MIN_MONTHS = 36
TEST_MONTHS = 12
STEP_MONTHS = 12
EMBARGO_MONTHS = 1
MIN_FOLDS = 3
HOLDOUT = (date(2022, 10, 1), date(2025, 9, 30))
OOT_START = date(2025, 10, 1)
REQUIRED_SECURITIES = 100  # NOT changed in this phase (see docs/adr/0049: separate proposal)
REQUIRED_FUNDAMENTAL_SECURITIES = 30
REQUIRED_FUNDAMENTAL_MONTHS = 36
CORE_PRICE_FEATURES = ("ret_12m", "momentum_12_1", "realized_vol_126", "distance_sma200")
CORE_FUNDAMENTAL_FEATURES = ("fund_net_margin", "fund_revenue_yoy", "fund_debt_to_assets")

PRICE_FAMILY = (
    "ret_1m", "ret_3m", "ret_6m", "ret_12m", "momentum_12_1", "distance_sma20", "distance_sma50", "distance_sma200", "sma50_vs_sma200", "distance_52w_high", "drawdown_from_52w_high",
    "realized_vol_20", "realized_vol_63", "realized_vol_126", "atr14_pct", "downside_vol_63", "volume_zscore_20", "rsi14",
)  # fmt: skip
RISK_FAMILY = (
    "risk_alert_h6",
    "risk_alert_h12",
    "rc_below_sma200",
    "rc_momentum_negative",
    "rc_support_broken",
    "rc_elevated_volatility",
    "rc_drawdown_state",
    "support_distance_atr",
)
FUNDAMENTAL_FAMILY = (
    "fund_gross_margin", "fund_operating_margin", "fund_net_margin", "fund_roa", "fund_roe", "fund_fcf_margin", "fund_cfo_to_net_income", "fund_accruals_to_assets", "fund_revenue_yoy", "fund_net_income_yoy",
    "fund_debt_to_assets", "fund_current_ratio", "fund_shareholder_yield", "val_pe", "val_price_to_sales", "val_price_to_book", "val_fcf_yield", "val_pe_own_pct",
)  # fmt: skip
OPTIONAL_FEATURES = (
    "fund_dividend_yield",
    "fund_interest_coverage",
    "fund_gross_profitability",
)  # kept out of the first models: coverage / mapping gaps documented, never zero-filled


@dataclass(frozen=True)
class ModelConfig:
    model_id: str
    kind: str  # BASELINE | HEURISTIC | LOGISTIC
    features: tuple[str, ...]
    description: str
    trainable: bool = True
    notes: tuple[str, ...] = ()


M0 = ModelConfig(
    "M0_NAIVE_BASE_RATE",
    "BASELINE",
    (),
    "predicts the base rate of outperform in the TRAINING fold only",
    False,
)
M1 = ModelConfig(
    "M1_V0_HEURISTIC",
    "HEURISTIC",
    (),
    "the live V0 heuristic score as it is: weights NOT modified, no fitting",
    False,
    ("score mapped to a probability only by rank within the test cohort",),
)
M2 = ModelConfig(
    "M2_PRICE_CONTINUOUS_LOGISTIC",
    "LOGISTIC",
    PRICE_FAMILY,
    "price / market / volatility continuous family + same-date ranks",
)
M3 = ModelConfig(
    "M3_FUNDAMENTALS_LOGISTIC",
    "LOGISTIC",
    FUNDAMENTAL_FAMILY,
    "numeric fundamentals and valuation eligible by sector (financials / insurers excluded: UNSUPPORTED_SECTOR)",
)
M4 = ModelConfig(
    "M4_PRICE_FUNDAMENTALS_RISK_LOGISTIC",
    "LOGISTIC",
    PRICE_FAMILY + FUNDAMENTAL_FAMILY + RISK_FAMILY,
    "complete combination; RISK_ALERT enters as a risk feature, never as SELL",
)
MODELS = (M0, M1, M2, M3, M4)
FUTURE = {
    "FIRST_DOWNSIDE_MODEL_6M_V0": {
        "target": "drawdown_15 @ 6M",
        "model": "LOGISTIC",
        "features": "RISK_FAMILY + PRICE_FAMILY (RISK_ALERT is a candidate input)",
        "status": "CONTRACT_ONLY",
    },
    "FIRST_RETURN_MODEL_12M_V0": {
        "target": "excess_total_return @ 12M",
        "model": "ELASTIC_NET",
        "features": "M4 families",
        "status": "CONTRACT_ONLY",
    },
}
METRICS = {
    "classification": (
        "brier",
        "log_loss",
        "roc_auc (secondary)",
        "calibration (slope, intercept)",
        "n",
    ),
    "ranking": (
        "spearman_ic(P(outperform), realized excess)",
        "deciles",
        "D10-D1",
        "top20-bottom20",
    ),
    "strategy": "NONE: probabilities are not converted to BUY/SELL in this experiment",
}


@dataclass(frozen=True)
class Fold:
    index: int
    train_start: int
    train_end: int  # last decision month (index into the sorted month list) whose label is allowed
    test_start: int
    test_end: int
    n_train_months: int
    purged_months: int


@dataclass
class FoldPlan:
    folds: list[Fold] = field(default_factory=list)
    reason_if_none: str | None = None


def month_index(d: date) -> int:
    return d.year * 12 + d.month


def walk_forward_folds(
    months: list[date],
    *,
    train_min: int = TRAIN_MIN_MONTHS,
    test_len: int = TEST_MONTHS,
    step: int = STEP_MONTHS,
    horizon: int = HORIZON_MONTHS,
    embargo: int = EMBARGO_MONTHS,
) -> FoldPlan:
    """Expanding-window folds over CONSECUTIVE decision months. ``months`` = the sorted first-of-month dates that are fully usable (membership, identity, benchmark...): a hole breaks the run, so a fold never silently
    spans a missing month. Purge + embargo: a training month t is allowed for a test window starting at s iff idx(t) + horizon + embargo <= idx(s). A fold needs >= ``train_min`` allowed training months and a FULL test window."""
    if not months:
        return FoldPlan([], "no usable decision months")
    idx = sorted({month_index(m) for m in months})
    runs: list[list[int]] = [[idx[0]]]
    for i in idx[1:]:
        if i == runs[-1][-1] + 1:
            runs[-1].append(i)
        else:
            runs.append([i])
    plan = FoldPlan()
    k = 0
    for run in runs:
        start = run[0]
        s = start + train_min + horizon + embargo
        while s + test_len - 1 <= run[-1]:
            train_end = s - horizon - embargo
            n_train = train_end - start + 1
            plan.folds.append(
                Fold(k, start, train_end, s, s + test_len - 1, n_train, (s - 1) - train_end)
            )
            k += 1
            s += step
    if not plan.folds:
        longest = max(len(r) for r in runs)
        need = train_min + horizon + embargo + test_len
        plan.reason_if_none = f"longest consecutive usable run = {longest} months; one fold needs {need} (train_min {train_min} + purge {horizon} + embargo {embargo} + test {test_len})"
    return plan
