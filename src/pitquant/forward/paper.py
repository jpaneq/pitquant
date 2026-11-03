"""Read/update only simulations explicitly linked to a frozen pilot forecast."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from pitquant.config.settings import Settings
from pitquant.core.errors import PITQuantError
from pitquant.forward.engine import records
from pitquant.simulation.service import latest_outcome, update_simulation


def refresh(s: Session, cfg: Settings, now: datetime) -> list[dict[str, Any]]:
    from pitquant.btc.simulation import update as update_btc

    result = []
    for row in records(s, "SIMULATION_LINK"):
        sid = row.payload["simulation_id"]
        old = latest_outcome(s, sid)
        if old and old.is_closed:
            continue
        try:
            with s.begin_nested():
                if row.market == "BTC":
                    update_btc(s, sid, now)
                else:
                    update_simulation(s, cfg, sid, now)
            result.append({"simulation_id": sid, "status": "REVIEWED"})
        except (PITQuantError, ValueError) as exc:
            result.append({"simulation_id": sid, "status": "ERROR", "reason": str(exc)})
    return result


def statistics(s: Session, model_id: str) -> dict[str, Any]:
    links = [r for r in records(s, "SIMULATION_LINK") if r.payload["model_id"] == model_id]
    items = []
    for row in links:
        out = latest_outcome(s, row.payload["simulation_id"])
        items.append(
            {
                "simulation_id": row.payload["simulation_id"],
                "market": row.market,
                "state": out.state if out else "CREATED",
                "closed": bool(out and out.is_closed),
                "gross_return": out.realized_return if out else None,
                "max_drawdown": out.max_drawdown if out else None,
                "excess_vs_benchmark": out.excess_return_vs_benchmark if out else None,
            }
        )
    closed = [v for v in items if v["closed"] and v["gross_return"] is not None]
    enough = len(closed) >= 10
    wins = [v["gross_return"] for v in closed if v["gross_return"] > 0]
    losses = [v["gross_return"] for v in closed if v["gross_return"] <= 0]
    dd = [v["max_drawdown"] for v in closed if v["max_drawdown"] is not None]
    excess = [v["excess_vs_benchmark"] for v in closed if v["excess_vs_benchmark"] is not None]
    return {
        "total": len(items),
        "closed": sum(v["closed"] for v in items),
        "open": sum(not v["closed"] for v in items),
        "metrics_available": enough,
        "mean_win": float(np.mean(wins)) if enough and wins else None,
        "mean_loss": float(np.mean(losses)) if enough and losses else None,
        "worst_trade_drawdown": max(dd) if enough and dd else None,
        "mean_excess_vs_benchmark": float(np.mean(excess)) if enough and excess else None,
        "benchmark_n": len(excess),
        "items": items,
        "costs": "NOT_MODELED",
        "portfolio_return": None,
        "portfolio_drawdown": None,
        "note": "Per-trade gross statistics only; overlapping trades are not a funded portfolio. "
        "Aggregate metrics require at least 10 closed trades. Benchmark missing stays null.",
    }
