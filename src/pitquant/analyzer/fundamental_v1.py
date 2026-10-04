# ruff: noqa: E501
"""FundamentalEngine V1 (SEC, point-in-time). Builds ONLY on the existing normalized fact layer and the
Feature Engine's periodization (``features.v0.fundamentals``): raw filing facts -> latest KNOWN revision ->
TTM = FY(prev) + YTD(cur) - YTD(prior year). No second fact store, no new ingestion.

Missing stays missing (value None + reason): ``missing_fundamental``, ``insufficient_history``,
``denominator_invalid``, ``NOT_MEANINGFUL`` (sign change / non-positive base for a ratio), ``unresolved_tag``,
``sign_unexpected``. Nothing is imputed.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from pitquant.features.v0 import fundamentals as F
from pitquant.features.v0.engine import _debt as total_debt
from pitquant.features.v0.engine import load_facts

FUNDAMENTAL_ENGINE_VERSION = "fundamental-v1.1"  # v1.1 (ADR-0048): 25-day period tolerance (52/53-week retailers) and an explicit revenue-tag priority; never changes a value v1.0 could compute
TAG_MAP_VERSION_V1 = "sec-tags-3"  # sec-tags-2 + revenue priority on conflicting tags (Revenues > RevenueFromContract… > SalesRevenueNet)
PERIOD_TOL_DAYS = 25  # 12/24/36-week year-to-date periods of 52/53-week fiscal calendars
REVENUE_PRIORITY = (
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
)
EXTRA_TAGS: dict[str, tuple[str, ...]] = {
    "assets_current": ("AssetsCurrent",),
    "liabilities_current": ("LiabilitiesCurrent",),
    "interest_expense": ("InterestExpense", "InterestExpenseDebt"),
    "dividends_paid": ("PaymentsOfDividendsCommonStock", "PaymentsOfDividends"),
    "buybacks": ("PaymentsForRepurchaseOfCommonStock",),
    "issuance": ("ProceedsFromIssuanceOfCommonStock",),
}
MATERIALITY_NI = 1_000_000.0  # |net income| below this (USD) makes CFO/NI meaningless


def _d(m: F.Metric) -> dict[str, Any]:
    out: dict[str, Any] = {"value": m.value}
    if m.value is None:
        out["reason"] = m.reason
    if m.available_at is not None:
        out["available_at"] = m.available_at.isoformat()
    return out


def _flow(vis: Sequence[F.Fact], key: str, end: date | None = None) -> F.Metric:
    tags = EXTRA_TAGS.get(key)
    prefer = REVENUE_PRIORITY if key == "revenue" else None
    return F.resolve_flow_ttm(vis, key, end, tags, tol=PERIOD_TOL_DAYS, prefer=prefer)


def _inst(vis: Sequence[F.Fact], key: str) -> F.Metric:
    tags = EXTRA_TAGS.get(key)
    return F.latest_instant(vis, key, tags=tags) if tags else F.latest_instant(vis, key)


def _end(m: F.Metric) -> date | None:
    if not m.provenance:
        return None
    return max(date.fromisoformat(str(p["period"]).split("..")[-1]) for p in m.provenance)


def _years_before(d: date, n: int) -> date:
    try:
        return d.replace(year=d.year - n)
    except ValueError:
        return d.replace(year=d.year - n, day=28)


def _cagr(now: F.Metric, then: F.Metric, years: int, name: str) -> F.Metric:
    if now.value is None or then.value is None:
        return F.Metric.missing(now.reason or then.reason or "missing_fundamental", name)
    if now.value <= 0 or then.value <= 0:
        return F.Metric.missing(
            "NOT_MEANINGFUL",
            f"{name}: a ratio-based CAGR needs positive start and end values ({then.value} -> {now.value})",
        )
    return F.Metric(
        (now.value / then.value) ** (1.0 / years) - 1.0,
        None,
        max(x for x in (now.available_at, then.available_at) if x),
        now.provenance + then.provenance,
        f"{name}: (end/start)^(1/{years}) - 1",
    )


def _growth(now: F.Metric, then: F.Metric, name: str) -> F.Metric:
    if now.value is None or then.value is None:
        return F.Metric.missing(now.reason or then.reason or "missing_fundamental", name)
    if then.value <= 0:
        return F.Metric.missing("NOT_MEANINGFUL", f"{name}: prior value {then.value} <= 0")
    return F.Metric(
        now.value / then.value - 1.0,
        None,
        max(x for x in (now.available_at, then.available_at) if x),
        now.provenance + then.provenance,
        name,
    )


def _instant_ago(vis: Sequence[F.Fact], key: str, cur: F.Metric, years: int) -> F.Metric:
    end = _end(cur)
    if cur.value is None or end is None:
        return F.Metric.missing("missing_fundamental")
    tags = EXTRA_TAGS.get(key) or F.TAGS[key]
    best = None
    tgt = _years_before(end, years)
    for f in vis:
        if (
            f.concept in tags
            and f.period_start is None
            and f.unit == "USD"
            and abs((f.period_end - tgt).days) <= 25
            and (best is None or abs((f.period_end - tgt).days) < abs((best.period_end - tgt).days))
        ):
            best = f
    if best is None:
        return F.Metric.missing("insufficient_history", f"no {key} near {tgt}")
    return F.Metric(
        best.value,
        None,
        best.available_at,
        [F._prov(best, f"{years}y_ago")],
        f"{key} at {best.period_end}",
    )


def compute_fundamentals(
    session: Session,
    security_id: str,
    decision_at: datetime,
    *,
    actions: Sequence[Any] = (),
    last_adj_price: float | None = None,
    last_raw_price: float | None = None,
    facts: Sequence[F.Fact] | None = None,
) -> dict[str, Any]:
    if (
        facts is None
    ):  # a caller sweeping many dates may pass the full fact list: ``visible`` still cuts at decision_at
        facts = load_facts(session, security_id, decision_at)
    vis = F.visible(facts, decision_at)
    out: dict[str, Any] = {
        "as_of": decision_at.isoformat(),
        "engine_version": FUNDAMENTAL_ENGINE_VERSION,
        "tag_map_version": TAG_MAP_VERSION_V1,
        "warnings": [],
    }
    if not vis:
        out.update(
            status="NO_DATA",
            warnings=["no SEC facts known at decision_at"],
            coverage={"available": 0, "expected": 0},
        )
        return out
    ttm = {
        k: _flow(vis, k)
        for k in ("revenue", "gross_profit", "operating_income", "net_income", "cfo", "capex")
    }
    capex = ttm["capex"]
    if capex.value is not None and capex.value < 0:
        out["warnings"].append(
            "capex TTM is negative (unexpected sign for PaymentsToAcquirePropertyPlantAndEquipment): FCF withheld"
        )
        capex = F.Metric.missing("sign_unexpected", "capex < 0")
        ttm["capex"] = capex
    ttm["fcf"] = F.linear(
        ttm["cfo"], capex, -1, "FCF = CFO - CapEx (CapEx = payments, positive outflow)"
    )
    prior = {
        k: _flow(vis, k, _years_before(_end(ttm[k]) or date.max, 1))
        if ttm[k].value is not None
        else F.Metric.missing("missing_fundamental")
        for k in ("revenue", "operating_income", "net_income", "cfo", "capex", "gross_profit")
    }
    prior["fcf"] = F.linear(prior["cfo"], prior["capex"], -1, "prior FCF")
    prior3 = {
        k: _flow(vis, k, _years_before(_end(ttm[k]) or date.max, 3))
        if ttm[k].value is not None
        else F.Metric.missing("missing_fundamental")
        for k in ("revenue", "operating_income", "cfo", "capex")
    }
    prior3["fcf"] = F.linear(prior3["cfo"], prior3["capex"], -1, "FCF 3y ago")
    prior5 = {
        k: _flow(vis, k, _years_before(_end(ttm[k]) or date.max, 5))
        if ttm[k].value is not None
        else F.Metric.missing("missing_fundamental")
        for k in ("revenue", "operating_income")
    }
    assets, equity, cash = _inst(vis, "assets"), _inst(vis, "equity"), _inst(vis, "cash")
    liab, a_cur, l_cur = (
        _inst(vis, "liabilities"),
        _inst(vis, "assets_current"),
        _inst(vis, "liabilities_current"),
    )
    avg_assets, avg_equity = F.average_instant(vis, "assets"), F.average_instant(vis, "equity")
    debt = total_debt(vis)
    net_debt = (
        F.linear(debt, cash, -1, "net debt = total debt - cash")
        if debt.value is not None and cash.value is not None
        else F.Metric.missing(debt.reason or cash.reason or "missing_fundamental")
    )
    interest = _flow(vis, "interest_expense")
    shares_now = F.shares_outstanding(vis)
    ni = ttm["net_income"]
    latest = max((e for e in (_end(m) for m in ttm.values()) if e), default=None)
    out["latest_period"] = None if latest is None else str(latest)  # never the string "None"
    out["latest_filing_available_at"] = max(
        (m.available_at for m in ttm.values() if m.available_at), default=None
    )
    if out["latest_filing_available_at"]:
        out["latest_filing_available_at"] = out["latest_filing_available_at"].isoformat()
    out["ttm"] = {k: _d(v) for k, v in ttm.items()}
    out["profitability"] = {
        "gross_profitability": _d(
            F.safe_div(
                ttm["gross_profit"],
                avg_assets,
                "gross_profit_ttm / average_assets",
                den_positive=True,
            )
        ),
        "operating_margin": _d(
            F.safe_div(
                ttm["operating_income"], ttm["revenue"], "operating margin", den_positive=True
            )
        ),
        "net_margin": _d(F.safe_div(ni, ttm["revenue"], "net margin", den_positive=True)),
        "fcf_margin": _d(F.safe_div(ttm["fcf"], ttm["revenue"], "fcf margin", den_positive=True)),
        "gross_margin": _d(
            F.safe_div(ttm["gross_profit"], ttm["revenue"], "gross margin", den_positive=True)
        ),
        "roa": _d(F.safe_div(ni, avg_assets, "ROA", den_positive=True)),
        "roe": _d(F.safe_div(ni, avg_equity, "ROE", den_positive=True)),
    }
    cfo_ni = (
        F.safe_div(ttm["cfo"], ni, "cfo / net income", den_positive=True)
        if ni.value is not None and abs(ni.value) > MATERIALITY_NI
        else F.Metric.missing(
            "NOT_MEANINGFUL" if ni.value is not None else (ni.reason or "missing_fundamental"),
            "net income below materiality",
        )
    )
    out["quality"] = {
        "cfo_to_net_income": _d(cfo_ni),
        "accruals_to_assets": _d(
            F.safe_div(
                F.linear(ni, ttm["cfo"], -1, "NI - CFO"),
                avg_assets,
                "accruals / average assets",
                den_positive=True,
            )
        ),
    }
    out["growth"] = {
        "revenue_yoy": _d(_growth(ttm["revenue"], prior["revenue"], "revenue yoy")),
        "operating_income_yoy": _d(
            _growth(ttm["operating_income"], prior["operating_income"], "operating income yoy")
        ),
        "net_income_yoy": _d(_growth(ni, prior["net_income"], "net income yoy")),
        "fcf_yoy": _d(_growth(ttm["fcf"], prior["fcf"], "fcf yoy")),
        "revenue_cagr3": _d(_cagr(ttm["revenue"], prior3["revenue"], 3, "revenue CAGR 3y")),
        "operating_income_cagr3": _d(
            _cagr(
                ttm["operating_income"], prior3["operating_income"], 3, "operating income CAGR 3y"
            )
        ),
        "fcf_cagr3": _d(_cagr(ttm["fcf"], prior3["fcf"], 3, "fcf CAGR 3y")),
        "revenue_cagr5": _d(_cagr(ttm["revenue"], prior5["revenue"], 5, "revenue CAGR 5y")),
        "operating_income_cagr5": _d(
            _cagr(
                ttm["operating_income"], prior5["operating_income"], 5, "operating income CAGR 5y"
            )
        ),
    }
    a1, a3 = _instant_ago(vis, "assets", assets, 1), _instant_ago(vis, "assets", assets, 3)
    out["investment"] = {
        "asset_growth1": _d(_growth(assets, a1, "asset growth 1y")),
        "asset_growth3": _d(_cagr(assets, a3, 3, "asset growth 3y (CAGR)")),
        "capex_to_assets": _d(
            F.safe_div(capex, avg_assets, "capex / average assets", den_positive=True)
        ),
        "capex_growth_yoy": _d(_growth(capex, prior["capex"], "capex yoy")),
    }
    out["balance"] = {
        "cash": _d(cash),
        "total_debt": _d(debt),
        "net_debt": _d(net_debt),
        "debt_to_assets": _d(F.safe_div(debt, assets, "debt / assets", den_positive=True)),
        "debt_to_equity": _d(F.safe_div(debt, equity, "debt / equity", den_positive=True)),
        "cash_to_assets": _d(F.safe_div(cash, assets, "cash / assets", den_positive=True)),
        "current_ratio": _d(
            F.safe_div(a_cur, l_cur, "current assets / current liabilities", den_positive=True)
        ),
        "interest_coverage": _d(
            F.safe_div(
                ttm["operating_income"],
                interest,
                "operating income / interest expense",
                den_positive=True,
            )
        ),
        "total_assets": _d(assets),
        "total_liabilities": _d(liab),
        "equity": _d(equity),
    }
    # capital allocation: shares are cover-page COUNTS aligned to splits; weighted-average shares are never substituted
    now_end = _end(shares_now)
    sh1 = shares_ago(vis, shares_now, 1)
    sh3 = shares_ago(vis, shares_now, 3)

    def sg(prior_m: F.Metric, years: int) -> F.Metric:
        if shares_now.value is None or prior_m.value is None or now_end is None:
            return F.Metric.missing(shares_now.reason or prior_m.reason or "missing_fundamental")
        pend = _end(prior_m)
        f = F.split_factor_between(actions, pend, now_end) if pend else 1.0
        adj = F.Metric(
            prior_m.value * f,
            None,
            prior_m.available_at,
            prior_m.provenance,
            "split-aligned prior shares",
        )
        return (
            _growth(shares_now, adj, f"shares growth {years}y")
            if years == 1
            else _cagr(shares_now, adj, years, f"shares growth {years}y (CAGR)")
        )

    div_ttm, buy_ttm, iss_ttm = (
        _flow(vis, "dividends_paid"),
        _flow(vis, "buybacks"),
        _flow(vis, "issuance"),
    )
    mcap = (
        (
            last_raw_price
            * (
                shares_now.value
                * (
                    F.split_factor_between(
                        actions, now_end, date.fromisoformat(str(out["latest_period"]))
                    )
                    if now_end and out.get("latest_period")
                    else 1.0
                )
            )
        )
        if last_raw_price and shares_now.value
        else None
    )
    dy = None
    if last_adj_price and actions:
        # trailing 12 months of CASH dividends per share, on the split-adjusted basis of the last price
        end_d = decision_at.date()
        tot = 0.0
        cnt = 0
        for a in actions:
            k = str(getattr(a.kind, "value", a.kind))
            if (
                k in ("CASH_DIVIDEND", "SPECIAL_DIVIDEND")
                and a.anchor_date
                and a.cash_amount is not None
                and _years_before(end_d, 1) < a.anchor_date <= end_d
            ):
                later = F.split_factor_between(actions, a.anchor_date, end_d)
                tot += a.cash_amount / later
                cnt += 1
        dy = (
            F.Metric(
                tot / last_adj_price if cnt else 0.0,
                None,
                decision_at,
                [],
                f"sum of {cnt} cash dividends in the last 365 days (split-adjusted) / last split-adjusted close",
            )
            if cnt or any(True for _ in actions)
            else None
        )
    div_pos = F.Metric(div_ttm.value, div_ttm.reason, div_ttm.available_at, div_ttm.provenance)
    bb_y = F.safe_div(
        buy_ttm,
        F.Metric(mcap, None, decision_at, [], "market cap")
        if mcap
        else F.Metric.missing("missing_price"),
        "buybacks / market cap",
        den_positive=True,
    )
    net_issue = (
        F.linear(iss_ttm, buy_ttm, -1, "issuance - buybacks")
        if iss_ttm.value is not None and buy_ttm.value is not None
        else F.Metric.missing(
            "missing_fundamental", "net equity issuance needs both cash-flow tags"
        )
    )
    sh_yield = (
        F.linear(dy, bb_y, 1, "dividend yield + buyback yield")
        if dy is not None and dy.value is not None and bb_y.value is not None
        else F.Metric.missing(
            "missing_fundamental", "shareholder yield needs dividend yield and buyback yield"
        )
    )
    out["capital_allocation"] = {
        "shares_outstanding": _d(shares_now),
        "shares_growth1": _d(sg(sh1, 1)),
        "shares_growth3": _d(sg(sh3, 3)),
        "dividend_yield": _d(dy)
        if dy is not None
        else {"value": None, "reason": "missing_fundamental"},
        "dividends_paid_ttm": _d(div_pos),
        "dividends_to_fcf": _d(
            F.safe_div(div_ttm, ttm["fcf"], "dividends paid / fcf", den_positive=True)
        ),
        "buyback_yield": _d(bb_y),
        "buybacks_ttm": _d(buy_ttm),
        "net_equity_issuance": _d(net_issue),
        "shareholder_yield": _d(sh_yield),
        "note": "cover-page shares outstanding aligned to splits; weighted-average diluted shares are not substituted",
    }
    flat = [
        v
        for grp in (
            "ttm",
            "profitability",
            "quality",
            "growth",
            "investment",
            "balance",
            "capital_allocation",
        )
        for v in out[grp].values()
        if isinstance(v, dict) and "value" in v
    ]
    out["coverage"] = {
        "available": sum(1 for v in flat if v["value"] is not None),
        "expected": len(flat),
    }
    out["status"] = "OK" if out["coverage"]["available"] else "NO_DATA"
    out["_metrics"] = {
        "ttm": ttm,
        "assets": assets,
        "equity": equity,
        "cash": cash,
        "debt": debt,
        "shares": shares_now,
        "prior": prior,
        "avg_assets": avg_assets,
    }
    return out


def shares_ago(vis: Sequence[F.Fact], now: F.Metric, years: int) -> F.Metric:
    if now.value is None:
        return F.Metric.missing(now.reason or "missing_fundamental")
    end = _end(now)
    assert end is not None
    tgt = _years_before(end, years)
    c = [
        f for f in vis if f.concept in F.TAGS["shares_out"] and abs((f.period_end - tgt).days) <= 60
    ]
    if not c:
        return F.Metric.missing("insufficient_history", f"no cover shares near {tgt}")
    f = min(c, key=lambda x: abs((x.period_end - tgt).days))
    return F.Metric(
        f.value,
        None,
        f.available_at,
        [F._prov(f, f"{years}y_ago_shares")],
        f"shares at {f.period_end}",
    )


# ───────────────────────────── history series for the Analyzer charts ─────────────────────────
def discrete_quarters(
    vis: Sequence[F.Fact], tags: tuple[str, ...], unit: str = "USD"
) -> list[tuple[date, float, str]]:
    """Discrete quarterly values (period_end, value, method) from the latest KNOWN revisions: a direct 3-month
    fact when filed, else cumulative differencing within the fiscal year (Q2 = H1 - Q1, Q3 = 9M - H1,
    Q4 = FY - 9M). YTD facts are never summed as if they were quarters."""
    fs = [f for f in vis if f.concept in tags and f.unit == unit and f.period_start is not None]
    # keep one fact per (start, end) preferring the first tag in ``tags`` that has it
    pick: dict[tuple[date, date], F.Fact] = {}
    for tag in tags:
        for f in fs:
            if (
                f.concept == tag
                and f.period_start is not None
                and (f.period_start, f.period_end) not in pick
            ):
                pick[(f.period_start, f.period_end)] = f
    by_start: dict[date, dict[int, F.Fact]] = {}
    direct: dict[date, F.Fact] = {}
    for (s, e), f in pick.items():
        m = F._months(s, e)
        if m == 3:
            direct[e] = f
        if m in (3, 6, 9, 12):
            by_start.setdefault(s, {})[m] = f
    out: dict[date, tuple[float, str]] = {e: (f.value, "direct 3M") for e, f in direct.items()}
    for d in by_start.values():
        for m_hi, m_lo in ((6, 3), (9, 6), (12, 9)):
            hi, lo = d.get(m_hi), d.get(m_lo)
            if hi is not None and lo is not None and hi.period_end not in out:
                out[hi.period_end] = (hi.value - lo.value, f"{m_hi}M - {m_lo}M")
    return sorted((e, v, how) for e, (v, how) in out.items())


def annual_values(
    vis: Sequence[F.Fact], tags: tuple[str, ...], unit: str = "USD"
) -> list[tuple[date, float]]:
    best: dict[date, F.Fact] = {}
    for tag in tags:
        for f in vis:
            if (
                f.concept == tag
                and f.unit == unit
                and f.period_start is not None
                and F._months(f.period_start, f.period_end) == 12
                and f.period_end not in best
            ):
                best[f.period_end] = f
    return sorted((e, f.value) for e, f in best.items())


def instant_values(
    vis: Sequence[F.Fact], tags: tuple[str, ...], unit: str = "USD"
) -> list[tuple[date, float]]:
    best: dict[date, F.Fact] = {}
    for tag in tags:
        for f in vis:
            if (
                f.concept == tag
                and f.unit == unit
                and f.period_start is None
                and f.period_end not in best
            ):
                best[f.period_end] = f
    return sorted((e, f.value) for e, f in best.items())


def history_series(
    session: Session,
    security_id: str,
    decision_at: datetime,
    period: str = "quarterly",
    years: int = 8,
) -> dict[str, Any]:
    vis = F.visible(load_facts(session, security_id, decision_at), decision_at)
    if not vis:
        return {
            "status": "NO_DATA",
            "as_of": decision_at.isoformat(),
            "engine_version": FUNDAMENTAL_ENGINE_VERSION,
            "period": period,
            "series": {},
        }
    cut = date(decision_at.year - years, decision_at.month, 1)

    def flow(key: str) -> list[tuple[date, float]]:
        tags = EXTRA_TAGS.get(key) or F.TAGS[key]
        if period == "annual":
            return [(e, v) for e, v in annual_values(vis, tags) if e >= cut]
        return [(e, v) for e, v, _ in discrete_quarters(vis, tags) if e >= cut]

    rev, oi, ni, cfo, capex = (
        flow("revenue"),
        flow("operating_income"),
        flow("net_income"),
        flow("cfo"),
        flow("capex"),
    )
    cfo_d, cap_d = dict(cfo), dict(capex)
    fcf = [(e, cfo_d[e] - cap_d[e]) for e in sorted(cfo_d) if e in cap_d]
    rev_d, oi_d, fcf_d = dict(rev), dict(oi), dict(fcf)
    ser: dict[str, list[dict[str, Any]]] = {}

    def put(name: str, pts: list[tuple[date, float]]) -> None:
        d = dict(pts)
        step = 4 if period == "quarterly" else 1
        keys = sorted(d)
        rows = []
        for i, k in enumerate(keys):
            prev = keys[i - step] if i >= step else None
            g = (d[k] / d[prev] - 1.0) if prev is not None and d[prev] > 0 else None
            rows.append({"date": str(k), "value": d[k], "yoy": g})
        ser[name] = rows

    for name, pts in (("revenue", rev), ("operating_income", oi), ("net_income", ni), ("fcf", fcf)):
        put(name, pts)
    ser["operating_margin"] = [
        {"date": str(e), "value": oi_d[e] / rev_d[e], "yoy": None}
        for e in sorted(oi_d)
        if e in rev_d and rev_d[e] > 0
    ]
    ser["fcf_margin"] = [
        {"date": str(e), "value": fcf_d[e] / rev_d[e], "yoy": None}
        for e in sorted(fcf_d)
        if e in rev_d and rev_d[e] > 0
    ]
    ser["shares_outstanding"] = [
        {"date": str(e), "value": v, "yoy": None}
        for e, v in instant_values(vis, F.TAGS["shares_out"], "shares")
        if e >= cut
    ]
    ser["cash"] = [
        {"date": str(e), "value": v, "yoy": None}
        for e, v in instant_values(vis, F.TAGS["cash"])
        if e >= cut
    ]
    ser["total_debt"] = [
        {"date": str(e), "value": v, "yoy": None}
        for e, v in instant_values(vis, ("LongTermDebt",))
        if e >= cut
    ]
    return {
        "status": "OK",
        "as_of": decision_at.isoformat(),
        "engine_version": FUNDAMENTAL_ENGINE_VERSION,
        "period": period,
        "currency": "USD",
        "series": ser,
        "note": "quarterly = discrete quarters (direct or derived from YTD facts), latest revision known at as_of",
    }
