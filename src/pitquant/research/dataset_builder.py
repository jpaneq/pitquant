# ruff: noqa: E501
"""Dataset Builder (ADR-0030). Same engines as the Analyzer; nothing is imputed; nothing is dropped silently.

Input: universe (security_ids) + version, start/end, snapshot frequency (monthly: first NYSE session),
feature set (RAW feature names only), label horizon (6/12), benchmark.
Output rows: security_id, decision_at, features, feature_reasons, label (excess total return), outperform,
label_available_at, benchmark_return, security_return, eligibility, blocking_reason.

Rules:
* INELIGIBLE rows stay in the dataset WITH their reason (``NO_PRICE_HISTORY``, ``FEATURES_TOO_SPARSE``,
  ``LABEL_UNAVAILABLE:<why>``, ``BENCHMARK_UNAVAILABLE``, ``LABEL_WINDOW_TOUCHES_HOLDOUT``).
* The sealed holdout is never read: decision dates inside it are not generated (counted), and rows whose
  label window would reach it are recorded as ineligible WITHOUT computing the label (no outcome is loaded).
* Human-analysis labels (Strong/Expensive/Uptrend...) are not features and not targets: only
  ``FEATURE_NAMES`` can be requested.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from pitquant.backtest.targets import (
    BENCHMARK_NAME,
    BENCHMARK_TYPE,
    LABEL_VERSION,
    compute_label,
    target_session,
)
from pitquant.config.settings import get_settings
from pitquant.core.errors import HoldoutAccessError
from pitquant.core.hashing import content_hash
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.features.v0.engine import (
    FEATURE_NAMES,
    FEATURE_VERSION,
    compute_features,
    decision_time,
)
from pitquant.features.v0.fundamentals import TAG_MAP_VERSION

BUILDER_VERSION = "dataset-builder-1"
MIN_FEATURE_COVERAGE = (
    0.5  # share of requested features that must be non-null for a row to be ELIGIBLE
)


@dataclass(frozen=True)
class DatasetSpec:
    universe: str
    universe_version: str
    security_ids: tuple[str, ...]
    start_date: date
    end_date: date
    feature_set: tuple[str, ...] = FEATURE_NAMES
    label_horizon_months: int = 6
    benchmark_security_id: str | None = None
    benchmark_name: str = BENCHMARK_NAME
    benchmark_type: str = BENCHMARK_TYPE
    snapshot_frequency: str = "MONTHLY"

    def __post_init__(self) -> None:
        unknown = [f for f in self.feature_set if f not in FEATURE_NAMES]
        if unknown:
            raise ValueError(
                f"not RAW features (human-analysis labels are never features): {unknown}"
            )
        if self.label_horizon_months not in (6, 12):
            raise ValueError("label horizon must be 6 or 12 months")
        if self.snapshot_frequency != "MONTHLY":
            raise ValueError("only MONTHLY snapshots are defined")

    def canonical(self) -> dict[str, Any]:
        return {
            "universe": self.universe,
            "universe_version": self.universe_version,
            "security_ids": sorted(self.security_ids),
            "start": str(self.start_date),
            "end": str(self.end_date),
            "feature_set": list(self.feature_set),
            "horizon": self.label_horizon_months,
            "benchmark": self.benchmark_name,
            "benchmark_type": self.benchmark_type,
            "benchmark_security_id": self.benchmark_security_id,
            "frequency": self.snapshot_frequency,
            "feature_version": FEATURE_VERSION,
            "tag_map_version": TAG_MAP_VERSION,
            "label_version": LABEL_VERSION,
            "builder_version": BUILDER_VERSION,
        }


@dataclass
class DatasetResult:
    spec: DatasetSpec
    rows: list[dict[str, Any]]
    holdout_dates_excluded: int
    dataset_hash: str
    summary: dict[str, Any] = field(default_factory=dict)
    path: str | None = None


def decision_dates(spec: DatasetSpec, holdout: tuple[date, date]) -> tuple[list[date], int]:
    cal = get_calendar("XNYS")
    ds = cal.first_sessions_of_months(
        max(spec.start_date, cal.first_session), min(spec.end_date, cal.last_session)
    )
    hs, he = holdout
    kept = [d for d in ds if not (hs <= d <= he)]
    return kept, len(ds) - len(kept)


def build_dataset(
    session: Session, spec: DatasetSpec, *, out_dir: Path | None = None
) -> DatasetResult:
    ho = get_settings().validation.final_holdout
    hold = (ho.start, ho.end)
    dates, excluded = decision_dates(spec, hold)
    rows: list[dict[str, Any]] = []
    for sid in spec.security_ids:
        for d in dates:
            rows.append(_row(session, spec, sid, d, hold))
    summary = summarize(rows)
    canon = {"spec": spec.canonical(), "rows": [_hashable(r) for r in rows]}
    h = content_hash(canon)
    res = DatasetResult(spec, rows, excluded, h, {**summary, "holdout_dates_excluded": excluded})
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        p = out_dir / f"{h}.jsonl"
        if not p.exists():
            p.write_text(
                "\n".join(json.dumps(_hashable(r), sort_keys=True, default=str) for r in rows)
                + "\n",
                encoding="utf-8",
            )
        res.path = str(p)
    return res


def _hashable(r: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = json.loads(json.dumps(r, sort_keys=True, default=str))
    return out


def _row(
    session: Session, spec: DatasetSpec, sid: str, d: date, hold: tuple[date, date]
) -> dict[str, Any]:
    dt = decision_time(d)
    base: dict[str, Any] = {
        "security_id": sid,
        "decision_session": d,
        "decision_at": dt,
        "features": dict.fromkeys(spec.feature_set),
        "feature_reasons": {},
        "label": None,
        "outperform": None,
        "label_available_at": None,
        "benchmark_return": None,
        "security_return": None,
        "eligibility": "INELIGIBLE",
        "blocking_reason": [],
    }
    reasons: list[str] = base["blocking_reason"]
    feats = {
        f.name: f
        for f in compute_features(session, sid, d, benchmark_security_id=spec.benchmark_security_id)
    }
    for name in spec.feature_set:
        f = feats[name]
        base["features"][name] = f.value
        if f.value is None:
            base["feature_reasons"][name] = f.reason
    avail = sum(v is not None for v in base["features"].values())
    if avail == 0 or all(
        base["feature_reasons"].get(n) == "insufficient_history"
        for n in spec.feature_set
        if n.startswith(("tr_", "vol_", "mom_", "close_vs"))
    ):
        reasons.append("NO_PRICE_HISTORY")
    if avail / max(len(spec.feature_set), 1) < MIN_FEATURE_COVERAGE:
        reasons.append("FEATURES_TOO_SPARSE")
    tgt = target_session(d, spec.label_horizon_months)
    if tgt >= hold[0]:
        reasons.append(
            "LABEL_WINDOW_TOUCHES_HOLDOUT"
        )  # the label is NOT computed: no holdout price is read
    elif spec.benchmark_security_id is None:
        reasons.append("BENCHMARK_UNAVAILABLE")
    else:
        lab = compute_label(session, sid, spec.benchmark_security_id, d, spec.label_horizon_months)
        base["label_available_at"] = lab.label_available_at
        if lab.status == "OK":
            base.update(
                label=lab.excess_total_return,
                outperform=lab.outperform,
                benchmark_return=lab.benchmark_total_return,
                security_return=lab.security_total_return,
            )
        else:
            reasons.append(f"LABEL_UNAVAILABLE:{lab.reason}")
    if not reasons:
        base["eligibility"] = "ELIGIBLE"
    return base


def summarize(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    reasons: dict[str, int] = {}
    for r in rows:
        for x in r["blocking_reason"]:
            k = x.split(":")[0]
            reasons[k] = reasons.get(k, 0) + 1
    ds = [r["decision_session"] for r in rows]
    return {
        "n_rows": len(rows),
        "n_eligible": sum(r["eligibility"] == "ELIGIBLE" for r in rows),
        "n_securities": len({r["security_id"] for r in rows}),
        "first_decision": str(min(ds)) if ds else None,
        "last_decision": str(max(ds)) if ds else None,
        "blocking_reasons": dict(sorted(reasons.items(), key=lambda kv: -kv[1])),
        "ineligible_rows_are_kept": True,
    }


def assert_no_holdout(rows: Sequence[dict[str, Any]], hold: tuple[date, date]) -> None:
    for r in rows:
        d = (
            r["decision_session"]
            if isinstance(r["decision_session"], date)
            else date.fromisoformat(str(r["decision_session"])[:10])
        )
        if hold[0] <= d <= hold[1]:
            raise HoldoutAccessError(f"row {r['security_id']} {d} inside the sealed holdout")
