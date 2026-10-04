# ruff: noqa: E501
"""XBRL gaps behind WMT / COST / CVX (SYNTHETIC facts): 52/53-week retailers' 12/24/36-week YTD periods and two revenue tags with different values for the same period."""

from datetime import UTC, date, datetime

import pytest

from pitquant.analyzer import fundamental_v1 as fv1
from pitquant.features.v0 import fundamentals as F


def fact(concept, start, end, value, filed=datetime(2024, 12, 20, tzinfo=UTC), rev=0):
    return F.Fact(
        concept,
        start,
        end,
        value,
        "USD",
        filed,
        "0000000000-24-000001",
        "10-Q",
        rev,
        f"{concept}-{start}-{end}",
    )


def cost_like(tag="RevenueFromContractWithCustomerExcludingAssessedTax"):
    """FY ends ~Sep 1; Q1-Q3 are 12/24/36 weeks. TTM at the 36-week YTD = FY(prev) + YTD(36w) - YTD(36w prior year)."""
    return [
        fact(tag, date(2022, 8, 29), date(2023, 9, 3), 1000.0),  # FY (53 weeks)
        fact(tag, date(2023, 9, 4), date(2024, 5, 12), 800.0),  # 36-week YTD current
        fact(tag, date(2022, 8, 29), date(2023, 5, 14), 700.0),  # 36-week YTD prior year
    ]


def test_v0_cannot_read_a_36_week_ytd_but_the_wider_tolerance_can() -> None:
    facts = cost_like()
    stale = F.resolve_flow_ttm(facts, "revenue")
    assert (
        stale.value == 1000.0 and "FY ending 2023-09-03" in stale.formula
    )  # V0 is frozen: it cannot read the 252-day YTD, so it falls back to the OLDER fiscal year
    m = F.resolve_flow_ttm(facts, "revenue", tol=fv1.PERIOD_TOL_DAYS)
    assert m.value == pytest.approx(1000.0 + 800.0 - 700.0) and "YTD" in m.formula


def test_the_wider_tolerance_never_confuses_nominal_lengths() -> None:
    for months, days in (
        (3, 91),
        (6, 183),
        (9, 274),
        (12, 365),
        (3, 84),
        (6, 168),
        (9, 252),
        (12, 371),
    ):
        s = date(2023, 1, 1)
        e = date.fromordinal(s.toordinal() + days - 1)
        assert F._months(s, e, fv1.PERIOD_TOL_DAYS) == months, (months, days)
    assert (
        F._months(date(2023, 1, 1), date(2023, 4, 30), fv1.PERIOD_TOL_DAYS) is None
    )  # 120 days belongs to no period


def test_two_revenue_tags_with_different_values_fail_closed_unless_a_priority_is_given() -> None:
    a = [
        fact("Revenues", date(2023, 2, 1), date(2024, 1, 31), 650.0),
        fact(
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            date(2023, 2, 1),
            date(2024, 1, 31),
            640.0,
        ),
    ]
    assert F.resolve_flow_ttm(a, "revenue").reason == "unresolved_tag"  # V0 behaviour: fail closed
    m = F.resolve_flow_ttm(a, "revenue", prefer=fv1.REVENUE_PRIORITY)
    assert (
        m.value == 650.0 and "conflict resolved by priority" in m.formula and "640.0" in m.formula
    )  # the discarded value stays visible
    same = [
        fact("Revenues", date(2023, 2, 1), date(2024, 1, 31), 650.0),
        fact(
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            date(2023, 2, 1),
            date(2024, 1, 31),
            650.5,
        ),
    ]
    assert (
        "conflict" not in F.resolve_flow_ttm(same, "revenue", prefer=fv1.REVENUE_PRIORITY).formula
    )  # inside 1 %: no conflict


def test_values_that_v1_0_could_compute_do_not_change() -> None:
    clean = [fact("Revenues", date(2023, 1, 1), date(2023, 12, 31), 500.0)]
    assert (
        F.resolve_flow_ttm(clean, "revenue").value
        == F.resolve_flow_ttm(
            clean, "revenue", tol=fv1.PERIOD_TOL_DAYS, prefer=fv1.REVENUE_PRIORITY
        ).value
        == 500.0
    )
    assert (
        fv1.TAG_MAP_VERSION_V1 == "sec-tags-3"
        and fv1.FUNDAMENTAL_ENGINE_VERSION == "fundamental-v1.1"
    )
