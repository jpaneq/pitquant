"""Temporal validation: purged walk-forward with embargo, label availability and a locked
final holdout (ADR-0009). Never shuffles.

Observations are a DataFrame with tz-aware UTC columns:
``t_exec``, ``label_end``, ``label_available_at`` (one row per prediction).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

from pitquant.core.errors import HoldoutAccessError, LabelLeakageError
from pitquant.core.timeutils import require_aware, utc_now
from pitquant.core.types import ValidationMode

REQUIRED_COLUMNS = ("t_exec", "label_end", "label_available_at")


def _utc(d: date) -> pd.Timestamp:
    return pd.Timestamp(datetime.combine(d, time(0, 0), tzinfo=UTC))


def _check_obs(obs: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in obs.columns]
    if missing:
        raise ValueError(f"observations missing columns {missing}")
    for c in REQUIRED_COLUMNS:
        tz = getattr(obs[c].dtype, "tz", None)
        if tz is None:
            raise ValueError(f"column {c} must be timezone-aware")
    if (obs["label_end"] <= obs["t_exec"]).any():
        raise ValueError("label_end must be after t_exec")
    if (obs["label_available_at"] < obs["label_end"]).any():
        raise ValueError("label_available_at must be >= label_end")


# ───────────────────────────── holdout ─────────────────────────────


@dataclass(frozen=True)
class HoldoutAccess:
    model_version: str
    reason: str
    requested_by: str
    accessed_at: datetime


@dataclass
class HoldoutGuard:
    """Final holdout ``[start, end]`` (dates of t_exec). Locked unless explicitly unlocked
    for a FROZEN model version; every unlock is logged via ``on_access`` (persisted to
    ``holdout_access_log``) and cannot be revoked."""

    start: date
    end: date
    on_access: Callable[[HoldoutAccess], None] | None = None
    _unlocked_for: str | None = field(default=None, init=False)
    log: list[HoldoutAccess] = field(default_factory=list, init=False)

    @property
    def start_ts(self) -> pd.Timestamp:
        return _utc(self.start)

    def unlock(
        self, *, model_version: str, model_frozen: bool, reason: str, requested_by: str
    ) -> None:
        if not model_frozen:
            raise HoldoutAccessError("holdout can only be evaluated with a frozen model version")
        if not reason.strip():
            raise HoldoutAccessError("a reason is mandatory to access the holdout")
        access = HoldoutAccess(model_version, reason, requested_by, utc_now())
        self.log.append(access)
        if self.on_access is not None:
            self.on_access(access)
        self._unlocked_for = model_version

    def is_unlocked_for(self, model_version: str) -> bool:
        return self._unlocked_for == model_version

    def assert_development_safe(self, obs: pd.DataFrame, *, strict_labels: bool = True) -> None:
        """Raise if any development observation lies in — or (strict) peeks into — the holdout."""
        bad = obs["t_exec"] >= self.start_ts
        if strict_labels:
            bad |= obs["label_end"] >= self.start_ts
        if bool(bad.any()):
            raise HoldoutAccessError(
                f"{int(bad.sum())} observation(s) touch the final holdout starting {self.start}"
            )

    def development_mask(self, obs: pd.DataFrame, *, strict_labels: bool = True) -> pd.Series:
        """Observations usable during development (before the holdout, labels included)."""
        mask = obs["t_exec"] < self.start_ts
        if strict_labels:
            mask &= obs["label_end"] < self.start_ts
        return mask


# ───────────────────────────── folds ─────────────────────────────


@dataclass(frozen=True)
class Fold:
    k: int
    train_idx: np.ndarray
    val_idx: np.ndarray
    test_idx: np.ndarray
    train_cutoff: pd.Timestamp  # labels must be known by this instant to train
    decision_time: pd.Timestamp  # = test_start: model/hyperparameters fixed here
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    n_purged: int
    n_embargoed: int
    n_label_unavailable: int


@dataclass(frozen=True)
class PurgedWalkForward:
    first_test_start: date
    train_min_months: int = 60
    validation_months: int = 24
    test_months: int = 12
    step_months: int = 12
    embargo: relativedelta = field(default_factory=lambda: relativedelta(months=12))
    mode: ValidationMode = ValidationMode.EXPANDING
    rolling_train_months: int | None = None
    holdout: HoldoutGuard | None = None
    strict_holdout_labels: bool = True

    def split(self, obs: pd.DataFrame, last_test_end: date | None = None) -> Iterator[Fold]:
        _check_obs(obs)
        if self.holdout is not None:
            dev = self.holdout.development_mask(obs, strict_labels=self.strict_holdout_labels)
            obs = obs[dev]
            hard_end = self.holdout.start
            last_test_end = min(last_test_end, hard_end) if last_test_end else hard_end
        t_exec = obs["t_exec"]
        label_end = obs["label_end"]
        label_av = obs["label_available_at"]
        data_start = t_exec.min()
        final = _utc(last_test_end) if last_test_end else t_exec.max() + pd.Timedelta(days=1)

        k = 0
        test_start_d = self.first_test_start
        while True:
            test_start = _utc(test_start_d)
            if test_start >= final:
                return
            test_end = min(_utc(test_start_d + relativedelta(months=self.test_months)), final)
            val_start = _utc(test_start_d - relativedelta(months=self.validation_months))
            train_cutoff = val_start
            embargo_start = _utc(
                (test_start_d - relativedelta(months=self.validation_months)) - self.embargo
            )
            if val_start - data_start < pd.Timedelta(days=30 * self.train_min_months):
                raise ValueError("not enough history before the first validation block")

            in_train_time = t_exec < val_start
            if self.mode is ValidationMode.ROLLING:
                months = self.rolling_train_months or self.train_min_months
                in_train_time &= t_exec >= _utc(
                    test_start_d - relativedelta(months=self.validation_months + months)
                )

            label_ok = label_av <= train_cutoff
            # Purge: outcome interval overlaps the evaluation span [val_start, test_end).
            overlaps_eval = (t_exec < test_end) & (label_end >= val_start)
            embargoed = (t_exec >= embargo_start) & (t_exec < val_start)

            train = in_train_time & label_ok & ~overlaps_eval & ~embargoed
            n_label_unavailable = int((in_train_time & ~label_ok).sum())
            n_purged = int((in_train_time & label_ok & overlaps_eval).sum())
            n_embargoed = int((in_train_time & label_ok & ~overlaps_eval & embargoed).sum())

            # Validation labels must be known when hyper-parameters are chosen (test_start).
            val = (t_exec >= val_start) & (t_exec < test_start) & (label_av <= test_start)
            test = (t_exec >= test_start) & (t_exec < test_end)
            if not bool(test.any()):
                return  # no evaluable observations left (data end or holdout boundary)

            fold = Fold(
                k=k,
                train_idx=np.flatnonzero(train.to_numpy()),
                val_idx=np.flatnonzero(val.to_numpy()),
                test_idx=np.flatnonzero(test.to_numpy()),
                train_cutoff=train_cutoff,
                decision_time=test_start,
                test_start=test_start,
                test_end=test_end,
                n_purged=n_purged,
                n_embargoed=n_embargoed,
                n_label_unavailable=n_label_unavailable,
            )
            # Positions refer to the (possibly holdout-filtered) frame; map back to labels.
            fold = _remap(fold, obs.index)
            assert_fold_integrity(fold, obs)
            yield fold
            k += 1
            test_start_d = test_start_d + relativedelta(months=self.step_months)


def _remap(fold: Fold, index: pd.Index) -> Fold:
    return Fold(
        k=fold.k,
        train_idx=np.asarray(index[fold.train_idx]),
        val_idx=np.asarray(index[fold.val_idx]),
        test_idx=np.asarray(index[fold.test_idx]),
        train_cutoff=fold.train_cutoff,
        decision_time=fold.decision_time,
        test_start=fold.test_start,
        test_end=fold.test_end,
        n_purged=fold.n_purged,
        n_embargoed=fold.n_embargoed,
        n_label_unavailable=fold.n_label_unavailable,
    )


def assert_fold_integrity(fold: Fold, obs: pd.DataFrame) -> None:
    """Invariants re-checked on every fold (defence in depth). Indices are obs.index labels."""
    tr, va, te = set(fold.train_idx), set(fold.val_idx), set(fold.test_idx)
    if tr & va or tr & te or va & te:
        raise LabelLeakageError(f"fold {fold.k}: partitions share observations")
    if tr:
        sub = obs.loc[list(fold.train_idx)]
        if (sub["label_available_at"] > fold.train_cutoff).any():
            raise LabelLeakageError(f"fold {fold.k}: train label unavailable at cutoff")
        if (sub["label_end"] > fold.train_cutoff).any():
            raise LabelLeakageError(f"fold {fold.k}: train outcome overlaps evaluation")
    if va:
        sub = obs.loc[list(fold.val_idx)]
        if (sub["label_available_at"] > fold.decision_time).any():
            raise LabelLeakageError(f"fold {fold.k}: validation label unknown at decision time")
    if (
        te
        and tr
        and obs.loc[list(fold.train_idx), "t_exec"].max()
        >= obs.loc[list(fold.test_idx), "t_exec"].min()
    ):
        raise LabelLeakageError(f"fold {fold.k}: train not strictly before test")


def assert_training_labels_available(label_available_at: pd.Series, train_cutoff: datetime) -> None:
    """Final gate called by every model ``fit``: refuses labels unknown at the cutoff."""
    cutoff = pd.Timestamp(require_aware(train_cutoff, "train_cutoff"))
    late = label_available_at > cutoff
    if bool(late.any()):
        raise LabelLeakageError(
            f"{int(late.sum())} training label(s) not available at cutoff {cutoff.isoformat()}"
        )
