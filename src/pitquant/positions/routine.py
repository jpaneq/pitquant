# ruff: noqa: E501
"""Daily simulated-trading routine (ADR-0042). Paper only: no broker, no real money, no prediction model.

Every day, for each market (IBEX, SP500, MSCI_WORLD) ONE company is analysed (deterministic rotation over the configured list, skipping tickers with no price data) and BTC is analysed too.
For each horizon (1, 3, 6, 12, 24 months) the same rule engine as the position review decides whether an entry is justified (``ADD`` for a brand-new position at today's price). When it is,
a simulated purchase is opened with the entry price, a TARGET price and a protective STOP derived from realised volatility (``target = k·σ·√(h/12)``), all listed in ``PARAMS`` so they can
be adjusted. Weekly (and at the end) each open prediction is evaluated against the bars that followed: target hit, stop hit, or expired. Nothing is back-dated: only bars after the entry count.
Everything not accessible (no price data, no quote) is recorded as NO_DATA and shown in the report; nothing is invented.
"""

from __future__ import annotations

import json
import math
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from dateutil.relativedelta import relativedelta
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pitquant.analyzer.market import load_market
from pitquant.config.settings import Settings
from pitquant.core.timeutils import utc_now
from pitquant.db.models import Price
from pitquant.db.models import new_id as new_pick_id
from pitquant.db.models_positions import PaperPosition
from pitquant.db.models_routine import DailyEvaluation, DailyPick, DailyVirtualEvaluation
from pitquant.market.exchanges import calendar_of
from pitquant.positions import review as engine
from pitquant.positions import service as ps
from pitquant.simulation.service import restated_bars
from pitquant.strategy.daily import resolve_universe
from pitquant.strategy.spec import StrategyError

PARAMS_VERSION = "daily-routine-v0"
PARAMS: dict[str, Any] = {
    "horizons_months": [1, 3, 6, 12, 24], "notional_per_position": 10_000.0, "entry_requires": "review recommendation == ADD (same rule engine as the position review, horizon-weighted)",
    "target_k": 0.5, "target_floor": 0.02, "stop_k": 0.35, "stop_atr_mult": 2.0, "min_bars_for_data": 250,
    "target_rule": "target = entry · (1 + max(target_floor, target_k · σ_annual · sqrt(h/12)))", "stop_rule": "stop = entry − max(stop_atr_mult · ATR14, stop_k · σ_annual · sqrt(h/12) · entry)",
    "evaluation": "weekly (ISO week) and at the end: first touch of target or stop on daily bars AFTER the entry; both in one bar = AMBIGUOUS_STOP (counted as a stop); horizon end = EXPIRED",
}  # fmt: skip
HORIZONS = tuple(PARAMS["horizons_months"])
MARKET_ORDER = ("IBEX", "SP500", "MSCI_WORLD")
# Orientative lists (edit with data/daily_universe.json or PITQUANT_DAILY_UNIVERSE): NOT an official index composition. A ticker with no price data is skipped and reported.
DEFAULT_UNIVERSE: dict[str, list[str]] = {
    "IBEX": ["SAN", "BBVA", "ITX", "IBE", "TEF", "REP", "CABK", "AMS", "FER", "ELE", "ACS", "NTGY"],
    "SP500": ["AAPL", "MSFT", "KO", "JNJ", "JPM", "XOM", "PG", "AMZN", "GOOGL", "NVDA"],
    "MSCI_WORLD": [
        "META",
        "V",
        "UNH",
        "LLY",
        "AVGO",
        "TSLA",
        "MA",
        "COST",
        "HD",
        "WMT",
        "ABBV",
        "MRK",
        "CVX",
        "BAC",
        "ORCL",
        "CRM",
        "NFLX",
        "ADBE",
        "CSCO",
        "PEP",
        "TMO",
        "ACN",
        "MCD",
        "ABT",
        "LIN",
        "DIS",
        "WFC",
        "CAT",
        "IBM",
        "GE",
        "QCOM",
        "TXN",
        "AMGN",
        "INTU",
        "VZ",
        "PFE",
        "BA",
        "HON",
        "UNP",
        "LOW",
        "SPGI",
        "NEE",
        "RTX",
        "LMT",
        "UPS",
        "ASML.AS",
        "NESN.SW",
        "NOVN.SW",
        "ROG.SW",
        "SAP.DE",
        "SIE.DE",
        "ALV.DE",
        "AIR.PA",
        "MC.PA",
        "OR.PA",
        "SU.PA",
        "TTE.PA",
        "AZN.L",
        "SHEL.L",
        "HSBA.L",
        "ULVR.L",
        "BP.L",
        "GSK.L",
        "NOVO-B.CO",
        "ENEL.MI",
        "ISP.MI",
        "7203.T",
        "6758.T",
        "9984.T",
        "8306.T",
        "7974.T",
        "BHP.AX",
        "CBA.AX",
        "CSL.AX",
        "RY.TO",
        "TD.TO",
        "SHOP.TO",
        "ENB.TO",
    ],  # US-listed names only until other exchange calendars are mapped
}
NOTE_PREFIX = f"routine:{PARAMS_VERSION}|"
MARKET_EXCHANGE: dict[str, str | None] = {
    "IBEX": "XMAD",
    "SP500": "XNYS",
    "MSCI_WORLD": "XNYS",
    "BTC": None,
}
VENDOR_SUFFIX = {
    "IBEX": ".MC",
    "SP500": ".US",
    "MSCI_WORLD": ".US",
    "BENCHMARK": ".US",
}  # EODHD exchange suffix when the list entry has none


def entry_exchange(entry: str, market: str) -> str:
    """Calendar of a universe entry: its own suffix, else the market's default suffix (IBEX → Madrid, others → US)."""
    return calendar_of(entry.upper() if "." in entry else "X" + VENDOR_SUFFIX[market])


def exchange_open(code: str, now: datetime) -> bool:
    """True when ``now`` is inside today's session of the exchange (local date), open <= now < close."""
    from zoneinfo import ZoneInfo

    from pitquant.data.calendars.market_calendar import get_calendar

    cal = get_calendar(code)
    local = now.astimezone(ZoneInfo(cal.tz)).date()
    if local < cal.first_session or local > cal.last_session or not cal.is_session(local):
        return False
    return cal.session_open(local) <= now < cal.session_close(local)


def market_is_open(market: str, now: datetime) -> bool:
    """BTC trades 24/7; an equity market counts as open only inside today's session. MSCI_WORLD has no single exchange (decided per ticker)."""
    code = MARKET_EXCHANGE.get(market)
    return True if code is None else exchange_open(code, now)


def load_universe() -> dict[str, list[str]]:
    path = os.environ.get("PITQUANT_DAILY_UNIVERSE") or "data/daily_universe.json"
    if Path(path).exists():
        data = json.loads(Path(path).read_text())
        return {m: [str(t).upper() for t in data.get(m, DEFAULT_UNIVERSE[m])] for m in MARKET_ORDER}
    return DEFAULT_UNIVERSE


def eligibility(session: Session, ticker: str) -> tuple[str | None, str]:
    """(security_id, reason). A ticker is usable only if it maps to its CURRENT security and that security has enough real price bars."""
    from pitquant.positions.universe_ingest import find_security

    base = ticker.upper().rsplit(".", 1)[0] if "." in ticker else ticker.upper()
    sid = find_security(session, base)
    if sid is None:
        try:
            sid = resolve_universe(session, [base])[0]
        except StrategyError:
            return None, "NOT_RESOLVED: the ticker is not in the security master"
    n = session.scalar(select(func.count()).select_from(Price).where(Price.security_id == sid)) or 0
    if n < PARAMS["min_bars_for_data"]:
        return (
            None,
            f"NO_PRICE_DATA: {n} bars (needs {PARAMS['min_bars_for_data']}); run routine-run --refresh to download them",
        )
    return sid, "OK"


def levels(price: float, ctx: engine.Context, horizon: int) -> dict[str, float] | None:
    """Target and stop for one horizon from volatility; ``None`` when volatility or ATR is unknown (nothing is guessed)."""
    if not ctx.vol_annual or not ctx.atr14 or ctx.vol_annual <= 0:
        return None
    span = ctx.vol_annual * math.sqrt(horizon / 12.0)
    target_pct = max(PARAMS["target_floor"], PARAMS["target_k"] * span)
    stop_dist = max(PARAMS["stop_atr_mult"] * ctx.atr14, PARAMS["stop_k"] * span * price)
    stop = price - stop_dist
    if stop <= 0:
        return None
    return {
        "target_pct": target_pct,
        "target_price": price * (1 + target_pct),
        "stop_price": stop,
        "stop_pct": stop_dist / price,
        "sigma_horizon": span,
    }


def pick_ticker(eligible: list[str], market: str, run_date: date) -> str:
    return sorted(eligible)[
        (
            run_date.toordinal() + MARKET_ORDER.index(market)
            if market in MARKET_ORDER
            else run_date.toordinal()
        )
        % len(eligible)
    ]


def _decide(
    session: Session,
    settings: Settings,
    *,
    market: str,
    ticker: str,
    sid: str | None,
    ctx: engine.Context,
    meta: dict[str, Any],
    now: datetime,
    pick_id: str,
) -> list[dict[str, Any]]:
    out = []
    for h in HORIZONS:
        rv = engine.review(engine.Position(ctx.price, 1.0, now, h), ctx, now)
        row: dict[str, Any] = {
            "horizon_months": h,
            "score": rv["score"],
            "recommendation": rv["recommendation"],
            "reason": rv["reason"],
            "decision": "NO_ORDER",
            "position_id": None,
            "decided_at": now.isoformat(),
        }
        lv = levels(ctx.price, ctx, h)
        if (
            lv is not None
        ):  # a decision NOT to buy keeps the levels it WOULD have used, so it can be valued later
            row["hypothetical"] = {"entry_price": ctx.price, **lv}
        if rv["recommendation"] == "ADD":
            if lv is None:
                row["reason"] = (
                    "Entrada justificada por las reglas pero sin volatilidad/ATR para fijar objetivo y stop: no se abre."
                )
            else:
                try:
                    pos = ps.open_position(
                        session, settings, asset_type="BTC" if market == "BTC" else "EQUITY", security_id=sid, horizon_months=h, notional=PARAMS["notional_per_position"], price=ctx.price, target_return=lv["target_pct"],
                        stop_price=lv["stop_price"], note=f"{NOTE_PREFIX}{market}|{ticker}|{h}|{pick_id}", now=now, price_source=str(meta["price_source"]), stop_rule="ROUTINE_VOL_ATR",
                    )  # fmt: skip
                    row |= {
                        "decision": "BUY",
                        "position_id": pos.position_id,
                        "entry_price": ctx.price,
                        **lv,
                    }
                except ps.PositionError as exc:
                    row["reason"] = f"No se pudo abrir la compra simulada: {exc}"
        out.append(row)
    return out


def run_daily(
    session: Session,
    settings: Settings,
    now: datetime | None = None,
    universe: dict[str, list[str]] | None = None,
    respect_hours: bool = False,
) -> dict[str, Any]:
    """One idempotent daily step: at most one analysis per (day, market). Returns what was decided."""
    now = now or utc_now()
    today = now.date()
    uni = universe or load_universe()
    used: set[str] = set()
    done: list[dict[str, Any]] = []
    for market in (*MARKET_ORDER, "BTC"):
        if session.scalar(
            select(DailyPick).where(DailyPick.run_date == today, DailyPick.market == market)
        ):
            done.append({"market": market, "status": "ALREADY_DONE_TODAY"})
            continue
        if respect_hours and not market_is_open(market, now):
            done.append(
                {"market": market, "status": "MARKET_CLOSED"}
            )  # nothing is stored: the next run inside the session analyses it
            continue
        pick_id = new_pick_id()
        unavailable: dict[str, str] = {}
        ticker: str | None = None
        sid: str | None = None
        ctx: engine.Context | None = None
        meta: dict[str, Any] = {}
        if market == "BTC":
            ticker = "BTC"
            try:
                ctx, meta = ps.btc_context(session, now)
            except ps.PositionError as exc:
                unavailable["BTC"] = str(exc)
        else:
            ok: dict[str, str] = {}
            exch: dict[str, str] = {}
            for t in uni.get(market, []):
                sid_t, why = eligibility(session, t)
                base_t = t.upper().rsplit(".", 1)[0] if "." in t else t.upper()
                if sid_t is None:
                    unavailable[base_t] = why
                elif sid_t not in used:
                    ok[base_t] = sid_t
                    exch[base_t] = entry_exchange(t, market)
            if respect_hours and market == "MSCI_WORLD" and ok:
                open_now = {b: v for b, v in ok.items() if exchange_open(exch[b], now)}
                if not open_now:
                    done.append(
                        {"market": market, "status": "MARKET_CLOSED"}
                    )  # every eligible exchange is closed right now
                    continue
                ok = open_now
            if ok:
                ticker = pick_ticker(list(ok), market, today)
                sid = ok[ticker]
                try:
                    ctx, meta = ps.equity_context(session, settings, sid, now)
                except ps.PositionError as exc:
                    unavailable[ticker] = str(exc)
                    ctx = None
        if ctx is None:
            session.add(
                DailyPick(
                    pick_id=pick_id,
                    run_date=today,
                    market=market,
                    ticker=ticker,
                    security_id=sid,
                    status="NO_DATA",
                    params_version=PARAMS_VERSION,
                    params=PARAMS,
                    price=None,
                    price_freshness=None,
                    decisions=[],
                    unavailable=unavailable,
                )
            )
            session.flush()
            done.append({"market": market, "status": "NO_DATA", "unavailable": unavailable})
            continue
        if sid:
            used.add(sid)
        decisions = _decide(
            session,
            settings,
            market=market,
            ticker=str(ticker),
            sid=sid,
            ctx=ctx,
            meta=meta,
            now=now,
            pick_id=pick_id,
        )
        session.add(
            DailyPick(
                pick_id=pick_id,
                run_date=today,
                market=market,
                ticker=ticker,
                security_id=sid,
                status="ANALYZED",
                params_version=PARAMS_VERSION,
                params=PARAMS,
                price=ctx.price,
                price_freshness=meta.get("freshness"),
                decisions=decisions,
                unavailable=unavailable,
            )
        )
        session.flush()
        done.append(
            {
                "market": market,
                "status": "ANALYZED",
                "ticker": ticker,
                "price": ctx.price,
                "bought": [d["horizon_months"] for d in decisions if d["decision"] == "BUY"],
            }
        )
    return {"run_date": str(today), "markets": done}


# ───────────────────────────────────────────── weekly evaluation
def routine_positions(session: Session) -> list[PaperPosition]:
    return list(
        session.scalars(select(PaperPosition).where(PaperPosition.note.like(f"{NOTE_PREFIX}%")))
    )


def parse_note(note: str) -> dict[str, str]:
    _, market, ticker, horizon, pick = note.split("|")
    return {"market": market, "ticker": ticker, "horizon": horizon, "pick_id": pick}


def bars_after_entry(
    session: Session, settings: Settings, pos: Any, entry_at: datetime, now: datetime
) -> pd.DataFrame:
    """Daily OHLC strictly AFTER the entry (units of the entry price)."""
    if pos.asset_type == "BTC":
        from datetime import timedelta

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
            (ts.date() - timedelta(days=1), p["open"], p["high"], p["low"], p["close"])
            for ts, p in sorted(by_ts.items())
            if ts - timedelta(days=1)
            >= entry_at.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            and ts <= now
        ]
        return (
            pd.DataFrame(recs, columns=["date", "open", "high", "low", "close"]).set_index("date")
            if recs
            else pd.DataFrame(columns=["open", "high", "low", "close"])
        )
    md = load_market(session, pos.security_id, now)
    bars, _ = restated_bars(md, entry_at.date(), now)
    return bars


def outcome(
    bars: pd.DataFrame, entry: float, target: float, stop: float, horizon_end: date, now: datetime
) -> dict[str, Any]:
    state, fill, when, used = "IN_PROGRESS", None, None, 0
    max_fav, max_adv, last_close = None, None, None
    for d, row in bars.iterrows():
        if d > horizon_end:
            break
        used += 1
        last_close = float(row["close"])
        max_fav = max(max_fav if max_fav is not None else -1e9, float(row["high"]) / entry - 1)
        max_adv = min(max_adv if max_adv is not None else 1e9, float(row["low"]) / entry - 1)
        hit_t, hit_s = float(row["high"]) >= target, float(row["low"]) <= stop
        if hit_t and hit_s:
            state, fill, when = "AMBIGUOUS_STOP", min(stop, float(row["open"])), d
        elif hit_s:
            state, fill, when = (
                "STOP_HIT",
                min(stop, float(row["open"])),
                d,
            )  # a gap below the stop fills at the open
        elif hit_t:
            state, fill, when = "TARGET_HIT", target, d
        if when is not None:
            break
    if state == "IN_PROGRESS" and now.date() >= horizon_end and last_close is not None:
        state, fill, when = "EXPIRED", last_close, horizon_end
    price = fill if fill is not None else last_close
    return {
        "state": state,
        "fill": fill,
        "when": when,
        "bars_used": used,
        "price": price,
        "max_favorable": max_fav,
        "max_adverse": max_adv,
    }


def week_key(d: datetime) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def evaluate_positions(
    session: Session, settings: Settings, now: datetime | None = None
) -> dict[str, Any]:
    now = now or utc_now()
    wk = week_key(now)
    written, closed, skipped = 0, 0, 0
    for pos in routine_positions(session):
        evs = ps.events_of(session, pos.position_id)
        st = ps.fold(evs)
        if st["closed"]:
            continue
        open_ev = evs[0]
        entry, target, stop = (
            open_ev.price,
            open_ev.price * (1 + (pos.target_return or 0)),
            pos.stop_price,
        )
        if stop is None or not pos.target_return:
            skipped += 1
            continue
        horizon_end = (pos.opened_at + relativedelta(months=pos.horizon_months)).date()
        bars = bars_after_entry(session, settings, pos, pos.opened_at, now)
        o = outcome(bars, entry, target, stop, horizon_end, now)
        price = o["price"] if o["price"] is not None else entry
        terminal = o["state"] != "IN_PROGRESS"
        key = "FINAL" if terminal else wk
        if session.scalar(
            select(DailyEvaluation).where(
                DailyEvaluation.position_id == pos.position_id, DailyEvaluation.week_key == key
            )
        ):
            continue
        session.add(
            DailyEvaluation(
                position_id=pos.position_id, week_key=key, evaluated_at=now, state=o["state"], price=price, return_pct=price / entry - 1, target_progress=(price - entry) / (target - entry), max_favorable=o["max_favorable"],
                max_adverse=o["max_adverse"], outcome_date=o["when"], bars_used=o["bars_used"], detail={"entry": entry, "target": target, "stop": stop, "horizon_end": str(horizon_end), "params_version": PARAMS_VERSION},
            )
        )  # fmt: skip
        written += 1
        if terminal:
            ps.add_event(
                session,
                settings,
                pos.position_id,
                "CLOSE",
                price=float(price),
                now=now,
                price_source="ROUTINE_RULE",
            )
            closed += 1
    session.flush()
    return {"week": wk, "evaluations_written": written, "closed": closed, "skipped": skipped}


def evaluate_virtual(
    session: Session, settings: Settings, now: datetime | None = None
) -> dict[str, Any]:
    """Value the decisions NOT to buy: the levels they would have used are played on the bars after the decision (counterfactual, no position is ever opened). A NO_ORDER was RIGHT if the
    target would NOT have been reached first; it was a MISSED OPPORTUNITY if it would have."""
    from types import SimpleNamespace

    now = now or utc_now()
    wk = week_key(now)
    written = 0
    for pick in session.scalars(select(DailyPick).where(DailyPick.status == "ANALYZED")):
        ref = SimpleNamespace(
            asset_type="BTC" if pick.market == "BTC" else "EQUITY", security_id=pick.security_id
        )
        for d in pick.decisions:
            hyp = d.get("hypothetical")
            if d["decision"] != "NO_ORDER" or not hyp:
                continue
            h = int(d["horizon_months"])
            if session.scalar(
                select(DailyVirtualEvaluation).where(
                    DailyVirtualEvaluation.pick_id == pick.pick_id,
                    DailyVirtualEvaluation.horizon_months == h,
                    DailyVirtualEvaluation.week_key == "FINAL",
                )
            ):
                continue
            decided = datetime.fromisoformat(d["decided_at"])
            horizon_end = (decided + relativedelta(months=h)).date()
            o = outcome(
                bars_after_entry(session, settings, ref, decided, now),
                hyp["entry_price"],
                hyp["target_price"],
                hyp["stop_price"],
                horizon_end,
                now,
            )
            price = o["price"] if o["price"] is not None else hyp["entry_price"]
            key = "FINAL" if o["state"] != "IN_PROGRESS" else wk
            if session.scalar(
                select(DailyVirtualEvaluation).where(
                    DailyVirtualEvaluation.pick_id == pick.pick_id,
                    DailyVirtualEvaluation.horizon_months == h,
                    DailyVirtualEvaluation.week_key == key,
                )
            ):
                continue
            session.add(
                DailyVirtualEvaluation(
                    pick_id=pick.pick_id, horizon_months=h, week_key=key, evaluated_at=now, state=o["state"], price=price, return_pct=price / hyp["entry_price"] - 1,
                    target_progress=(price - hyp["entry_price"]) / (hyp["target_price"] - hyp["entry_price"]), max_favorable=o["max_favorable"], max_adverse=o["max_adverse"], outcome_date=o["when"],
                    bars_used=o["bars_used"], detail={**hyp, "horizon_end": str(horizon_end), "params_version": PARAMS_VERSION},
                )
            )  # fmt: skip
            written += 1
    session.flush()
    return {"week": wk, "virtual_evaluations_written": written}
