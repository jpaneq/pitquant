# ruff: noqa: E501
"""Visual trade viewer data (candles + trend + the planned entry / target / stop + what happened). READ-ONLY: it assembles what the routine and the Simulation Lab already stored; it computes nothing new about the strategy.

* One chart per decision of the daily routine (a BUY opens a paper position, a NO_ORDER is the counterfactual) or per Simulation Lab row.
* The levels are the ones frozen when the decision was made (never recomputed); the bars are the RAW daily bars known today. SMA50/SMA200 are context for the TREND, not signals.
* ``markers``: the decision, the entry fill and the exit (target / stop / expiry) when it happened. ``outcome.state`` says plainly whether it is still in progress.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pandas as pd
from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.analyzer.market import load_market
from pitquant.db.models_positions import PaperPosition
from pitquant.db.models_routine import DailyEvaluation, DailyPick, DailyVirtualEvaluation

CONTEXT_DAYS = 200
CLOSED = {
    "TARGET_HIT": "Objetivo cumplido",
    "STOP_HIT": "Stop tocado",
    "EXPIRED": "Horizonte vencido",
    "AMBIGUOUS_INTRABAR": "Ambigua (objetivo y stop en la misma barra)",
}


def btc_daily_bars(session: Session, now: datetime) -> pd.DataFrame:
    from pitquant.btc.contracts import Cohort
    from pitquant.btc.models import BTCDatum

    rows = session.scalars(
        select(BTCDatum)
        .where(
            BTCDatum.source == "BINANCE_SPOT",
            BTCDatum.metric == "spot",
            BTCDatum.cohort == Cohort.FORWARD_PAPER,
        )
        .order_by(BTCDatum.exchange_timestamp, BTCDatum.retrieved_at)
    )
    by_ts = {r.exchange_timestamp: r.payload for r in rows}  # last revision per bar
    recs = [
        (
            (ts - timedelta(days=1)).date(),
            p["open"],
            p["high"],
            p["low"],
            p["close"],
            p.get("volume", 0.0),
        )
        for ts, p in sorted(by_ts.items())
        if ts <= now
    ]  # a bar stamped 00:00 UTC closes the previous day
    return (
        pd.DataFrame(recs, columns=["date", "open", "high", "low", "close", "volume"]).set_index(
            "date"
        )
        if recs
        else pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    )


def equity_daily_bars(session: Session, security_id: str, now: datetime) -> pd.DataFrame:
    md = load_market(session, security_id, now)
    return (
        md.bars[["open", "high", "low", "close"]].astype(float)
        if not md.bars.empty
        else pd.DataFrame(columns=["open", "high", "low", "close"])
    )


def _series(bars: pd.DataFrame, start: date) -> dict[str, Any]:
    c = bars["close"].astype(float)
    out: dict[str, Any] = {}
    for n in (50, 200):
        s = c.rolling(n, min_periods=n).mean()
        out[f"sma{n}"] = [
            {"date": str(d), "value": float(v)} for d, v in s.items() if pd.notna(v) and d >= start
        ]
    cut = bars[bars.index >= start]
    out["bars"] = [
        {
            "date": str(d),
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
        }
        for d, r in cut.iterrows()
    ]
    return out


def _level(label: str, price: float | None, kind: str) -> list[dict[str, Any]]:
    return [] if price is None else [{"label": label, "price": float(price), "kind": kind}]


def list_trades(session: Session, days: int = 120) -> list[dict[str, Any]]:
    since = datetime.now(UTC).date() - timedelta(days=days)
    out: list[dict[str, Any]] = []
    for p in session.scalars(
        select(DailyPick)
        .where(DailyPick.run_date >= since)
        .order_by(DailyPick.run_date.desc(), DailyPick.market)
    ):
        for d in p.decisions or []:
            out.append(
                {
                    "ref": f"R~{p.pick_id}~{d['horizon_months']}",
                    "kind": "ROUTINE",
                    "date": str(p.run_date),
                    "market": p.market,
                    "ticker": p.ticker,
                    "horizon_months": d["horizon_months"],
                    "decision": d["decision"],
                    "recommendation": d["recommendation"],
                    "score": d["score"],
                }
            )
    try:
        from pitquant.db.models import Simulation

        for s in session.scalars(
            select(Simulation).order_by(Simulation.created_at.desc()).limit(200)
        ):
            out.append(
                {
                    "ref": f"S~{s.simulation_id}",
                    "kind": "SIMULATION",
                    "date": str(s.decision_at.date()),
                    "market": s.asset_type,
                    "ticker": s.price_snapshot.get("ticker") or s.security_id[:8],
                    "horizon_months": None,
                    "decision": "SIMULATED",
                    "recommendation": None,
                    "score": None,
                }
            )
    except Exception:  # the Simulation Lab is optional here
        pass
    return out


def routine_chart(
    session: Session, ref_pick: str, horizon: int, now: datetime | None = None
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    pick = session.get_one(DailyPick, ref_pick)
    dec = next((d for d in pick.decisions or [] if d["horizon_months"] == horizon), None)
    if dec is None:
        raise KeyError(f"no decision for horizon {horizon}")
    hyp = dec.get("hypothetical") or {}
    entry = float(dec.get("entry_price") or hyp["entry_price"])
    target, stop = (
        dec.get("target_price") or hyp.get("target_price"),
        dec.get("stop_price") or hyp.get("stop_price"),
    )
    bars = (
        btc_daily_bars(session, now)
        if pick.market == "BTC"
        else equity_daily_bars(session, pick.security_id or "", now)
    )
    day0 = pick.run_date
    horizon_end = day0 + relativedelta(months=horizon)
    chart = (
        _series(bars, day0 - timedelta(days=CONTEXT_DAYS))
        if len(bars)
        else {"bars": [], "sma50": [], "sma200": []}
    )
    buy = dec["decision"] == "BUY"
    ev: Any = None
    if buy and dec.get("position_id"):
        ev = session.scalars(
            select(DailyEvaluation)
            .where(DailyEvaluation.position_id == dec["position_id"])
            .order_by(DailyEvaluation.evaluated_at.desc())
        ).first()
        pos = session.get(PaperPosition, dec["position_id"])
        stop = stop or (pos.stop_price if pos else None)
    else:
        ev = session.scalars(
            select(DailyVirtualEvaluation)
            .where(
                DailyVirtualEvaluation.pick_id == pick.pick_id,
                DailyVirtualEvaluation.horizon_months == horizon,
            )
            .order_by(DailyVirtualEvaluation.evaluated_at.desc())
        ).first()
    state = ev.state if ev else "NOT_EVALUATED_YET"
    closed = state in CLOSED
    markers = [
        {
            "date": str(day0),
            "price": entry,
            "kind": "entry" if buy else "skip",
            "label": "ENTRADA simulada" if buy else "No comprar (decisión)",
        }
    ]
    if ev and closed and ev.outcome_date:
        markers.append(
            {
                "date": str(ev.outcome_date),
                "price": float(
                    target
                    if state == "TARGET_HIT" and target
                    else stop
                    if state == "STOP_HIT" and stop
                    else ev.price
                ),
                "kind": "exit",
                "label": CLOSED[state],
            }
        )
    tgt_pct, stp_pct = (
        (target / entry - 1) if target else None,
        (stop / entry - 1) if stop else None,
    )
    lines = [
        f"{'COMPRA simulada' if buy else 'NO se compra'} ({pick.market} {pick.ticker}, horizonte {horizon} meses) decidida el {day0}.",
        f"Regla: {dec['recommendation']} · puntuación {dec['score']:+.1f}. {dec['reason']}",
        f"Entrada planteada {entry:,.2f}"
        + (f" · objetivo {target:,.2f} ({tgt_pct:+.1%})" if target else "")
        + (f" · stop {stop:,.2f} ({stp_pct:+.1%})" if stop else "")
        + f" · horizonte hasta {horizon_end}.",
    ]
    if ev:
        what = "Operación real simulada" if buy else "Lo que habría pasado (no se compró)"
        lines.append(
            f"{what}: {CLOSED.get(state, 'en curso')} · rentabilidad {ev.return_pct:+.1%}"
            + (f" · cerrada el {ev.outcome_date}" if closed and ev.outcome_date else "")
            + "."
        )
    else:
        lines.append(
            "Todavía no hay evaluación: se actualiza cada semana con las velas diarias cerradas."
        )
    if not buy:
        lines.append(
            "Si la regla hubiera comprado, estas serían las líneas del plan; el gráfico enseña si habría acertado."
        )
    return {
        "ref": f"R~{pick.pick_id}~{horizon}",
        "title": f"{pick.market} · {pick.ticker} · {horizon} meses · {'COMPRA' if buy else 'NO COMPRAR'}",
        "kind": "ROUTINE",
        "asset": "BTC" if pick.market == "BTC" else "EQUITY",
        "decision": {
            "action": dec["decision"],
            "recommendation": dec["recommendation"],
            "score": dec["score"],
            "reason": dec["reason"],
            "decided_at": dec.get("decided_at"),
        },
        **chart,
        "levels": _level("Entrada", entry, "entry")
        + _level("Objetivo", target, "target")
        + _level("Stop", stop, "stop"),
        "markers": markers,
        "decision_date": str(day0),
        "horizon_end": str(horizon_end),
        "outcome": {
            "state": state,
            "closed": closed,
            "return_pct": float(ev.return_pct) if ev else None,
            "exit_date": str(ev.outcome_date) if ev and ev.outcome_date else None,
        },
        "explanation": lines,
        "disclaimer": "Dinero simulado. Reglas sin validar: sirve para entender qué se planteó y qué ocurrió, no para operar.",
    }


def simulation_chart(
    session: Session, simulation_id: str, now: datetime | None = None
) -> dict[str, Any]:
    from pitquant.db.models import Simulation
    from pitquant.simulation import service as sim

    now = now or datetime.now(UTC)
    s = session.get_one(Simulation, simulation_id)
    bars = (
        btc_daily_bars(session, now)
        if s.asset_type == "BTC"
        else equity_daily_bars(session, s.security_id, now)
    )
    day0 = s.decision_at.date()
    chart = (
        _series(bars, day0 - timedelta(days=CONTEXT_DAYS))
        if len(bars)
        else {"bars": [], "sma50": [], "sma200": []}
    )
    out = sim.latest_outcome(session, simulation_id)
    entry_px = out.entry_price if out and out.entry_price else s.entry_zone_high
    markers = [
        {
            "date": str(day0),
            "price": float(s.entry_zone_high),
            "kind": "skip",
            "label": "Decisión (T0)",
        }
    ]
    if out and out.entry_date and out.entry_price:
        markers.append(
            {
                "date": str(out.entry_date),
                "price": float(out.entry_price),
                "kind": "entry",
                "label": "ENTRADA (fill)",
            }
        )
    if out and out.is_closed and out.exit_date:
        markers.append(
            {
                "date": str(out.exit_date),
                "price": float(entry_px * (1 + out.realized_return))
                if out.realized_return is not None
                else float(entry_px),
                "kind": "exit",
                "label": f"SALIDA · {out.state}",
            }
        )
    levels = (
        _level("Entrada (alta)", s.entry_zone_high, "entry")
        + (
            _level("Entrada (baja)", s.entry_zone_low, "entry")
            if s.entry_zone_low != s.entry_zone_high
            else []
        )
        + _level("Stop", s.stop_loss, "stop")
        + _level("Objetivo 1", s.target_1, "target")
        + _level("Objetivo 2", s.target_2, "target")
        + _level("Invalidación", s.invalidation_level, "invalidation")
    )
    lines = [
        f"Simulación {simulation_id[:8]} ({s.asset_type}) creada el {day0}.",
        f"Plan: entrada {s.entry_zone_low:,.2f}–{s.entry_zone_high:,.2f} · stop {s.stop_loss:,.2f} · objetivo {s.target_1:,.2f}.",
        f"Estado: {out.state if out else 'CREADA'}"
        + (
            f" · rentabilidad {out.realized_return:+.1%}"
            if out and out.realized_return is not None
            else ""
        )
        + ".",
    ]
    return {"ref": f"S~{simulation_id}", "title": f"Simulación · {s.asset_type} · {day0}", "kind": "SIMULATION", "asset": s.asset_type, "decision": {"action": "SIMULATED", "recommendation": None, "score": None, "reason": "", "decided_at": str(s.decision_at)}, **chart, "levels": levels, "markers": markers,
            "decision_date": str(day0), "horizon_end": str(s.expiration_at.date()), "outcome": {"state": out.state if out else "CREATED", "closed": bool(out and out.is_closed), "return_pct": out.realized_return if out else None, "exit_date": str(out.exit_date) if out and out.exit_date else None}, "explanation": lines, "disclaimer": "Dinero simulado."}  # fmt: skip
