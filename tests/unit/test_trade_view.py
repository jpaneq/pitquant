# ruff: noqa: E501
"""Visual trade viewer data: a routine decision becomes candles + trend + frozen levels + markers. SYNTHETIC bars (SYN)."""

from __future__ import annotations

from datetime import UTC, date, datetime

import numpy as np
import pandas as pd

from pitquant.db.models_routine import DailyPick
from pitquant.positions import trade_view as tv


def fake_bars(n: int = 320) -> pd.DataFrame:
    idx = pd.bdate_range(end="2026-10-02", periods=n).date
    c = 100 + np.cumsum(np.full(n, 0.2))
    return pd.DataFrame({"open": c, "high": c + 1, "low": c - 1, "close": c}, index=pd.Index(idx))


def decision(kind: str, h: int = 6) -> dict:
    return {
        "horizon_months": h,
        "score": 3.0,
        "recommendation": "ADD" if kind == "BUY" else "HOLD",
        "reason": "SYN rule text",
        "decision": kind,
        "position_id": None,
        "decided_at": "2026-10-05T07:00:00+00:00",
        "hypothetical": {"entry_price": 150.0, "target_price": 165.0, "stop_price": 142.0},
    }


def test_buy_and_no_order_charts_carry_frozen_levels_markers_and_explanation(session, monkeypatch):
    monkeypatch.setattr(tv, "equity_daily_bars", lambda *_a, **_k: fake_bars())
    p = DailyPick(
        run_date=date(2026, 10, 5),
        market="SP500",
        ticker="SYN1",
        security_id="SYN-1",
        status="ANALYZED",
        params_version="t",
        params={},
        price=150.0,
        decisions=[decision("BUY", 6), decision("NO_ORDER", 12)],
        unavailable={},
    )
    session.add(p)
    session.flush()
    buy = tv.routine_chart(session, p.pick_id, 6, now=datetime(2026, 10, 5, tzinfo=UTC))
    skip = tv.routine_chart(session, p.pick_id, 12, now=datetime(2026, 10, 5, tzinfo=UTC))
    assert [lv["kind"] for lv in buy["levels"]] == ["entry", "target", "stop"] and buy["levels"][1][
        "price"
    ] == 165.0
    assert buy["markers"][0]["kind"] == "entry" and skip["markers"][0]["kind"] == "skip"
    assert (
        len(buy["sma200"]) > 0 and buy["bars"][0]["date"] >= "2026-03-01"
    )  # ~200 days of context before the decision
    assert buy["outcome"]["state"] == "NOT_EVALUATED_YET" and any(
        "Entrada planteada 150.00" in x for x in buy["explanation"]
    )
    refs = {r["ref"] for r in tv.list_trades(session, days=3650)}
    assert f"R~{p.pick_id}~6" in refs and f"R~{p.pick_id}~12" in refs
