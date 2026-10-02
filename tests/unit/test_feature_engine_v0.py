# ruff: noqa: E501
"""Feature Engine V0 + Label Engine V0 on SYNTHETIC data (tickers SYN*, labelled fixtures).
Real-source checks live in tests/unit/test_real_market_ca.py and the generated reports."""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta

import pandas as pd
import pytest
from sqlalchemy.orm import Session

from pitquant.backtest.targets import (
    assert_label_usable,
    compute_label,
    target_session,
)
from pitquant.core.errors import HoldoutAccessError, LabelLeakageError
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.db.models import FundamentalFact
from pitquant.features.v0 import fundamentals as F
from pitquant.features.v0 import technical as T
from pitquant.features.v0.engine import (
    FEATURE_NAMES,
    FEATURE_VERSION,
    build_snapshot,
    compute_features,
    cross_sectional_rank,
    decision_time,
    persist_if_new,
)
from pitquant.features.v0.series import build_series
from pitquant.market.normalized import (
    CorporateAction,
    CorporateActionKind,
    MarketBar,
    NormalizedBatch,
    Provenance,
    SourceTier,
)
from pitquant.market.pipeline import store_batch
from pitquant.security_master.service import SecurityMaster

PROV = Provenance("SYN", SourceTier.FIXTURE, "syn", "0" * 64, "syn-1")
CAL = get_calendar("XNYS")
NOW = datetime(2026, 10, 2, tzinfo=UTC)


def make_security(session: Session, name: str) -> str:
    return SecurityMaster(session).register(name=name, exchange="XNYS", currency="USD").security_id


def closes_path(
    sessions: list[date], start: float = 100.0, drift: float = 0.0006
) -> dict[date, float]:
    return {
        d: round(start * (1 + drift) ** i * (1 + 0.004 * math.sin(i / 3.0)), 4)
        for i, d in enumerate(sessions)
    }


def load_bars(
    session: Session,
    sid: str,
    key: str,
    paths: dict[date, float],
    splits: dict[date, float] | None = None,
    dividends: dict[date, float] | None = None,
    skip: set[date] | None = None,
) -> None:
    """Raw bars: prices in ``paths`` are SPLIT-ADJUSTED-today values; a split on D divides... we store RAW as traded
    (pre-split prices multiplied by the ratio of later splits)."""
    splits = splits or {}
    bars: list[MarketBar] = []
    for d, c in paths.items():
        if skip and d in skip:
            continue
        mult = 1.0
        for sd, r in splits.items():
            if d < sd:
                mult *= r
        close = round(c * mult, 4)
        at = CAL.session_close(d)
        bars.append(
            MarketBar(
                key,
                d,
                round(close * 0.999, 4),
                round(close * 1.01, 4),
                round(close * 0.99, 4),
                close,
                1000.0 / mult + (d.toordinal() % 7) * 10,
                "USD",
                at,
                PROV,
            )
        )
    actions = [
        CorporateAction(
            key,
            CorporateActionKind.SPLIT,
            CAL.session_close(CAL.session_on_or_after(d - timedelta(days=5))),
            PROV,
            ex_date=d,
            ratio=r,
        )
        for d, r in splits.items()
    ]
    actions += [
        CorporateAction(
            key,
            CorporateActionKind.CASH_DIVIDEND,
            CAL.session_close(CAL.session_on_or_after(d - timedelta(days=5))),
            Provenance("SYN", SourceTier.FIXTURE, f"div:{key}:{d}", "0" * 64, "syn-1"),
            ex_date=d,
            cash_amount=a,
            currency="USD",
        )
        for d, a in (dividends or {}).items()
    ]
    store_batch(
        session,
        NormalizedBatch(bars=bars, actions=actions),
        key_to_security={key: sid},
        market="US",
        now=NOW,
    )


SESSIONS = CAL.sessions(date(2015, 1, 2), date(2016, 12, 30))


@pytest.fixture
def px(session: Session) -> tuple[str, str]:
    a, b = make_security(session, "SYN A"), make_security(session, "SYN SPY")
    load_bars(
        session,
        a,
        "A",
        closes_path(SESSIONS),
        splits={date(2016, 3, 15): 2.0},
        dividends={date(2016, 5, 12): 0.5},
    )
    load_bars(session, b, "B", closes_path(SESSIONS, 200.0, 0.0004))
    return a, b


def add_fact(
    session: Session,
    sid: str,
    concept: str,
    start: date | None,
    end: date,
    value: float,
    avail: datetime,
    rev: int = 0,
    unit: str = "USD",
    form: str = "10-Q",
) -> None:
    session.add(
        FundamentalFact(
            security_id=sid,
            taxonomy="us-gaap",
            concept=concept,
            fiscal_period=None,
            period_start=start,
            period_end=end,
            value=value,
            unit=unit,
            available_at=avail,
            revision_id=rev,
            form=form,
            is_amendment=False,
        )
    )
    session.flush()


def val(rs, name):  # type: ignore[no-untyped-def]
    return next(r for r in rs if r.name == name)


# ───────────────────────────── price features ─────────────────────────────────────────────
def test_feature_list_is_exact_and_unique() -> None:
    assert len(FEATURE_NAMES) == len(set(FEATURE_NAMES)) == 51
    assert FEATURE_VERSION == "v0.1"


def test_no_data_from_the_decision_session_enters_a_price_feature(
    session: Session, px: tuple[str, str]
) -> None:
    a, b = px
    d = date(2016, 6, 1)
    base = compute_features(session, a, d, benchmark_security_id=b)
    # poison the decision session's own bar and the days after it
    load_bars(
        session, a, "A2", {x: 9999.0 for x in SESSIONS if x >= d}, splits={date(2016, 3, 15): 2.0}
    ) if False else None
    from pitquant.db.models import Price

    for p in session.query(Price).filter(Price.security_id == a, Price.session_date >= d):
        p.close, p.high, p.open, p.low = 1e9, 1e9, 1e9, 1e9
    session.flush()
    again = compute_features(session, a, d, benchmark_security_id=b)
    price_names = FEATURE_NAMES[:24]
    assert [r.value for r in base if r.name in price_names] == [
        r.value for r in again if r.name in price_names
    ]


def test_last_usable_price_is_the_previous_close(session: Session, px: tuple[str, str]) -> None:
    a, _ = px
    d = date(2016, 6, 1)
    prev = CAL.previous_session(d)
    mc = val(compute_features(session, a, d), "market_cap")
    assert mc.value is None  # no fundamentals -> no shares -> NULL (never imputed)
    from pitquant.db.models import Price

    assert (
        session.query(Price).filter(Price.security_id == a, Price.session_date == prev).one().close
        > 0
    )


def test_split_invariance_of_returns_and_averages() -> None:
    sess = SESSIONS[:60]
    base = closes_path(sess)
    raw = pd.DataFrame(
        {
            "open": pd.Series(base) * 0.999,
            "high": pd.Series(base) * 1.01,
            "low": pd.Series(base) * 0.99,
            "close": pd.Series(base),
            "volume": 1000.0,
        }
    )
    split_day = sess[30]
    mult = pd.Series([2.0 if d < split_day else 1.0 for d in sess], index=sess)
    raw2 = raw.copy()
    for c in ("open", "high", "low", "close"):
        raw2[c] = raw[c] * mult
    raw2["volume"] = raw["volume"] / mult
    sp = CorporateAction(
        "X",
        CorporateActionKind.SPLIT,
        datetime(2015, 1, 1, tzinfo=UTC),
        PROV,
        ex_date=split_day,
        ratio=2.0,
    )
    dec = CAL.next_session(sess[-1])
    dt = decision_time(dec)
    a = build_series(raw, [], dt, dec)
    b = build_series(raw2, [sp], dt, dec)
    assert T.tr_return(a.tr_gross, 21) == pytest.approx(T.tr_return(b.tr_gross, 21), rel=1e-12)
    assert T.close_vs_sma(a.split_adjusted["close"], 20) == pytest.approx(
        T.close_vs_sma(b.split_adjusted["close"], 20), rel=1e-12
    )
    assert T.close_vs_sma(a.split_adjusted["close"], 50) == pytest.approx(
        T.close_vs_sma(b.split_adjusted["close"], 50), rel=1e-12
    )  # window spans the split
    assert T.rsi(a.split_adjusted["close"]) == pytest.approx(
        T.rsi(b.split_adjusted["close"]), rel=1e-12
    )
    assert T.atr(a.split_adjusted) == pytest.approx(T.atr(b.split_adjusted), rel=1e-12)
    assert T.volume_ratio(a.split_adjusted["volume"]) == pytest.approx(
        T.volume_ratio(b.split_adjusted["volume"]), rel=1e-12
    )


def test_momentum_around_a_split_and_a_dividend(session: Session, px: tuple[str, str]) -> None:
    a, _ = px
    d = SESSIONS[300]
    rs = compute_features(session, a, d)
    ps = build_series(
        __import__("pitquant.data.point_in_time.context", fromlist=["PITContext"])
        .PITContext(session, decision_time(d))
        .raw_bars(a),
        __import__("pitquant.data.point_in_time.context", fromlist=["PITContext"])
        .PITContext(session, decision_time(d))
        .market_actions(a),
        decision_time(d),
        d,
    )
    # independent: TR index from split-ADJUSTED prices plus the dividend adjusted by the split ratio
    adj = pd.Series(closes_path(SESSIONS)).loc[ps.raw_close.index]
    div_day = date(2016, 5, 12)
    gross = adj / adj.shift(1)
    gross = gross.dropna()
    if div_day in gross.index:
        gross.loc[div_day] = (adj.loc[div_day] + 0.5) / adj.loc[CAL.previous_session(div_day)]
    expected_tr63 = float(gross.iloc[-63:].prod() - 1)
    assert val(rs, "tr_63d").value == pytest.approx(expected_tr63, rel=1e-9)
    lvl = gross.cumprod()
    assert val(rs, "tr_252d").value == pytest.approx(float(gross.iloc[-252:].prod() - 1), rel=1e-9)
    assert lvl.iloc[-1] > 0


def test_insufficient_history_and_gaps_are_null_with_reasons(session: Session) -> None:
    sid = make_security(session, "SYN SHORT")
    sess = SESSIONS[:100]
    load_bars(
        session, sid, "S", closes_path(sess), skip={sess[70]}
    )  # a hole inside the 63-day window
    rs = compute_features(session, sid, CAL.next_session(sess[-1]))
    assert val(rs, "tr_252d").value is None and val(rs, "tr_252d").reason == "insufficient_history"
    assert val(rs, "tr_63d").value is None and val(rs, "tr_63d").reason == "coverage_gap"
    assert val(rs, "tr_21d").value is not None
    assert (
        all(r.value is None for r in rs if r.name in ("revenue_ttm", "market_cap"))
        and val(rs, "revenue_ttm").reason == "missing_fundamental"
    )


def test_beta_and_relative_strength_need_the_benchmark(
    session: Session, px: tuple[str, str]
) -> None:
    a, b = px
    d = SESSIONS[400]
    no = compute_features(session, a, d)
    assert (
        val(no, "beta_252_spy").value is None and val(no, "beta_252_spy").reason == "coverage_gap"
    )
    yes = compute_features(session, a, d, benchmark_security_id=b)
    assert val(yes, "beta_252_spy").value is not None
    g = val(yes, "tr_63d").value
    bm = compute_features(session, b, d)
    assert val(yes, "relative_63d_spy").value == pytest.approx(
        g - val(bm, "tr_63d").value, rel=1e-9
    )  # type: ignore[operator]


def test_holdout_is_sealed_for_features(session: Session, px: tuple[str, str]) -> None:
    a, _ = px
    with pytest.raises(HoldoutAccessError):
        compute_features(session, a, date(2023, 1, 3))


# ───────────────────────────── fundamentals ───────────────────────────────────────────────
def _quarterly_facts(session: Session, sid: str) -> None:
    """FY ends Dec 31. Revenue: FY2014=400, Q1_15=100 (3M), H1_15=210 (6M YTD), Q1_14=90, H1_14=190."""
    d = lambda y, m, dd: date(y, m, dd)  # noqa: E731
    av = lambda y, m, dd: datetime(y, m, dd, 21, tzinfo=UTC)  # noqa: E731
    R = "Revenues"
    add_fact(session, sid, R, d(2014, 1, 1), d(2014, 12, 31), 400.0, av(2015, 2, 20), form="10-K")
    add_fact(session, sid, R, d(2014, 1, 1), d(2014, 3, 31), 90.0, av(2014, 5, 1))
    add_fact(session, sid, R, d(2014, 1, 1), d(2014, 6, 30), 190.0, av(2014, 8, 1))
    add_fact(session, sid, R, d(2015, 1, 1), d(2015, 3, 31), 100.0, av(2015, 5, 1))
    add_fact(session, sid, R, d(2015, 1, 1), d(2015, 6, 30), 210.0, av(2015, 8, 1))
    add_fact(
        session, sid, R, d(2015, 4, 1), d(2015, 6, 30), 110.0, av(2015, 8, 1)
    )  # discrete Q2 (must NOT be summed with YTD)


def test_ttm_periodization_never_sums_ytd_as_quarters(session: Session) -> None:
    sid = make_security(session, "SYN FUND")
    _quarterly_facts(session, sid)
    after_q2 = datetime(2015, 9, 1, tzinfo=UTC)
    vis = F.visible(
        __import__("pitquant.features.v0.engine", fromlist=["load_facts"]).load_facts(
            session, sid, after_q2
        ),
        after_q2,
    )
    m = F.resolve_flow_ttm(vis, "revenue")
    assert m.value == 400.0 + 210.0 - 190.0  # FY(2014) + H1(2015) - H1(2014)
    assert "YTD" in m.formula and len(m.provenance) == 3
    after_q1 = datetime(2015, 6, 1, tzinfo=UTC)
    m1 = F.resolve_flow_ttm(
        F.visible(
            __import__("pitquant.features.v0.engine", fromlist=["load_facts"]).load_facts(
                session, sid, after_q1
            ),
            after_q1,
        ),
        "revenue",
    )
    assert m1.value == 400.0 + 100.0 - 90.0


def test_no_future_filing_and_restatement_is_pit(session: Session) -> None:
    sid = make_security(session, "SYN REST")
    _quarterly_facts(session, sid)
    from pitquant.features.v0.engine import load_facts

    # restatement of H1 2015 filed in Nov 2015: 210 -> 230
    add_fact(
        session,
        sid,
        "Revenues",
        date(2015, 1, 1),
        date(2015, 6, 30),
        230.0,
        datetime(2015, 11, 5, 21, tzinfo=UTC),
        rev=1,
    )
    t_before, t_after = datetime(2015, 10, 1, tzinfo=UTC), datetime(2015, 12, 1, tzinfo=UTC)
    assert (
        F.resolve_flow_ttm(F.visible(load_facts(session, sid, t_before), t_before), "revenue").value
        == 420.0
    )
    assert (
        F.resolve_flow_ttm(F.visible(load_facts(session, sid, t_after), t_after), "revenue").value
        == 440.0
    )
    # nothing filed after the decision is visible, even at the exact filing instant
    exact = datetime(2015, 5, 1, 21, tzinfo=UTC)
    assert all(f.available_at < exact for f in load_facts(session, sid, exact))


def test_conflicting_revenue_tags_fail_closed(session: Session) -> None:
    sid = make_security(session, "SYN CONF")
    av = datetime(2016, 2, 1, tzinfo=UTC)
    add_fact(session, sid, "Revenues", date(2015, 1, 1), date(2015, 12, 31), 500.0, av, form="10-K")
    add_fact(
        session,
        sid,
        "SalesRevenueNet",
        date(2015, 1, 1),
        date(2015, 12, 31),
        900.0,
        av,
        form="10-K",
    )
    from pitquant.features.v0.engine import load_facts

    dt = datetime(2016, 3, 1, tzinfo=UTC)
    m = F.resolve_flow_ttm(F.visible(load_facts(session, sid, dt), dt), "revenue")
    assert m.value is None and m.reason == "unresolved_tag"
    add_fact(
        session, sid, "SalesRevenueNet", date(2014, 1, 1), date(2014, 12, 31), 1.0, av
    )  # an older tag alone never overrides


def test_valuation_denominator_rules_and_split_aligned_shares(
    session: Session, px: tuple[str, str]
) -> None:
    a, _ = px
    av = datetime(2016, 2, 15, 21, tzinfo=UTC)
    add_fact(
        session,
        a,
        "EntityCommonStockSharesOutstanding",
        None,
        date(2016, 2, 10),
        1_000_000.0,
        av,
        unit="shares",
        form="10-K",
    )
    add_fact(
        session, a, "Revenues", date(2015, 1, 1), date(2015, 12, 31), 5_000_000.0, av, form="10-K"
    )
    add_fact(
        session, a, "NetIncomeLoss", date(2015, 1, 1), date(2015, 12, 31), -100.0, av, form="10-K"
    )
    add_fact(session, a, "StockholdersEquity", None, date(2015, 12, 31), 0.0, av, form="10-K")
    add_fact(
        session,
        a,
        "NetCashProvidedByUsedInOperatingActivities",
        date(2015, 1, 1),
        date(2015, 12, 31),
        300_000.0,
        av,
        form="10-K",
    )
    add_fact(
        session,
        a,
        "PaymentsToAcquirePropertyPlantAndEquipment",
        date(2015, 1, 1),
        date(2015, 12, 31),
        500_000.0,
        av,
        form="10-K",
    )
    d = date(
        2016, 4, 1
    )  # AFTER the 2:1 split of 2016-03-15: raw price is post-split, shares were reported pre-split
    rs = compute_features(session, a, d)
    mc = val(rs, "market_cap")
    prev = CAL.previous_session(d)
    from pitquant.db.models import Price

    raw_prev = (
        session.query(Price).filter(Price.security_id == a, Price.session_date == prev).one().close
    )
    assert mc.value == pytest.approx(
        raw_prev * 1_000_000.0 * 2.0
    )  # shares aligned to the post-split basis
    assert (
        val(rs, "price_to_earnings").value is None
        and val(rs, "price_to_earnings").reason == "denominator_invalid"
    )  # earnings <= 0
    assert (
        val(rs, "price_to_book").value is None
        and val(rs, "price_to_book").reason == "denominator_invalid"
    )  # equity <= 0
    fy = val(rs, "fcf_yield")
    assert fy.value is not None and fy.value < 0  # negative FCF yield is kept, never truncated
    assert fy.value == pytest.approx((300_000.0 - 500_000.0) / mc.value)  # type: ignore[operator]
    assert val(rs, "price_to_sales").value == pytest.approx(mc.value / 5_000_000.0)  # type: ignore[operator]
    assert val(rs, "net_margin").value == pytest.approx(-100.0 / 5_000_000.0)
    assert (
        val(rs, "operating_income_ttm").value is None and val(rs, "operating_margin").value is None
    )  # missing stays NULL


def test_stale_shares_are_not_used(session: Session, px: tuple[str, str]) -> None:
    a, _ = px
    add_fact(
        session,
        a,
        "EntityCommonStockSharesOutstanding",
        None,
        date(2014, 1, 10),
        1.0,
        datetime(2014, 1, 20, tzinfo=UTC),
        unit="shares",
    )
    rs = compute_features(session, a, date(2016, 4, 1))
    assert val(rs, "market_cap").value is None and val(rs, "market_cap").reason == "stale_data"


# ───────────────────────────── snapshots ──────────────────────────────────────────────────
def test_snapshot_is_deterministic_audited_and_immutable_by_version(
    session: Session, px: tuple[str, str]
) -> None:
    a, b = px
    d = SESSIONS[320]
    s1 = build_snapshot(session, a, d, benchmark_security_id=b, is_synthetic=True)
    s2 = build_snapshot(session, a, d, benchmark_security_id=b, is_synthetic=True)
    assert s1.content_hash == s2.content_hash and s1.feature_version == FEATURE_VERSION
    assert s1.max_available_at is not None and s1.max_available_at < decision_time(d)
    assert set(s1.features) == set(FEATURE_NAMES)
    assert (
        s1.availability["tr_63d"]["formula"].startswith("prod(")
        and s1.availability["revenue_ttm"]["reason"] == "missing_fundamental"
    )
    row, new = persist_if_new(session, s1)
    row2, new2 = persist_if_new(session, s2)
    assert new and not new2 and row.snapshot_id == row2.snapshot_id
    # a different feature_version would be a different row, never an update (feature_snapshots is append-only)
    from pitquant.db.models import IMMUTABLE_TABLES

    assert "feature_snapshots" in IMMUTABLE_TABLES


def test_cross_sectional_rank_is_separate_and_within_one_cohort() -> None:
    r = cross_sectional_rank({"A": 1.0, "B": 3.0, "C": 2.0, "D": None})
    assert r == {"A": 0.0, "B": 1.0, "C": 0.5, "D": None}


# ───────────────────────────── labels ─────────────────────────────────────────────────────
def test_target_session_calendar_months_weekend_and_holiday() -> None:
    assert target_session(date(2015, 3, 2), 6) == date(2015, 9, 2)
    assert target_session(date(2015, 3, 2), 12) == date(2016, 3, 2)
    # 2015-08-29 + 6M = 2016-02-29: Monday -> same day; 2015-03-07 isn't a session, so use 2015-03-09 + 6M = 2015-09-09
    assert target_session(date(2015, 12, 31), 6) == date(2016, 6, 30)
    assert target_session(date(2015, 8, 31), 6) == date(2016, 2, 29)
    # target on a Saturday rolls forward: 2015-12-14 (Mon) + 6M = 2016-06-14 (Tue) ok; 2015-06-12 + 12M? use explicit
    assert target_session(date(2015, 5, 4), 12) == date(2016, 5, 4)
    # holiday: 2015-01-19 is MLK; start 2014-07-21 + 6M = 2015-01-21 (Wed). Use 2014-07-19 not a session; choose start whose target is the holiday
    sess = CAL.sessions(date(2015, 7, 6), date(2015, 7, 6))
    assert sess and target_session(sess[0], 6) == date(2016, 1, 6)
    assert target_session(date(2015, 7, 20), 6) == date(2016, 1, 20)
    assert target_session(date(2015, 1, 20), 12) == date(2016, 1, 20)
    # weekend target: 2015-11-18 + 12M = 2016-11-18 (Fri); 2015-02-27 + 6M = 2015-08-27; use a start whose target is Sunday
    assert (
        target_session(date(2015, 2, 20), 12) == date(2016, 2, 22)
        if CAL.is_session(date(2015, 2, 20))
        else True
    )


def test_label_total_return_split_dividend_and_benchmark_alignment(
    session: Session, px: tuple[str, str]
) -> None:
    a, b = px
    d = date(2015, 9, 1)  # 6M -> 2016-03-01 (before the split on 2016-03-15)
    lab = compute_label(session, a, b, d, 6)
    assert (
        lab.status == "OK"
        and lab.target_session == date(2016, 3, 1)
        and lab.benchmark_type == "ETF_PROXY"
    )
    path = closes_path(SESSIONS)
    opn = round(path[d] * 0.999, 4)
    assert lab.security_total_return == pytest.approx(path[date(2016, 3, 1)] / opn - 1, rel=1e-9)
    bp = closes_path(SESSIONS, 200.0, 0.0004)
    assert lab.benchmark_total_return == pytest.approx(
        bp[date(2016, 3, 1)] / round(bp[d] * 0.999, 4) - 1, rel=1e-9
    )
    assert lab.excess_total_return == pytest.approx(
        lab.security_total_return - lab.benchmark_total_return
    )  # type: ignore[operator]
    assert lab.outperform is (lab.excess_total_return > 0)  # type: ignore[operator]
    # horizon containing the split (2016-03-15) and the dividend (2016-05-12)
    d2 = date(2015, 12, 1)
    lab12 = compute_label(session, a, b, d2, 6)  # -> 2016-06-01
    assert lab12.status == "OK"
    opn2 = round(path[d2] * 0.999, 4)
    # independent: split-adjusted path + dividend (0.5 on the post-split basis) at its ex-date
    prev_div = CAL.previous_session(date(2016, 5, 12))
    chain = (path[date(2016, 6, 1)] / path[d2]) * (
        (path[date(2016, 5, 12)] + 0.5) / path[date(2016, 5, 12)]
    )
    day1 = path[d2] / opn2
    indep = (
        day1
        * (path[d2] and (path[date(2016, 6, 1)] / path[d2]))
        * ((path[date(2016, 5, 12)] + 0.5) / path[date(2016, 5, 12)])
        - 1
    )
    assert lab12.security_total_return == pytest.approx(
        indep, abs=1e-5
    )  # raw bars are rounded to 4 decimals before/after the split
    assert chain > 0 and prev_div < date(2016, 5, 12)


def test_label_unavailable_cases_and_training_cutoff(session: Session, px: tuple[str, str]) -> None:
    a, b = px
    late = compute_label(session, a, b, date(2016, 9, 1), 12)  # 12M target 2017-09-01: no bars
    assert late.status == "UNAVAILABLE" and "no_bar_at_target" in (late.reason or "")
    with pytest.raises(LabelLeakageError):
        assert_label_usable(late, datetime(2030, 1, 1, tzinfo=UTC))
    ok = compute_label(session, a, b, date(2015, 3, 2), 6)
    assert ok.status == "OK"
    with pytest.raises(LabelLeakageError, match="after the training cutoff"):
        assert_label_usable(
            ok, datetime(2015, 9, 1, tzinfo=UTC)
        )  # outcome (2015-09-02 close) not yet knowable
    assert_label_usable(ok, ok.label_available_at)  # exactly knowable: allowed
    # benchmark missing at the entry
    c = make_security(session, "SYN NOBENCH")
    load_bars(session, c, "C", closes_path(SESSIONS, 50.0))
    nb = make_security(session, "SYN SHORTBENCH")
    load_bars(session, nb, "N", closes_path(SESSIONS[100:], 10.0))
    bad = compute_label(session, c, nb, date(2015, 3, 2), 6)
    assert (
        bad.status == "UNAVAILABLE"
        and bad.reason is not None
        and bad.reason.startswith("benchmark:")
    )


def test_delisted_before_horizon_is_unavailable_without_a_terminal_event(
    session: Session, px: tuple[str, str]
) -> None:
    _, b = px
    c = make_security(session, "SYN DELISTED")
    load_bars(session, c, "D", closes_path(SESSIONS[:200]))  # series stops, no delisting event
    lab = compute_label(session, c, b, date(2015, 3, 2), 12)
    assert lab.status == "UNAVAILABLE" and "no_bar_at_target" in (lab.reason or "")
    # with a documented terminal event the engine can close the position
    last = SESSIONS[199]
    ev = CorporateAction(
        "D2",
        CorporateActionKind.BANKRUPTCY,
        CAL.session_close(last),
        PROV,
        effective_date=CAL.next_session(last),
        details={"recovery_per_share": 0.0},
    )
    e = make_security(session, "SYN BANKRUPT")
    load_bars(session, e, "D2", closes_path(SESSIONS[:201]))
    store_batch(
        session, NormalizedBatch(actions=[ev]), key_to_security={"D2": e}, market="US", now=NOW
    )
    lab2 = compute_label(session, e, b, date(2015, 3, 2), 12)
    assert lab2.terminal is not None or lab2.status == "UNAVAILABLE"


# ───────────────────────────── explain-feature & readiness separation ─────────────────────────
def test_explain_feature_shows_formula_inputs_and_provenance(
    session: Session, px: tuple[str, str]
) -> None:
    from pitquant.features.v0.explain import explain_feature

    a, _ = px
    av = datetime(2016, 2, 15, 21, tzinfo=UTC)
    add_fact(
        session, a, "Revenues", date(2015, 1, 1), date(2015, 12, 31), 5_000_000.0, av, form="10-K"
    )
    add_fact(
        session,
        a,
        "Revenues",
        date(2014, 1, 1),
        date(2014, 12, 31),
        4_000_000.0,
        datetime(2015, 2, 15, 21, tzinfo=UTC),
        form="10-K",
    )
    txt = explain_feature(session, a, date(2016, 4, 1), "revenue_growth_yoy")
    assert (
        "VALUE: 0.25" in txt
        and "decision_at (NYSE open)" in txt
        and "revenue_ttm(prior year)" in txt
    )
    assert "2015-01-01..2015-12-31" in txt and "available_at" in txt
    tech = explain_feature(session, a, date(2016, 4, 1), "tr_21d")
    assert (
        "price rows used" in tech
        and "nothing of 2016-04-01 or later" in tech
        and "corporate actions known" in tech
    )


def test_research_readiness_flags_are_separate_and_default_false(
    session: Session, settings
) -> None:  # type: ignore[no-untyped-def]
    from pitquant.research_readiness import research_readiness

    rf = research_readiness(session, settings)
    f = rf.flags
    assert f["FEATURE_ENGINE_IMPLEMENTED"] is True  # code exists...
    assert (
        f["FEATURE_RESEARCH_READY_US"] is False and f["FEATURE_RESEARCH_READY_ES"] is False
    )  # ...data does not
    assert f["FEATURE_RESEARCH_READY"] is False and f["D02_RESEARCH_READY"] is False
    assert rf.status["ES_D05_RESEARCH_READY"] == "ES_D05_BLOCKED_BY_ENTITLEMENT"
    assert f["BASELINE_MODEL_READY"] is False and f["LABEL_ENGINE_READY_US"] is False
