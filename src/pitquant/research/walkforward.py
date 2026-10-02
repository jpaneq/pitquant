# ruff: noqa: E501
"""Walk-forward contract (dry-run, no training). ADR-0030.

Rows are monthly decision dates (per security). A row's LABEL window runs from the decision date to
``label_end(d)`` (calendar horizon, first NYSE session on/after). Rules enforced for every fold:

* training rows: ``label_end(d) + embargo <= validation_start`` (label availability), and nothing in the
  ``purge`` months right before validation_start;
* validation rows: decision dates inside [validation_start, validation_end];
* the sealed holdout is NEVER touched: no decision date inside it AND no label window reaching it
  (``label_end(d) >= holdout.start`` makes a row unusable for training or validation);
* EXPANDING (train_start fixed) or ROLLING (fixed length) windows.
Nothing here reads prices or features: it plans folds from dates only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from typing import Literal

from dateutil.relativedelta import relativedelta

from pitquant.backtest.targets import target_session
from pitquant.core.errors import HoldoutAccessError

WalkForwardKind = Literal["EXPANDING", "ROLLING"]


@dataclass(frozen=True)
class WalkForwardConfig:
    window_kind: WalkForwardKind = "EXPANDING"
    train_min_months: int = 60
    rolling_train_months: int = 60
    validation_months: int = 12
    step_months: int = 12
    purge_months: int = 0
    embargo_months: int = 1
    label_horizon_months: int = 6


@dataclass(frozen=True)
class Fold:
    fold: int
    train_start: date
    train_end: date
    validation_start: date
    validation_end: date
    n_train: int
    n_validation: int

    def as_row(self) -> dict[str, object]:
        return asdict(self)


def label_end(d: date, horizon_months: int) -> date:
    return target_session(d, horizon_months)


def usable_dates(dates: Sequence[date], horizon: int, holdout: tuple[date, date]) -> list[date]:
    """Decision dates whose decision AND label window stay strictly before the sealed holdout."""
    hs, he = holdout
    out = []
    for d in sorted(dates):
        if hs <= d <= he:
            continue
        if d >= hs:
            continue  # after the holdout is not part of this research period either
        if label_end(d, horizon) >= hs:
            continue
        out.append(d)
    return out


def plan_folds(
    decision_dates: Sequence[date],
    cfg: WalkForwardConfig,
    holdout: tuple[date, date],
    rows_per_date: Mapping[date, int] | None = None,
) -> list[Fold]:
    ds = usable_dates(decision_dates, cfg.label_horizon_months, holdout)
    if not ds:
        return []

    def n(d: date) -> int:
        return rows_per_date.get(d, 0) if rows_per_date is not None else 1

    folds: list[Fold] = []
    first = ds[0]
    val_start = first + relativedelta(months=cfg.train_min_months)
    idx = 0
    while True:
        val_end_limit = val_start + relativedelta(months=cfg.validation_months)
        val = [d for d in ds if val_start <= d < val_end_limit]
        if not val:
            break
        embargo_edge = val_start - relativedelta(months=cfg.purge_months)
        train_lo = (
            first
            if cfg.window_kind == "EXPANDING"
            else val_start - relativedelta(months=cfg.rolling_train_months)
        )
        train = [
            d
            for d in ds
            if train_lo <= d < embargo_edge
            and label_end(d, cfg.label_horizon_months) + relativedelta(months=cfg.embargo_months)
            <= val_start
        ]
        if train:
            fold = Fold(
                idx,
                train[0],
                train[-1],
                val[0],
                val[-1],
                sum(n(d) for d in train),
                sum(n(d) for d in val),
            )
            assert_fold_clear_of_holdout(fold, cfg.label_horizon_months, holdout)
            folds.append(fold)
            idx += 1
        val_start = val_start + relativedelta(months=cfg.step_months)
    return folds


def assert_fold_clear_of_holdout(f: Fold, horizon: int, holdout: tuple[date, date]) -> None:
    hs, he = holdout
    for name, d in (
        ("train_start", f.train_start),
        ("train_end", f.train_end),
        ("validation_start", f.validation_start),
        ("validation_end", f.validation_end),
    ):
        if hs <= d <= he:
            raise HoldoutAccessError(
                f"fold {f.fold}: {name} {d} inside the sealed holdout {hs}..{he}"
            )
    if label_end(f.validation_end, horizon) >= hs or label_end(f.train_end, horizon) >= hs:
        raise HoldoutAccessError(
            f"fold {f.fold}: a label window reaches the sealed holdout {hs}..{he}"
        )


def dry_run(
    decision_dates: Sequence[date],
    cfg: WalkForwardConfig,
    holdout: tuple[date, date],
    rows_per_date: Mapping[date, int] | None = None,
) -> list[dict[str, object]]:
    return [f.as_row() for f in plan_folds(decision_dates, cfg, holdout, rows_per_date)]


def format_dry_run(rows: Sequence[Mapping[str, object]]) -> str:
    if not rows:
        return "no fold can be formed (not enough usable decision dates before the sealed holdout)"
    head = f"{'fold':>4} {'train_start':<11} {'train_end':<11} {'val_start':<11} {'val_end':<11} {'n_train':>8} {'n_val':>6}"
    lines = [head]
    for r in rows:
        lines.append(
            f"{r['fold']!s:>4} {r['train_start']!s:<11} {r['train_end']!s:<11} {r['validation_start']!s:<11} {r['validation_end']!s:<11} {r['n_train']!s:>8} {r['n_validation']!s:>6}"
        )
    return "\n".join(lines)
