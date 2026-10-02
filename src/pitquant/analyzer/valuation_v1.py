# ruff: noqa: E501
"""ValuationEngine V1 on top of the shared fundamental/market layers (``decision_at`` mandatory).

market_cap = last RAW close * latest valid cover-page shares ALIGNED to splits after the cover date.
PE and P/B are NULL for non-positive earnings / equity; FCF yield may be negative (never truncated).
EV = market cap + total debt - cash only when all three components resolve (no EBITDA).
Own-history context re-computes each historical point with ONLY the facts and prices known at that
date (monthly, up to 5 years): no future shares or fundamentals.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np

from pitquant.analyzer.fundamental_v1 import _flow, _inst
from pitquant.analyzer.market import MarketData
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.features.v0 import fundamentals as F
from pitquant.features.v0.engine import MAX_SHARES_AGE_DAYS
from pitquant.features.v0.engine import _debt as total_debt

VALUATION_ENGINE_VERSION = "valuation-v1.0"
METRICS = ("pe", "price_to_sales", "price_to_book", "fcf_yield")


def valuation_point(
    vis: Sequence[F.Fact], raw_price: float, price_date: date, actions: Sequence[Any]
) -> dict[str, float | str | None]:
    """All valuation multiples at ``price_date`` from the visible facts. Values are raw numbers or None."""
    shares = F.shares_outstanding(vis)
    out: dict[str, float | str | None] = dict.fromkeys(
        (
            "market_cap",
            "earnings_yield",
            "pe",
            "price_to_sales",
            "price_to_book",
            "fcf_yield",
            "ev",
            "ev_to_sales",
            "ev_to_operating_income",
        )
    )
    if shares.value is None:
        out["reason"] = shares.reason or "missing_fundamental"
        return out
    end = date.fromisoformat(str(shares.provenance[0]["period"]).split("..")[-1])
    if (price_date - end).days > MAX_SHARES_AGE_DAYS:
        out["reason"] = "stale_data"
        return out
    sh = shares.value * F.split_factor_between(actions, end, price_date)
    mc = raw_price * sh
    out["market_cap"] = mc
    ni, rev, equity = _flow(vis, "net_income"), _flow(vis, "revenue"), _inst(vis, "equity")
    cfo, cap = _flow(vis, "cfo"), _flow(vis, "capex")
    fcf = (
        F.linear(cfo, cap, -1, "fcf")
        if cap.value is not None and cap.value >= 0
        else F.Metric.missing("sign_unexpected")
    )
    if ni.value is not None:
        out["earnings_yield"] = ni.value / mc
        out["pe"] = mc / ni.value if ni.value > 0 else None
    if rev.value is not None and rev.value > 0:
        out["price_to_sales"] = mc / rev.value
    if equity.value is not None and equity.value > 0:
        out["price_to_book"] = mc / equity.value
    if fcf.value is not None:
        out["fcf_yield"] = fcf.value / mc
    debt, cash = total_debt(list(vis)), F.latest_instant(vis, "cash")
    if debt.value is not None and cash.value is not None:
        ev = mc + debt.value - cash.value
        out["ev"] = ev
        if rev.value and rev.value > 0:
            out["ev_to_sales"] = ev / rev.value
        oi = _flow(vis, "operating_income")
        if oi.value is not None and oi.value > 0:
            out["ev_to_operating_income"] = ev / oi.value
    return out


def percentile_of(history: list[float], current: float, higher_is_cheaper: bool = False) -> float:
    """Share of historical values <= current, in [0, 100]."""
    h = np.asarray(history, dtype=float)
    return float(100.0 * (h <= current).sum() / len(h))


def compute_valuation(
    md: MarketData,
    facts: Sequence[F.Fact],
    decision_at: datetime,
    years: int = 5,
    min_points: int = 24,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "as_of": decision_at.isoformat(),
        "engine_version": VALUATION_ENGINE_VERSION,
        "warnings": [],
    }
    if md.series.n_bars == 0:
        out.update(status="NO_DATA", warnings=["no price"])
        return out
    last = md.series.last_session
    assert last is not None
    raw_close = float(md.bars["close"].iloc[-1])
    vis = F.visible(facts, decision_at)
    now = valuation_point(vis, raw_close, last, md.actions)
    out["price"] = raw_close
    out["price_date"] = str(last)
    out["currency"] = "USD"
    sh = F.shares_outstanding(vis)
    out["shares"] = sh.value
    out["current"] = {k: v for k, v in now.items() if k != "reason"}
    out["market_cap"] = now.get("market_cap")
    if "reason" in now:
        out["warnings"].append(f"valuation unavailable: {now['reason']}")
    out["status"] = "OK" if now.get("market_cap") else "NO_DATA"
    # own history: monthly sessions over the last ``years`` years, facts and prices known at each date
    cal = get_calendar(md.exchange)
    start = max(last - timedelta(days=365 * years), md.bars.index[0])
    pts: dict[str, list[float]] = {m: [] for m in METRICS}
    n = 0
    for d in cal.first_sessions_of_months(start, last):
        if d >= last:
            continue
        prev = cal.previous_session(d)
        if prev not in md.bars.index:
            continue
        dt_ = cal.session_close(prev)
        vp = F.visible([f for f in facts if f.available_at <= dt_], dt_)
        acts = [a for a in md.actions if a.available_at <= dt_]
        v = valuation_point(vp, float(md.bars.loc[prev, "close"]), prev, acts)
        if v.get("market_cap"):
            n += 1
            for m in METRICS:
                if isinstance(v.get(m), float):
                    pts[m].append(float(v[m]))  # type: ignore[arg-type]
    own: dict[str, Any] = {}
    for m in METRICS:
        cur = now.get(m)
        if isinstance(cur, float) and len(pts[m]) >= min_points:
            own[m] = {
                "percentile": round(percentile_of(pts[m], cur), 1),
                "median": float(np.median(pts[m])),
                "p10": float(np.percentile(pts[m], 10)),
                "p90": float(np.percentile(pts[m], 90)),
                "window_years": years,
                "sample_count": len(pts[m]),
            }
        else:
            own[m] = {
                "percentile": None,
                "reason": "insufficient_history"
                if isinstance(cur, float)
                else "metric_not_meaningful_now",
                "sample_count": len(pts[m]),
            }
    out["own_history"] = own
    out["own_history_points"] = n
    out["peer_context"] = {
        "reference_type": None,
        "sample_count": 0,
        "percentile": None,
        "reason": "PEER COMPARISON NOT AVAILABLE: no current peer universe with fundamentals ingested",
    }
    # three separated readings (ADR-0030): each states what it is and what it is NOT
    out["absolute"] = {
        "kind": "ABSOLUTE",
        "status": "OK" if out["status"] == "OK" else "NO_DATA",
        "metrics": out["current"],
        "note": "levels from price and PIT fundamentals; no judgement of cheap/expensive",
    }
    out["own_history_view"] = {
        "kind": "OWN_HISTORY",
        "status": "OK"
        if any(v.get("percentile") is not None for v in own.values())
        else "INSUFFICIENT_HISTORY",
        "metrics": own,
    }
    out["peer_relative"] = {
        "kind": "PEER_RELATIVE",
        "status": "NOT_AVAILABLE",
        "reason": out["peer_context"]["reason"],
        "metrics": {},
    }
    return out
