# ruff: noqa: E501
"""Daily forward paper test of the rule-based Trade Plan over several stocks (ADR-0040).

One FORWARD_PAPER run of ``TRADE_PLAN_DAILY_V0`` (TRADE_PLAN_ONLY family) over a frozen universe. Every call is one forward tick at the SERVER clock: it decides once per security per
daily period (idempotent), opens AUTO_PAPER simulations through the existing authority path, lets the frozen simulation engine move them with new bars, and appends a ``StrategyRunResult``.
Nothing is back-dated and nothing here predicts: PREDICTION_ONLY/HYBRID stay disabled and the Prediction Engine stays NOT_YET_VALIDATED.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pitquant.analyzer.market import benchmark_security
from pitquant.analyzer.search import search
from pitquant.analyzer.service import AnalyzerService
from pitquant.config.settings import Settings, get_settings
from pitquant.db.models import Price
from pitquant.db.models_lab import StrategyDecision, StrategyDefinition, StrategyRun
from pitquant.strategy import service as strat
from pitquant.strategy.evaluation import evaluate_run
from pitquant.strategy.spec import StrategyError, preset_trade_plan_only, save_strategy

DAILY_STRATEGY_ID = "TRADE_PLAN_DAILY_V0"
MIN_BARS = 250


def ticker_of(session: Session, security_id: str) -> str:
    """The ticker the Analyzer shows (profile first, then the dated ticker history)."""
    sec = AnalyzerService(session, get_settings()).security(security_id)
    return str(sec.get("ticker") or security_id[:8])


def resolve_universe(session: Session, tickers: list[str] | None) -> list[str]:
    """Explicit tickers (exact match only) or, by default, every security with enough real price history except the benchmark proxy."""
    if tickers:
        out: list[str] = []
        for t in tickers:
            found: list[dict[str, Any]] = search(session, t, limit=5)["results"]  # type: ignore[assignment]
            hits = [h for h in found if h["match_type"] in ("EXACT", "IDENTIFIER")]
            if len(hits) != 1:
                raise StrategyError(f"cannot resolve {t!r} to exactly one security")
            out.append(str(hits[0]["security_id"]))
        return sorted(set(out))
    bench = benchmark_security(session)
    rows = session.execute(
        select(Price.security_id).group_by(Price.security_id).having(func.count() >= MIN_BARS)
    )
    return sorted(str(sid) for (sid,) in rows if not bench or sid != bench[0])


def ensure_daily_run(
    session: Session, settings: Settings, universe: list[str]
) -> tuple[StrategyRun, bool]:
    """Reuse the ACTIVE run when its universe is the same; otherwise stop it and open a new one (a run's universe is frozen)."""
    runs = list(
        session.scalars(
            select(StrategyRun)
            .where(
                StrategyRun.strategy_id == DAILY_STRATEGY_ID,
                StrategyRun.run_kind == "FORWARD_PAPER",
            )
            .order_by(StrategyRun.created_at.desc())
        )
    )
    for r in runs:
        if strat.run_status(session, r) == "ACTIVE":
            if sorted(r.universe) == sorted(universe):
                return r, False
            strat.stop_run(session, r)
    row = session.scalars(
        select(StrategyDefinition)
        .where(StrategyDefinition.strategy_id == DAILY_STRATEGY_ID)
        .order_by(StrategyDefinition.strategy_version.desc())
    ).first()
    if row is None:
        row = save_strategy(session, preset_trade_plan_only(DAILY_STRATEGY_ID), "daily-routine")
    return strat.create_run(session, settings, row, "FORWARD_PAPER", universe), True


def daily_test(
    session: Session,
    settings: Settings,
    tickers: list[str] | None = None,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    """One idempotent daily step. ``as_of`` exists for tests only; the CLI never passes it."""
    universe = resolve_universe(session, tickers)
    if not universe:
        raise StrategyError("no security with enough price history: ingest market data first")
    run, created = ensure_daily_run(session, settings, universe)
    decisions = strat.forward_tick(session, settings, run, as_of)
    result = evaluate_run(session, settings, run, as_of or strat.CLOCK())
    names = {sid: ticker_of(session, sid) for sid in universe}
    return {
        "run_id": run.run_id, "run_created": created, "strategy": f"{run.strategy_id} v{run.strategy_version}", "activated_at": run.activated_at.isoformat() if run.activated_at else None,
        "universe": [names[s] for s in universe], "new_decisions": [{"ticker": names[d.security_id], "decision": d.decision, "decision_at": d.decision_at.isoformat(), "reasons_failed": d.rules_failed} for d in decisions],
        "n_decisions_total": session.scalar(select(func.count()).select_from(StrategyDecision).where(StrategyDecision.run_id == run.run_id)),
        "trades": result.metrics["trades"], "portfolio": result.metrics["portfolio"], "excess_vs_buy_and_hold": result.metrics["excess_vs_buy_and_hold"], "flags": result.flags,
        "label": "RULE_BASED_NOT_BACKTEST_VALIDATED · FORWARD PAPER · NO REAL MONEY",
    }  # fmt: skip
