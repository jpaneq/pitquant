"""Read-only audit of daily-rule decisions; never tune rules or rewrite their history."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import numpy as np
from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.config.settings import Settings
from pitquant.core.timeutils import utc_now
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.db.models_routine import DailyPick
from pitquant.positions.routine import bars_after_entry, outcome


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    states = Counter(r["state"] for r in rows)
    closed = [r for r in rows if r["state"] not in ("IN_PROGRESS", "WAITING_FIRST_BAR", "NO_DATA")]
    returns = [r["return_pct"] for r in closed if r["return_pct"] is not None]
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r <= 0]
    return {
        "n": len(rows),
        "states": dict(states),
        "closed": len(closed),
        "pending": states["IN_PROGRESS"] + states["WAITING_FIRST_BAR"],
        "waiting_first_bar": states["WAITING_FIRST_BAR"],
        "no_data": states["NO_DATA"],
        "target_first": states["TARGET_HIT"],
        "stop_first": states["STOP_HIT"],
        "ambiguous": states["AMBIGUOUS_INTRABAR"],
        "target_rate_closed": states["TARGET_HIT"] / len(closed) if closed else None,
        "profitable_rate_closed": len(wins) / len(returns) if returns else None,
        "mean_closed_return": float(np.mean(returns)) if returns else None,
        "mean_winner": float(np.mean(wins)) if wins else None,
        "mean_loser": float(np.mean(losses)) if losses else None,
        "calendar_mature": sum(r["horizon_mature"] for r in rows),
        "stale_at_creation": sum(r.get("price_freshness_at_creation") == "STALE" for r in rows),
        "distinct_pick_ids": len({r["pick_id"] for r in rows}),
    }


def audit(s: Session, cfg: Settings, now: datetime | None = None) -> dict[str, Any]:
    now = now or utc_now()
    picks = list(
        s.scalars(
            select(DailyPick)
            .where(DailyPick.created_at <= now)
            .order_by(DailyPick.run_date, DailyPick.market)
        )
    )
    rows = []
    for pick in picks:
        cache = {}
        for decision in pick.decisions or []:
            hyp = decision.get("hypothetical") or {}
            entry = decision.get("entry_price") or hyp.get("entry_price")
            target = decision.get("target_price") or hyp.get("target_price")
            stop = decision.get("stop_price") or hyp.get("stop_price")
            h = int(decision["horizon_months"])
            end = pick.run_date + relativedelta(months=h)
            base = {
                "ref": f"R~{pick.pick_id}~{h}",
                "pick_id": pick.pick_id,
                "ticker": pick.ticker,
                "market": pick.market,
                "decision_date": str(pick.run_date),
                "horizon_months": h,
                "horizon_mature": now.date() >= end,
                "horizon_end": str(end),
                "action": decision["decision"],
                "score": decision.get("score"),
                "entry": entry,
                "target": target,
                "stop": stop,
                "planned_reward_risk": (
                    (target - entry) / (entry - stop)
                    if entry and target and stop and entry > stop
                    else None
                ),
                "price_freshness_at_creation": pick.price_freshness,
            }
            if not entry or not target or not stop or not decision.get("decided_at"):
                rows.append({**base, "state": "NO_DATA", "return_pct": None, "bars": 0})
                continue
            at = datetime.fromisoformat(decision["decided_at"])
            if at not in cache:
                position = SimpleNamespace(
                    asset_type="BTC" if pick.market == "BTC" else "EQUITY",
                    security_id=pick.security_id,
                )
                cache[at] = bars_after_entry(s, cfg, position, at, now)
            bars = cache[at]
            result = outcome(bars, float(entry), float(target), float(stop), end, now)
            if pick.market == "BTC":
                first_close = datetime.combine(
                    pick.run_date + timedelta(days=2), datetime.min.time(), UTC
                )
            else:
                cal = get_calendar("XMAD" if pick.market == "IBEX" else "XNYS")
                first_close = cal.session_close(
                    cal.next_session(cal.session_on_or_before(pick.run_date))
                )
            value = result["price"]
            rows.append(
                {
                    **base,
                    "state": result["state"]
                    if len(bars)
                    else ("WAITING_FIRST_BAR" if now < first_close else "NO_DATA"),
                    "return_pct": value / entry - 1 if value is not None else None,
                    "bars": result["bars_used"],
                    "last_bar": str(bars.index[-1]) if len(bars) else None,
                    "exit_date": str(result["when"]) if result["when"] else None,
                    "mae": result["max_adverse"],
                    "mfe": result["max_favorable"],
                }
            )
    buys = [r for r in rows if r["action"] == "BUY"]
    no = [r for r in rows if r["action"] == "NO_ORDER"]
    return {
        "as_of": now.isoformat(),
        "total_decisions": len(rows),
        "picks": len({r["pick_id"] for r in rows}),
        "routine_runs": len(picks),
        "first_date": str(min((p.run_date for p in picks), default="")),
        "last_date": str(max((p.run_date for p in picks), default="")),
        "buy": summarize(buys),
        "no_order_counterfactual": summarize(no),
        "by_market": {
            m: {
                "buy": summarize([r for r in buys if r["market"] == m]),
                "no_order": summarize([r for r in no if r["market"] == m]),
            }
            for m in sorted({r["market"] for r in rows})
        },
        "by_horizon": {
            str(h): {
                "buy": summarize([r for r in buys if r["horizon_months"] == h]),
                "no_order": summarize([r for r in no if r["horizon_months"] == h]),
            }
            for h in (1, 3, 6, 12, 24)
        },
        "findings": [
            f"{sum(r['price_freshness_at_creation'] == 'STALE' for r in buys)} of "
            f"{len(buys)} legacy BUY decisions used a quote labelled STALE; future entries "
            "require LIVE/EOD freshness, without rewriting those decisions.",
            "Five horizons per pick are correlated decisions, not five independent trades.",
            "A closed target/stop is a trade-plan result, not a mature directional forecast.",
            "Entry prices are legacy reference fills, not verified next-session fills.",
            "Costs not modeled; per-decision averages are not an investable portfolio return.",
            "No thresholds were optimized from these observations; old decisions remain immutable.",
        ],
        "rows": rows,
    }
