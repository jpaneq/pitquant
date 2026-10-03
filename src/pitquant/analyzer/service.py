# ruff: noqa: E501
"""Analyzer orchestration: ONE place that composes the engines for a (security_id, decision_at).

Frontend and API only render what this returns. ``decision_at`` is always explicit; the CURRENT view passes
``utc_now()`` from the caller. Results are plain dicts (JSON-ready) with ``as_of``, ``engine_version`` and
warnings. A TTL cache keyed by (security_id, decision_at truncated to the minute) lets the independent
endpoints share one computation without coupling them.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.analyzer import (
    analysis_v0,
    fundamental_v1,
    sr_v1,
    technical_v1,
    trade_plan_v0,
    valuation_v1,
)
from pitquant.analyzer.market import (
    MARKET_ENGINE_VERSION,
    MarketData,
    benchmark_security,
    freshness,
    load_market,
)
from pitquant.config.settings import Settings
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.db.models import (
    DataSource,
    IdentifierHistory,
    Issuer,
    ModelRow,
    Price,
    SecFiling,
    Security,
    SecurityIdentifierEvidence,
    SecurityProfile,
)
from pitquant.features.v0.engine import FEATURE_VERSION, load_facts

SERVICE_VERSION = "analyzer-service-1"
_CACHE: dict[tuple[str, str, str], tuple[float, Any]] = {}
_LOCK = threading.Lock()
TTL_SECONDS = 60.0


def _cached[T](key: tuple[str, str, str], fn: Callable[[], T]) -> T:
    now = time.monotonic()
    with _LOCK:
        hit = _CACHE.get(key)
        if hit and now - hit[0] < TTL_SECONDS:
            result: T = hit[1]
            return result
    val = fn()
    with _LOCK:
        _CACHE[key] = (now, val)
        if len(_CACHE) > 256:
            for k in sorted(_CACHE, key=lambda k: _CACHE[k][0])[:64]:
                _CACHE.pop(k, None)
    return val


def clear_cache() -> None:
    with _LOCK:
        _CACHE.clear()


def _tkey(decision_at: datetime) -> str:
    return decision_at.replace(second=0, microsecond=0).isoformat()


class AnalyzerService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.s = session
        self.cfg = settings

    # ── identity / profile ──────────────────────────────────────────────────────────────────────
    def security(self, security_id: str) -> dict[str, Any]:
        sec = self.s.get_one(Security, security_id)
        prof = self.s.scalars(
            select(SecurityProfile)
            .where(SecurityProfile.security_id == security_id)
            .order_by(SecurityProfile.ingested_at.desc())
        ).first()
        issuer = self.s.get(Issuer, sec.issuer_id) if sec.issuer_id else None
        tick = prof.current_ticker if prof else None
        if tick is None:
            from pitquant.db.models import TickerHistory

            tick = self.s.scalars(
                select(TickerHistory.ticker).where(
                    TickerHistory.security_id == security_id, TickerHistory.valid_to.is_(None)
                )
            ).first()
        ids = [
            f"{i.id_type}={i.value}"
            for i in self.s.scalars(
                select(IdentifierHistory).where(IdentifierHistory.security_id == security_id)
            )
        ]
        ids += sorted(
            {
                f"{e.id_type}={e.value} ({e.kind})"
                for e in self.s.scalars(
                    select(SecurityIdentifierEvidence).where(
                        SecurityIdentifierEvidence.security_id == security_id
                    )
                )
            }
        )
        name = prof.display_name if prof else sec.name
        return {
            "security_id": security_id,
            "issuer_id": sec.issuer_id,
            "ticker": tick,
            "name": name,
            "exchange": (prof.exchange if prof else None) or sec.exchange,
            "currency": sec.currency,
            "country": (prof.country if prof else None) or sec.country,
            "sector": prof.sector if prof else None,
            "industry": prof.industry if prof else None,
            "sector_source": "SEC SIC division / description (no GICS)" if prof else None,
            "profile_type": prof.profile_type if prof else "STANDARD_CORPORATE",
            "asset_class": "ETF"
            if "ETF" in name.upper().split() or "(ETF" in name.upper()
            else "Equity",
            "identifiers": ids,
            "issuer": issuer.name if issuer else None,
            "profile_source": prof.source if prof else None,
        }

    # ── engines (cached) ─────────────────────────────────────────────────────────────────────────
    def _md(self, sid: str, at: datetime) -> MarketData:
        return _cached((sid, _tkey(at), "md"), lambda: load_market(self.s, sid, at))

    def _bench(self, at: datetime) -> tuple[MarketData | None, str | None]:
        b = benchmark_security(self.s)
        if b is None:
            return None, None
        return self._md(b[0], at), b[1]

    def technicals(self, sid: str, at: datetime) -> dict[str, Any]:
        def go() -> dict[str, Any]:
            md = self._md(sid, at)
            bm, bt = (
                self._bench(at) if sid != (benchmark_security(self.s) or ("",))[0] else (None, None)
            )
            return technical_v1.compute_technicals(md, bm, bt)

        return _cached((sid, _tkey(at), "tech"), go)

    def fundamentals(self, sid: str, at: datetime) -> dict[str, Any]:
        def go() -> dict[str, Any]:
            md = self._md(sid, at)
            adj = float(md.series.split_adjusted["close"].iloc[-1]) if md.series.n_bars else None
            raw = float(md.bars["close"].iloc[-1]) if md.series.n_bars else None
            f = fundamental_v1.compute_fundamentals(
                self.s, sid, at, actions=md.actions, last_adj_price=adj, last_raw_price=raw
            )
            f.pop("_metrics", None)
            return f

        return _cached((sid, _tkey(at), "fund"), go)

    def valuation(self, sid: str, at: datetime) -> dict[str, Any]:
        def go() -> dict[str, Any]:
            md = self._md(sid, at)
            return valuation_v1.compute_valuation(md, load_facts(self.s, sid, at), at)

        return _cached((sid, _tkey(at), "val"), go)

    def fundamental_history(self, sid: str, at: datetime, period: str) -> dict[str, Any]:
        return _cached(
            (sid, _tkey(at), f"fhist-{period}"),
            lambda: fundamental_v1.history_series(self.s, sid, at, period),
        )

    def chart(self, sid: str, at: datetime, range_: str) -> dict[str, Any]:
        return _cached(
            (sid, _tkey(at), f"chart-{range_}"),
            lambda: technical_v1.chart_payload(self._md(sid, at), range_, at),
        )

    # ── quote ────────────────────────────────────────────────────────────────────────────────────
    def quote(self, sid: str, at: datetime) -> dict[str, Any]:
        md = self._md(sid, at)
        sec = self.s.get_one(Security, sid)
        if md.series.n_bars == 0:
            return {
                "status": "NO_DATA",
                "as_of": at.isoformat(),
                "badge": "NO_DATA",
                "reason": "no price bars known at as_of",
                "currency": sec.currency,
            }
        b = md.bars
        last, prev = b.iloc[-1], (b.iloc[-2] if len(b) > 1 else None)
        px, pc = float(last["close"]), (float(prev["close"]) if prev is not None else None)
        # a split between the two raw closes would make a raw change meaningless: compare on the split-adjusted basis
        adj = md.series.split_adjusted["close"]
        change = float(adj.iloc[-1] - adj.iloc[-2]) if len(adj) > 1 else None
        fr = freshness(md.last_close_at, at, md.exchange)
        cal = get_calendar(md.exchange)
        now_open = cal.is_session(
            at.astimezone(cal.session_close(cal.last_closed_session(at)).tzinfo).date()
        ) and cal.session_open(
            at.astimezone(cal.session_close(cal.last_closed_session(at)).tzinfo).date()
        ) <= at < cal.session_close(
            at.astimezone(cal.session_close(cal.last_closed_session(at)).tzinfo).date()
        )
        src_rows = self.s.execute(
            select(DataSource.name)
            .join(Price, Price.source_id == DataSource.source_id)
            .where(Price.security_id == sid, Price.bar_close_at == md.last_close_at)
        ).all()
        source = src_rows[0][0] if src_rows else None
        val = self.valuation(sid, at)
        return {
            "status": "OK",
            "as_of": at.isoformat(),
            "price": px,
            "previous_close": pc,
            "change": change,
            "change_pct": None
            if change is None or not len(adj) > 1
            else change / float(adj.iloc[-2]),
            "currency": sec.currency,
            "timestamp": md.last_close_at.isoformat() if md.last_close_at else None,
            "session": str(md.last_session),
            "kind": "EOD (completed session close)",
            "badge": fr["status"],
            "freshness": fr,
            "market_status": "OPEN" if now_open else "CLOSED",
            "source": source,
            "source_note": "EODHD public demo token (vendor / QA tier)"
            if source and source.startswith("EODHD")
            else None,
            "market_cap": val.get("market_cap"),
        }

    # ── composite ────────────────────────────────────────────────────────────────────────────────
    def eligibility(self, sid: str, at: datetime) -> dict[str, Any]:
        tech, fund = self.technicals(sid, at), self.fundamentals(sid, at)
        n_bars = tech.get("n_bars") or 0
        cov = fund.get("coverage") or {}
        fr = (cov.get("available", 0) / cov["expected"]) if cov.get("expected") else 0.0
        price_ok, price_some = n_bars >= 252, n_bars >= 60
        fund_ok, fund_some = fr >= 0.6, fr > 0
        reasons = []
        if not price_ok:
            reasons.append(f"price history {n_bars} bars (< 252 for the main technicals)")
        if not fund_ok:
            reasons.append(f"fundamental coverage {fr:.0%} (< 60%)")
        if price_ok and fund_ok:
            level = "FULL"
        elif (price_some and fund_ok) or (price_ok and fund_some):
            level = "PARTIAL"
        elif price_ok:
            level = "TECHNICAL_ONLY"
        elif fund_ok and not price_some:
            level = "FUNDAMENTAL_ONLY"
        elif price_some or fund_some:
            level = "PARTIAL"
        else:
            level = "INSUFFICIENT"
        return {
            "analyzer_eligibility": level,
            "reasons": reasons,
            "n_bars": n_bars,
            "fundamental_coverage": round(fr, 3),
            "note": "ANALYZER_ELIGIBLE is independent of BACKTEST_ELIGIBLE and of index membership",
        }

    def analysis(self, sid: str, at: datetime) -> dict[str, Any]:
        def go() -> dict[str, Any]:
            sec = self.security(sid)
            tech, fund, val = (
                self.technicals(sid, at),
                self.fundamentals(sid, at),
                self.valuation(sid, at),
            )
            md = self._md(sid, at)
            fr = freshness(md.last_close_at, at, md.exchange)
            a = analysis_v0.build_analysis(tech, fund, val, fr, sec["profile_type"])
            a["as_of"] = at.isoformat()
            a["engine_versions"] = self.versions()
            return a

        return _cached((sid, _tkey(at), "analysis"), go)

    def trade_plan(self, sid: str, at: datetime) -> dict[str, Any]:
        return trade_plan_v0.build_trade_plan(self.technicals(sid, at), at.isoformat())

    def explain(self, sid: str, at: datetime, panel: str) -> dict[str, Any]:
        """Provenance of one panel: what it used, from which source tier, with which rules (ADR-0030)."""
        if panel not in ("analysis", "trade-plan"):
            raise ValueError("panel must be 'analysis' or 'trade-plan'")
        md = self._md(sid, at)
        tech = self.technicals(sid, at)
        out: dict[str, Any] = {
            "panel": panel,
            "decision_at": at.isoformat(),
            "engine_versions": self.versions(),
            "market_data": {
                "sources": md.sources,
                "bars": md.series.n_bars,
                "last_session": str(md.last_session) if md.last_session else None,
                "last_close_at": md.last_close_at.isoformat() if md.last_close_at else None,
                "series": "RAW OHLCV; split-adjusted for indicators; vendor adjusted_close is QA only",
                "corporate_actions_applied": tech.get("corporate_actions_applied", []),
            },
            "nature": "RULE_BASED explanation; not a prediction, not a recommendation, no BUY/HOLD/SELL",
            "prediction": "NOT_YET_VALIDATED",
        }
        if panel == "analysis":
            out["result"] = self.analysis(sid, at)
            out["fundamental_filings_used"] = self.filings(sid, at).get("filings", [])
        else:
            plan = self.trade_plan(sid, at)
            out["result"] = plan
            out["structure_used"] = tech.get("support_resistance")
            out["trend_context"] = tech.get("trend")
        return out

    def prediction(self, sid: str, at: datetime) -> dict[str, Any]:
        champion = self.s.scalars(select(ModelRow).where(ModelRow.role == "champion")).first()
        base = {
            "as_of": at.isoformat(),
            "model_status": "NOT_YET_VALIDATED",
            "champion": None,
            "horizons": {
                h: {
                    "expected_excess_return": None,
                    "p_outperform": None,
                    "quantiles": {"p10": None, "p25": None, "p50": None, "p75": None, "p90": None},
                    "confidence": None,
                    "calibration_quality": None,
                }
                for h in ("6M", "12M")
            },
            "ood": {"status": "NOT_EVALUATED"},
            "message": "No validated Champion model exists: no probabilities, expected returns or confidence are shown.",
        }
        if (
            champion is not None
        ):  # a champion row alone is not enough: promotion needs a calibrated, reviewed model (not implemented yet)
            base["registry_note"] = (
                f"registry has role=champion row {champion.model_id}, but no calibration gate is implemented: prediction stays disabled"
            )
        return base

    def versions(self) -> dict[str, str]:
        return {
            "market_series": MARKET_ENGINE_VERSION,
            "technical_engine_version": technical_v1.TECHNICAL_ENGINE_VERSION,
            "support_resistance_version": sr_v1.SR_VERSION,
            "fundamental_engine_version": fundamental_v1.FUNDAMENTAL_ENGINE_VERSION,
            "valuation_engine_version": valuation_v1.VALUATION_ENGINE_VERSION,
            "trade_plan_version": trade_plan_v0.TRADE_PLAN_VERSION,
            "analysis_score_version": analysis_v0.ANALYSIS_SCORE_VERSION,
            "feature_engine_version": FEATURE_VERSION,
            "model_version": "none",
        }

    def summary(self, sid: str, at: datetime) -> dict[str, Any]:
        sec, q, elig = self.security(sid), self.quote(sid, at), self.eligibility(sid, at)
        an = self.analysis(sid, at)
        tech, fund, val = (
            self.technicals(sid, at),
            self.fundamentals(sid, at),
            self.valuation(sid, at),
        )
        plan = self.trade_plan(sid, at)
        warnings = []
        if q.get("badge") == "STALE":
            warnings.append(
                f"price is STALE: {q['freshness']['sessions_behind']} completed sessions behind"
            )
        warnings += (tech.get("warnings") or [])[:3]
        if sec["profile_type"] != "STANDARD_CORPORATE":
            warnings.append("SPECIALIZED FUNDAMENTAL PROFILE NOT YET SUPPORTED")
        return {
            "as_of": at.isoformat(),
            "security": sec,
            "quote": q,
            "availability": {
                **elig,
                "technical": tech.get("status"),
                "fundamental": fund.get("status"),
                "valuation": val.get("status"),
                "trade_plan": plan.get("status"),
                "prediction": "NOT_YET_VALIDATED",
            },
            "simulation": {
                "enabled": q.get("status") != "NO_DATA" and tech.get("status") == "OK",
                "reason": None if tech.get("status") == "OK" else "PRICE_DATA_REQUIRED",
            },
            "summary": {k: v.get("label") for k, v in an["labels"].items()},
            "summary_detail": an["labels"],
            "positives": an["positives"],
            "risks": an["risks"],
            "warnings": warnings,
            "data_notice": self.data_notice(),
            "engine_versions": self.versions(),
        }

    def data_notice(self) -> dict[str, Any]:
        import os

        if os.environ.get("PITQUANT_E2E_FIXTURE") == "1":
            return {
                "live_reference": "FIXTURE",
                "required_env": None,
                "mode": "DEMO DATA · SYNTHETIC FIXTURE (not market data)",
            }
        tiingo = bool(os.environ.get("PITQUANT_TIINGO_API_KEY"))
        return {
            "live_reference": "CONFIGURED" if tiingo else "DATA SOURCE NOT CONFIGURED",
            "required_env": None if tiingo else "PITQUANT_TIINGO_API_KEY",
            "mode": "EOD from persisted bars (EODHD public demo token for AAPL/MSFT/VTI)"
            if not tiingo
            else "Tiingo configured (adapter available)",
        }

    # ── filings / data quality / report ──────────────────────────────────────────────────────────
    def filings(self, sid: str, at: datetime, limit: int = 8) -> dict[str, Any]:
        sec = self.s.get_one(Security, sid)
        rows = self.s.scalars(
            select(SecFiling)
            .where(
                ((SecFiling.security_id == sid) | (SecFiling.issuer_id == sec.issuer_id))
                if sec.issuer_id
                else (SecFiling.security_id == sid)
            )
            .where(
                SecFiling.available_at <= at,
                SecFiling.form.in_(["10-K", "10-Q", "8-K", "10-K/A", "10-Q/A"]),
            )
            .order_by(SecFiling.filed_date.desc())
            .limit(limit * 3)
        ).all()
        out = []
        for f in rows[:limit]:
            link = (
                f"https://www.sec.gov/Archives/edgar/data/{int(f.cik)}/{f.accession_number.replace('-', '')}/{f.primary_document}"
                if f.primary_document
                else None
            )
            out.append(
                {
                    "form": f.form,
                    "filed_date": str(f.filed_date),
                    "accepted_at": f.accepted_at.isoformat(),
                    "available_at": f.available_at.isoformat(),
                    "report_period": str(f.report_period) if f.report_period else None,
                    "accession": f.accession_number,
                    "link": link,
                }
            )
        return {
            "as_of": at.isoformat(),
            "status": "OK" if out else "NO_DATA",
            "source": "SEC EDGAR (archived headers)",
            "filings": out,
        }

    def data_quality(self, sid: str, at: datetime) -> dict[str, Any]:
        md, tech, fund, val = (
            self._md(sid, at),
            self.technicals(sid, at),
            self.fundamentals(sid, at),
            self.valuation(sid, at),
        )
        fr = freshness(md.last_close_at, at, md.exchange)
        missing = []
        for grp in (
            "ttm",
            "profitability",
            "quality",
            "growth",
            "investment",
            "balance",
            "capital_allocation",
        ):
            for k, v in (fund.get(grp) or {}).items():
                if isinstance(v, dict) and "value" in v and v["value"] is None:
                    missing.append({"group": grp, "metric": k, "reason": v.get("reason")})
        an = self.analysis(sid, at)
        cov = fund.get("coverage") or {}
        return {
            "as_of": at.isoformat(),
            "overall": an["labels"]["data_quality"],
            "panels": {
                "price": {
                    "quality": "HIGH"
                    if fr["status"] == "EOD" and (tech.get("n_bars") or 0) >= 252
                    else "MEDIUM"
                    if (tech.get("n_bars") or 0) >= 60
                    else "INSUFFICIENT",
                    "sources": md.sources,
                    "freshness": fr,
                    "n_bars": tech.get("n_bars"),
                    "first_bar": str(md.bars.index[0]) if len(md.bars) else None,
                    "last_bar": str(md.last_session),
                },
                "fundamentals": {
                    "quality": "HIGH"
                    if cov.get("expected") and cov["available"] / cov["expected"] >= 0.8
                    else "MEDIUM"
                    if cov.get("available")
                    else "INSUFFICIENT",
                    "coverage": cov,
                    "latest_period": fund.get("latest_period"),
                    "latest_filing_available_at": fund.get("latest_filing_available_at"),
                    "source": "SEC EDGAR normalized facts",
                    "missing_metrics": missing[:20],
                },
                "valuation": {
                    "status": val.get("status"),
                    "own_history_points": val.get("own_history_points"),
                    "peer_context": "NOT AVAILABLE",
                    "warnings": val.get("warnings"),
                },
                "technicals": {"status": tech.get("status"), "warnings": tech.get("warnings")},
            },
            "corporate_actions": (tech.get("corporate_actions_applied") or [])[-6:],
            "benchmark": (tech.get("relative_strength") or {}).get("benchmark"),
            "providers": self.providers(),
            "engine_versions": self.versions(),
        }

    def providers(self) -> list[dict[str, Any]]:
        import os

        rows = []
        for name, env in (
            ("Tiingo", "PITQUANT_TIINGO_API_KEY"),
            ("EODHD", "PITQUANT_EODHD_API_KEY"),
            ("Alpha Vantage", "PITQUANT_ALPHAVANTAGE_API_KEY"),
            ("Sharadar", "PITQUANT_SHARADAR_API_KEY"),
            ("SEC EDGAR (User-Agent)", "PITQUANT_SEC_USER_AGENT"),
        ):
            rows.append({"provider": name, "env_var": env, "configured": bool(os.environ.get(env))})
        rows.append(
            {
                "provider": "EODHD public demo token",
                "env_var": None,
                "configured": True,
                "note": "AAPL/MSFT/VTI only; vendor demo, not a production source",
            }
        )
        return rows

    def report(self, sid: str, at: datetime) -> dict[str, Any]:
        return {
            "report_version": "analyzer-report-1",
            "generated_for_as_of": at.isoformat(),
            "security": self.security(sid),
            "quote": self.quote(sid, at),
            "availability": self.eligibility(sid, at),
            "fundamentals": self.fundamentals(sid, at),
            "valuation": self.valuation(sid, at),
            "technicals": self.technicals(sid, at),
            "analysis": self.analysis(sid, at),
            "trade_plan": self.trade_plan(sid, at),
            "prediction": self.prediction(sid, at),
            "data_quality": self.data_quality(sid, at),
            "engine_versions": self.versions(),
            "disclaimer": "Structured analysis. Not investment advice. The trade plan is RULE_BASED and NOT BACKTEST VALIDATED; no prediction is shown without a validated Champion.",
        }


def _g(d: dict[str, Any], *keys: str) -> Any:
    cur: Any = d
    for k in keys:
        cur = cur.get(k) if isinstance(cur, dict) else None
    return cur.get("value") if isinstance(cur, dict) else cur


def _fmt(x: Any, pct: bool = False, money: bool = False) -> str:
    if x is None:
        return "—"
    if pct:
        return f"{x * 100:.1f}%"
    if money:
        a = abs(x)
        return (
            f"{x / 1e12:.2f}T"
            if a >= 1e12
            else f"{x / 1e9:.2f}B"
            if a >= 1e9
            else f"{x / 1e6:.1f}M"
            if a >= 1e6
            else f"{x:,.2f}"
        )
    return f"{x:.2f}" if isinstance(x, float) else str(x)


def report_markdown(r: dict[str, Any]) -> str:
    s, q, f, v, t, a, p = (
        r["security"],
        r["quote"],
        r["fundamentals"],
        r["valuation"],
        r["technicals"],
        r["analysis"],
        r["trade_plan"],
    )

    g = _g

    L = [
        f"# {s['name']} ({s['ticker']}) — PITQuant Analyzer report",
        "",
        f"*as_of `{r['generated_for_as_of']}` · {r['disclaimer']}*",
        "",
        "## Quote",
        f"- Price **{_fmt(q.get('price'))} {q.get('currency')}** ({_fmt(q.get('change_pct'), pct=True)}), previous close {_fmt(q.get('previous_close'))}; session {q.get('session')}; badge **{q.get('badge')}**; source {q.get('source')}; market cap {_fmt(q.get('market_cap'), money=True)}",
        "",
        "## Analysis summary (rule-based, not a prediction)",
    ]
    for k, d in a["labels"].items():
        L.append(
            f"- {k}: **{d.get('label')}**"
            + (f" (coverage {d['coverage']})" if d.get("coverage") else "")
        )
    L += (
        ["", "### Positives"]
        + [f"- {x['rendered_text']}" for x in a["positives"]]
        + ["", "### Risks"]
        + [f"- {x['rendered_text']}" for x in a["risks"]]
    )
    L += [
        "",
        "## Fundamentals (TTM)",
        f"- Revenue {_fmt(g(f, 'ttm', 'revenue'), money=True)} · Operating income {_fmt(g(f, 'ttm', 'operating_income'), money=True)} · Net income {_fmt(g(f, 'ttm', 'net_income'), money=True)} · FCF {_fmt(g(f, 'ttm', 'fcf'), money=True)}",
        f"- Operating margin {_fmt(g(f, 'profitability', 'operating_margin'), pct=True)} · FCF margin {_fmt(g(f, 'profitability', 'fcf_margin'), pct=True)} · ROA {_fmt(g(f, 'profitability', 'roa'), pct=True)} · ROE {_fmt(g(f, 'profitability', 'roe'), pct=True)}",
        f"- Revenue growth YoY {_fmt(g(f, 'growth', 'revenue_yoy'), pct=True)} · 3Y CAGR {_fmt(g(f, 'growth', 'revenue_cagr3'), pct=True)}",
        f"- Latest period {f.get('latest_period')}; coverage {f.get('coverage')}",
        "",
        "## Valuation",
        f"- P/E {_fmt(g(v, 'current', 'pe'))} · P/S {_fmt(g(v, 'current', 'price_to_sales'))} · P/B {_fmt(g(v, 'current', 'price_to_book'))} · FCF yield {_fmt(g(v, 'current', 'fcf_yield'), pct=True)} · EV/Sales {_fmt(g(v, 'current', 'ev_to_sales'))}",
    ]
    own = v.get("own_history") or {}
    for m, d in own.items():
        if d.get("percentile") is not None:
            L.append(
                f"- {m}: {d['percentile']:.0f}th percentile of its own {d['window_years']}-year history ({d['sample_count']} points)"
            )
    L += [
        "",
        "## Technicals",
        f"- Trend **{(t.get('trend') or {}).get('state')}** (score {(t.get('trend') or {}).get('score')})",
    ]
    for e in (t.get("trend") or {}).get("evidence", []):
        if e.get("available"):
            L.append(f"  - {e['text']}")
    ind = t.get("indicators") or {}
    L += [
        f"- SMA20/50/200: {_fmt(ind.get('sma20'))} / {_fmt(ind.get('sma50'))} / {_fmt(ind.get('sma200'))} · RSI14 {_fmt(ind.get('rsi14'))} · ATR14 {_fmt(ind.get('atr14'))} ({_fmt(ind.get('atr14_pct'), pct=True)}) · ADX14 {_fmt(ind.get('adx14'))}",
        f"- Momentum: 3M {_fmt((t.get('momentum') or {}).get('ret63'), pct=True)} · 6M {_fmt((t.get('momentum') or {}).get('ret126'), pct=True)} · 12M {_fmt((t.get('momentum') or {}).get('ret252'), pct=True)}; 52w-high distance {_fmt((t.get('momentum') or {}).get('distance_52w_high'), pct=True)}",
        f"- Risk: vol63 {_fmt((t.get('risk') or {}).get('vol63'), pct=True)} · max drawdown 12M {_fmt((t.get('risk') or {}).get('max_drawdown252'), pct=True)} · beta {_fmt((t.get('risk') or {}).get('beta252'))}",
    ]
    for kind in ("supports", "resistances"):
        for z in (t.get("support_resistance") or {}).get(kind, []):
            L.append(
                f"- {kind[:-1]} zone {z['lower']:.2f}–{z['upper']:.2f} (touches {z['touches']}, strength {z['strength']}, {z['distance_pct'] * 100:+.1f}%)"
            )
    L += [
        "",
        "## Trade plan — RULE_BASED · NOT BACKTEST VALIDATED",
        f"- Status: {p.get('status')}" + (f" — {p['reason']}" if p.get("reason") else ""),
    ]
    for st in p.get("setups", []):
        L.append(
            f"- {st['type']} / {st['profile']}: entry {st['entry']:.2f}, stop {st['stop']:.2f} ({st['stop_distance_pct'] * 100:.1f}%, {st['stop_distance_atr']:.1f} ATR), 1.5R {st['r_targets'][0]['price']:.2f}, 2R {st['r_targets'][1]['price']:.2f}, 3R {st['r_targets'][2]['price']:.2f}"
        )
    L += [
        "",
        "## Prediction",
        f"- {r['prediction']['model_status']}: {r['prediction']['message']}",
        "",
        "## Data quality",
        f"- Overall {r['data_quality']['overall'].get('label')}; price source(s) {r['data_quality']['panels']['price']['sources']}",
        "",
        "## Engine versions",
        "",
    ] + [f"- {k}: `{v_}`" for k, v_ in r["engine_versions"].items()]
    return "\n".join(L) + "\n"
