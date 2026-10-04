# ruff: noqa: E501
"""DATA READINESS FOR FIRST ML (ADR-0049): benchmark / return-basis / FX contract, membership eligibility, gates and the walk-forward contract. SYNTHETIC data only."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pandas as pd
import pytest

from pitquant.research import benchmark_contract as BC
from pitquant.research import first_ml as FM
from pitquant.research import first_ml_contract as C
from pitquant.research import targets_v1 as TG
from pitquant.research import targets_v2 as T2
from pitquant.research.fx import FxTable, parse_chart
from tests.unit.test_research_targets_v1 import HOLD, at, mk

pytestmark = pytest.mark.pit
D = date(2019, 5, 1)


# ---- benchmark / return basis / FX ----------------------------------------------------------------------------------------
def test_security_total_return_vs_price_return_benchmark_is_rejected():
    a = BC.assess(BC.IBEX_PRICE, "EUR", "TOTAL_RETURN", fx_ready=True)
    assert (
        a["quality_status"] == "PRICE_RETURN_ONLY"
        and a["comparability"] == "NOT_COMPARABLE_RETURN_BASIS"
    )


def test_currency_mismatch_without_fx_is_rejected():
    a = BC.assess(BC.URTH, "GBP", "TOTAL_RETURN", fx_ready=False)
    assert (
        a["quality_status"] == "FX_MISMATCH"
        and a["return_currency_basis"] is None
        and "FX_DATA_NOT_READY" in str(a["reason"])
    )


def test_usd_security_vs_spy_is_etf_proxy_never_the_official_index():
    a = BC.assess(BC.SPY, "USD", "TOTAL_RETURN", fx_ready=True)
    assert (
        BC.SPY.benchmark_type == "ETF_PROXY"
        and a["quality_status"] == "PROXY_ACCEPTABLE"
        and a["comparability"] == "COMPARABLE"
        and a["return_currency_basis"] == "USD"
    )
    assert "NOT the official" in BC.SPY.notes[0]


def test_foreign_security_uses_usd_basis_only_with_pit_fx():
    a = BC.assess(BC.URTH, "EUR", "TOTAL_RETURN", fx_ready=True)
    assert a["return_currency_basis"] == "USD" and "PIT_FX" in str(a["currency_conversion_method"])


def test_ibex_price_index_is_never_ready_for_excess_total_return_and_spain_falls_back_explicitly():
    spec, a, skipped = T2.choose("XMAD", "EUR", "TOTAL_RETURN", fx_ready=True)
    assert spec.ticker == "URTH" and any("^IBEX: PRICE_RETURN_ONLY" in s for s in skipped)
    spec, a, skipped = T2.choose("XMAD", "EUR", "TOTAL_RETURN", fx_ready=False)
    assert (
        a["quality_status"] in ("PRICE_RETURN_ONLY", "FX_MISMATCH")
        and a["quality_status"] not in BC.APPROVED_FOR_ML
    )


def test_total_return_index_benchmark_is_accepted_as_ready():
    ibex_tr = BC.BenchmarkSpec(
        "IBEX35_TR",
        "IBEX35TR",
        "IBEX 35 con dividendos",
        "INDEX",
        BC.ReturnType.TOTAL_RETURN,
        "EUR",
        "OFFICIAL",
    )
    a = BC.assess(ibex_tr, "EUR", "TOTAL_RETURN", fx_ready=False)
    assert a["quality_status"] == "READY" and a["comparability"] == "COMPARABLE"


def _fx() -> FxTable:
    t0 = datetime(2019, 1, 2, tzinfo=UTC)
    return FxTable(
        {
            "EUR": (
                [t0 + timedelta(days=i) for i in range(30)],
                [1.10 + i * 0.001 for i in range(30)],
                [date(2019, 1, 1) + timedelta(days=i) for i in range(30)],
            )
        }
    )


def test_future_fx_is_never_used():
    fx = _fx()
    inst = datetime(2019, 1, 10, 12, tzinfo=UTC)
    rate, _rate_date, avail = fx.usd_per_unit_at("EUR", inst)  # type: ignore[misc]
    assert avail <= inst and rate == pytest.approx(
        1.10 + 8 * 0.001
    )  # the rate available at that instant, not a later one
    assert (
        fx.usd_per_unit_at("EUR", datetime(2019, 1, 1, tzinfo=UTC)) is None
    )  # before the first rate
    assert (
        fx.usd_per_unit_at("EUR", datetime(2019, 3, 30, tzinfo=UTC)) is None
    )  # stale: no today's-rate fallback for history
    assert fx.usd_per_unit_at("SEK", inst) is None  # FX_DATA_NOT_READY
    with pytest.raises(ValueError):
        fx.usd_per_unit_at("EUR", datetime(2019, 1, 10))


def test_fx_parse_inverts_and_rejects_wrong_direction():
    body = b'{"chart":{"result":[{"timestamp":[1546300800,1546387200],"indicators":{"quote":[{"close":[100.0,null]}]}}]}}'
    assert parse_chart(body, True)[0][1] == pytest.approx(0.01)
    with pytest.raises(ValueError):
        parse_chart(body, False)  # 100 USD per unit is implausible: wrong quote direction


def test_usd_conversion_changes_the_return_by_the_fx_move():
    s = mk(1)
    days = list(s.index)
    t0 = datetime(2014, 12, 1, tzinfo=UTC)
    n = 2200
    fx = FxTable(
        {
            "EUR": (
                [t0 + timedelta(days=i) for i in range(n)],
                [1.0 + 0.0002 * i for i in range(n)],
                [date(2014, 12, 1) + timedelta(days=i) for i in range(n)],
            )
        }
    )
    u, _, _ = T2.to_usd(s, "EUR", fx)
    assert u.level.iloc[300] / s.level.iloc[300] > u.level.iloc[100] / s.level.iloc[
        100
    ] > 1.0 and len(days) == len(u.level)


def test_benchmark_not_after_the_decision_and_missing_benchmark_rejected():
    b = mk(2)
    d = at(date(2016, 3, 1))
    pos = TG._pos_at(b, d)
    assert pd.Timestamp(b.close_instants[pos]).tz_localize("UTC") <= d
    t = TG.compute_targets(mk(1), None, TG.US, d, HOLD, (6,))[0]
    assert (
        t["excess_total_return"] is None
        and t["details"]["benchmark_status"] == "BENCHMARK_NOT_INGESTED"
    )


def test_same_observation_is_deterministic():
    a = TG.compute_targets(mk(1), mk(2), TG.US, at(date(2016, 3, 1)), HOLD, (6, 12))
    b = TG.compute_targets(mk(1), mk(2), TG.US, at(date(2016, 3, 1)), HOLD, (6, 12))
    assert a == b


# ---- membership / eligibility -----------------------------------------------------------------------------------------------
def ctx(**o):
    base = dict(
        cohorts={D: {"status": "MEMBERSHIP_READY", "members": frozenset({"A1", "A2"})}, date(2019, 6, 3): {"status": "BLOCKED", "members": frozenset()}},
        bridge={"S1": frozenset({"A1"}), "S2": frozenset({"A9"}), "S3": frozenset({"A1"})}, identity_ready={"S1", "S2", "S3"}, price_accepted=True, price_present={"S1", "S2", "S3"},
    )  # fmt: skip
    base.update(o)
    return FM.EligibilityContext(**base)


def snap(sid="S1", d=D, **f):
    feats = {n: 0.1 for n in C.CORE_PRICE_FEATURES + C.CORE_FUNDAMENTAL_FEATURES}
    feats.update(f)
    return {
        "security_id": sid,
        "decision_session": d,
        "exchange": "XNYS",
        "features": feats,
        "meta": {"fundamental_status": "OK"},
    }


def tgt(**o):
    bc = {"benchmark_quality_status": "PROXY_ACCEPTABLE", "comparability": "COMPARABLE"}
    base = {"status": "OK", "outperform": True, "details": {"benchmark_contract": bc}}
    base.update(o)
    return base


def test_member_at_t_is_eligible_and_non_member_or_unproven_month_is_not():
    assert FM.first_ml_eligibility(ctx(), snap(), tgt())["eligible"]
    assert (
        FM.first_ml_eligibility(ctx(), snap("S2"), tgt())["first_reason"] == "NOT_INDEX_MEMBER_AT_T"
    )
    r = FM.first_ml_eligibility(ctx(), snap(d=date(2019, 6, 3)), tgt())
    assert r["first_reason"] == "UNIVERSE_NOT_CANONICAL"  # missing canonical membership blocks
    assert (
        FM.first_ml_eligibility(ctx(), snap(d=date(2019, 7, 1)), tgt())["first_reason"]
        == "UNIVERSE_NOT_CANONICAL"
    )  # no cohort at all


def test_membership_is_by_issuer_so_ticker_recycling_or_a_new_security_id_does_not_matter():
    assert FM.first_ml_eligibility(ctx(), snap("S3"), tgt())[
        "eligible"
    ]  # same issuer I1, another security_id
    s = snap("S1")
    s["meta"] = {"ticker": "RECYCLED", "fundamental_status": "OK"}
    assert FM.first_ml_eligibility(ctx(), s, tgt())["eligible"]


def test_holdout_and_oot_are_never_eligible():
    h = date(2023, 1, 3)
    c = ctx(
        cohorts={
            h: {"status": "MEMBERSHIP_READY", "members": frozenset({"A1"})},
            date(2025, 10, 1): {"status": "MEMBERSHIP_READY", "members": frozenset({"A1"})},
        }
    )
    assert "HOLDOUT" in FM.first_ml_eligibility(c, snap(d=h), tgt())["reasons"]
    assert "OOT" in FM.first_ml_eligibility(c, snap(d=date(2025, 10, 1)), tgt())["reasons"]


def test_each_blocking_reason_is_reported():
    assert (
        FM.first_ml_eligibility(ctx(price_accepted=False), snap(), tgt())["first_reason"]
        == "PRICE_DATA_NOT_READY"
    )
    assert (
        FM.first_ml_eligibility(ctx(identity_ready=set()), snap(), tgt())["first_reason"]
        == "SECURITY_IDENTITY_NOT_READY"
    )
    mism = tgt(
        details={
            "benchmark_contract": {
                "benchmark_quality_status": "PRICE_RETURN_ONLY",
                "comparability": "NOT_COMPARABLE_RETURN_BASIS",
            }
        }
    )
    assert FM.first_ml_eligibility(ctx(), snap(), mism)["first_reason"] == "RETURN_BASIS_MISMATCH"
    fx = tgt(
        details={
            "benchmark_contract": {
                "benchmark_quality_status": "FX_MISMATCH",
                "comparability": "FX_NOT_READY",
            }
        }
    )
    assert FM.first_ml_eligibility(ctx(), snap(), fx)["first_reason"] == "FX_NOT_READY"
    assert FM.first_ml_eligibility(ctx(), snap(), None)["first_reason"] == "BENCHMARK_NOT_READY"
    assert (
        FM.first_ml_eligibility(ctx(), snap(), tgt(status="UNAVAILABLE"))["first_reason"]
        == "TARGET_IMMATURE"
    )
    assert (
        FM.first_ml_eligibility(ctx(), snap(ret_12m=None), tgt())["first_reason"]
        == "INSUFFICIENT_HISTORY"
    )


def test_fundamental_family_needs_core_metrics_and_a_supported_sector():
    assert (
        FM.first_ml_eligibility(ctx(), snap(fund_net_margin=None), tgt(), family="FUNDAMENTALS")[
            "first_reason"
        ]
        == "FUNDAMENTALS_NOT_READY"
    )
    assert FM.first_ml_eligibility(ctx(), snap(fund_net_margin=None), tgt(), family="PRICE")[
        "eligible"
    ]  # price-only family does not need them
    s = snap()
    s["meta"] = {"fundamental_status": "UNSUPPORTED_SECTOR"}
    assert (
        FM.first_ml_eligibility(ctx(), s, tgt(), family="FUNDAMENTALS")["first_reason"]
        == "UNSUPPORTED_SECTOR"
    )
    assert FM.first_ml_eligibility(ctx(), s, tgt(), family="PRICE")["eligible"]


def test_funnel_attributes_each_row_to_its_first_failing_reason():
    rows = [
        FM.first_ml_eligibility(ctx(), snap(), tgt()),
        FM.first_ml_eligibility(ctx(), snap("S2"), tgt()),
        FM.first_ml_eligibility(ctx(price_accepted=False), snap(), tgt()),
    ]
    f = FM.funnel(rows)
    assert (
        f["raw"] == 3
        and f["eligible"] == 1
        and f["removed_by"]["NOT_INDEX_MEMBER_AT_T"] == 1
        and f["removed_by"]["PRICE_DATA_NOT_READY"] == 1
    )


# ---- gates ----------------------------------------------------------------------------------------------------------------------
def test_one_closed_gate_blocks_the_first_ml_and_all_ready_opens_it_without_training():
    ready = {g: FM.gate("READY", 1, 1, None) for g in FM.REQUIRED_GATES}
    assert FM.first_ml_baseline_ready(ready, FM.REQUIRED_GATES)
    for closed in ("BLOCKED", "PARTIAL", "NOT_APPLICABLE"):
        g = {**ready, "D05_READY": FM.gate(closed, 1, 0, "x")}
        assert not FM.first_ml_baseline_ready(g, FM.REQUIRED_GATES)
    assert not FM.first_ml_baseline_ready({}, FM.REQUIRED_GATES)  # an unknown gate does not pass
    assert all(not m.trainable or m.kind == "LOGISTIC" for m in C.MODELS)  # M0/M1 are not fitted
    with pytest.raises(ValueError):
        FM.gate("ALMOST_READY", 1, 1, None)
    assert C.REQUIRED_SECURITIES == 100  # the gate was NOT lowered


def test_fundamentals_gate_counts_only_usable_pit_months():
    rows = [
        {
            "security_id": "A",
            "ticker": "A",
            "decision_session": date(2015 + i // 12, i % 12 + 1, 1),
            "features": {n: 1.0 for n in C.CORE_FUNDAMENTAL_FEATURES},
            "meta": {"fundamental_status": "OK"},
        }
        for i in range(40)
    ]
    rows += [
        {
            "security_id": "B",
            "ticker": "B",
            "decision_session": date(2015 + i // 12, i % 12 + 1, 1),
            "features": {n: None for n in C.CORE_FUNDAMENTAL_FEATURES},
            "meta": {"fundamental_status": "OK"},
        }
        for i in range(40)
    ]
    rows += [
        {
            "security_id": "A",
            "ticker": "A",
            "decision_session": date(2023, 1, 1),
            "features": {n: 1.0 for n in C.CORE_FUNDAMENTAL_FEATURES},
            "meta": {"fundamental_status": "OK"},
        }
    ]  # holdout: not counted
    r = FM.fundamentals_months(rows)
    assert (
        r["per_security"]["A"]["usable"] == 40
        and r["per_security"]["B"]["usable"] == 0
        and r["ok"] == ["A"]
    )


# ---- walk-forward contract --------------------------------------------------------------------------------------------------
def months(start: date, n: int) -> list[date]:
    return [
        date(start.year + (start.month - 1 + i) // 12, (start.month - 1 + i) % 12 + 1, 1)
        for i in range(n)
    ]


def test_54_consecutive_months_give_zero_folds_and_say_why():
    p = C.walk_forward_folds(months(date(2018, 4, 1), 54))
    assert p.folds == [] and "longest consecutive usable run = 54" in str(p.reason_if_none)


def test_folds_purge_embargo_and_expanding_window():
    ms = months(date(2012, 1, 1), 120)
    p = C.walk_forward_folds(ms)
    assert len(p.folds) >= 3
    for f in p.folds:
        assert (
            f.train_end + C.HORIZON_MONTHS + C.EMBARGO_MONTHS <= f.test_start
        )  # no label of a training row reaches the test window
        assert (
            f.test_end - f.test_start + 1 == C.TEST_MONTHS
            and f.n_train_months >= C.TRAIN_MIN_MONTHS
        )
    assert (
        p.folds[1].train_start == p.folds[0].train_start
        and p.folds[1].train_end > p.folds[0].train_end
    )  # expanding
    assert all(
        b.test_start > a.test_end for a, b in zip(p.folds, p.folds[1:], strict=False)
    )  # test windows do not overlap


def test_a_missing_month_breaks_the_run_instead_of_being_spanned():
    ms = months(date(2012, 1, 1), 120)
    del ms[60]
    p = C.walk_forward_folds(ms)
    assert all(
        f.train_end < C.month_index(months(date(2012, 1, 1), 61)[60])
        or f.train_start > C.month_index(months(date(2012, 1, 1), 61)[60])
        for f in p.folds
    )
    assert C.walk_forward_folds([]).reason_if_none == "no usable decision months"


def test_holdout_months_contribute_nothing_to_folds():
    allm = months(date(2012, 1, 1), 160)  # reaches 2025
    usable = [m for m in allm if not (C.HOLDOUT[0] <= m <= C.HOLDOUT[1])]
    for f in C.walk_forward_folds(usable).folds:
        assert f.test_end < C.month_index(C.HOLDOUT[0]) or f.train_start > C.month_index(
            C.HOLDOUT[1]
        )
