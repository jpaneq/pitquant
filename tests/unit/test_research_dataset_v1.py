# ruff: noqa: E501
"""Cohort ranks, write-time PIT guard, effectiveness statistics, fundamentals gating, Filing Intelligence contract, model gates."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from pitquant.core.errors import LookAheadError
from pitquant.research import dataset_v1 as DS
from pitquant.research import effectiveness_v1 as E
from pitquant.research import filing_intelligence as FI
from pitquant.research import fundamentals_v1 as FU
from pitquant.research import model_contracts as MC

T = datetime(2020, 5, 4, 13, 30, tzinfo=UTC)


def row(v: float | None) -> dict:
    return {"features": {"x": {"value": v}}}


def test_rank_cohort_percentile_ties_missing_and_small_cohort():
    rows = [row(1.0), row(2.0), row(2.0), row(None), row(10.0), row(11.0)]
    DS.rank_cohort(rows)
    assert rows[0]["ranks"]["x"] == 0.0 and rows[5]["ranks"]["x"] == 1.0
    assert rows[1]["ranks"]["x"] == rows[2]["ranks"]["x"]  # average ties
    assert (
        rows[3]["ranks"]["x"] is None and rows[3]["rank_reasons"]["x"] == "MISSING_VALUE"
    )  # never 0
    small = [row(1.0), row(2.0), row(3.0)]
    DS.rank_cohort(small)
    assert all(
        r["ranks"]["x"] is None and r["rank_reasons"]["x"] == "COHORT_TOO_SMALL" for r in small
    )


def test_rank_uses_only_the_same_cohort():
    a = [row(float(i)) for i in range(6)]
    b = [row(float(i) * 1000) for i in range(6)]
    DS.rank_cohort(a)
    DS.rank_cohort(b)
    assert [r["ranks"]["x"] for r in a] == [r["ranks"]["x"] for r in b]


def test_write_guard_rejects_future_available_at():
    ok = {"f": {"value": 1.0, "available_at": (T - timedelta(hours=1)).isoformat()}}
    DS.guard_snapshot(ok, T)
    with pytest.raises(LookAheadError):
        DS.guard_snapshot(
            {"f": {"value": 1.0, "available_at": (T + timedelta(seconds=1)).isoformat()}}, T
        )


def test_offset_summary_and_ic_on_a_known_relationship():
    rng = np.random.default_rng(3)
    months = [f"{2012 + i // 12}-{i % 12 + 1:02d}" for i in range(120)]
    rows = []
    for m in months:
        x = rng.normal(size=30)
        rows += [
            {"month": m, "x": xi, "noise": rng.normal(), "excess_6": xi + rng.normal(scale=0.5)}
            for xi in x
        ]
    df = pd.DataFrame(rows)
    ic = E.monthly_ic(df, "x", "excess_6")
    s = E.offset_summary(ic, 6)
    assert s["ic"] is not None and s["ic"] > 0.7 and s["t"] is not None and s["t"] > 5
    assert abs(E.offset_summary(E.monthly_ic(df, "noise", "excess_6"), 6)["ic"] or 0) < 0.1
    q = E.quantiles(df, "x", "excess_6", 10)
    assert q["top_minus_bottom"] > 0 and q["monotonicity"] > 0.9


def test_label_rules():
    good = {"ic": 0.05, "t": 3.0}
    assert (
        E.label(
            good,
            {"H1_2011_2016": 0.04, "H2_2017_2022": 0.06, "regime=BULL": 0.05, "regime=BEAR": 0.03},
            5.0,
            40.0,
        )
        == "PROMISING"
    )
    assert E.label(good, {"H1_2011_2016": 0.04, "H2_2017_2022": -0.06}, 5.0, 40.0) == "UNSTABLE"
    assert E.label({"ic": 0.01, "t": 0.5}, {}, 5.0, 40.0) == "WEAK"
    assert E.label(good, {}, 60.0, 40.0) == "DATA_QUALITY_LIMITED"
    assert E.label(good, {}, 5.0, 5.0) == "DATA_QUALITY_LIMITED"  # too few names per month


def test_odds_ratio_has_known_value():
    f = pd.Series([1] * 100 + [0] * 100)
    o = pd.Series([1] * 50 + [0] * 50 + [1] * 25 + [0] * 75)
    r = E.odds_ratio(f, o)
    assert (
        r["or"] == pytest.approx(3.0, rel=0.05)
        and r["lo"] < 3.0 < r["hi"]
        and r["rate_flag"] == 0.5
        and r["rate_no_flag"] == 0.25
    )


def test_sector_gating_and_no_sec_means_not_registered():
    assert (
        FU.sector_status("6021") == "UNSUPPORTED_SECTOR"
        and FU.sector_status("2834") is None
        and FU.sector_status(None) is None
    )
    feats, meta = FU.fundamental_features(
        None,
        "s",
        [],
        T,
        sic="2834",
        last_session=date(2020, 5, 1),
        raw_close=10.0,
        actions=[],
        adj_close=10.0,
        history=FU.ValuationHistory(),
        registered=False,
    )
    assert meta["fundamental_status"] == "NOT_REGISTERED" and all(
        f["value"] is None and f["missing_reason"] == "NOT_REGISTERED" for f in feats.values()
    )
    feats, meta = FU.fundamental_features(
        None,
        "s",
        [],
        T,
        sic="6021",
        last_session=date(2020, 5, 1),
        raw_close=10.0,
        actions=[],
        adj_close=10.0,
        history=FU.ValuationHistory(),
        registered=True,
    )
    assert meta["fundamental_status"] == "UNSUPPORTED_SECTOR"


def test_own_history_percentile_uses_only_earlier_points():
    h = FU.ValuationHistory()
    assert h.percentile("pe", 20.0) == (None, "INSUFFICIENT_HISTORY")
    for i in range(30):
        h.add({"pe": float(10 + i)})
    p, why = h.percentile("pe", 25.0)
    assert why is None and p is not None and 40 < p < 60
    n_before = len(h.pts["pe"])
    h.percentile("pe", 1000.0)
    assert len(h.pts["pe"]) == n_before  # reading never adds the current point


def test_every_fundamental_feature_has_one_component_and_orientation():
    assert len(FU.FEATURE_NAMES) == len(set(FU.FEATURE_NAMES))
    assert set(FU.FEATURE_COMPONENT.values()) == {
        "profitability",
        "cash_flow",
        "growth",
        "leverage",
        "capital_allocation",
        "valuation",
    }
    assert all(n in E.ORIENT for n in FU.FEATURE_NAMES)


# ---- Filing Intelligence contract -------------------------------------------------------------------------------


def snap(**over):
    base = dict(
        accession_number="0000999999-20-000001", security_id="SYN-1", form="10-K", accepted_at=T, filing_available_at=T, document_hash="a" * 64, prompt_version="p1", model_provider="NONE", model_name="FIXTURE", model_version="0",
        analysis_available_at=T, blocks={b: FI.Block() for b in FI.BLOCKS},
    )  # fmt: skip
    base.update(over)
    return FI.FilingAnalysisSnapshot(**base)


def ev() -> FI.Evidence:
    return FI.Evidence(section="Item 7", quote="Revenue increased 5%", char_start=10, char_end=40)


def test_filing_has_18_blocks_and_rejects_missing_or_extra():
    assert len(FI.BLOCKS) == 18
    snap()
    with pytest.raises(ValidationError):
        snap(blocks={b: FI.Block() for b in FI.BLOCKS[:-1]})
    with pytest.raises(ValidationError):
        snap(blocks={**{b: FI.Block() for b in FI.BLOCKS}, "invented": FI.Block()})


def test_assertion_without_evidence_is_rejected_and_quotes_are_pointers():
    with pytest.raises(ValidationError):
        FI.Block(signal=FI.Signal.IMPROVING)
    FI.Block(signal=FI.Signal.IMPROVING, evidence=(ev(),))
    with pytest.raises(ValidationError):
        FI.Evidence(section="Item 1A", quote=" ".join(["word"] * 31), char_start=0, char_end=5)
    with pytest.raises(ValidationError):
        FI.Block(signal="BULLISH")  # type: ignore[arg-type]  # free text is not an enum value


def test_pit_rule_filing_and_analysis_must_both_exist():
    s = snap(analysis_available_at=T + timedelta(days=2000))  # a backfill years later
    assert s.is_retrospective
    assert not s.usable_at(T + timedelta(days=30))  # the filing existed, the analysis did not
    assert s.usable_at(T + timedelta(days=2001))
    assert not snap().usable_at(T - timedelta(seconds=1))
    with pytest.raises(ValueError):
        snap().usable_at(datetime(2020, 1, 1))
    with pytest.raises(ValidationError):
        snap(filing_available_at=T - timedelta(days=1))


def test_feature_vector_is_numeric_enums_only_and_not_stated_is_none():
    blocks = {b: FI.Block() for b in FI.BLOCKS}
    blocks["growth_outlook"] = FI.Block(
        signal=FI.Signal.IMPROVING,
        magnitude=FI.Magnitude.HIGH,
        change_vs_prior=FI.Change.INCREASED,
        evidence=(ev(),),
        note="free text must stay out",
    )
    v = snap(blocks=blocks).feature_vector()
    assert (
        v["fi_growth_outlook_signal"] == 1.0
        and v["fi_growth_outlook_magnitude"] == 3.0
        and v["fi_business_model_signal"] is None
    )
    assert len(v) == 3 * 18 and all(x is None or isinstance(x, float) for x in v.values())


def test_pit_snapshots_picks_usable_latest_and_no_llm_runs():
    a, b = snap(), snap(prompt_version="p2", analysis_available_at=T + timedelta(days=5))
    assert FI.pit_snapshots([a, b], T + timedelta(days=1)) == [a]
    assert FI.pit_snapshots([a, b], T + timedelta(days=6)) == [b]
    assert FI.LLM_CALLS_ENABLED is False
    with pytest.raises(NotImplementedError):
        FI.analyze_filing()


def test_models_stay_blocked_without_data(session):
    assert {c.model_id for c in MC.CONTRACTS} >= {
        "EQUITY_6M_ELASTIC_NET_V0",
        "EQUITY_12M_ELASTIC_NET_V0",
        "EQUITY_6M_LOGISTIC_V0",
        "EQUITY_12M_LOGISTIC_V0",
    }
    g = {x["gate"]: x["status"] for x in MC.gate_status(session)}
    assert g["DEV_ROWS"] == "BLOCKED" and g["CANONICAL_UNIVERSE"] == "BLOCKED"
    with pytest.raises(MC.ModelBlockedError):
        MC.train("EQUITY_6M_LOGISTIC_V0", session)
