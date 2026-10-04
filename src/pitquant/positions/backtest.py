# ruff: noqa: E501
"""Walk-forward replay of the daily routine's rule over history (ADR-0044/0045): did the algorithm's call — UP (entry justified), DOWN (score ≤ sell threshold) or NEUTRAL — match what the price did?

* At each sampled past session T the SAME rule engine as the live routine sees ONLY bars known at the close of T (``AnalyzerService.technicals(sid, T)``). Price-only rules (trend, 200-day trend,
  6-month momentum, nearest support). Where SEC fundamentals exist (point-in-time by accession) a SECOND call adds valuation and fundamentals, so the contribution of fundamentals can be measured.
* Outcomes use only bars AFTER T: end-of-horizon return (direction) and, for UP calls, first touch of target/stop (``routine.outcome``). Immature windows are not scored.
* The sealed holdout (2022-10-01 → 2025-09-30) is never touched: a decision inside it, or whose horizon reaches it, is skipped and counted.
* RETROSPECTIVE: prices come from an unofficial free source downloaded after the fact; overlapping windows are not independent; the ticker list is today's large caps (SURVIVORSHIP BIAS); no costs.
Each row keeps the raw value of every rule, so variants (ablation, thresholds) are re-scored offline without re-running the analysis.
"""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import date, datetime
from statistics import mean
from typing import Any

from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from pitquant.analyzer.market import load_market
from pitquant.analyzer.service import AnalyzerService, clear_cache
from pitquant.config.settings import Settings
from pitquant.core.timeutils import utc_now
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.positions import review as engine
from pitquant.positions import routine as rt
from pitquant.simulation.service import restated_bars

BACKTEST_VERSION = "routine-backtest-2"
SENSITIVITY_K = (0.3, 0.5, 0.7, 1.0)
MIN_N = 10
CALL = {"ADD": "UP", "SELL": "DOWN", "HOLD": "NEUTRAL"}
RULE_IDS = ("trend", "long_trend", "momentum", "valuation", "fundamentals", "support")


def context_at(
    svc: AnalyzerService, sid: str, at: datetime, price: float, with_labels: bool = False
) -> engine.Context | None:
    """Context built from bars known at ``at``; ``None`` when there is not enough history. ``with_labels`` adds the PIT valuation/fundamentals labels (needs SEC facts)."""
    tech = svc.technicals(sid, at)
    if tech.get("status") != "OK":
        return None
    ind = tech.get("indicators", {})
    zones = (tech.get("support_resistance") or {}).get("supports", [])
    below = [z for z in zones if z.get("upper") is not None and z["upper"] < price]
    ctx = engine.Context(
        price=price, atr14=ind.get("atr14"), trend_state=(tech.get("trend") or {}).get("state"), close_vs_sma200=ind.get("close_vs_sma200"), close_vs_sma50=ind.get("close_vs_sma50"),
        ret_6m=(tech.get("momentum") or {}).get("ret126"), rsi14=ind.get("rsi14"), vol_annual=(tech.get("risk") or {}).get("vol63"), support_lower=float(max(below, key=lambda z: z["upper"])["lower"]) if below else None,
    )  # fmt: skip
    if with_labels:
        labels = (svc.analysis(sid, at).get("labels")) or {}
        ctx = replace(
            ctx,
            valuation_label=(labels.get("valuation") or {}).get("label"),
            fundamentals_label=(labels.get("fundamentals") or {}).get("label"),
        )
    return ctx


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)


def has_fundamentals(svc: AnalyzerService, sid: str, now: datetime) -> bool:
    try:
        return svc.fundamentals(sid, now).get("status") == "OK"
    except Exception:
        return False


def _why(rv: dict[str, Any]) -> str:
    parts = [f"{r['id']}={r['value']}→{r['contribution']:+.2f}" for r in rv["rules"]]
    return " ".join(parts) if parts else "sin reglas con datos"


def backtest_security(
    session: Session, settings: Settings, sid: str, ticker: str, market: str, start: date, end: date, *, step_sessions: int = 21, now: datetime | None = None, exchange: str | None = None,
    with_fundamentals: bool = False, fund_stride: int = 3,
) -> tuple[list[dict[str, Any]], dict[str, int]]:  # fmt: skip
    now = now or utc_now()
    ho = settings.validation.final_holdout
    cal = get_calendar(exchange or rt.MARKET_EXCHANGE.get(market) or "XNYS")
    svc = AnalyzerService(session, settings)
    md = load_market(session, sid, now)
    skipped = {"holdout": 0, "no_context": 0, "immature": 0}
    if md.series.n_bars == 0:
        return [], skipped
    idx = list(md.bars.index)
    last_bar = idx[-1]
    closes = md.bars["close"].astype(float)
    fund = with_fundamentals and has_fundamentals(svc, sid, now)
    rows: list[dict[str, Any]] = []
    zero = datetime.min.time()
    for n_date, d in enumerate([x for x in idx if start <= x <= end][::step_sessions]):
        if d < cal.first_session or d > cal.last_session:
            continue
        if ho.start <= d <= ho.end:
            skipped["holdout"] += 1
            continue
        price = float(closes.loc[d])
        at = cal.session_close(d)
        ctx = context_at(svc, sid, at, price)
        if ctx is None:
            skipped["no_context"] += 1
            continue
        ctx_f = (
            context_at(svc, sid, at, price, with_labels=True)
            if fund and n_date % fund_stride == 0
            else None
        )
        bars, _ = restated_bars(md, d, now)
        stamp = datetime.combine(d, zero, tzinfo=now.tzinfo)
        for h in rt.HORIZONS:
            h_end = d + relativedelta(months=h)
            if d < ho.start <= h_end:  # this horizon's window would reach the sealed holdout
                skipped["holdout"] += 1
                continue
            if h_end > last_bar:
                skipped["immature"] += 1
                continue
            win = bars[bars.index <= h_end]
            if win.empty:
                skipped["immature"] += 1
                continue
            rv = engine.review(engine.Position(price, 1.0, stamp, h), ctx, stamp)
            row: dict[str, Any] = {
                "ticker": ticker, "market": market, "date": d, "horizon": h, "price": price, "call": CALL[rv["recommendation"]], "score": rv["score"], "raws": {r["id"]: r["raw"] for r in rv["rules"]}, "why": _why(rv),
                "reason": rv["reason"], "ret_h": float(win["close"].iloc[-1]) / price - 1.0, "max_adverse": float(win["low"].min()) / price - 1.0, "max_favorable": float(win["high"].max()) / price - 1.0, "state": None,
            }  # fmt: skip
            if ctx_f is not None:
                rf = engine.review(engine.Position(price, 1.0, stamp, h), ctx_f, stamp)
                row |= {
                    "call_f": CALL[rf["recommendation"]],
                    "score_f": rf["score"],
                    "why_f": _why(rf),
                    "labels_f": {
                        "valuation": ctx_f.valuation_label,
                        "fundamentals": ctx_f.fundamentals_label,
                    },
                }
            lv = rt.levels(price, ctx, h)
            if rv["recommendation"] == "ADD" and lv is not None:
                end_stamp = datetime.combine(h_end, zero, tzinfo=now.tzinfo)
                o = rt.outcome(bars, price, lv["target_price"], lv["stop_price"], h_end, end_stamp)
                row |= {
                    "state": o["state"],
                    "target_pct": lv["target_pct"],
                    "stop_pct": lv["stop_pct"],
                    "outcome_date": o["when"],
                }
                row["sensitivity"] = {
                    k: rt.outcome(
                        bars,
                        price,
                        price * (1 + max(rt.PARAMS["target_floor"], k * lv["sigma_horizon"])),
                        lv["stop_price"],
                        h_end,
                        end_stamp,
                    )["state"]
                    for k in SENSITIVITY_K
                }
            rows.append(row)
    clear_cache()  # per-date engine caches hold full market frames
    return rows, skipped


# ───────────────────────────────────────────── analysis over rows (offline: no database)
def base_rates(rows: list[dict[str, Any]], h: int) -> tuple[int, float, float]:
    hs = [r for r in rows if r["horizon"] == h]
    n = len(hs)
    return (
        n,
        (sum(1 for r in hs if r["ret_h"] > 0) / n if n else float("nan")),
        (sum(1 for r in hs if r["ret_h"] < 0) / n if n else float("nan")),
    )


def stats_for(rows: list[dict[str, Any]], h: int, calls: dict[int, str]) -> dict[str, Any]:
    """Direction stats of a call assignment (index → UP/DOWN/NEUTRAL) over the rows of horizon ``h``."""
    hs = [(i, r) for i, r in enumerate(rows) if r["horizon"] == h]
    n, up_base, down_base = base_rates([r for _, r in hs], h)
    ups = [r for i, r in hs if calls[i] == "UP"]
    downs = [r for i, r in hs if calls[i] == "DOWN"]
    return {
        "n": n, "up_base": up_base, "down_base": down_base, "n_up": len(ups), "up_rate": (sum(1 for r in ups if r["ret_h"] > 0) / len(ups)) if ups else None, "up_mean": mean(r["ret_h"] for r in ups) if ups else None,
        "n_down": len(downs), "down_rate": (sum(1 for r in downs if r["ret_h"] < 0) / len(downs)) if downs else None, "down_mean": mean(r["ret_h"] for r in downs) if downs else None,
    }  # fmt: skip


V1 = "V1 solo puntuación (sin bloqueos)"
V10 = "V10 umbral de entrada 3.5"
V11 = "V11 umbral de entrada 1.5"
V12 = "V12 contrarian (invertir)"


def variant_calls(rows: list[dict[str, Any]], name: str) -> dict[int, str]:
    """Re-score every row under a variant of the rule (no new data needed). ``V0`` = the live rule (with its blockers)."""
    out: dict[int, str] = {}
    for i, r in enumerate(rows):
        w = engine.WEIGHTS[engine.horizon_bucket(r["horizon"])]
        raws = r["raws"]

        def score(
            include: tuple[str, ...] = RULE_IDS,
            _raws: dict[str, float] = raws,
            _w: dict[str, float] = w,
        ) -> float:
            return sum(_raws[k] * _w[k] for k in include if k in _raws)

        if name == "V0":
            out[i] = r["call"]
        elif name == V1:
            s = score()
            out[i] = "UP" if s >= engine.ADD_AT else "DOWN" if s <= engine.SELL_AT else "NEUTRAL"
        elif name in ABLATE:
            s = score(tuple(k for k in RULE_IDS if k != ABLATE[name]))
            out[i] = "UP" if s >= engine.ADD_AT else "DOWN" if s <= engine.SELL_AT else "NEUTRAL"
        elif name in SIGN_ONLY:
            raw = sum(raws.get(k, 0.0) for k in SIGN_ONLY[name])
            out[i] = "UP" if raw > 0 else "DOWN" if raw < 0 else "NEUTRAL"
        elif name in (V10, V11):
            s = score()
            add_at = 3.5 if name == V10 else 1.5
            out[i] = "UP" if s >= add_at else "DOWN" if s <= engine.SELL_AT else "NEUTRAL"
        elif name == V12:
            s = score()
            out[i] = "DOWN" if s >= engine.ADD_AT else "UP" if s <= engine.SELL_AT else "NEUTRAL"
        else:
            out[i] = "NEUTRAL"
    return out


ABLATE = {
    "V2 sin soporte": "support",
    "V3 sin tendencia corta": "trend",
    "V4 sin media 200": "long_trend",
    "V5 sin momentum 6 m": "momentum",
}
SIGN_ONLY = {
    "V6 solo momentum 6 m (signo)": ("momentum",),
    "V7 solo media 200 (signo)": ("long_trend",),
    "V8 tendencia + media 200 (signo)": ("trend", "long_trend"),
}
VARIANTS = [
    "V0",
    "V1 solo puntuación (sin bloqueos)",
    *ABLATE,
    *SIGN_ONLY,
    "V10 umbral de entrada 3.5",
    "V11 umbral de entrada 1.5",
    "V12 contrarian (invertir)",
]


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """Rank correlation (information coefficient); ``None`` with fewer than 30 pairs or a constant side."""
    import pandas as pd

    if len(xs) < 30:
        return None
    df = pd.DataFrame({"x": xs, "y": ys})
    if df["x"].nunique() < 2 or df["y"].nunique() < 2:
        return None
    return float(df["x"].rank().corr(df["y"].rank()))


def run_backtest(
    session: Session, settings: Settings, universe: dict[str, list[str]] | None = None, *, start: date = date(2012, 1, 2), step_sessions: int = 21, now: datetime | None = None, max_tickers: int | None = None,
    with_fundamentals: bool = True, out_dir: Any = None, progress: Any = None,
) -> tuple[str, dict[str, Any]]:  # fmt: skip
    """Backtest every ticker of the universe that has enough history; returns (plain-text report, machine summary). With ``out_dir`` the full per-decision log is written next to the report."""
    from pitquant.positions.backtest_report import render_full, write_detail

    now = now or utc_now()
    uni = universe or rt.load_universe()
    rows: list[dict[str, Any]] = []
    skipped = {"holdout": 0, "no_context": 0, "immature": 0}
    coverage: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    for market, tickers in uni.items():
        for t in tickers:
            base = t.upper().rsplit(".", 1)[0] if "." in t else t.upper()
            if base in seen or (
                max_tickers is not None
                and len([c for c in coverage.values() if c["used"]]) >= max_tickers
            ):
                continue
            seen.add(base)
            sid, why = rt.eligibility(session, base)
            if sid is None:
                coverage[base] = {
                    "market": market,
                    "used": False,
                    "why": why.split(":")[0],
                    "entry": t,
                }
                continue
            md_last = load_market(session, sid, now).last_session
            rs, sk = backtest_security(
                session,
                settings,
                sid,
                base,
                market,
                start,
                md_last or now.date(),
                step_sessions=step_sessions,
                now=now,
                exchange=rt.entry_exchange(t, market),
                with_fundamentals=with_fundamentals,
            )
            rows += rs
            for k, v in sk.items():
                skipped[k] += v
            fund = any("call_f" in r for r in rs)
            coverage[base] = {
                "market": market,
                "used": True,
                "entry": t,
                "n": len(rs),
                "first": str(min((r["date"] for r in rs), default="")),
                "last": str(md_last),
                "fundamentals": fund,
                "exchange": rt.entry_exchange(t, market),
            }
            if progress:
                progress(base, len(rs))
    text = render_full(rows, skipped, coverage, now, step_sessions, start)
    if out_dir is not None:
        write_detail(rows, out_dir, now)
    return text, {
        "version": BACKTEST_VERSION,
        "rows": len(rows),
        "skipped": skipped,
        "tickers": sum(1 for c in coverage.values() if c["used"]),
    }
