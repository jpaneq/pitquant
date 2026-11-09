"""Company factsheet from SEC filings + an «expensive / cheap» indicator (ADR-0067).

Everything comes from the existing engines (``fundamental_v1`` / ``valuation_v1``): TTM flows,
margins, growth, balance and capital allocation as known NOW, a quarterly history over ten
years (each point uses only filings accepted before it) and a monthly valuation history.

**Cheapness indicator.** Four *yields* (what the company earns, sells or generates per unit of
price; higher = cheaper): earnings/price, free cash flow/price, sales/price and operating
income/enterprise value. Each is placed against
  * its OWN monthly history (last 10 years, ≥ 24 points): percentile of today's yield, and
  * the OTHER companies of the universe today (non-financial): percentile among peers.
Score 0–100 = mean of the available percentiles (100 = cheapest). Bands: ≥ 80 very cheap,
60–80 cheap, 40–60 fair, 20–40 expensive, < 20 very expensive.

Descriptive, not predictive: being cheap is not a forecast (the v3 exam, ADR-0066, found
valuation adds almost nothing at one month). Banks/insurers: not applicable (other metrics).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.analyzer import fundamental_v1 as FV
from pitquant.analyzer import valuation_v1 as VV
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.db.models import Security, SecurityProfile
from pitquant.features.v0 import fundamentals as F

FACTSHEET_VERSION = "factsheet-v1"
HISTORY_YEARS = 10
MIN_OWN_POINTS = 24
YIELDS: dict[str, tuple[str, Callable[[dict[str, Any]], float | None]]] = {
    "earnings_yield": ("Beneficio / precio", lambda p: p.get("earnings_yield")),
    "fcf_yield": ("Caja libre / precio", lambda p: p.get("fcf_yield")),
    "sales_yield": (
        "Ventas / precio",
        lambda p: 1 / p["price_to_sales"] if p.get("price_to_sales") else None,
    ),
    "ebit_ev": (
        "Beneficio operativo / valor de empresa",
        lambda p: (
            1 / p["ev_to_operating_income"]
            if p.get("ev_to_operating_income") and p["ev_to_operating_income"] > 0
            else None
        ),
    ),
}
VALUATION_KEYS = (
    "market_cap",
    "pe",
    "price_to_sales",
    "price_to_book",
    "ev",
    "ev_to_operating_income",
    *YIELDS,
)
BANDS = ((80, "MUY_BARATA"), (60, "BARATA"), (40, "PRECIO_NORMAL"), (20, "CARA"), (0, "MUY_CARA"))


@dataclass
class Context:
    ticker: str
    sid: str
    sec: Security
    bundle: Any
    market: Any
    facts: list[F.Fact]
    sic: str | None
    sic_description: str | None
    name: str


def context(s: Session, ticker: str, now: datetime) -> Context | None:
    from pitquant.features.v0.engine import load_facts
    from pitquant.positions.universe_ingest import find_security
    from pitquant.research.dataset_v1 import _bundle, _profile_sic

    sid = find_security(s, ticker)
    if sid is None:
        return None
    sec = s.get_one(Security, sid)
    got = _bundle(s, sid, ticker, sec.exchange, now)
    if got is None:
        return None
    sic, desc = _profile_sic(s, sec)
    profile = s.scalars(
        select(SecurityProfile).where(SecurityProfile.current_ticker == ticker)
    ).first()
    return Context(
        ticker, sid, sec, got[0], got[1], load_facts(s, sid, now), sic, desc,
        profile.display_name if profile else ticker,
    )  # fmt: skip


def _price_at(ctx: Context, decision_at: datetime) -> tuple[int, date] | None:
    from pitquant.research import targets_v1 as TG

    pos = TG._pos_at(ctx.bundle, decision_at)
    return None if pos is None else (pos, ctx.bundle.index[pos])


def _valuation(ctx: Context, decision_at: datetime) -> dict[str, Any] | None:
    at = _price_at(ctx, decision_at)
    if at is None:
        return None
    pos, day = at
    vis = F.visible(ctx.facts, decision_at)
    if not vis:
        return None
    acts = [a for a in ctx.market.actions if a.available_at <= decision_at]
    point = VV.valuation_point(vis, float(ctx.market.bars["close"].iloc[pos]), day, acts)
    return {**point, "date": str(day), **{k: f(point) for k, (_, f) in YIELDS.items()}}


def _fundamentals(ctx: Context, s: Session, decision_at: datetime) -> dict[str, Any] | None:
    at = _price_at(ctx, decision_at)
    if at is None or not F.visible(ctx.facts, decision_at):
        return None
    pos, _ = at
    acts = [a for a in ctx.market.actions if a.available_at <= decision_at]
    tree: dict[str, Any] = FV.compute_fundamentals(
        s, ctx.sid, decision_at, actions=acts,
        last_adj_price=float(ctx.bundle.adj["close"].iloc[pos]),
        last_raw_price=float(ctx.market.bars["close"].iloc[pos]), facts=ctx.facts,
    )  # fmt: skip
    return tree


def _v(tree: dict[str, Any], path: str) -> float | None:
    cur: Any = tree
    for part in path.split("."):
        cur = cur.get(part) if isinstance(cur, dict) else None
    value = cur.get("value") if isinstance(cur, dict) else None
    return float(value) if isinstance(value, (int, float)) and np.isfinite(value) else None


QUARTERLY = {
    "revenue": "ttm.revenue",
    "net_income": "ttm.net_income",
    "operating_income": "ttm.operating_income",
    "fcf": "ttm.fcf",
    "operating_margin": "profitability.operating_margin",
    "net_margin": "profitability.net_margin",
    "debt_to_assets": "balance.debt_to_assets",
    "net_debt": "balance.net_debt",
    "shares": "capital_allocation.shares_outstanding",
}


def quarterly_history(ctx: Context, s: Session, now: datetime) -> list[dict[str, Any]]:
    """One point per new reported period (checked at the first session of each quarter)."""
    cal = get_calendar(ctx.sec.exchange)
    start = date(now.year - HISTORY_YEARS, 1, 1)
    out: list[dict[str, Any]] = []
    for d in cal.first_sessions_of_months(max(start, cal.first_session), now.date()):
        if d.month not in (2, 5, 8, 11):  # ~1 month after quarter ends: the 10-Q is out
            continue
        tree = _fundamentals(ctx, s, cal.session_open(d))
        if tree is None or tree.get("latest_period") is None:
            continue
        if out and out[-1]["period"] == str(tree["latest_period"]):
            continue
        out.append(
            {"period": str(tree["latest_period"]), **{k: _v(tree, p) for k, p in QUARTERLY.items()}}
        )
    return out


def valuation_history(ctx: Context, now: datetime) -> list[dict[str, Any]]:
    cal = get_calendar(ctx.sec.exchange)
    start = date(now.year - HISTORY_YEARS, now.month, 1)
    out = []
    for d in cal.first_sessions_of_months(max(start, cal.first_session), now.date()):
        point = _valuation(ctx, cal.session_open(d))
        if point is not None:
            out.append({k: point.get(k) for k in ("date", "pe", *YIELDS)})
    return out


_PEERS: dict[str, dict[str, dict[str, float | None]]] = {}


def peer_yields(
    s: Session, now: datetime, tickers: list[str]
) -> dict[str, dict[str, float | None]]:
    """Today's yields of every non-financial company of the universe (cached per day)."""
    from pitquant.research import fundamentals_v1 as FU

    key = f"{now.date()}:{','.join(sorted(tickers))}"
    if key in _PEERS:
        return _PEERS[key]
    out: dict[str, dict[str, float | None]] = {}
    for t in tickers:
        ctx = context(s, t, now)
        if ctx is None or FU.sector_status(ctx.sic):
            continue
        point = _valuation(ctx, now)
        if point is not None:
            out[t] = {k: point.get(k) for k in YIELDS}
    _PEERS.clear()
    _PEERS[key] = out
    return out


def _band(score: float) -> str:
    return next(label for floor, label in BANDS if score >= floor)


def cheapness(
    current: dict[str, Any],
    own: list[dict[str, Any]],
    peers: dict[str, dict[str, float | None]],
    ticker: str,
) -> dict[str, Any]:
    components = []
    for key, (label, _) in YIELDS.items():
        value = current.get(key)
        hist = [float(p[key]) for p in own[-HISTORY_YEARS * 12 :] if p.get(key) is not None]
        others = [
            float(x) for t, v in peers.items() if t != ticker and (x := v.get(key)) is not None
        ]
        own_pct = (
            VV.percentile_of(hist, value)
            if value is not None and len(hist) >= MIN_OWN_POINTS
            else None
        )
        peer_pct = (
            VV.percentile_of(others, value) if value is not None and len(others) >= 10 else None
        )
        components.append(
            {
                "metric": key, "label": label, "value": value,
                "own_median": float(np.median(hist)) if hist else None,
                "peer_median": float(np.median(others)) if others else None,
                "own_pct": own_pct, "peer_pct": peer_pct,
            }
        )  # fmt: skip
    own_vals = [float(c["own_pct"]) for c in components if c["own_pct"] is not None]
    peer_vals = [float(c["peer_pct"]) for c in components if c["peer_pct"] is not None]
    own_score = float(np.mean(own_vals)) if own_vals else None
    peer_score = float(np.mean(peer_vals)) if peer_vals else None
    parts = [x for x in (own_score, peer_score) if x is not None]
    score = float(np.mean(parts)) if parts else None
    return {
        "score": score,
        "label": _band(score) if score is not None else "SIN_DATOS",
        "vs_own_history": own_score,
        "vs_peers": peer_score,
        "peers_n": len(peers) - (1 if ticker in peers else 0),
        "components": components,
        "note": "Descriptivo, no predictivo: barata no significa que vaya a subir.",
    }


def factsheet(s: Session, ticker: str, now: datetime, universe: list[str]) -> dict[str, Any]:
    from pitquant.research import fundamentals_v1 as FU

    ticker = ticker.upper()
    ctx = context(s, ticker, now)
    if ctx is None:
        raise ValueError("UNKNOWN_TICKER")
    tree = _fundamentals(ctx, s, now) or {}
    current = _valuation(ctx, now) or {}
    unsupported = FU.sector_status(ctx.sic)
    own = valuation_history(ctx, now)
    sections = {
        group: {k: _v(tree, f"{group}.{k}") for k in (tree.get(group) or {}) if k != "note"}
        for group in ("ttm", "profitability", "growth", "balance", "capital_allocation")
    }
    return {
        "version": FACTSHEET_VERSION,
        "ticker": ticker,
        "name": ctx.name,
        "sector": ctx.sic_description,
        "sector_supported": unsupported is None,
        "currency": ctx.sec.currency,
        "price": float(ctx.market.bars["close"].iloc[-1]),
        "price_date": str(ctx.bundle.index[-1]),
        "latest_period": tree.get("latest_period") and str(tree["latest_period"]),
        "latest_filing_at": tree.get("latest_filing_available_at")
        and str(tree["latest_filing_available_at"]),
        "status": tree.get("status"),
        **sections,
        "valuation": {k: current.get(k) for k in VALUATION_KEYS},
        "history": quarterly_history(ctx, s, now),
        "valuation_history": own,
        "cheapness": {"label": "NO_APLICABLE", "reason": unsupported, "components": []}
        if unsupported
        else cheapness(current, own, peer_yields(s, now, universe), ticker),
        "source": "SEC EDGAR (10-K/10-Q), cada dato desde su fecha de presentación",
    }  # fmt: skip
