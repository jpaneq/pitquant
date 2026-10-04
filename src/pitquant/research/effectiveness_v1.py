# ruff: noqa: E501
"""RUN 3 feature effectiveness (ADR-0048). DESCRIPTIVE statistics on the DEV segment only; nothing here selects, weights or trains a model.

* Data: snapshots + targets read from the DB; only decisions <= 2022-09-30 whose target is OK (a target touching the sealed holdout is UNAVAILABLE and has no outcome). OOT rows (>= 2025-10) are never mixed in.
* Cross-section = the calendar MONTH of the decision (all exchanges pooled): a per-month Spearman IC, then averaged. Overlap: for horizon H months, ONLY months congruent mod H are used (H offsets, each
  non-overlapping); the reported t-statistic is the mean over offsets of the per-offset t, never a pooled over-confident one.
* Labels: PROMISING needs |mean IC| >= 0.03, offset t >= 2, the same sign in both halves of the dev period and in BULL and BEAR, missing <= 30%. UNSTABLE: sign flips. WEAK: |IC| < 0.02. DATA_QUALITY_LIMITED: missing > 50% or too few months.
  PROMISING is a hypothesis to test out of sample, not a rule.
* Regime = benchmark close above its SMA200 at the decision (diagnostic stratum, never a filter).
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.db.models_research import ResearchFeatureSnapshot, ResearchTarget
from pitquant.research import features_v1 as FT
from pitquant.research import fundamentals_v1 as FU
from pitquant.research import targets_v1 as TG

DEV_END = date(2022, 9, 30)
LEVEL_FEATURES = {
    "support_zone_low",
    "support_zone_high",
}  # price levels: not comparable across securities
MIN_MONTH_N = 8
MIN_MONTHS = 24
ORIENT = {  # a-priori orientation of a fundamental feature inside a component composite (+1 higher is better); fixed BEFORE looking at any IC
    "fund_gross_profitability": 1, "fund_operating_margin": 1, "fund_net_margin": 1, "fund_gross_margin": 1, "fund_roa": 1, "fund_roe": 1,
    "fund_fcf_margin": 1, "fund_cfo_to_net_income": 1, "fund_accruals_to_assets": -1,
    "fund_revenue_yoy": 1, "fund_operating_income_yoy": 1, "fund_net_income_yoy": 1, "fund_fcf_yoy": 1,
    "fund_debt_to_assets": -1, "fund_debt_to_equity": -1, "fund_cash_to_assets": 1, "fund_current_ratio": 1, "fund_interest_coverage": 1,
    "fund_dividend_yield": 1, "fund_buyback_yield": 1, "fund_shareholder_yield": 1, "fund_net_equity_issuance": -1, "fund_dividends_to_fcf": 0, "fund_capex_to_assets": 0, "fund_capex_growth_yoy": 0,
    "val_pe": -1, "val_earnings_yield": 1, "val_price_to_sales": -1, "val_price_to_book": -1, "val_fcf_yield": 1, "val_ev_to_sales": -1, "val_ev_to_operating_income": -1,
    "val_pe_own_pct": -1, "val_price_to_sales_own_pct": -1, "val_price_to_book_own_pct": -1, "val_fcf_yield_own_pct": 1,
}  # fmt: skip
TARGET_COLS = ("excess", "ret", "mdd", "dd10", "dd15", "dd20", "up", "out")


def load_frame(session: Session, horizons: tuple[int, ...] = TG.HORIZONS) -> pd.DataFrame:
    """One row per (security, decision) of the DEV segment with every feature value and, per horizon, its target columns ``<col>_<H>`` (NaN when the target is UNAVAILABLE)."""
    snaps = session.scalars(
        select(ResearchFeatureSnapshot).where(
            ResearchFeatureSnapshot.feature_set_version == FT.FEATURE_SET_VERSION
        )
    ).all()
    tg = session.scalars(
        select(ResearchTarget).where(
            ResearchTarget.target_set_version == TG.TARGET_SET_VERSION,
            ResearchTarget.status == "OK",
        )
    ).all()
    tmap: dict[tuple[str, Any], dict[int, ResearchTarget]] = {}
    for t in tg:
        tmap.setdefault((t.security_id, t.decision_at), {})[t.horizon_months] = t
    rows: list[dict[str, Any]] = []
    for sn in snaps:
        if sn.decision_session > DEV_END or sn.meta.get("segment") != "DEV":
            continue
        r: dict[str, Any] = {
            "security_id": sn.security_id,
            "decision_at": sn.decision_at,
            "month": sn.decision_session.strftime("%Y-%m"),
            "year": sn.decision_session.year,
            "exchange": sn.exchange,
        }
        r.update(
            {
                k: sn.meta.get(k)
                for k in (
                    "ticker",
                    "region",
                    "regime",
                    "sector_group",
                    "benchmark_type",
                    "fundamental_status",
                )
            }
        )
        for n, f in sn.features.items():
            r[n] = f["value"]
        for h in horizons:
            tt = tmap.get((sn.security_id, sn.decision_at), {}).get(h)
            for c, v in zip(
                TARGET_COLS,
                (
                    tt
                    and (
                        tt.excess_total_return,
                        tt.security_total_return,
                        tt.max_drawdown,
                        tt.drawdown_10,
                        tt.drawdown_15,
                        tt.drawdown_20,
                        tt.direction_up,
                        tt.outperform,
                    )
                )
                or (None,) * 8,
                strict=True,
            ):
                r[f"{c}_{h}"] = np.nan if v is None else float(v)
        rows.append(r)
    return pd.DataFrame(rows)


def feature_columns(df: pd.DataFrame) -> list[str]:
    return [
        c for c in FT.ALL_NAMES + FU.FEATURE_NAMES if c in df.columns and c not in LEVEL_FEATURES
    ]


def describe(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    x = df[cols].astype(float)
    return pd.DataFrame(
        {"n": x.notna().sum(), "missing_pct": 100 * x.isna().mean(), "mean": x.mean(), "std": x.std(), "p10": x.quantile(0.1), "p50": x.quantile(0.5), "p90": x.quantile(0.9)}
    )  # fmt: skip


def monthly_ic(df: pd.DataFrame, feat: str, target: str) -> pd.Series:
    """Spearman IC per decision month (cross-section over every security with both values)."""
    out: dict[str, float] = {}
    for m, g in df[["month", feat, target]].dropna().groupby("month"):
        if len(g) >= MIN_MONTH_N and g[feat].nunique() > 1:
            out[str(m)] = float(g[feat].rank().corr(g[target].rank()))
    return pd.Series(
        list(out.values()), index=pd.Index(list(out.keys()), dtype=object), dtype=float
    ).sort_index()


def offset_summary(ic: pd.Series, h: int) -> dict[str, float | None]:
    """Mean IC and t over the H non-overlapping month offsets (months congruent mod H)."""
    if len(ic) < MIN_MONTHS:
        return {"ic": None, "t": None, "n_months": float(len(ic)), "pos_share": None}
    idx = pd.Series(np.arange(len(ic)), index=ic.index)
    ts, means = [], []
    for k in range(h):
        s = ic[(idx % h) == k]
        if len(s) >= 6 and s.std() > 0:
            means.append(float(s.mean()))
            ts.append(float(s.mean() / (s.std() / np.sqrt(len(s)))))
    if not means:
        return {"ic": None, "t": None, "n_months": float(len(ic)), "pos_share": None}
    return {
        "ic": float(np.mean(means)),
        "t": float(np.mean(ts)),
        "n_months": float(len(ic)),
        "pos_share": float((ic > 0).mean()),
    }


def quantiles(df: pd.DataFrame, feat: str, target: str, q: int = 10) -> dict[str, Any]:
    """Per-month cross-sectional buckets (q=10 deciles, 5 quintiles), mean target per bucket, top - bottom, monotonicity (Spearman bucket vs mean)."""
    acc: dict[int, list[float]] = {i: [] for i in range(q)}
    for _m, g in df[["month", feat, target]].dropna().groupby("month"):
        if len(g) < max(q * 2, MIN_MONTH_N):
            continue
        b = np.minimum((g[feat].rank(pct=True, method="first").sub(1e-12) * q).astype(int), q - 1)
        for i, v in g[target].groupby(b).mean().items():
            acc[int(i)].append(float(v))
    means = {i: float(np.mean(v)) for i, v in acc.items() if v}
    if len(means) < q:
        return {"means": means, "top_minus_bottom": None, "monotonicity": None}
    s = pd.Series(means)
    return {
        "means": means,
        "top_minus_bottom": float(s.iloc[-1] - s.iloc[0]),
        "monotonicity": float(pd.Series(range(q), dtype=float).corr(s.reset_index(drop=True))),
    }


def _sign(x: float | None) -> int:
    return 0 if x is None or abs(x) < 1e-12 else (1 if x > 0 else -1)


def feature_report(df: pd.DataFrame, feat: str, h: int, target: str = "excess") -> dict[str, Any]:
    col = f"{target}_{h}"
    ic = monthly_ic(df, feat, col)
    s = offset_summary(ic, h)
    halves = {"H1": ic[ic.index < "2017-01"], "H2": ic[ic.index >= "2017-01"]}
    strata: dict[str, float | None] = {}
    for name, sub in (("H1_2011_2016", halves["H1"]), ("H2_2017_2022", halves["H2"])):
        strata[name] = float(sub.mean()) if len(sub) >= 12 else None
    for key in ("regime", "region"):
        for v in sorted(x for x in df[key].dropna().unique()):
            sub_ic = monthly_ic(df[df[key] == v], feat, col)
            strata[f"{key}={v}"] = float(sub_ic.mean()) if len(sub_ic) >= 12 else None
    base = (
        df[
            ~df["fundamental_status"].isin(["NOT_REGISTERED", "UNSUPPORTED_SECTOR"])
            & df["fundamental_status"].notna()
        ]
        if feat in FU.FEATURE_NAMES
        else df
    )
    miss = (
        float(base[feat].isna().mean() * 100) if feat in base and len(base) else 100.0
    )  # fundamentals: among companies the engine supports (coverage is reported separately)
    pair = df[["month", feat, col]].dropna().groupby("month").size()
    avg_n = float(pair.mean()) if len(pair) else 0.0
    return {
        "feature": feat,
        "horizon": h,
        "target": target,
        **s,
        "missing_pct": miss,
        "avg_names_per_month": avg_n,
        "strata": strata,
        "label": label(s, strata, miss, avg_n),
    }


MIN_AVG_NAMES = 15


def label(
    s: dict[str, float | None], strata: dict[str, float | None], miss: float, avg_n: float = 99.0
) -> str:
    ic, t = s["ic"], s["t"]
    if miss > 50 or ic is None or avg_n < MIN_AVG_NAMES:
        return "DATA_QUALITY_LIMITED"
    signs = {
        _sign(v)
        for k, v in strata.items()
        if v is not None and (k.startswith("H") or k.startswith("regime"))
    }
    if len(signs - {0}) > 1:
        return "UNSTABLE"
    if abs(ic) < 0.02:
        return "WEAK"
    if (
        abs(ic) >= 0.03
        and t is not None
        and abs(t) >= 2
        and miss <= 30
        and _sign(ic) == next(iter(signs - {0}), _sign(ic))
    ):
        return "PROMISING"
    return "WEAK"


def redundancy(
    df: pd.DataFrame, cols: list[str], threshold: float = 0.85
) -> list[tuple[str, str, float]]:
    c = (
        df[cols].astype(float).rank().corr(min_periods=200)
    )  # Spearman = Pearson on ranks (no scipy dependency)
    out = [
        (a, b, float(c.loc[a, b]))
        for i, a in enumerate(cols)
        for b in cols[i + 1 :]
        if pd.notna(c.loc[a, b]) and abs(c.loc[a, b]) >= threshold
    ]
    return sorted(out, key=lambda x: -abs(x[2]))


def component_composites(df: pd.DataFrame) -> pd.DataFrame:
    """Per component, the mean of the ORIENTED cross-sectional percentile ranks of its features (orientation fixed a priori in ``ORIENT``; 0 = not used)."""
    out = pd.DataFrame(index=df.index)
    for comp, items in FU.COMPONENTS.items():
        parts = []
        for name, _ in items:
            sign = ORIENT.get(name, 0)
            if sign == 0 or name not in df:
                continue
            r = df.groupby("month")[name].rank(pct=True)
            parts.append(r if sign > 0 else 1 - r)
        out[f"comp_{comp}"] = (
            pd.concat(parts, axis=1).mean(axis=1, skipna=True) if parts else np.nan
        )
    return out


def odds_ratio(flag: pd.Series, outcome: pd.Series) -> dict[str, float | None]:
    """2x2 odds ratio of ``outcome`` for flag=1 vs 0 with Haldane-Anscombe correction and a 95% Woolf interval; also the base rates."""
    d = pd.DataFrame({"f": flag, "o": outcome}).dropna()
    if d["f"].nunique() < 2 or len(d) < 50:
        return {
            "or": None,
            "lo": None,
            "hi": None,
            "n": float(len(d)),
            "rate_flag": None,
            "rate_no_flag": None,
        }
    a = float(((d.f == 1) & (d.o == 1)).sum()) + 0.5
    b = float(((d.f == 1) & (d.o == 0)).sum()) + 0.5
    c = float(((d.f == 0) & (d.o == 1)).sum()) + 0.5
    e = float(((d.f == 0) & (d.o == 0)).sum()) + 0.5
    orr, se = (a * e) / (b * c), float(np.sqrt(1 / a + 1 / b + 1 / c + 1 / e))
    return {
        "or": orr,
        "lo": float(np.exp(np.log(orr) - 1.96 * se)),
        "hi": float(np.exp(np.log(orr) + 1.96 * se)),
        "n": float(len(d)),
        "rate_flag": float(d[d.f == 1].o.mean()),
        "rate_no_flag": float(d[d.f == 0].o.mean()),
    }


def risk_alert_report(
    df: pd.DataFrame, horizons: tuple[int, ...] = (6, 12, 24)
) -> list[dict[str, Any]]:
    out = []
    for h in horizons:
        for ah in (6, 12):
            f = f"risk_alert_h{ah}"
            if f not in df:
                continue
            ic = monthly_ic(df, f, f"mdd_{h}")
            row: dict[str, Any] = {
                "alert": f,
                "target_horizon": h,
                "ic_vs_max_drawdown": offset_summary(ic, h),
                "base_rate_alert": float(df[f].mean()) if df[f].notna().any() else None,
            }
            for k in ("dd10", "dd15", "dd20"):
                row[k] = odds_ratio(df[f], df[f"{k}_{h}"])
            out.append(row)
    return out


def auc(score: pd.Series, y: pd.Series) -> float | None:
    d = pd.DataFrame({"s": score, "y": y}).dropna()
    pos, neg = d[d.y == 1], d[d.y == 0]
    if len(pos) < 20 or len(neg) < 20:
        return None
    r = d["s"].rank()
    return float((r[d.y == 1].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def naive_baselines(df: pd.DataFrame, h: int) -> dict[str, Any]:
    """Naive yardsticks for ``outperform_H``: base rate and single-feature rank scores. A future model must beat these OUT OF SAMPLE."""
    y = df[f"out_{h}"]
    ok = y.notna()
    base = float(y[ok].mean()) if ok.any() else None
    return {"n": int(ok.sum()), "base_rate_outperform": base, "accuracy_always_outperform": base, "auc_momentum_12_1": auc(df["momentum_12_1"], y), "auc_low_vol_63": auc(-df["realized_vol_63"], y), "auc_ret_6m": auc(df["ret_6m"], y), "auc_risk_alert_inverse": auc(-df[f"risk_alert_h{h if h in (1, 3, 6, 12, 24) else 6}"], y)}  # fmt: skip
