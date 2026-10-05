"""Calendar-only derivation and coverage-independent label certification."""

from datetime import UTC, date, datetime

import pytest
from dateutil.relativedelta import relativedelta

from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.research import first_ml_contract as C
from pitquant.research.fold_readiness import (
    audit_folds,
    latest_label_safe_history,
    temporal_evidence,
)
from tests.unit.test_first_ml_fold_readiness import AS_OF, observation
from tests.unit.test_first_ml_readiness import ctx, snap

pytestmark = pytest.mark.pit


def world():
    plan, requirement = latest_label_safe_history()
    cal = get_calendar("XNYS")
    start = date.fromisoformat(requirement["minimum_ready_history_start"] + "-01")
    samples, targets, cohorts = [], {}, {}
    for i in range(requirement["minimum_contiguous_ready_months"]):
        d = cal.session_on_or_after(start + relativedelta(months=i))
        decision, target = observation(d)
        s = snap(d=d)
        s.update(decision_at=decision, issuer_id="ISSUER-1")
        samples.append(s)
        targets[("S1", decision)] = target
        cohorts[d] = {"status": "MEMBERSHIP_READY", "members": frozenset({"A1"})}
    return plan, samples, targets, ctx(cohorts=cohorts)


def test_latest_h12_month_is_derived_from_market_open_and_nominal_window():
    plan, r = latest_label_safe_history()
    assert r["last_admissible_decision_month"] == "2021-09"
    assert r["last_decision_at"] == "2021-09-01T13:30:00+00:00"
    assert r["target_end"] == "2022-09-01T13:30:00+00:00"
    assert r["security_exit_session"] == r["benchmark_exit_session"] == "2022-08-31"
    assert r["earliest_target_mature_at"] == "2022-08-31T21:00:00+00:00"
    assert r["next_month_rejected"] == "2021-10"
    assert len(plan.folds) == 3
    d = get_calendar("XNYS").session_open(date(2021, 10, 1))
    assert temporal_evidence(d, None, as_of=AS_OF)["touches_holdout"]


def test_derivation_changes_with_boundary_and_horizon_not_a_hardcoded_month():
    _, r = latest_label_safe_history(holdout_start=date(2021, 10, 1))
    assert r["last_admissible_decision_month"] == "2020-09"
    assert r["minimum_ready_history_start"] == "2013-09"
    _, r = latest_label_safe_history(horizon=6)
    assert r["last_admissible_decision_month"] == "2022-03"


def test_exact_three_latest_folds_and_positioned_85_month_requirement():
    plan, r = latest_label_safe_history()
    assert r["minimum_contiguous_ready_months"] == 85
    assert r["minimum_ready_history_start"] == "2014-09"
    assert r["last_required_dev_month"] == "2021-09"
    expected = [
        ("2017-09", "2018-10", "2019-09"),
        ("2018-09", "2019-10", "2020-09"),
        ("2019-09", "2020-10", "2021-09"),
    ]

    def month(i):
        return f"{(i - 1) // 12:04d}-{(i - 1) % 12 + 1:02d}"

    assert [
        (month(f.train_end), month(f.test_start), month(f.test_end)) for f in plan.folds
    ] == expected
    assert all(month(f.train_start) == "2014-09" for f in plan.folds)
    shorter = [date(2014, 10, 1) + relativedelta(months=i) for i in range(84)]
    assert len(C.walk_forward_folds(shorter).folds) == 2


def test_all_months_and_labels_safe_but_coverage_never_evaluated():
    plan, samples, targets, context = world()
    r = audit_folds(plan, samples, targets, context, as_of=AS_OF)
    assert r["label_safe_folds"] == 3
    assert r["coverage_evaluated"] is False
    assert r["ml_eligible_folds"] is None
    assert r["row_minimum_status"] == "UNSPECIFIED_CONTRACT"
    assert all(
        f["calendar_valid"] and f["label_safe"] and f["ml_eligible"] is None for f in r["folds"]
    )
    assert all(len(f["TEST"]["rows_by_month"]) == 12 for f in r["folds"])


def test_security_count_threshold_does_not_decide_label_safety(monkeypatch):
    plan, samples, targets, context = world()
    a = audit_folds(plan, samples, targets, context, as_of=AS_OF)
    monkeypatch.setattr(C, "REQUIRED_SECURITIES", 100000)
    b = audit_folds(plan, samples, targets, context, as_of=AS_OF)
    assert a == b and b["label_safe_folds"] == 3


def test_individual_missing_row_does_not_erase_whole_month():
    plan, samples, targets, context = world()
    second = [dict(s, security_id="S3") for s in samples]
    targets.update({("S3", s["decision_at"]): targets[("S1", s["decision_at"])] for s in samples})
    d = next(
        s["decision_at"] for s in samples if s["decision_session"].strftime("%Y-%m") == "2021-09"
    )
    targets.pop(("S1", d))
    assert (
        audit_folds(plan, samples + second, targets, context, as_of=AS_OF)["label_safe_folds"] == 3
    )


def test_eleven_test_months_cannot_pass_a_twelve_month_contract():
    plan, samples, targets, context = world()
    samples = [s for s in samples if s["decision_session"].strftime("%Y-%m") != "2021-09"]
    r = audit_folds(plan, samples, targets, context, as_of=AS_OF)
    assert r["folds"][2]["calendar_valid"]
    assert not r["folds"][2]["label_safe"]
    assert "TEST_LABEL_MONTHS_INCOMPLETE" in r["folds"][2]["blocking_reasons"]


@pytest.mark.parametrize("field", ["benchmark_total_return", "total_return", "exit_session"])
def test_whole_month_missing_outcome_blocks_label_safety(field):
    plan, samples, targets, context = world()
    for s in samples:
        if s["decision_session"].strftime("%Y-%m") == "2021-09":
            targets[("S1", s["decision_at"])][field] = None
    assert not audit_folds(plan, samples, targets, context, as_of=AS_OF)["folds"][2]["label_safe"]


def test_missing_universe_month_blocks_without_a_security_threshold():
    plan, samples, targets, context = world()
    context.cohorts[date(2014, 9, 2)]["status"] = "BLOCKED"
    r = audit_folds(plan, samples, targets, context, as_of=AS_OF)
    assert r["label_safe_folds"] == 0
    assert all("2014-09" in f["missing_history_months"] for f in r["folds"])


def test_features_missing_can_block_ml_rows_without_changing_label_safety():
    plan, samples, targets, context = world()
    for s in samples:
        s["features"] = {}
    r = audit_folds(plan, samples, targets, context, as_of=AS_OF)
    assert r["label_safe_folds"] == 3
    assert all(f["TEST"]["eligible_rows"] == 0 for f in r["folds"])


def test_sealed_outcome_values_are_never_read_even_if_supplied():
    class Poison(dict):
        def get(self, key, default=None):
            if key in ("total_return", "benchmark_total_return", "outperform", "details"):
                raise AssertionError("sealed outcome read")
            return super().get(key, default)

    for decision in (datetime(2021, 10, 1, tzinfo=UTC), datetime(2024, 10, 1, tzinfo=UTC)):
        r = temporal_evidence(decision, Poison(), as_of=AS_OF)
        assert not r["target_available"]


def test_determinism_with_same_asof_and_reordered_rows():
    plan, samples, targets, context = world()
    a = audit_folds(plan, samples, targets, context, as_of=AS_OF)
    b = audit_folds(plan, list(reversed(samples)), targets, context, as_of=AS_OF)
    assert a == b


def test_future_entry_or_exit_close_is_not_available_at_the_declared_instant():
    decision, target = observation(date(2020, 11, 2))
    target["entry_session"] = decision.date()
    assert not temporal_evidence(decision, target, as_of=AS_OF)["price_ready"]
    decision, target = observation(date(2020, 11, 2))
    target["exit_session"] = date(2021, 11, 2)  # close is after nominal target-at-open
    assert not temporal_evidence(decision, target, as_of=AS_OF)["price_ready"]


@pytest.mark.parametrize("field", ["total_return", "benchmark_total_return"])
def test_nonfinite_outcomes_cannot_certify_label_safety(field):
    decision, target = observation(date(2020, 11, 2))
    target[field] = float("nan")
    assert not temporal_evidence(decision, target, as_of=AS_OF)["target_available"]
