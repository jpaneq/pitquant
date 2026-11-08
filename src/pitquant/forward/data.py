"""Bounded data access: training ends before reservations; live context is not replay."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.btc.contracts import Cohort
from pitquant.btc.models import BTCDatum
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.data.point_in_time.context import PITContext
from pitquant.features.v0.series import build_series
from pitquant.forward.engine import MARKETS, TICKERS
from pitquant.positions.universe_ingest import find_security


def load_frame(
    s: Session,
    market: str,
    ticker: str,
    now: datetime,
    *,
    training: bool = False,
    full_history: bool = False,
) -> pd.DataFrame:
    """``training``: history before the V1 seal. ``full_history``: everything known at ``now``
    (learning refits and the one-time exam, ADR-0064). Default: recent live context."""
    cutoff = date.fromisoformat(str(MARKETS[market]["cutoff"]))
    until = (
        datetime.combine(cutoff, datetime.min.time(), UTC) - timedelta(microseconds=1)
        if training
        else now
    )
    training = training or full_history  # no live-context truncation
    if market == "BTC":
        query = select(BTCDatum).where(
            BTCDatum.source == "BINANCE_SPOT",
            BTCDatum.metric == "spot",
            BTCDatum.cohort == Cohort.FORWARD_PAPER,
            BTCDatum.exchange_timestamp <= until,
            BTCDatum.available_at <= now,
            BTCDatum.retrieved_at <= now,
        )
        if not training:
            query = query.where(BTCDatum.exchange_timestamp >= now - timedelta(days=300))
        latest = {}
        ids = []
        for r in s.scalars(
            query.order_by(BTCDatum.exchange_timestamp, BTCDatum.available_at, BTCDatum.datum_id)
        ):
            day = (r.exchange_timestamp - timedelta(days=1)).date()
            latest[day] = {k: r.payload.get(k) for k in ("open", "high", "low", "close", "volume")}
            ids.append(r.datum_id)
        b = pd.DataFrame.from_dict(latest, orient="index").sort_index()
        if b.empty:
            raise ValueError("BTC_PRICE_HISTORY_REQUIRED")
        dates = [d.date() for d in pd.date_range(b.index[0], b.index[-1], freq="D")]
        b = b.reindex(dates).astype(float)
        provenance: dict[str, Any] = {
            "source": "BINANCE_SPOT",
            "datum_ids_hash": hashlib.sha256("|".join(ids).encode()).hexdigest(),
            "price_basis": "spot price return",
            "vintage": "available now, not historical PIT",
        }
    else:
        sid = find_security(s, ticker)
        if sid is None:
            raise ValueError("SECURITY_NOT_RESOLVED")
        ctx = PITContext(s, until, ingested_before=now)
        b = ctx.raw_bars(sid)
        b = b[b.index >= date(2011, 1, 1)]
        if b.empty:
            raise ValueError("PRICE_HISTORY_REQUIRED")
        if not training:
            b = b.tail(300)
        series = build_series(b, ctx.market_actions(sid), until, b.index[-1] + timedelta(days=1))
        b = series.split_adjusted.copy()
        b["signal_close"] = series.tr_level
        b = b.reindex(get_calendar("XNYS").sessions(b.index[0], b.index[-1]))
        provenance = {
            "security_id": sid,
            "price_basis": "internal split-adjusted OHLCV and internal total-return signal",
            "vintage": "current archived vintage, not historical PIT",
        }
    b.attrs["provenance"] = provenance
    b.attrs["source_frame_hash"] = hashlib.sha256(b.to_csv().encode()).hexdigest()
    return b


def training_frames(
    s: Session,
    market: str,
    now: datetime,
    *,
    tickers: list[str] | None = None,
    full_history: bool = False,
) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    frames, exclusions = {}, {}
    universe = ["BTC"] if market == "BTC" else (tickers or TICKERS)
    for ticker in universe:
        try:
            frame = load_frame(
                s, market, ticker, now, training=not full_history, full_history=full_history
            )
            if frame.close.notna().sum() < 500:
                raise ValueError("INSUFFICIENT_HISTORY_MIN500")
            frames[ticker] = frame
        except ValueError as exc:
            exclusions[ticker] = str(exc)
    return frames, exclusions
