# ruff: noqa: E501
"""Research features V1 (ADR-0048): causality (truncation), missing reasons, frozen support, risk alert. SYNTHETIC bars (SYN): never presented as history."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from pitquant.analyzer import indicators as I
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.research import features_v1 as FT

pytestmark = pytest.mark.pit


def synth_bars(n: int = 700, seed: int = 7, start: date = date(2015, 1, 5)) -> pd.DataFrame:
    cal = get_calendar("XNYS")
    days = cal.sessions(start, date(2019, 12, 31))[:n]
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.012, len(days))))
    high, low = (
        close * (1 + rng.uniform(0, 0.01, len(days))),
        close * (1 - rng.uniform(0, 0.01, len(days))),
    )
    return pd.DataFrame(
        {
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": rng.uniform(1e6, 2e6, len(days)),
        },
        index=pd.Index(days),
    )


def bundle(bars: pd.DataFrame) -> FT.SeriesBundle:
    return FT.build_bundle("SYN-1", "SYN1", "XNYS", bars, [])


def values(feats: dict[str, dict]) -> dict[str, float | None]:
    return {k: v["value"] for k, v in feats.items()}


def test_truncation_property_every_feature():
    """The value at bar t from the FULL series equals the one computed from the series cut at t: no feature reads the future."""
    bars = synth_bars()
    full = bundle(bars)
    p_full = FT.technical_panel(full)
    for k in (260, 400, 650):
        cut = bundle(bars.iloc[: k + 1])
        a = values(FT.features_at(full, p_full, k))
        b = values(FT.features_at(cut, FT.technical_panel(cut), k))
        for name in a:
            if a[name] is None or b[name] is None:
                assert a[name] is None and b[name] is None, name
            else:
                assert a[name] == pytest.approx(b[name], rel=1e-9, abs=1e-9), name


def test_changing_the_future_does_not_change_the_past():
    bars = synth_bars()
    k = 500
    base = values(FT.features_at(bundle(bars), FT.technical_panel(bundle(bars)), k))
    shocked = bars.copy()
    shocked.iloc[k + 1 :, :4] *= 3.0
    after = values(FT.features_at(bundle(shocked), FT.technical_panel(bundle(shocked)), k))
    assert base == after


def test_missing_is_none_with_reason_never_zero():
    bars = synth_bars()
    b = bundle(bars)
    f = FT.features_at(b, FT.technical_panel(b), 30)
    assert f["ret_12m"]["value"] is None and f["ret_12m"]["missing_reason"] == "NOT_ENOUGH_HISTORY"
    assert f["distance_sma200"]["value"] is None
    assert all(x["value"] is None or isinstance(x["value"], float) for x in f.values())
    assert all(x["missing_reason"] for x in f.values() if x["value"] is None)


def test_return_and_indicator_definitions():
    bars = synth_bars()
    b = bundle(bars)
    p = FT.technical_panel(b)
    k = 400
    assert p["ret_6m"].iloc[k] == pytest.approx(b.level.iloc[k] / b.level.iloc[k - 126] - 1.0)
    assert p["rsi14"].iloc[k] == pytest.approx(I.rsi(b.adj["close"], 14).iloc[k])
    assert p["distance_sma50"].iloc[k] == pytest.approx(
        b.adj["close"].iloc[k] / I.sma(b.adj["close"], 50).iloc[k] - 1.0
    )
    assert p["momentum_12_1"].iloc[k] == pytest.approx(
        b.level.iloc[k - 21] / b.level.iloc[k - 252] - 1.0
    )


def test_available_at_is_the_bar_close_not_later():
    b = bundle(synth_bars())
    f = FT.features_at(b, FT.technical_panel(b), 300)
    cal = get_calendar("XNYS")
    expect = cal.session_close(b.index[300]).isoformat().replace("+00:00", "+00:00")
    assert all(
        x["available_at"] == pd.Timestamp(expect).tz_convert("UTC").isoformat() for x in f.values()
    )


def test_gap_in_sessions_makes_windows_missing_not_wrong():
    bars = synth_bars()
    holey = bars.drop(bars.index[300:306])  # six sessions vanish
    b = bundle(holey)
    p = FT.technical_panel(b)
    pos = 330  # the 126-session window spans the hole; the 21-session one does not
    assert pd.isna(p["ret_6m"].iloc[pos])
    assert not pd.isna(p["ret_1m"].iloc[pos])


def test_support_is_frozen_at_t_minus_1():
    """support_broken at t compares the close of t with a zone computed WITHOUT bar t: altering bar t's own high/low/close cannot move the zone."""
    bars = synth_bars()
    k = 450
    b = bundle(bars)
    s1 = FT.frozen_support(FT.technical_panel(b), b.adj, k)
    shocked = bars.copy()
    shocked.iloc[k, shocked.columns.get_indexer(["high", "low", "close"])] *= 0.7
    b2 = bundle(shocked)
    s2 = FT.frozen_support(FT.technical_panel(b2), b2.adj, k)
    assert s1 == s2


def test_no_support_zone_is_unavailable_not_unbroken():
    b = bundle(synth_bars())
    f = FT.features_at(b, FT.technical_panel(b), 3)
    assert f["support_broken"]["value"] is None and f["support_broken"]["missing_reason"] in {
        "NOT_ENOUGH_HISTORY",
        "UNAVAILABLE",
    }


def test_risk_alert_is_a_feature_with_components_and_names_do_not_collide():
    assert len(set(FT.ALL_NAMES)) == len(FT.ALL_NAMES)
    b = bundle(synth_bars())
    f = FT.features_at(b, FT.technical_panel(b), 500)
    assert {f"risk_alert_h{h}" for h in (1, 3, 6, 12, 24)} <= set(f)
    assert set(FT.RISK_COMPONENTS) <= set(f)
    assert all(f[n]["value"] in (None, 0.0, 1.0) for n in (*FT.RISK_ALERT, *FT.RISK_COMPONENTS))
