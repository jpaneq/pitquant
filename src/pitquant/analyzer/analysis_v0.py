# ruff: noqa: E501
"""AnalysisEngine V0: deterministic, explainable structured analysis. It is NOT a validated predictor.

Labels are rule-based (``ABSOLUTE_RULE_V0`` unless an own-history reference exists) and carry the coverage
they were computed from; a category with poor coverage is ``Insufficient``, never ``Strong``. Missing is
never imputed to 50. Positives/risks are generated from structured rules with a reason code, metric, value
and reference; nothing is generated text. No overall BUY score exists.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

ANALYSIS_SCORE_VERSION = "analysis-v0.1"
MIN_COVERAGE = 0.6


def _v(d: dict[str, Any], *path: str) -> float | None:
    cur: Any = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    if isinstance(cur, dict):
        cur = cur.get("value")
    return cur if isinstance(cur, (int, float)) else None


def _label(
    passes: int, avail: int, expected: int, strong: int, moderate: int, labels: tuple[str, str, str]
) -> dict[str, Any]:
    cov = avail / expected if expected else 0.0
    if avail == 0 or cov < MIN_COVERAGE or avail < 2:
        return {
            "label": "Insufficient",
            "coverage": f"{avail}/{expected}",
            "reference_type": "ABSOLUTE_RULE_V0",
        }
    lab = labels[0] if passes >= strong else labels[1] if passes >= moderate else labels[2]
    return {
        "label": lab,
        "coverage": f"{avail}/{expected}",
        "passes": passes,
        "reference_type": "ABSOLUTE_RULE_V0",
    }


def fundamentals_label(f: dict[str, Any]) -> dict[str, Any]:
    checks: list[tuple[str, float | None, Callable[[float], bool]]] = [
        ("operating_margin > 10%", _v(f, "profitability", "operating_margin"), lambda x: x > 0.10),
        ("FCF margin > 5%", _v(f, "profitability", "fcf_margin"), lambda x: x > 0.05),
        ("ROA > 5%", _v(f, "profitability", "roa"), lambda x: x > 0.05),
        ("CFO / net income >= 0.8", _v(f, "quality", "cfo_to_net_income"), lambda x: x >= 0.8),
        ("net margin > 0", _v(f, "profitability", "net_margin"), lambda x: x > 0),
    ]
    avail = [(n, v, fn(v)) for n, v, fn in checks if v is not None]
    return _label(
        sum(1 for _, _, ok in avail if ok),
        len(avail),
        len(checks),
        4,
        2,
        ("Strong", "Moderate", "Weak"),
    )


def growth_label(f: dict[str, Any]) -> dict[str, Any]:
    keys = [
        ("growth", "revenue_yoy"),
        ("growth", "operating_income_yoy"),
        ("growth", "fcf_yoy"),
        ("growth", "revenue_cagr3"),
        ("growth", "operating_income_cagr3"),
    ]
    vals = [_v(f, *k) for k in keys]
    av = [x for x in vals if x is not None]
    return _label(
        sum(1 for x in av if x > 0.05), len(av), len(keys), 4, 2, ("Strong", "Moderate", "Weak")
    )


def valuation_label(v: dict[str, Any]) -> dict[str, Any]:
    own = v.get("own_history") or {}
    pcts = [
        own[m]["percentile"]
        for m in ("pe", "price_to_sales")
        if own.get(m, {}).get("percentile") is not None
    ]
    fy = own.get("fcf_yield", {}).get("percentile")
    if fy is not None:
        pcts.append(100.0 - fy)  # a HIGH FCF yield is cheap: invert
    if not pcts:
        return {"label": "Insufficient", "coverage": "0/3", "reference_type": "OWN_HISTORY_5Y"}
    avg = sum(pcts) / len(pcts)
    lab = "Cheap" if avg <= 30 else "Expensive" if avg >= 70 else "Fair"
    return {
        "label": lab,
        "coverage": f"{len(pcts)}/3",
        "reference_type": "OWN_HISTORY_5Y",
        "percentile_mean": round(avg, 1),
        "note": "relative to the company's own 5-year history, not to peers",
    }


def trend_label(t: dict[str, Any]) -> dict[str, Any]:
    st = (t.get("trend") or {}).get("state")
    return {
        "label": {
            "STRONG_UPTREND": "Strong uptrend",
            "UPTREND": "Uptrend",
            "NEUTRAL": "Neutral",
            "DOWNTREND": "Downtrend",
            "STRONG_DOWNTREND": "Strong downtrend",
        }.get(st or "", "Insufficient"),
        "state": st,
    }


def momentum_label(t: dict[str, Any]) -> dict[str, Any]:
    m = t.get("momentum") or {}
    r126, r252, mom = m.get("ret126"), m.get("mom_12m"), m.get("mom_12_1")
    vals = [x for x in (m.get("ret63"), r126, mom) if x is not None]
    if len(vals) < 2:
        return {"label": "Insufficient"}
    pos = sum(1 for x in vals if x > 0.05)
    neg = sum(1 for x in vals if x < -0.05)
    lab = (
        "Strong"
        if pos == len(vals)
        else "Positive"
        if pos > neg
        else "Negative"
        if neg > pos
        else "Mixed"
    )
    return {"label": lab, "pos": pos, "neg": neg, "n": len(vals), "ret252": r252}


def relative_strength_label(t: dict[str, Any]) -> dict[str, Any]:
    rs = t.get("relative_strength") or {}
    vals: list[float] = [float(rs[k]) for k in ("63", "126", "252") if rs.get(k) is not None]
    if len(vals) < 2:
        return {"label": "Insufficient", "benchmark": rs.get("benchmark")}
    pos = sum(1 for x in vals if x > 0)
    return {
        "label": "Outperforming"
        if pos == len(vals)
        else "Underperforming"
        if pos == 0
        else "Mixed",
        "benchmark": rs.get("benchmark"),
        "benchmark_type": rs.get("benchmark_type"),
    }


def risk_label(t: dict[str, Any]) -> dict[str, Any]:
    r = t.get("risk") or {}
    vol, mdd = r.get("vol63"), r.get("max_drawdown252")
    if vol is None:
        return {"label": "Insufficient"}
    score = (0 if vol < 0.22 else 1 if vol < 0.38 else 2) + (
        0 if mdd is None or mdd > -0.15 else 1 if mdd > -0.30 else 2
    )
    return {
        "label": "Low" if score <= 1 else "Moderate" if score <= 2 else "High",
        "vol63": vol,
        "max_drawdown252": mdd,
        "reference_type": "ABSOLUTE_RULE_V0",
    }


def data_quality(
    tech: dict[str, Any], fund: dict[str, Any], fresh: dict[str, Any]
) -> dict[str, Any]:
    pts, warn = 0, []
    if tech.get("status") == "OK" and (tech.get("n_bars") or 0) >= 252:
        pts += 1
    else:
        warn.append("price history < 252 sessions or missing")
    if fresh.get("status") == "EOD":
        pts += 1
    else:
        warn.append(
            f"price data {fresh.get('status')} ({fresh.get('sessions_behind')} sessions behind)"
        )
    cov = fund.get("coverage") or {}
    if cov.get("expected") and cov["available"] / cov["expected"] >= 0.8:
        pts += 1
    else:
        warn.append("fundamental coverage < 80% or missing")
    return {
        "label": "High"
        if pts == 3
        else "Medium"
        if pts == 2
        else "Low"
        if pts == 1
        else "Insufficient",
        "warnings": warn,
    }


def positives_and_risks(
    f: dict[str, Any], v: dict[str, Any], t: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    pos: list[dict[str, Any]] = []
    neg: list[dict[str, Any]] = []

    def add(
        lst: list[dict[str, Any]], code: str, metric: str, value: float | None, ref: str, text: str
    ) -> None:
        if value is not None:
            lst.append(
                {
                    "reason_code": code,
                    "metric": metric,
                    "value": value,
                    "reference": ref,
                    "rendered_text": text.format(value=value),
                }
            )

    om, fm = _v(f, "profitability", "operating_margin"), _v(f, "profitability", "fcf_margin")
    if om is not None and om > 0.20:
        add(
            pos,
            "HIGH_OPERATING_MARGIN",
            "operating_margin",
            om,
            "> 20%",
            "Operating margin {value:.1%} (> 20%)",
        )
    if fm is not None and fm > 0.15:
        add(
            pos,
            "STRONG_FCF_MARGIN",
            "fcf_margin",
            fm,
            "> 15%",
            "Free-cash-flow margin {value:.1%} (> 15%)",
        )
    rg = _v(f, "growth", "revenue_yoy")
    if rg is not None and rg > 0.10:
        add(
            pos,
            "REVENUE_GROWTH",
            "revenue_yoy",
            rg,
            "> 10%",
            "Revenue growth {value:.1%} year over year",
        )
    ic = _v(f, "balance", "interest_coverage")
    if ic is not None and ic > 10:
        add(
            pos,
            "INTEREST_COVERAGE",
            "interest_coverage",
            ic,
            "> 10x",
            "Interest coverage {value:.1f}x",
        )
    sy = _v(f, "capital_allocation", "shareholder_yield")
    if sy is not None and sy > 0.02:
        add(
            pos,
            "SHAREHOLDER_YIELD",
            "shareholder_yield",
            sy,
            "> 2%",
            "Shareholder yield {value:.1%}",
        )
    tr = (t.get("trend") or {}).get("state")
    if tr in ("UPTREND", "STRONG_UPTREND"):
        add(
            pos,
            "UPTREND",
            "trend_score",
            float((t.get("trend") or {}).get("score", 0)),
            "state",
            "Price trend: " + tr.replace("_", " ").lower(),
        )
    rs = (t.get("relative_strength") or {}).get("252")
    if rs is not None and rs > 0.05:
        add(
            pos,
            "OUTPERFORMING_BENCHMARK",
            "relative_252d",
            rs,
            "> +5% vs benchmark proxy",
            "12-month return {value:+.1%} vs the benchmark proxy",
        )
    own = (v.get("own_history") or {}).get("pe", {}).get("percentile")
    if own is not None and own >= 85:
        add(
            neg,
            "EXPENSIVE_VS_OWN_HISTORY",
            "pe_percentile",
            own,
            ">= 85th",
            "P/E in the {value:.0f}th percentile of its own 5-year history",
        )
    if own is not None and own <= 15:
        add(
            pos,
            "CHEAP_VS_OWN_HISTORY",
            "pe_percentile",
            own,
            "<= 15th",
            "P/E in the {value:.0f}th percentile of its own 5-year history",
        )
    nm = _v(f, "profitability", "net_margin")
    if nm is not None and nm < 0:
        add(neg, "NEGATIVE_EARNINGS", "net_margin", nm, "< 0", "Negative net margin {value:.1%}")
    de = _v(f, "balance", "debt_to_equity")
    if de is not None and de > 2.0:
        add(neg, "HIGH_LEVERAGE", "debt_to_equity", de, "> 2x", "Debt / equity {value:.1f}x")
    cr = _v(f, "balance", "current_ratio")
    if cr is not None and cr < 1.0:
        add(neg, "LOW_CURRENT_RATIO", "current_ratio", cr, "< 1", "Current ratio {value:.2f} (< 1)")
    if tr in ("DOWNTREND", "STRONG_DOWNTREND"):
        add(
            neg,
            "DOWNTREND",
            "trend_score",
            float((t.get("trend") or {}).get("score", 0)),
            "state",
            "Price trend: " + tr.replace("_", " ").lower(),
        )
    mdd = (t.get("risk") or {}).get("max_drawdown252")
    if mdd is not None and mdd < -0.25:
        add(
            neg,
            "DEEP_DRAWDOWN",
            "max_drawdown252",
            mdd,
            "< -25%",
            "Maximum drawdown over 12 months {value:.1%}",
        )
    vol = (t.get("risk") or {}).get("vol63")
    if vol is not None and vol > 0.40:
        add(
            neg,
            "HIGH_VOLATILITY",
            "vol63",
            vol,
            "> 40%",
            "Annualised 3-month volatility {value:.1%}",
        )
    oe = (t.get("overextension") or {}).get("distance_from_sma20_atr")
    if oe is not None and oe > 2.5:
        add(
            neg,
            "EXTENDED_ABOVE_SMA20",
            "distance_from_sma20_atr",
            oe,
            "> 2.5 ATR",
            "Price {value:.1f} ATR above its 20-day average",
        )
    cni = _v(f, "quality", "cfo_to_net_income")
    if cni is not None and cni < 0.6:
        add(
            neg,
            "LOW_CASH_CONVERSION",
            "cfo_to_net_income",
            cni,
            "< 0.6",
            "Operating cash flow is only {value:.2f}x net income",
        )
    return {"positives": pos[:3], "risks": neg[:3]}


def build_analysis(
    tech: dict[str, Any],
    fund: dict[str, Any],
    val: dict[str, Any],
    fresh: dict[str, Any],
    profile_type: str,
) -> dict[str, Any]:
    special = profile_type != "STANDARD_CORPORATE"
    labels = {
        "fundamentals": {
            "label": "Insufficient",
            "note": "SPECIALIZED FUNDAMENTAL PROFILE NOT YET SUPPORTED",
        }
        if special
        else fundamentals_label(fund),
        "growth": {
            "label": "Insufficient",
            "note": "SPECIALIZED FUNDAMENTAL PROFILE NOT YET SUPPORTED",
        }
        if special
        else growth_label(fund),
        "valuation": valuation_label(val),
        "trend": trend_label(tech),
        "momentum": momentum_label(tech),
        "relative_strength": relative_strength_label(tech),
        "risk": risk_label(tech),
        "data_quality": data_quality(tech, fund, fresh),
    }
    pr = positives_and_risks(fund, val, tech) if not special else positives_and_risks({}, val, tech)
    return {
        "engine_version": ANALYSIS_SCORE_VERSION,
        "status": "AVAILABLE",
        "kind": "RULE_BASED / OWN_HISTORY_CONTEXT",
        "not_a_prediction": True,
        "labels": labels,
        **pr,
        "profile_type": profile_type,
        "notes": [
            "Deterministic rules, not a validated predictor. No BUY/HOLD/SELL.",
            "Category labels use absolute V0 rules where no peer universe exists (documented in docs/ANALYSIS_ENGINE_V0.md).",
        ],
    }
