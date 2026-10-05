"""First-ML temporal certification and the actual frozen calendar contract."""

from datetime import UTC, date, datetime

import pytest
from dateutil.relativedelta import relativedelta

from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.research import first_ml as FM
from pitquant.research import first_ml_contract as C
from pitquant.research.fold_readiness import audit_folds, temporal_evidence
from pitquant.research.targets_v1 import LAG
from tests.unit.test_first_ml_readiness import ctx, snap, tgt

pytestmark = pytest.mark.pit
AS_OF = datetime(2026, 10, 5, tzinfo=UTC)


def observation(d):
    decision = datetime(d.year, d.month, d.day, 14, 30, tzinfo=UTC)
    end = decision + relativedelta(months=12)
    cal = get_calendar("XNYS")
    exit_session = cal.session_on_or_before(end.date() - relativedelta(days=1))
    target = tgt(
        entry_session=cal.session_on_or_before(d - relativedelta(days=1)),
        exit_session=exit_session,
        label_available_at=cal.session_close(exit_session) + LAG,
        total_return=0.2,
        benchmark_total_return=0.1,
    )
    return decision, target


def test_calendar_is_not_label_safe_and_missing_minimum_is_not_invented():
    dates = [date(2015, 9, 1) + relativedelta(months=i) for i in range(85)]
    plan = C.walk_forward_folds(dates)
    audit = audit_folds(plan, [], {}, ctx(), as_of=AS_OF)
    assert audit["calendar_folds"] == 3
    assert audit["label_safe_folds"] == 0
    assert audit["row_minimum_status"] == "UNSPECIFIED_CONTRACT"
    assert all(f["minimum_rows_per_fold"] is None for f in audit["folds"])
    assert C.REQUIRED_SECURITIES == 100


@pytest.mark.parametrize(
    "d,excluded", [(date(2021, 9, 1), False), (date(2021, 10, 1), True), (date(2021, 11, 1), True)]
)
def test_nominal_h12_boundary_even_if_supplied_label_claims_ok(d, excluded):
    decision, target = observation(d)
    result = temporal_evidence(decision, target, as_of=AS_OF)
    assert result["touches_holdout"] is excluded
    assert result["target_available"] is not excluded
    assert ("HOLDOUT" in FM.first_ml_eligibility(ctx(), snap(d=d), target)["reasons"]) is excluded


def test_actual_exit_in_holdout_cannot_hide_behind_pre_holdout_nominal_end():
    decision, target = observation(date(2021, 9, 1))
    target["exit_session"] = date(2022, 10, 3)
    assert temporal_evidence(decision, target, as_of=AS_OF)["touches_holdout"]
    assert "HOLDOUT" in FM.first_ml_eligibility(ctx(), snap(d=decision.date()), target)["reasons"]


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"benchmark_total_return": None}, "TARGET_BENCHMARK_NOT_READY"),
        ({"outperform": None}, "TARGET_BENCHMARK_NOT_READY"),
        ({"exit_session": None}, "TARGET_PRICE_NOT_READY"),
        ({"total_return": None}, "TARGET_PRICE_NOT_READY"),
        ({"label_available_at": None}, "LABEL_NOT_AVAILABLE_AT_CUTOFF"),
        ({"label_available_at": datetime(2027, 1, 1, tzinfo=UTC)}, "LABEL_NOT_AVAILABLE_AT_CUTOFF"),
    ],
)
def test_missing_benchmark_future_price_and_availability_fail_closed(change, reason):
    decision, target = observation(date(2020, 11, 2))
    target.update(change)
    result = temporal_evidence(decision, target, as_of=AS_OF)
    assert reason in result["reasons"]
    assert not result["target_available"]


def test_label_cannot_train_before_actual_maturity_or_full_h12_window():
    decision, target = observation(date(2019, 10, 1))
    assert not temporal_evidence(
        decision, target, as_of=target["label_available_at"] - relativedelta(seconds=1)
    )["mature"]
    assert temporal_evidence(decision, target, as_of=datetime(2020, 11, 2, tzinfo=UTC))["mature"]


def test_oot_target_is_excluded_even_for_an_earlier_decision():
    decision, target = observation(date(2024, 10, 1))
    result = temporal_evidence(decision, target, as_of=AS_OF)
    assert result["touches_oot"] and not result["target_available"]
    assert "OOT" in FM.first_ml_eligibility(ctx(), snap(d=decision.date()), target)["reasons"]


def test_training_availability_purge_embargo_and_test_exclusions():
    dates = [date(2016, 10, 1) + relativedelta(months=i) for i in range(72)]
    plan = C.walk_forward_folds(dates)
    samples, targets, cohorts = [], {}, {}
    # Last allowed TRAIN, excluded purge/embargo months, and two TEST boundaries.
    for d in (
        date(2019, 10, 1),
        date(2019, 11, 1),
        date(2020, 10, 1),
        date(2020, 11, 2),
        date(2021, 10, 1),
    ):
        decision, target = observation(d)
        sample = snap(d=d)
        sample["decision_at"] = decision
        samples.append(sample)
        targets[("S1", decision)] = target
        cohorts[d] = {"status": "MEMBERSHIP_READY", "members": frozenset({"A1"})}
    # Delayed materialisation after fit must not enter TRAIN, even with an old nominal endpoint.
    targets[("S1", samples[0]["decision_at"])]["label_available_at"] = datetime(
        2020, 11, 3, tzinfo=UTC
    )
    audited = audit_folds(plan, samples, targets, ctx(cohorts=cohorts), as_of=AS_OF)["folds"][0]
    assert audited["TRAIN"]["calendar_rows"] == 1
    assert audited["TRAIN"]["eligible_rows"] == 0
    assert audited["TEST"]["calendar_rows"] == 2
    assert audited["TEST"]["eligible_rows"] == 1
    assert audited["TEST"]["holdout_touching_rows_excluded"] == 1
    assert not audited["complete_test_window"]
    assert not audited["label_safe"]


def test_malformed_fold_cannot_bypass_purge_embargo():
    d = date(2020, 10, 1)
    decision, target = observation(d)
    sample = snap(d=d)
    sample["decision_at"] = decision
    test = snap(d=date(2020, 11, 2))
    test["decision_at"] = datetime(2020, 11, 2, 14, 30, tzinfo=UTC)
    # Inject an invalid calendar object to test the independent certification guard.
    idx = C.month_index(d)
    plan = C.FoldPlan([C.Fold(0, idx, idx, idx + 1, idx + 12, 1, 0)])
    result = audit_folds(plan, [sample, test], {("S1", decision): target}, ctx(), as_of=AS_OF)
    assert (
        "PURGE_EMBARGO_VIOLATION"
        in result["folds"][0]["TRAIN"]["rows"][0]["family_reasons"]["PRICE"]
    )


def test_naive_availability_is_not_silently_utc():
    decision, target = observation(date(2020, 11, 2))
    target["label_available_at"] = datetime(2021, 11, 1)
    with pytest.raises(ValueError, match="timezone aware"):
        temporal_evidence(decision, target, as_of=AS_OF)


def test_reported_availability_before_exit_close_plus_lag_is_rejected():
    decision, target = observation(date(2020, 11, 2))
    target["label_available_at"] = get_calendar("XNYS").session_close(target["exit_session"])
    assert not temporal_evidence(decision, target, as_of=AS_OF)["mature"]
