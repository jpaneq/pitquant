# ruff: noqa: E501
"""Dataset Builder on SYNTHETIC data: keeps ineligible rows with reasons, never touches the sealed holdout."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from pitquant.research.baselines import ELASTIC_NET
from pitquant.research.dataset_builder import DatasetSpec, assert_no_holdout, build_dataset
from pitquant.research.registry import ExperimentSpec, define_experiment
from pitquant.research.walkforward import WalkForwardConfig
from tests.unit.test_feature_engine_v0 import SESSIONS, closes_path, load_bars, make_security

HOLD = (date(2022, 10, 1), date(2025, 9, 30))


@pytest.fixture
def spec_ids(session: Session) -> tuple[str, str]:
    a, b = make_security(session, "SYN A"), make_security(session, "SYN NO DATA")
    load_bars(session, a, "A", closes_path(SESSIONS, 100.0, 0.0006))
    return a, b


@pytest.mark.pit
def test_builder_keeps_ineligible_rows_and_excludes_holdout(
    session: Session, spec_ids: tuple[str, str]
) -> None:
    a, b = spec_ids
    spec = DatasetSpec("SYN", "SYN-1", (a, b), date(2015, 6, 1), date(2026, 1, 1))
    res = build_dataset(session, spec)
    assert res.holdout_dates_excluded > 0
    assert_no_holdout(res.rows, HOLD)
    assert not [
        r
        for r in res.rows
        if HOLD[0] <= date.fromisoformat(str(r["decision_session"])[:10]) <= HOLD[1]
    ]
    by_sec = {sid: [r for r in res.rows if r["security_id"] == sid] for sid in (a, b)}
    assert len(by_sec[a]) == len(by_sec[b]) > 0  # nothing dropped silently
    assert all(
        r["eligibility"] != "ELIGIBLE" and "NO_PRICE_HISTORY" in " ".join(r["blocking_reason"])
        for r in by_sec[b]
    )
    assert all(r["eligibility"] != "ELIGIBLE" for r in res.rows)  # no benchmark → never eligible


@pytest.mark.pit
def test_label_never_computed_when_window_reaches_holdout(
    session: Session, spec_ids: tuple[str, str]
) -> None:
    a, _ = spec_ids
    res = build_dataset(
        session, DatasetSpec("SYN", "SYN-1", (a,), date(2022, 1, 1), date(2022, 9, 30))
    )
    late = [
        r
        for r in res.rows
        if str(r["decision_session"])[:7]
        in ("2022-04", "2022-05", "2022-06", "2022-07", "2022-08", "2022-09")
    ]
    assert late and all(
        r["label"] is None
        and any(x.startswith("LABEL_WINDOW_TOUCHES_HOLDOUT") for x in r["blocking_reason"])
        for r in late
    )


def test_dataset_hash_is_deterministic_and_rejects_human_labels(
    session: Session, spec_ids: tuple[str, str]
) -> None:
    a, b = spec_ids
    s = DatasetSpec("SYN", "SYN-1", (a, b), date(2015, 6, 1), date(2016, 6, 1))
    assert build_dataset(session, s).dataset_hash == build_dataset(session, s).dataset_hash
    with pytest.raises(ValueError, match="human-analysis"):
        DatasetSpec(
            "SYN",
            "SYN-1",
            (a,),
            date(2015, 6, 1),
            date(2016, 6, 1),
            feature_set=("fundamentals_label",),
        )


def test_blocked_experiment_is_recorded_not_trained(
    session: Session, spec_ids: tuple[str, str]
) -> None:
    a, _ = spec_ids
    ds = build_dataset(
        session, DatasetSpec("SYN", "SYN-1", (a,), date(2015, 6, 1), date(2016, 6, 1))
    )
    ex = ExperimentSpec("SYN-baseline", ELASTIC_NET, WalkForwardConfig(), 6, "SYN-1", "none")
    row = define_experiment(session, ex, ds, {"FEATURE_RESEARCH_READY_US": False})
    assert row.status == "BLOCKED" and row.blocked_reasons and row.commit_sha
    again = define_experiment(session, ex, ds, {"FEATURE_RESEARCH_READY_US": False})
    assert again.experiment_id == row.experiment_id
