# ruff: noqa: E501
"""Position review V0: should a simulated position be ADDED to, HELD or SOLD, given the user's horizon in months? (ADR-0041)

A transparent, deterministic RULE ENGINE. It is NOT a prediction and NOT backtest-validated: no probability, no expected return, nothing inferred from a trained model. Each rule reads one
measured fact (trend, long-term trend, momentum, valuation, fundamentals, nearest support) and adds a signed contribution scaled by a horizon-dependent weight: short horizons care about
the price tape, long horizons about the long trend, valuation and fundamentals. Hard rules (protective stop, target reached, horizon reached) can override the score. Every output lists the
rules that fired so the user can disagree with any of them. The weights are UNVALIDATED_STRATEGY_PARAMETER values: changing them is a new engine version.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

ENGINE_VERSION = "position-review-v0"
LABEL = "RULE_BASED · NOT BACKTEST VALIDATED · NOT A PREDICTION"
DAYS_PER_MONTH = 30.44
SELL_AT, ADD_AT = -2.0, 2.5
OVEREXTENDED_ATR = 3.0
WEIGHTS: dict[str, dict[str, float]] = {
    "SHORT": {"trend": 1.0, "long_trend": 0.5, "momentum": 0.5, "valuation": 0.25, "fundamentals": 0.25, "support": 1.0},
    "MEDIUM": {"trend": 0.75, "long_trend": 1.0, "momentum": 1.0, "valuation": 1.0, "fundamentals": 1.0, "support": 0.75},
    "LONG": {"trend": 0.5, "long_trend": 1.5, "momentum": 1.0, "valuation": 1.5, "fundamentals": 1.5, "support": 0.5},
}  # fmt: skip
TREND_RAW = {
    "STRONG_UPTREND": 2.0,
    "UPTREND": 1.0,
    "SIDEWAYS": 0.0,
    "MIXED": 0.0,
    "DOWNTREND": -1.0,
    "STRONG_DOWNTREND": -2.0,
}
VALUATION_RAW = {"Cheap": 1.0, "Fair": 0.0, "Expensive": -1.0}
FUNDAMENTAL_RAW = {"Strong": 1.0, "Moderate": 0.0, "Weak": -1.0}


def horizon_bucket(months: int) -> str:
    return "SHORT" if months <= 3 else "MEDIUM" if months <= 8 else "LONG"


@dataclass
class Context:
    """Normalised facts about the asset at review time (built by the equity or BTC adapter). ``None`` = not available: that rule is skipped, never guessed."""

    price: float
    atr14: float | None = None
    trend_state: str | None = None  # STRONG_UPTREND … STRONG_DOWNTREND
    close_vs_sma200: float | None = None  # fraction
    close_vs_sma50: float | None = None
    ret_6m: float | None = None
    rsi14: float | None = None
    valuation_label: str | None = None  # Cheap | Fair | Expensive (equities only)
    fundamentals_label: str | None = None  # Strong | Moderate | Weak (equities only)
    support_lower: float | None = None  # nearest confirmed support zone below the price
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Position:
    avg_cost: float
    quantity: float
    opened_at: datetime
    horizon_months: int
    target_return: float | None = None
    stop_price: float | None = None


def _rule(rid: str, label: str, value: Any, raw: float, weight: float, text: str) -> dict[str, Any]:
    return {
        "id": rid,
        "label": label,
        "value": value,
        "raw": raw,
        "weight": weight,
        "contribution": round(raw * weight, 4),
        "text": text,
    }


def review(pos: Position, ctx: Context, now: datetime) -> dict[str, Any]:
    bucket = horizon_bucket(pos.horizon_months)
    w = WEIGHTS[bucket]
    elapsed = max((now - pos.opened_at).total_seconds() / 86400 / DAYS_PER_MONTH, 0.0)
    remaining = pos.horizon_months - elapsed
    pnl = ctx.price / pos.avg_cost - 1.0
    rules: list[dict[str, Any]] = []
    if ctx.trend_state in TREND_RAW:
        raw = TREND_RAW[ctx.trend_state]
        rules.append(
            _rule(
                "trend",
                "Tendencia",
                ctx.trend_state,
                raw,
                w["trend"],
                f"Tendencia {ctx.trend_state.lower().replace('_', ' ')}: {'a favor' if raw > 0 else 'en contra' if raw < 0 else 'sin dirección clara'}.",
            )
        )
    if ctx.close_vs_sma200 is not None:
        raw = 1.0 if ctx.close_vs_sma200 > 0 else -1.0
        rules.append(
            _rule(
                "long_trend",
                "Tendencia larga (media 200)",
                round(ctx.close_vs_sma200, 4),
                raw,
                w["long_trend"],
                f"El precio está {'por encima' if raw > 0 else 'por debajo'} de su media de 200 sesiones ({ctx.close_vs_sma200:+.1%}).",
            )
        )
    if ctx.ret_6m is not None:
        raw = 1.0 if ctx.ret_6m > 0 else -1.0
        rules.append(
            _rule(
                "momentum",
                "Momentum 6 meses",
                round(ctx.ret_6m, 4),
                raw,
                w["momentum"],
                f"Rentabilidad de los últimos 6 meses {ctx.ret_6m:+.1%}.",
            )
        )
    if ctx.valuation_label in VALUATION_RAW:
        raw = VALUATION_RAW[ctx.valuation_label]
        rules.append(
            _rule(
                "valuation",
                "Valoración vs su historia",
                ctx.valuation_label,
                raw,
                w["valuation"],
                f"Valoración {ctx.valuation_label.lower()} frente a su propia historia.",
            )
        )
    if ctx.fundamentals_label in FUNDAMENTAL_RAW:
        raw = FUNDAMENTAL_RAW[ctx.fundamentals_label]
        rules.append(
            _rule(
                "fundamentals",
                "Fundamentales",
                ctx.fundamentals_label,
                raw,
                w["fundamentals"],
                f"Fundamentales {ctx.fundamentals_label.lower()} según las reglas V0.",
            )
        )
    if ctx.support_lower is not None and ctx.atr14:
        broke = ctx.price < ctx.support_lower - 0.5 * ctx.atr14
        rules.append(
            _rule(
                "support",
                "Soporte cercano",
                round(ctx.support_lower, 4),
                -2.0 if broke else 0.0,
                w["support"],
                "El precio ha perdido el soporte más cercano."
                if broke
                else "El soporte cercano se mantiene.",
            )
        )
    score = round(sum(r["contribution"] for r in rules), 4)

    hard: list[dict[str, Any]] = []
    if pos.stop_price is not None and ctx.price <= pos.stop_price:
        hard.append(
            {
                "id": "STOP_HIT",
                "text": f"El precio ({ctx.price:,.2f}) ha tocado tu stop protector ({pos.stop_price:,.2f}): la regla manda salir.",
            }
        )
    target_met = pos.target_return is not None and pnl >= pos.target_return
    horizon_reached = remaining <= 0
    reco, why = "HOLD", "Ninguna regla pide actuar: mantener."
    if hard:
        reco, why = "SELL", hard[0]["text"]
    elif target_met and (horizon_reached or score < 1.5):
        reco, why = (
            "SELL",
            f"Objetivo de {pos.target_return:.0%} cumplido ({pnl:+.1%})"
            + (
                " y el horizonte ha vencido."
                if horizon_reached
                else " y la tendencia ya no es claramente fuerte: asegurar beneficio."
            ),
        )
    elif target_met:
        reco, why = (
            "HOLD",
            f"Objetivo de {pos.target_return:.0%} cumplido, pero la señal sigue fuerte (puntuación {score:+.1f}): mantener y vigilar el stop.",
        )
    elif horizon_reached and ((pnl > 0 and score < 1.0) or (pnl <= 0 and score < 0)):
        reco, why = (
            "SELL",
            f"El horizonte de {pos.horizon_months} meses ha vencido y la señal no justifica seguir (puntuación {score:+.1f}).",
        )
    elif horizon_reached:
        reco, why = (
            "HOLD",
            f"El horizonte de {pos.horizon_months} meses ha vencido, pero la señal sigue a favor (puntuación {score:+.1f}): revisa si ampliar el plazo.",
        )
    elif score <= SELL_AT:
        reco, why = (
            "SELL",
            f"Las reglas pesan en contra para un horizonte {bucket.lower()} (puntuación {score:+.1f} ≤ {SELL_AT:+.1f}).",
        )
    elif score >= ADD_AT:
        trend_raw = TREND_RAW.get(ctx.trend_state or "", 0.0)
        ext = (
            (ctx.price - (ctx.price / (1 + ctx.close_vs_sma50))) / ctx.atr14
            if ctx.close_vs_sma50 is not None and ctx.atr14
            else None
        )
        blockers = []
        if trend_raw < 1:
            blockers.append("la tendencia no es claramente alcista")
        if ext is not None and ext > OVEREXTENDED_ATR:
            blockers.append(f"el precio está estirado ({ext:.1f} ATR sobre su media de 50)")
        if ctx.rsi14 is not None and ctx.rsi14 > 70:
            blockers.append(f"RSI {ctx.rsi14:.0f} por encima de 70")
        if target_met:
            blockers.append("el objetivo ya está cumplido")
        if remaining < 1:
            blockers.append("queda menos de un mes de horizonte")
        if blockers:
            reco, why = (
                "HOLD",
                f"Puntuación favorable ({score:+.1f}) pero no se amplía porque "
                + "; ".join(blockers)
                + ".",
            )
        else:
            reco, why = (
                "ADD",
                f"Puntuación favorable ({score:+.1f} ≥ {ADD_AT:+.1f}) con tendencia alcista, sin estiramiento y con horizonte por delante: se podría ampliar.",
            )
    return {
        "engine_version": ENGINE_VERSION, "label": LABEL, "recommendation": reco, "reason": why, "score": score, "thresholds": {"sell_at_or_below": SELL_AT, "add_at_or_above": ADD_AT},
        "horizon_bucket": bucket, "weights": w, "rules": rules, "hard_rules": hard,
        "position": {"avg_cost": pos.avg_cost, "quantity": pos.quantity, "price": ctx.price, "pnl_pct": pnl, "pnl_value": (ctx.price - pos.avg_cost) * pos.quantity, "months_elapsed": round(elapsed, 2), "months_remaining": round(remaining, 2), "horizon_months": pos.horizon_months, "target_return": pos.target_return, "target_met": target_met, "stop_price": pos.stop_price},
        "missing_rules": [k for k in ("trend", "long_trend", "momentum", "valuation", "fundamentals", "support") if k not in {r["id"] for r in rules}],
        "disclaimer": "Reglas descriptivas con pesos sin validar: no es una predicción ni consejo de inversión.",
    }  # fmt: skip
