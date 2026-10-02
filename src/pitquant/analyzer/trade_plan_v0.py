# ruff: noqa: E501
"""TradePlanEngine V0 — RULE_BASED, NOT BACKTEST VALIDATED (docs/TRADE_PLAN_ENGINE_V0.md).

Long setups from market STRUCTURE only: confirmed support/resistance zones, ATR14 and the trend context.
Fundamentals never shape the geometry. No percent stops, no forecast, no leverage. Targets are SCENARIO
TARGETS (next structural resistance and 1.5R / 2R / 3R), not predictions.

Setups:
* PULLBACK: nearest support zone below the last close (<= 4 ATR away, >= 2 touches or rejection >= 1 ATR).
  Entry zone = [support.lower, support.upper + 0.25 ATR]; confluence if SMA/EMA lie within 0.75 ATR of the zone midpoint.
* BREAKOUT_RETEST: a resistance cleared by a COMPLETED close above upper + 0.25 ATR within 30 sessions;
  entry zone = the cleared zone (retest). Needs price within 2 ATR above the zone.
Stop = zone.lower - 0.5 ATR (the same for all profiles). Invalidation = zone.lower.
Profiles change ONLY the entry behaviour: Aggressive = limit at zone.upper; Base = reclaim (close above zone.upper + 0.25 ATR);
Conservative = reclaim + close above EMA20.
"""

from __future__ import annotations

import math
from typing import Any

TRADE_PLAN_VERSION = "trade-plan-v0.1"
VALIDATION_STATUS = "RULE_BASED_NOT_BACKTEST_VALIDATED"
STOP_ATR = 0.5


def _targets(entry: float, stop: float, resistances: list[dict[str, Any]]) -> dict[str, Any] | None:
    risk = entry - stop
    if risk <= 0:
        return None
    rt = [
        {
            "r_multiple": m,
            "price": entry + m * risk,
            "potential_pct": m * risk / entry,
            "label": "SCENARIO TARGET",
        }
        for m in (1.5, 2.0, 3.0)
    ]
    above = [z for z in resistances if z["lower"] > entry]
    structural = None
    if above:
        z = min(above, key=lambda x: x["lower"])
        structural = {
            "zone_lower": z["lower"],
            "zone_upper": z["upper"],
            "price": z["lower"],
            "potential_pct": z["lower"] / entry - 1.0,
            "r_multiple": (z["lower"] - entry) / risk,
            "label": "SCENARIO TARGET (next resistance)",
        }
    return {"risk_per_share": risk, "r_targets": rt, "structural_target": structural}


def _setup(
    kind: str,
    profile: str,
    entry: float,
    zone: dict[str, Any],
    atr: float,
    resistances: list[dict[str, Any]],
    confluence: list[str],
    conditions: list[str],
    close: float,
) -> dict[str, Any] | None:
    stop = zone["lower"] - STOP_ATR * atr
    t = _targets(entry, stop, resistances)
    if t is None:
        return None
    st = t["structural_target"]
    t1 = st["price"] if st and st["price"] > entry else t["r_targets"][0]["price"]
    t2 = max(t["r_targets"][2]["price"], t1 + t["risk_per_share"])
    return {
        "type": kind,
        "setup_type": kind,
        "profile": profile,
        "entry_zone": {
            "lower": zone["lower"],
            "upper": zone["upper"] + (0.25 * atr if kind == "PULLBACK" else 0.0),
        },
        "entry": entry,
        "invalidation_level": zone["lower"],
        "stop": stop,
        "risk_per_share": t["risk_per_share"],
        "stop_distance_pct": (entry - stop) / entry,
        "stop_distance_atr": (entry - stop) / atr,
        "structural_target": t["structural_target"],
        "r_targets": t["r_targets"],
        "target_1": t1,
        "target_2": t2,
        "risk_reward_1": (t1 - entry) / t["risk_per_share"],
        "risk_reward_2": (t2 - entry) / t["risk_per_share"],
        "rules_version": TRADE_PLAN_VERSION,
        "inputs": {
            "atr14": atr,
            "last_close_split_adjusted": close,
            "support_zone": {"lower": zone["lower"], "upper": zone["upper"]},
            "stop_rule": f"zone.lower - {STOP_ATR} ATR14",
            "target_rule": "target_1 = next structural resistance (else 1.5R); target_2 = 3R (>= target_1 + 1R)",
        },
        "explanation": (
            f"{kind} {profile}: entry {entry:.2f} inside/at the zone {zone['lower']:.2f}-{zone['upper']:.2f}; "
            f"the setup is invalid below {zone['lower']:.2f}; stop {stop:.2f} = zone.lower - {STOP_ATR} ATR14; "
            f"scenario targets {t1:.2f} / {t2:.2f}. Rule-based scenario, not a forecast and not validated."
        ),
        "confluence": confluence,
        "conditions": conditions,
        "distance_from_last_close_pct": entry / close - 1.0,
        "warnings": []
        if (entry - stop) / atr <= 6
        else ["stop is wider than 6 ATR: the structure is far from price"],
    }


def build_trade_plan(tech: dict[str, Any], decision_at_iso: str) -> dict[str, Any]:
    out: dict[str, Any] = {
        "as_of": decision_at_iso,
        "engine_version": TRADE_PLAN_VERSION,
        "validation_status": VALIDATION_STATUS,
        "label": "RULE_BASED · NOT YET BACKTEST VALIDATED",
        "setups": [],
        "warnings": [],
    }
    if tech.get("status") != "OK":
        out.update(status="NO_DATA", reason="no technical data")
        return out
    ind, sr = tech["indicators"], tech["support_resistance"]
    atr, close = ind.get("atr14"), tech.get("last_close_split_adjusted")
    state = (tech.get("trend") or {}).get("state")
    out["trend_context"] = {"state": state, "adx14": ind.get("adx14")}
    if not atr or not close:
        out.update(status="NO_VALID_SETUP", reason="ATR14 unavailable")
        return out
    if state in ("DOWNTREND", "STRONG_DOWNTREND", "INSUFFICIENT_HISTORY", None):
        out.update(
            status="NO_VALID_SETUP",
            reason=f"trend context {state}: no LONG setup is offered against / without a trend context",
        )
        return out
    sups, ress, broken = sr["supports"], sr["resistances"], sr.get("broken_resistances", [])
    mas = {k: ind.get(k) for k in ("sma20", "sma50", "sma200", "ema20", "ema50")}
    setups: list[dict[str, Any]] = []
    # BREAKOUT_RETEST first: a freshly cleared resistance is the more specific structure
    for z in broken:
        if z["distance_atr"] > 2.0:
            continue
        conf = [
            f"{k.upper()} within 0.75 ATR of the zone"
            for k, v in mas.items()
            if v and abs(v - z["midpoint"]) <= 0.75 * atr
        ]
        zone = {"lower": z["lower"], "upper": z["upper"]}
        for prof, entry, cond in (
            (
                "AGGRESSIVE",
                z["upper"],
                [f"price retests the cleared zone ({z['lower']:.2f}-{z['upper']:.2f}) and holds"],
            ),
            (
                "BASE",
                z["upper"] + 0.25 * atr,
                [f"completed close above {z['upper'] + 0.25 * atr:.2f} after the retest"],
            ),
            (
                "CONSERVATIVE",
                z["upper"] + 0.25 * atr,
                [
                    f"completed close above {z['upper'] + 0.25 * atr:.2f} after the retest",
                    "completed close above EMA20"
                    + (f" ({ind['ema20']:.2f})" if ind.get("ema20") else ""),
                ],
            ),
        ):
            s = _setup(
                "BREAKOUT_RETEST",
                prof,
                entry,
                zone,
                atr,
                ress,
                conf,
                [f"breakout confirmed: completed close above {z['trigger']:.2f}", *cond],
                close,
            )
            if s:
                setups.append(s)
        break
    cands = [z for z in sups if z["distance_atr"] <= 4.0 and z["touches"] >= 1]
    if cands:
        z = max(cands, key=lambda x: (x["strength"], -x["distance_atr"]))
        conf = [
            f"{k.upper()} within 0.75 ATR of the zone ({v:.2f})"
            for k, v in mas.items()
            if v and abs(v - z["midpoint"]) <= 0.75 * atr
        ]
        for prof, entry, cond in (
            (
                "AGGRESSIVE",
                z["upper"],
                [f"price trades into the support zone ({z['lower']:.2f}-{z['upper']:.2f})"],
            ),
            (
                "BASE",
                z["upper"] + 0.25 * atr,
                [f"completed close above {z['upper'] + 0.25 * atr:.2f} after touching the zone"],
            ),
            (
                "CONSERVATIVE",
                z["upper"] + 0.25 * atr,
                [
                    f"completed close above {z['upper'] + 0.25 * atr:.2f} after touching the zone",
                    "completed close above EMA20"
                    + (f" ({ind['ema20']:.2f})" if ind.get("ema20") else ""),
                ],
            ),
        ):
            s = _setup("PULLBACK", prof, entry, z, atr, ress, conf, cond, close)
            if s:
                setups.append(s)
    if not setups:
        out.update(
            status="NO_VALID_SETUP",
            reason="no confirmed support within 4 ATR and no fresh breakout retest",
        )
        return out
    out.update(status="SETUPS_AVAILABLE", setups=setups, last_close=close, atr14=atr)
    return out


def position_size(capital: float, risk_pct: float, entry: float, stop: float) -> dict[str, Any]:
    """risk_amount = capital * risk_pct; shares = floor(risk_amount / |entry - stop|); no leverage."""
    if capital <= 0 or not (0 < risk_pct <= 100) or entry <= 0 or stop <= 0 or entry == stop:
        return {
            "status": "INVALID_INPUT",
            "reason": "capital, risk %, entry and stop must be positive and entry != stop",
        }
    risk_amount = capital * risk_pct / 100.0
    rps = abs(entry - stop)
    shares = math.floor(risk_amount / rps)
    notional = shares * entry
    capped = False
    if notional > capital:  # no leverage by default
        shares = math.floor(capital / entry)
        notional = shares * entry
        capped = True
    return {
        "status": "OK",
        "risk_amount": risk_amount,
        "risk_per_share": rps,
        "shares": shares,
        "notional": notional,
        "notional_pct_of_capital": notional / capital,
        "actual_risk": shares * rps,
        "capped_by_capital_no_leverage": capped,
    }
