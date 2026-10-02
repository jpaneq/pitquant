# ruff: noqa: E501
"""Feature Engine V0: RAW, explainable, point-in-time features (ADR-0027).

``decision_at`` = NYSE open of the decision session. Price features use ONLY sessions strictly
before it (last usable price = previous session close). Fundamentals use ONLY facts with
``available_at < decision_at``. Missing stays NULL with a reason; nothing is imputed, winsorized
or standardised here (that belongs to the model pipeline, fit on train only).

Any change of formula, tag map, periodization, corporate-action adjustment, calendar or benchmark
MUST change ``FEATURE_VERSION``: old snapshots are immutable.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from pitquant.config.settings import get_settings
from pitquant.core.errors import HoldoutAccessError
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.data.point_in_time.context import PITContext
from pitquant.db.models import FeatureSnapshotRow, FundamentalFact, Security
from pitquant.features.snapshot import FeatureValue, FrozenSnapshot, SnapshotBuilder
from pitquant.features.v0 import fundamentals as F
from pitquant.features.v0 import technical as T
from pitquant.features.v0.series import SHARE_KINDS, PriceSeries, build_series
from pitquant.market.total_return import InsufficientValuationError

FEATURE_VERSION = "v0.2"  # v0.2: shares_growth_yoy is aligned to splits between the two cover dates

TECHNICAL = (
    "tr_21d", "tr_63d", "tr_126d", "tr_252d", "mom_12_1",
    "close_vs_sma20", "close_vs_sma50", "close_vs_sma200", "close_vs_ema20", "close_vs_ema50",
    "vol_20d", "vol_63d", "vol_252d", "max_drawdown_252d", "atr_14", "atr_14_pct", "rsi_14",
    "volume_ratio_20", "volume_zscore_20", "beta_252_spy",
    "relative_21d_spy", "relative_63d_spy", "relative_126d_spy", "relative_252d_spy",
)  # fmt: skip
FUNDAMENTAL = (
    "revenue_ttm", "gross_profit_ttm", "operating_income_ttm", "net_income_ttm", "cfo_ttm",
    "capex_ttm", "fcf_ttm",
    "revenue_growth_yoy", "operating_income_growth_yoy", "net_income_growth_yoy", "fcf_growth_yoy",
    "gross_margin", "operating_margin", "net_margin", "fcf_margin",
    "roa", "roe", "cfo_to_net_income", "accruals_to_assets", "cash_to_assets", "debt_to_assets",
    "shares_growth_yoy",
)  # fmt: skip
VALUATION = ("market_cap", "price_to_sales", "price_to_book", "price_to_earnings", "fcf_yield")
FEATURE_NAMES: tuple[str, ...] = TECHNICAL + FUNDAMENTAL + VALUATION


@dataclass
class FeatureResult:
    name: str
    value: float | None
    reason: str | None = None
    available_at: datetime | None = None
    provenance: list[dict[str, Any]] = field(default_factory=list)
    formula: str = ""
    intermediates: dict[str, Any] = field(default_factory=dict)

    @property
    def coverage_status(self) -> str:
        return "COMPLETE" if self.value is not None else "MISSING"


def decision_time(decision_session: date, exchange: str = "XNYS") -> datetime:
    cal = get_calendar(exchange)
    if not cal.is_session(decision_session):
        raise ValueError(f"{decision_session} is not a {exchange} session")
    return cal.session_open(decision_session)


def assert_not_holdout(d: date) -> None:
    ho = get_settings().validation.final_holdout
    if ho.start <= d <= ho.end:
        raise HoldoutAccessError(
            f"{d} is inside the sealed final holdout {ho.start}..{ho.end}: no features"
        )


def load_facts(session: Session, security_id: str, decision_at: datetime) -> list[F.Fact]:
    sec = session.get_one(Security, security_id)
    subj = [FundamentalFact.security_id == security_id]
    if sec.issuer_id:
        subj.append(FundamentalFact.issuer_id == sec.issuer_id)
    rows = session.scalars(
        select(FundamentalFact).where(or_(*subj), FundamentalFact.available_at < decision_at)
    ).all()
    return [
        F.Fact(r.concept, r.period_start, r.period_end, float(r.value), r.unit, r.available_at,
               r.accession_number, r.form, r.revision_id, r.fact_id)
        for r in rows
        if r.value is not None
    ]  # fmt: skip


def _price_features(ps: PriceSeries, bench: PriceSeries | None) -> list[FeatureResult]:
    out: list[FeatureResult] = []
    av: datetime | None = None  # set by the caller from the last bar close

    def put(name: str, v: float | None, need: int, kind: str, formula: str, **inter: Any) -> None:
        reason = None
        if v is None:
            reason = "insufficient_history" if ps.n_bars < need + 1 else "coverage_gap"
        if v is not None and not ps.contiguous(need):
            v, reason = None, "coverage_gap"
        out.append(
            FeatureResult(
                name,
                v,
                reason,
                av,
                [],
                formula,
                {"bars_needed": need + 1, "bars_available": ps.n_bars, "series": kind, **inter},
            )
        )

    g, lvl, adj = ps.tr_gross, ps.tr_level, ps.split_adjusted
    for n in (21, 63, 126, 252):
        put(f"tr_{n}d", T.tr_return(g, n), n, "tr_index", f"prod(last {n} daily gross TR) - 1")
    put("mom_12_1", T.mom_12_1(lvl), 252, "tr_index", "TR_index[t-21] / TR_index[t-252] - 1")
    for n in (20, 50, 200):
        put(
            f"close_vs_sma{n}",
            T.close_vs_sma(adj["close"], n),
            n - 1,
            "split_adjusted",
            f"adj_close / SMA{n} - 1",
        )
    for n in (20, 50):
        put(
            f"close_vs_ema{n}",
            T.close_vs_ema(adj["close"], n),
            n - 1,
            "split_adjusted",
            f"adj_close / EMA{n} - 1 (alpha=2/(n+1), seeded with the first value)",
        )
    for n in (20, 63, 252):
        put(f"vol_{n}d", T.annualized_vol(g, n), n, "tr_index", f"std(ln R, last {n}) * sqrt(252)")
    put(
        "max_drawdown_252d",
        T.max_drawdown(lvl, 252),
        252,
        "tr_index",
        "min(TR_index / running max - 1) over the last 252 returns",
    )
    a = T.atr(adj, 14)
    put("atr_14", a, 14, "split_adjusted", "Wilder ATR(14) on split-adjusted OHLC")
    last_adj_close = float(adj["close"].iloc[-1]) if len(adj) else None
    put(
        "atr_14_pct",
        None if a is None or not last_adj_close else a / last_adj_close,
        14,
        "split_adjusted",
        "ATR14 / last split-adjusted close",
    )
    put(
        "rsi_14",
        T.rsi(adj["close"], 14),
        14,
        "split_adjusted",
        "Wilder RSI(14) on split-adjusted closes",
    )
    put(
        "volume_ratio_20",
        T.volume_ratio(adj["volume"], 20),
        19,
        "split_adjusted",
        "V_last / mean(V last 20), split-adjusted volume",
    )
    put(
        "volume_zscore_20",
        T.volume_zscore(adj["volume"], 20),
        19,
        "split_adjusted",
        "(V_last - mean20) / std20 (ddof=1)",
    )
    if bench is None or bench.n_bars == 0:
        for nm in (
            "beta_252_spy",
            "relative_21d_spy",
            "relative_63d_spy",
            "relative_126d_spy",
            "relative_252d_spy",
        ):
            out.append(
                FeatureResult(
                    nm,
                    None,
                    "coverage_gap",
                    None,
                    [],
                    "benchmark SPY total return unavailable",
                    {"benchmark": "US_BENCHMARK_SPY_TOTAL_RETURN"},
                )
            )
    else:
        bg = bench.tr_gross
        out.append(
            FeatureResult(
                "beta_252_spy",
                T.beta(g, bg),
                None,
                av,
                [],
                "cov(ln R_i, ln R_spy)/var(ln R_spy), last 252 common sessions, >= 126",
                {"benchmark": "US_BENCHMARK_SPY_TOTAL_RETURN", "benchmark_type": "ETF_PROXY"},
            )
        )
        for n in (21, 63, 126, 252):
            out.append(
                FeatureResult(
                    f"relative_{n}d_spy",
                    T.relative_return(g, bg, n),
                    None,
                    av,
                    [],
                    f"TR_i - TR_spy over {n} common sessions",
                    {"benchmark_type": "ETF_PROXY"},
                )
            )
        for r in out[-5:]:
            if r.value is None:
                r.reason = "insufficient_history"
    return out


def _fundamental_features(
    vis: list[F.Fact], decision_at: datetime, actions: Sequence[Any] = ()
) -> tuple[list[FeatureResult], dict[str, F.Metric]]:
    m: dict[str, F.Metric] = {}
    for k in ("revenue", "gross_profit", "operating_income", "net_income", "cfo", "capex"):
        m[k] = F.resolve_flow_ttm(vis, k)
    m["fcf"] = F.linear(
        m["cfo"],
        m["capex"],
        -1,
        "FCF = CFO - CapEx (CapEx = payments to acquire PP&E, positive outflow)",
    )

    def prior(k: str) -> F.Metric:
        cur = m[k]
        if cur.value is None:
            return F.Metric.missing(cur.reason or "missing_fundamental")
        end = max(date.fromisoformat(str(p["period"]).split("..")[-1]) for p in cur.provenance)
        return F.resolve_flow_ttm(vis, k, as_of_end=F._minus_year(end))

    pm = {k: prior(k) for k in ("revenue", "operating_income", "net_income", "cfo", "capex")}
    pm["fcf"] = F.linear(pm["cfo"], pm["capex"], -1, "prior-year FCF")

    def growth(k: str) -> F.Metric:
        a, b = m[k], pm[k]
        if a.value is None or b.value is None:
            return F.Metric.missing(a.reason or b.reason or "missing_fundamental", f"{k} growth")
        if b.value <= 0:
            return F.Metric.missing(
                "denominator_invalid", f"{k} growth: prior-year TTM {b.value} <= 0"
            )
        return F.Metric(
            a.value / b.value - 1.0,
            None,
            max(x for x in (a.available_at, b.available_at) if x),
            a.provenance + b.provenance,
            f"{k}_ttm / {k}_ttm(prior year) - 1",
        )

    avg_assets, avg_equity = F.average_instant(vis, "assets"), F.average_instant(vis, "equity")
    assets, cash = F.latest_instant(vis, "assets"), F.latest_instant(vis, "cash")
    debt = _debt(vis)
    ni_less_cfo = F.linear(m["net_income"], m["cfo"], -1, "net_income_ttm - cfo_ttm")
    shares_now = F.shares_outstanding(vis)
    sh_prior = _prior_shares(vis, shares_now)
    out_m: dict[str, F.Metric] = {
        "revenue_ttm": m["revenue"],
        "gross_profit_ttm": m["gross_profit"],
        "operating_income_ttm": m["operating_income"],
        "net_income_ttm": m["net_income"],
        "cfo_ttm": m["cfo"],
        "capex_ttm": m["capex"],
        "fcf_ttm": m["fcf"],
        "revenue_growth_yoy": growth("revenue"),
        "operating_income_growth_yoy": growth("operating_income"),
        "net_income_growth_yoy": growth("net_income"),
        "fcf_growth_yoy": growth("fcf"),
        "gross_margin": F.safe_div(
            m["gross_profit"], m["revenue"], "gross_profit_ttm / revenue_ttm", den_positive=True
        ),
        "operating_margin": F.safe_div(
            m["operating_income"],
            m["revenue"],
            "operating_income_ttm / revenue_ttm",
            den_positive=True,
        ),
        "net_margin": F.safe_div(
            m["net_income"], m["revenue"], "net_income_ttm / revenue_ttm", den_positive=True
        ),
        "fcf_margin": F.safe_div(
            m["fcf"], m["revenue"], "fcf_ttm / revenue_ttm", den_positive=True
        ),
        "roa": F.safe_div(
            m["net_income"], avg_assets, "net_income_ttm / average_assets", den_positive=True
        ),
        "roe": F.safe_div(
            m["net_income"], avg_equity, "net_income_ttm / average_equity", den_positive=True
        ),
        "cfo_to_net_income": F.safe_div(
            m["cfo"], m["net_income"], "cfo_ttm / net_income_ttm", den_positive=True
        ),
        "accruals_to_assets": F.safe_div(
            ni_less_cfo,
            avg_assets,
            "(net_income_ttm - cfo_ttm) / average_assets",
            den_positive=True,
        ),
        "cash_to_assets": F.safe_div(cash, assets, "cash / assets", den_positive=True),
        "debt_to_assets": F.safe_div(debt, assets, "debt / assets", den_positive=True),
        "shares_growth_yoy": _shares_growth(
            shares_now, sh_prior, _share_split_factor(shares_now, sh_prior, actions)
        ),
    }
    res = []
    for name in FUNDAMENTAL:
        x = out_m[name]
        res.append(FeatureResult(name, x.value, x.reason, x.available_at, x.provenance, x.formula))
    return res, {
        **m,
        "assets": assets,
        "equity": F.latest_instant(vis, "equity"),
        "shares": shares_now,
    }


def _debt(vis: list[F.Fact]) -> F.Metric:
    """Total debt = LongTermDebt (if present) else LongTermDebtNoncurrent + current portions; fail closed if none."""
    pick: dict[str, F.Fact] = {}
    for f in vis:
        if (
            f.concept in F.DEBT_TAGS
            and f.unit == "USD"
            and f.period_start is None
            and (f.concept not in pick or f.period_end > pick[f.concept].period_end)
        ):
            pick[f.concept] = f
    if "LongTermDebt" in pick:
        f = pick["LongTermDebt"]
        return F.Metric(
            f.value, None, f.available_at, [F._prov(f, "debt")], "LongTermDebt (total, instant)"
        )
    nc, cur = (
        pick.get("LongTermDebtNoncurrent"),
        pick.get("DebtCurrent") or pick.get("LongTermDebtCurrent"),
    )
    if nc is None or cur is None or nc.period_end != cur.period_end:
        return F.Metric.missing(
            "unresolved_tag", "debt: neither LongTermDebt nor a same-period noncurrent+current pair"
        )
    return F.Metric(
        nc.value + cur.value,
        None,
        max(nc.available_at, cur.available_at),
        [F._prov(nc, "debt_noncurrent"), F._prov(cur, "debt_current")],
        "LongTermDebtNoncurrent + current portion",
    )


def _prior_shares(vis: list[F.Fact], now: F.Metric) -> F.Metric:
    if now.value is None:
        return F.Metric.missing(now.reason or "missing_fundamental")
    end = date.fromisoformat(str(now.provenance[0]["period"]).split("..")[-1])
    c = [
        f
        for f in vis
        if f.concept in F.TAGS["shares_out"] and abs((f.period_end - F._minus_year(end)).days) <= 45
    ]
    if not c:
        return F.Metric.missing(
            "insufficient_history", f"no shares outstanding one year before {end}"
        )
    f = min(c, key=lambda x: abs((x.period_end - F._minus_year(end)).days))
    return F.Metric(
        f.value,
        None,
        f.available_at,
        [F._prov(f, "prior_year_shares")],
        f"shares outstanding at {f.period_end}",
    )


def _shares_growth(now: F.Metric, prior: F.Metric, split_factor: float = 1.0) -> F.Metric:
    if now.value is None or prior.value is None:
        return F.Metric.missing(
            now.reason or prior.reason or "missing_fundamental", "shares_growth_yoy"
        )
    if prior.value <= 0:
        return F.Metric.missing("denominator_invalid", "prior shares <= 0")
    return F.Metric(
        now.value / (prior.value * split_factor) - 1.0,
        None,
        max(x for x in (now.available_at, prior.available_at) if x),
        now.provenance + prior.provenance,
        f"shares_out / (shares_out(1y earlier) * split factor {split_factor:g} between the two cover dates) - 1 (cover-page shares)",
    )


def _share_split_factor(now: F.Metric, prior: F.Metric, actions: Sequence[Any]) -> float:
    if now.value is None or prior.value is None:
        return 1.0
    end_now = date.fromisoformat(str(now.provenance[0]["period"]).split("..")[-1])
    end_prior = date.fromisoformat(str(prior.provenance[0]["period"]).split("..")[-1])
    return F.split_factor_between(actions, end_prior, end_now)


MAX_SHARES_AGE_DAYS = 400


def _valuation(
    ps: PriceSeries,
    shares: F.Metric,
    actions: list[Any],
    mets: dict[str, F.Metric],
    decision_session: date,
) -> list[FeatureResult]:
    names = {n: FeatureResult(n, None, "missing_fundamental") for n in VALUATION}
    if ps.n_bars == 0 or shares.value is None:
        for n in VALUATION:
            names[n].reason = (
                "insufficient_history"
                if ps.n_bars == 0
                else (shares.reason or "missing_fundamental")
            )
        return list(names.values())
    last = ps.last_session
    assert last is not None
    prev_close = float(ps.raw_close.iloc[-1])
    sh_end = date.fromisoformat(str(shares.provenance[0]["period"]).split("..")[-1])
    if (decision_session - sh_end).days > MAX_SHARES_AGE_DAYS:
        for n in VALUATION:
            names[n].reason = "stale_data"
        return list(names.values())
    # raw price is as traded: shares must be on the same basis -> multiply by splits between the cover date and the price date
    factor = 1.0
    for a in actions:
        if a.kind in SHARE_KINDS and a.ratio and a.anchor_date and sh_end < a.anchor_date <= last:
            factor *= a.ratio
    sh = shares.value * factor
    mc = prev_close * sh
    av = max(x for x in (shares.available_at,) if x)
    prov = [
        *shares.provenance,
        {
            "role": "previous_close",
            "session": str(last),
            "raw_close": prev_close,
            "split_factor_applied_to_shares": factor,
        },
    ]
    names["market_cap"] = FeatureResult(
        "market_cap",
        mc,
        None,
        av,
        prov,
        "previous raw close * shares outstanding (cover page, split-aligned)",
        {"previous_close": prev_close, "shares": shares.value, "split_factor": factor},
    )

    def ratio(
        name: str,
        num: float | None,
        den: F.Metric,
        den_positive: bool,
        formula: str,
        invert: bool = False,
    ) -> None:
        if den.value is None:
            names[name] = FeatureResult(
                name, None, den.reason or "missing_fundamental", None, [], formula
            )
        elif den_positive and den.value <= 0:
            names[name] = FeatureResult(
                name,
                None,
                "denominator_invalid",
                None,
                den.provenance,
                f"{formula}: denominator {den.value} <= 0",
            )
        elif den.value == 0:
            names[name] = FeatureResult(
                name, None, "denominator_invalid", None, den.provenance, formula
            )
        else:
            assert num is not None
            v = den.value / num if invert else num / den.value
            names[name] = FeatureResult(
                name,
                v,
                None,
                max(x for x in (av, den.available_at) if x),
                prov + den.provenance,
                formula,
            )

    ratio("price_to_sales", mc, mets["revenue"], True, "market_cap / revenue_ttm")
    ratio("price_to_book", mc, mets["equity"], True, "market_cap / stockholders_equity")
    ratio(
        "price_to_earnings",
        mc,
        mets["net_income"],
        True,
        "market_cap / net_income_ttm (NULL if earnings <= 0)",
    )
    ratio(
        "fcf_yield", mc, mets["fcf"], False, "fcf_ttm / market_cap (negative allowed)", invert=True
    )
    return list(names.values())


def compute_features(
    session: Session,
    security_id: str,
    decision_session: date,
    *,
    benchmark_security_id: str | None = None,
    exchange: str = "XNYS",
    allow_holdout: bool = False,
) -> list[FeatureResult]:
    if not allow_holdout:
        assert_not_holdout(decision_session)
    dt = decision_time(decision_session, exchange)
    ctx = PITContext(session, dt)
    bars = ctx.raw_bars(security_id)
    actions = ctx.market_actions(security_id)
    try:
        ps = build_series(bars, actions, dt, decision_session, exchange)
        series_err = None
    except InsufficientValuationError as e:  # a dividend without ex-date inside the history
        ps, series_err = build_series(bars.iloc[0:0], [], dt, decision_session, exchange), str(e)
    bench = None
    if benchmark_security_id is not None:
        bb = PITContext(session, dt)
        try:
            bench = build_series(
                bb.raw_bars(benchmark_security_id),
                bb.market_actions(benchmark_security_id),
                dt,
                decision_session,
                exchange,
            )
        except InsufficientValuationError:
            bench = None
    res = _price_features(ps, bench)
    if ps.n_bars:
        last_close_at = bars[bars.index < decision_session]["bar_close_at"].iloc[-1]
        for r in res:
            if r.value is not None:
                r.available_at = last_close_at
    if series_err:
        for r in res:
            r.value, r.reason = None, "coverage_gap"
            r.intermediates["series_error"] = series_err
    vis = F.visible(load_facts(session, security_id, dt), dt)
    fres, mets = _fundamental_features(vis, dt, [a for a in actions if a.available_at < dt])
    vres = _valuation(
        ps, mets["shares"], [a for a in actions if a.available_at < dt], mets, decision_session
    )
    allr = res + fres + vres
    assert [r.name for r in allr] == list(FEATURE_NAMES), "feature order drifted from FEATURE_NAMES"
    return allr


def data_version(
    session: Session, security_id: str, decision_session: date, results: list[FeatureResult]
) -> str:
    h = hashlib.sha256()
    h.update(f"{security_id}|{decision_session}|{FEATURE_VERSION}|{F.TAG_MAP_VERSION}".encode())
    for r in results:
        h.update(f"|{r.name}={r.value!r}:{r.available_at}".encode())
    return "v0-" + h.hexdigest()[:16]


def build_snapshot(
    session: Session,
    security_id: str,
    decision_session: date,
    *,
    benchmark_security_id: str | None = None,
    code_version: str = "feature-engine-v0",
    is_synthetic: bool = False,
    exchange: str = "XNYS",
    extra_warnings: tuple[tuple[str, str, str], ...] = (),
) -> FrozenSnapshot:
    dt = decision_time(decision_session, exchange)
    results = compute_features(
        session,
        security_id,
        decision_session,
        benchmark_security_id=benchmark_security_id,
        exchange=exchange,
    )
    b = SnapshotBuilder(
        security_id,
        dt,
        FEATURE_VERSION,
        data_version(session, security_id, decision_session, results),
        code_version,
        is_synthetic,
    )
    for w in extra_warnings:
        b.warn(*w)
    for r in results:
        b.add(
            FeatureValue(
                r.name,
                r.value,
                r.available_at if r.value is not None else None,
                f"{FEATURE_VERSION}:{r.name}",
                False,
                r.reason,
                r.formula or None,
                r.provenance or None,
            )
        )
        if r.value is None:
            b.warn("feature_missing", "info", f"{r.name}: {r.reason}")
    return b.freeze()


def persist_if_new(session: Session, snap: FrozenSnapshot) -> tuple[FeatureSnapshotRow, bool]:
    from pitquant.features.snapshot import persist_snapshot

    ex = session.scalars(
        select(FeatureSnapshotRow).where(
            FeatureSnapshotRow.security_id == snap.security_id,
            FeatureSnapshotRow.as_of == snap.as_of,
            FeatureSnapshotRow.feature_version == snap.feature_version,
            FeatureSnapshotRow.content_hash == snap.content_hash,
        )
    ).first()
    if ex is not None:
        return ex, False
    return persist_snapshot(session, snap), True


def cross_sectional_rank(values: dict[str, float | None]) -> dict[str, float | None]:
    """Percentile rank in [0, 1] among the securities of ONE cohort and date (average ranks for ties).
    Stored next to, never instead of, the raw value."""
    s = pd.Series({k: v for k, v in values.items() if v is not None}, dtype=float)
    if len(s) < 2:
        return dict.fromkeys(values)
    r = s.rank(method="average", pct=False)
    pct = (r - 1) / (len(s) - 1)
    return {k: (float(pct[k]) if k in pct.index else None) for k in values}
