# ruff: noqa: E501
"""Continuous fundamental + valuation features for the research dataset (ADR-0048). Raw numbers from the SAME engine the Analyzer uses (``fundamental_v1`` / ``valuation_v1``), never a label.

* Facts are loaded once per security; ``F.visible`` cuts every decision at ``available_at < decision_at`` (the filing's acceptance instant, not the period end).
* Each feature carries its component, its own ``available_at`` and a ``missing_reason``; an unsupported sector (banks, insurers, REITs, ...) is ``UNSUPPORTED_SECTOR``, a tag the engine cannot read ``MAPPING_GAP``,
  a company with no filings ``NOT_REGISTERED``, a window too short ``INSUFFICIENT_HISTORY``. Missing is never 0.
* Own-history percentiles use only valuation points of EARLIER decision dates (up to 60 months, at least 24). Sector / country / region metadata is CURRENT descriptive classification (``CURRENT_PROFILE_NOT_PIT``)
  used only to stratify the analysis; it is not a predictor.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

import numpy as np

from pitquant.analyzer import fundamental_v1 as FV
from pitquant.analyzer import valuation_v1 as VV
from pitquant.features.v0 import fundamentals as F

FUNDAMENTAL_SET_VERSION = "research-fundamentals-v1"
HISTORY_MONTHS, MIN_HISTORY = 60, 24

COMPONENTS: dict[str, tuple[tuple[str, str], ...]] = {  # component -> (feature name, path in the analyzer output "group.key")
    "profitability": tuple((f"fund_{k}", f"profitability.{k}") for k in ("gross_profitability", "operating_margin", "net_margin", "gross_margin", "roa", "roe")),
    "cash_flow": (("fund_fcf_margin", "profitability.fcf_margin"), ("fund_cfo_to_net_income", "quality.cfo_to_net_income"), ("fund_accruals_to_assets", "quality.accruals_to_assets")),
    "growth": tuple((f"fund_{k}", f"growth.{k}") for k in ("revenue_yoy", "operating_income_yoy", "net_income_yoy", "fcf_yoy")),
    "leverage": tuple((f"fund_{k}", f"balance.{k}") for k in ("debt_to_assets", "debt_to_equity", "cash_to_assets", "current_ratio", "interest_coverage")),
    "capital_allocation": tuple((f"fund_{k}", f"capital_allocation.{k}") for k in ("dividend_yield", "buyback_yield", "shareholder_yield", "net_equity_issuance", "dividends_to_fcf")) + tuple((f"fund_{k}", f"investment.{k}") for k in ("capex_to_assets", "capex_growth_yoy")),
}  # fmt: skip
VALUATION_KEYS = (
    "pe",
    "earnings_yield",
    "price_to_sales",
    "price_to_book",
    "fcf_yield",
    "ev_to_sales",
    "ev_to_operating_income",
)
PERCENTILE_KEYS = ("pe", "price_to_sales", "price_to_book", "fcf_yield")
COMPONENTS["valuation"] = tuple((f"val_{k}", f"valuation.{k}") for k in VALUATION_KEYS) + tuple(
    (f"val_{k}_own_pct", f"valuation_pct.{k}") for k in PERCENTILE_KEYS
)
FEATURE_COMPONENT = {n: c for c, items in COMPONENTS.items() for n, _ in items}
FEATURE_NAMES = tuple(FEATURE_COMPONENT)

UNSUPPORTED_SIC_DIVISIONS = {
    "60",
    "61",
    "62",
    "63",
    "64",
    "65",
    "67",
}  # banks, credit, brokers, insurance, real estate, holding/other investment: the engine's ratios do not apply
SIC_DIVISIONS = (("01", "09", "Agriculture"), ("10", "14", "Mining"), ("15", "17", "Construction"), ("20", "39", "Manufacturing"), ("40", "49", "Transport, Comms, Utilities"), ("50", "51", "Wholesale"), ("52", "59", "Retail"), ("60", "67", "Finance, Insurance, RE"), ("70", "89", "Services"))  # fmt: skip


def sic_group(sic: str | None) -> str | None:
    if not sic or len(sic) < 2:
        return None
    for lo, hi, name in SIC_DIVISIONS:
        if lo <= sic[:2] <= hi:
            return name
    return None


def sector_status(sic: str | None) -> str | None:
    """None = supported; otherwise the reason the fundamental engine does not apply."""
    return "UNSUPPORTED_SECTOR" if sic and sic[:2] in UNSUPPORTED_SIC_DIVISIONS else None


def _get(tree: dict[str, Any], path: str) -> dict[str, Any]:
    cur: Any = tree
    for part in path.split("."):
        cur = cur.get(part) if isinstance(cur, dict) else None
    return cur if isinstance(cur, dict) else {"value": None, "reason": "missing_fundamental"}


class ValuationHistory:
    """Valuation multiples of one security at every earlier decision date, for own-history percentiles. Add ONE point per decision, AFTER reading the percentile of that decision."""

    def __init__(self) -> None:
        self.pts: dict[str, list[float]] = {k: [] for k in PERCENTILE_KEYS}

    def percentile(self, key: str, cur: float | None) -> tuple[float | None, str | None]:
        h = self.pts[key]
        if cur is None:
            return None, "METRIC_NOT_MEANINGFUL"
        if len(h) < MIN_HISTORY:
            return None, "INSUFFICIENT_HISTORY"
        return VV.percentile_of(h[-HISTORY_MONTHS:], cur), None

    def add(self, point: dict[str, Any]) -> None:
        for k in PERCENTILE_KEYS:
            v = point.get(k)
            if isinstance(v, float) and np.isfinite(v):
                self.pts[k].append(v)


def fundamental_features(
    session: Any,
    price_sid: str,
    facts: Sequence[F.Fact],
    decision_at: datetime,
    *,
    sic: str | None,
    last_session: Any,
    raw_close: float,
    actions: Sequence[Any],
    adj_close: float | None,
    history: ValuationHistory,
    registered: bool,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """(features, meta). ``last_session``/``raw_close`` = the last bar known at ``decision_at``. Mutates ``history`` AFTER reading it."""
    sup = sector_status(sic)
    feats: dict[str, dict[str, Any]] = {}

    def put(name: str, value: Any, avail: str | None, reason: str | None) -> None:
        v = value if isinstance(value, float) and np.isfinite(value) else None
        feats[name] = {
            "value": v,
            "available_at": avail,
            "source": "SEC_FACTS",
            "missing_reason": None if v is not None else (reason or "UNAVAILABLE"),
            "component": FEATURE_COMPONENT[name],
        }

    def all_missing(reason: str) -> None:
        for n in FEATURE_NAMES:
            put(n, None, None, reason)

    if not registered:
        all_missing("NOT_REGISTERED")
        return feats, {"fundamental_status": "NOT_REGISTERED"}
    if sup:
        all_missing(sup)
        return feats, {"fundamental_status": sup, "sic": sic}
    vis = F.visible(facts, decision_at)
    if not vis:
        all_missing("INSUFFICIENT_HISTORY")
        return feats, {"fundamental_status": "INSUFFICIENT_HISTORY"}
    fa = FV.compute_fundamentals(
        session,
        price_sid,
        decision_at,
        actions=actions,
        last_adj_price=adj_close,
        last_raw_price=raw_close,
        facts=facts,
    )
    point = VV.valuation_point(vis, raw_close, last_session, actions)
    val_tree = {k: {"value": point.get(k), "reason": point.get("reason")} for k in VALUATION_KEYS}
    pct_tree: dict[str, Any] = {}
    for k in PERCENTILE_KEYS:
        cur = point.get(k)
        p, why = history.percentile(k, float(cur) if isinstance(cur, float) else None)
        pct_tree[k] = {"value": p, "reason": why}
    tree = {**fa, "valuation": val_tree, "valuation_pct": pct_tree}
    fallback = fa.get("latest_filing_available_at")
    for items in COMPONENTS.values():
        for name, path in items:
            m = _get(tree, path)
            reason = m.get("reason")
            reason = (
                "MAPPING_GAP"
                if reason in ("missing_fundamental", "conflicting_tags")
                else (
                    "INSUFFICIENT_HISTORY"
                    if reason in ("insufficient_history", "stale_data")
                    else reason
                )
            )
            put(name, m.get("value"), m.get("available_at") or fallback, reason)
    history.add(point)
    meta = {
        "fundamental_status": fa.get("status"),
        "latest_period": fa.get("latest_period"),
        "coverage": fa.get("coverage"),
        "fundamental_engine_version": FV.FUNDAMENTAL_ENGINE_VERSION,
        "tag_map_version": FV.TAG_MAP_VERSION_V1,
    }
    return feats, meta


KEY_METRICS = (
    "fund_net_margin",
    "fund_fcf_margin",
    "fund_revenue_yoy",
    "fund_debt_to_assets",
    "val_pe",
)


def coverage_row(
    session: Any,
    price_sid: str,
    ticker: str,
    facts: Sequence[F.Fact],
    now: datetime,
    sic: str | None,
    last_session: Any,
    raw_close: float,
    actions: Sequence[Any],
) -> dict[str, Any]:
    """One line of the SEC coverage table as of ``now``: READY / PARTIAL / UNSUPPORTED_SECTOR / MAPPING_GAP / NOT_REGISTERED / INSUFFICIENT_HISTORY, with the missing metrics."""
    base: dict[str, Any] = {"ticker": ticker, "sic": sic, "sector_group": sic_group(sic)}
    if not facts:
        return {
            **base,
            "status": "NOT_REGISTERED",
            "missing": [],
            "coverage": None,
            "first_filing": None,
        }
    first = min(f.available_at for f in facts)
    if sector_status(sic):
        return {
            **base,
            "status": "UNSUPPORTED_SECTOR",
            "missing": [],
            "coverage": None,
            "first_filing": first.date().isoformat(),
        }
    feats, meta = fundamental_features(
        session,
        price_sid,
        facts,
        now,
        sic=sic,
        last_session=last_session,
        raw_close=raw_close,
        actions=actions,
        adj_close=None,
        history=ValuationHistory(),
        registered=True,
    )
    missing = [
        n
        for n, f in feats.items()
        if f["value"] is None and f["missing_reason"] in ("MAPPING_GAP", "UNAVAILABLE")
    ]
    cov = meta.get("coverage") or {}
    ratio = (cov.get("available", 0) / cov["expected"]) if cov.get("expected") else 0.0
    years = (now - first).days / 365.25
    key_missing = [k for k in KEY_METRICS if feats[k]["value"] is None and k != "val_pe"]
    if years < 3:
        status = "INSUFFICIENT_HISTORY"
    elif ratio >= 0.8 and not key_missing:
        status = "READY"
    elif ratio >= 0.5:
        status = "PARTIAL"
    else:
        status = "MAPPING_GAP"
    return {
        **base,
        "status": status,
        "missing": sorted(n for n in missing if n.startswith("fund_")),
        "coverage": round(ratio, 3),
        "first_filing": first.date().isoformat(),
        "latest_period": meta.get("latest_period"),
    }
