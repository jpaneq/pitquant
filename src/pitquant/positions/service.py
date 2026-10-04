# ruff: noqa: E501
"""Simulated positions: events, state, and the live review for equities and BTC (ADR-0041). Paper only: no broker, no real money."""

from __future__ import annotations

import math
import os
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.analyzer.service import AnalyzerService
from pitquant.config.settings import Settings
from pitquant.core.errors import PITQuantError
from pitquant.core.hashing import content_hash
from pitquant.core.timeutils import utc_now
from pitquant.db.models import Security
from pitquant.db.models_positions import PaperPosition, PaperPositionEvent, PositionReview
from pitquant.positions import review as engine

BTC_SECURITY_ID = "btc-spot"


class PositionError(PITQuantError):
    pass


def fixture_mode() -> bool:
    return os.environ.get("PITQUANT_E2E_FIXTURE") == "1"


def btc_security(session: Session) -> str:
    if session.get(Security, BTC_SECURITY_ID) is None:
        session.add(
            Security(
                security_id=BTC_SECURITY_ID,
                name="Bitcoin BTCUSDT",
                exchange="XCRY",
                currency="USDT",
            )
        )
        session.flush()
    return BTC_SECURITY_ID


# ───────────────────────────────────────────── context adapters (facts only; missing = None)
def _nearest_support(zones: list[dict[str, Any]], price: float) -> float | None:
    below = [z for z in zones if z.get("upper") is not None and z["upper"] < price]
    return float(max(below, key=lambda z: z["upper"])["lower"]) if below else None


def equity_context(
    session: Session, settings: Settings, security_id: str, at: datetime
) -> tuple[engine.Context, dict[str, Any]]:
    svc = AnalyzerService(session, settings)
    tech, ana, quote = (
        svc.technicals(security_id, at),
        svc.analysis(security_id, at),
        svc.quote(security_id, at),
    )
    if tech.get("status") != "OK" or not quote.get("price"):
        raise PositionError("PRICE_DATA_REQUIRED: this security has no usable price history")
    ind, labels = tech.get("indicators", {}), (ana.get("labels") or {})
    ctx = engine.Context(
        price=float(quote["price"]), atr14=ind.get("atr14"), trend_state=(tech.get("trend") or {}).get("state"), close_vs_sma200=ind.get("close_vs_sma200"), close_vs_sma50=ind.get("close_vs_sma50"),
        ret_6m=(tech.get("momentum") or {}).get("ret126"), rsi14=ind.get("rsi14"), vol_annual=(tech.get("risk") or {}).get("vol63"), valuation_label=(labels.get("valuation") or {}).get("label"), fundamentals_label=(labels.get("fundamentals") or {}).get("label"),
        support_lower=_nearest_support((tech.get("support_resistance") or {}).get("supports", []), float(quote["price"])),
    )  # fmt: skip
    return ctx, {
        "price_source": "EOD_CLOSE",
        "freshness": (quote.get("freshness") or {}).get("status") or quote.get("badge"),
        "as_of": quote.get("as_of"),
    }


def btc_latest_payload(session: Session, now: datetime) -> dict[str, Any]:
    """Features of the latest CLOSED daily bar (never the open candle). Fixture mode (E2E only) reads the SYNTHETIC cohort instead."""
    if fixture_mode():
        from pitquant.btc.contracts import Cohort as C
        from pitquant.btc.features import feature_payload as fp
        from pitquant.btc.fixtures import T0

        return fp(session, T0, C.SYNTHETIC)
    from pitquant.btc.contracts import Cohort
    from pitquant.btc.features import feature_payload

    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    payload: dict[str, Any] | None = None
    for cut in (
        midnight,
        midnight - timedelta(days=1),
    ):  # the latest CLOSED daily bar; never the open candle
        try:
            p = feature_payload(
                session, cut, Cohort.FORWARD_PAPER, now, allow_delayed_knowledge=True
            )
        except ValueError:
            continue
        if p.get("spot_ready"):
            payload = p
            break
    if payload is None:
        raise PositionError("BTC_FEATURES_UNAVAILABLE: no closed daily bar archived yet")
    return payload


def btc_context(session: Session, now: datetime) -> tuple[engine.Context, dict[str, Any]]:
    from pitquant.api.btc import _market

    m = _market(session)
    q = m["quote"]
    if q["price"] is None:
        raise PositionError(
            "PRICE_UNAVAILABLE: no real BTC quote right now (REAL DATA UNAVAILABLE)"
        )
    payload = btc_latest_payload(session, now)
    tr, vol, mom = (
        payload["trend_features"],
        payload["volatility_features"],
        payload["momentum_features"],
    )
    d50, d200, cross = tr.get("distance_sma50"), tr.get("distance_sma200"), tr.get("sma50_vs_200")
    avail = [v for v in (d50, d200, cross) if v is not None]
    state = None
    if len(avail) == 3:
        n = sum(1 for v in avail if v > 0)
        state = {3: "STRONG_UPTREND", 2: "UPTREND", 1: "DOWNTREND", 0: "STRONG_DOWNTREND"}[
            n
        ]  # same three facts the BTC regime uses, spread over four states
    r180 = mom.get("log_return_180d")
    price = float(q["price"])
    zones = (payload.get("support_resistance") or {}).get("supports", [])
    ctx = engine.Context(
        price=price, atr14=vol.get("ATR14"), trend_state=state, close_vs_sma200=d200, close_vs_sma50=d50, ret_6m=None if r180 is None else math.expm1(r180), rsi14=None, vol_annual=vol.get("realized_vol_90d"),
        support_lower=_nearest_support(zones, price),
    )  # fmt: skip
    return ctx, {
        "price_source": q["source"],
        "freshness": q["status"],
        "as_of": q["retrieved_at"],
        "data_mode": m.get("data_mode"),
    }


def context_for(
    session: Session, settings: Settings, pos: PaperPosition, now: datetime
) -> tuple[engine.Context, dict[str, Any]]:
    return (
        btc_context(session, now)
        if pos.asset_type == "BTC"
        else equity_context(session, settings, pos.security_id, now)
    )


# ───────────────────────────────────────────── events and state
def events_of(session: Session, position_id: str) -> list[PaperPositionEvent]:
    return list(
        session.scalars(
            select(PaperPositionEvent)
            .where(PaperPositionEvent.position_id == position_id)
            .order_by(PaperPositionEvent.occurred_at, PaperPositionEvent.created_at)
        )
    )


def fold(events: list[PaperPositionEvent]) -> dict[str, Any]:
    """Quantity, average cost (weighted on buys; unchanged by sells), realised P&L and open/closed."""
    qty, cost, realised, closed = 0.0, 0.0, 0.0, False
    for e in events:
        if e.event_type in ("OPEN", "ADD"):
            cost = (cost * qty + e.price * e.quantity) / (qty + e.quantity)
            qty += e.quantity
        else:
            sold = qty if e.event_type == "CLOSE" else e.quantity
            realised += (e.price - cost) * sold
            qty -= sold
            if e.event_type == "CLOSE" or qty <= 1e-12:
                qty, closed = 0.0, True
    return {"quantity": qty, "avg_cost": cost, "realized_pnl": realised, "closed": closed}


def _price(
    session: Session,
    settings: Settings,
    asset: str,
    security_id: str,
    now: datetime,
    manual: float | None,
) -> tuple[float, str, str | None]:
    if manual is not None:
        if not math.isfinite(manual) or manual <= 0:
            raise PositionError("price must be a positive number")
        return float(manual), "USER", None
    ctx, meta = context_for_asset(session, settings, asset, security_id, now)
    return ctx.price, str(meta["price_source"]), meta.get("freshness")


def context_for_asset(
    session: Session, settings: Settings, asset: str, security_id: str, now: datetime
) -> tuple[engine.Context, dict[str, Any]]:
    return (
        btc_context(session, now)
        if asset == "BTC"
        else equity_context(session, settings, security_id, now)
    )


def open_position(
    session: Session, settings: Settings, *, asset_type: str, security_id: str | None, horizon_months: int, quantity: float | None = None, notional: float | None = None, price: float | None = None,
    target_return: float | None = None, stop_price: float | None = None, note: str = "", now: datetime | None = None,
    price_source: str | None = None, stop_rule: str | None = None,
) -> PaperPosition:  # fmt: skip
    now = now or utc_now()
    if asset_type not in ("EQUITY", "BTC"):
        raise PositionError("asset_type must be EQUITY or BTC")
    if not 1 <= horizon_months <= 60:
        raise PositionError("horizon_months must be between 1 and 60")
    if target_return is not None and target_return <= 0:
        raise PositionError("target_return must be positive (e.g. 0.15 = +15 %)")
    sid = btc_security(session) if asset_type == "BTC" else security_id
    if not sid:
        raise PositionError("a security is required for an equity position")
    ctx, meta = context_for_asset(session, settings, asset_type, sid, now)
    px, source, fresh = (
        (float(price), price_source or "USER", meta.get("freshness") if price_source else None)
        if price is not None
        else (ctx.price, str(meta["price_source"]), meta.get("freshness"))
    )
    if px <= 0 or not math.isfinite(px):
        raise PositionError("price must be a positive number")
    if quantity is None and notional is None:
        raise PositionError("give a quantity or an amount (notional)")
    qty = quantity if quantity is not None else notional / px  # type: ignore[operator]
    if asset_type == "EQUITY" and quantity is None:
        qty = math.floor(qty)  # whole shares for equities
    if not math.isfinite(qty) or qty <= 0:
        raise PositionError("the amount does not buy any unit")
    if stop_price is not None and not 0 < stop_price < px:
        raise PositionError("the stop must be positive and below the entry price (long only)")
    default_stop = (
        (px - 2 * ctx.atr14)
        if (stop_price is None and ctx.atr14 and px - 2 * ctx.atr14 > 0)
        else None
    )
    row = PaperPosition(
        asset_type=asset_type, security_id=sid, horizon_months=horizon_months, target_return=target_return, stop_price=stop_price if stop_price is not None else default_stop,
        stop_rule=(stop_rule or "USER") if stop_price is not None else ("ATR14_2X_AT_OPEN" if default_stop else "NONE"), note=note[:300], is_synthetic=fixture_mode() or meta.get("data_mode") == "SYNTHETIC_TEST_DATA", opened_at=now,
    )  # fmt: skip
    session.add(row)
    session.flush()
    session.add(
        PaperPositionEvent(
            position_id=row.position_id,
            event_type="OPEN",
            occurred_at=now,
            price=px,
            quantity=qty,
            price_source=source,
            price_freshness=fresh,
        )
    )
    session.flush()
    return row


def add_event(
    session: Session,
    settings: Settings,
    position_id: str,
    kind: str,
    *,
    quantity: float | None = None,
    price: float | None = None,
    now: datetime | None = None,
    price_source: str | None = None,
) -> PaperPositionEvent:
    now = now or utc_now()
    pos = session.get_one(PaperPosition, position_id)
    st = fold(events_of(session, position_id))
    if st["closed"]:
        raise PositionError("the position is closed: open a new one")
    if kind not in ("ADD", "REDUCE", "CLOSE"):
        raise PositionError("event type must be ADD, REDUCE or CLOSE")
    px, source, fresh = _price(session, settings, pos.asset_type, pos.security_id, now, price)
    source = price_source or source
    if kind == "CLOSE":
        qty = st["quantity"]
    else:
        if quantity is None or quantity <= 0 or not math.isfinite(quantity):
            raise PositionError("quantity must be positive")
        if kind == "REDUCE" and quantity > st["quantity"] + 1e-12:
            raise PositionError(f"cannot sell {quantity} of {st['quantity']} held")
        qty = quantity
    ev = PaperPositionEvent(
        position_id=position_id,
        event_type=kind,
        occurred_at=now,
        price=px,
        quantity=qty,
        price_source=source,
        price_freshness=fresh,
    )
    session.add(ev)
    session.flush()
    return ev


def live_review(
    session: Session, settings: Settings, pos: PaperPosition, now: datetime | None = None
) -> dict[str, Any]:
    now = now or utc_now()
    evs = events_of(session, pos.position_id)
    st = fold(evs)
    head = {
        "position_id": pos.position_id, "asset_type": pos.asset_type, "security_id": pos.security_id, "horizon_months": pos.horizon_months, "target_return": pos.target_return, "stop_price": pos.stop_price, "stop_rule": pos.stop_rule,
        "note": pos.note, "is_synthetic": pos.is_synthetic, "opened_at": pos.opened_at.isoformat(), **st,
        "events": [{"type": e.event_type, "at": e.occurred_at.isoformat(), "price": e.price, "quantity": e.quantity, "price_source": e.price_source, "freshness": e.price_freshness} for e in evs],
    }  # fmt: skip
    if st["closed"]:
        return {**head, "review": None, "status": "CLOSED"}
    try:
        ctx, meta = context_for(session, settings, pos, now)
    except PositionError as exc:
        return {**head, "review": None, "status": "REVIEW_UNAVAILABLE", "reason": str(exc)}
    rv = engine.review(
        engine.Position(
            st["avg_cost"],
            st["quantity"],
            pos.opened_at,
            pos.horizon_months,
            pos.target_return,
            pos.stop_price,
        ),
        ctx,
        now,
    )
    return {
        **head,
        "status": "OPEN",
        "review": {
            **rv,
            "price_source": meta["price_source"],
            "price_freshness": meta.get("freshness"),
            "reviewed_at": now.isoformat(),
            "context": {k: v for k, v in vars(ctx).items() if k != "extra"},
        },
    }


def save_review(
    session: Session, settings: Settings, position_id: str, now: datetime | None = None
) -> PositionReview:
    now = now or utc_now()
    pos = session.get_one(PaperPosition, position_id)
    view = live_review(session, settings, pos, now)
    if view["status"] != "OPEN" or view["review"] is None:
        raise PositionError(view.get("reason") or "the position is not open")
    rv = view["review"]
    row = PositionReview(
        position_id=position_id, reviewed_at=now, engine_version=rv["engine_version"], horizon_bucket=rv["horizon_bucket"], recommendation=rv["recommendation"], score=rv["score"], price=rv["position"]["price"], avg_cost=view["avg_cost"],
        quantity=view["quantity"], pnl_pct=rv["position"]["pnl_pct"], rules=rv["rules"], inputs=rv["context"], context_hash=content_hash({"rules": rv["rules"], "context": rv["context"], "position": rv["position"]}),
    )  # fmt: skip
    session.add(row)
    session.flush()
    return row


def list_positions(
    session: Session,
    settings: Settings,
    asset_type: str | None = None,
    security_id: str | None = None,
    include_closed: bool = False,
) -> list[dict[str, Any]]:
    q = select(PaperPosition).order_by(PaperPosition.opened_at.desc())
    if asset_type:
        q = q.where(PaperPosition.asset_type == asset_type)
    if security_id:
        q = q.where(PaperPosition.security_id == security_id)
    out = [live_review(session, settings, p) for p in session.scalars(q)]
    return out if include_closed else [v for v in out if v["status"] != "CLOSED"]
