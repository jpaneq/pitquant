"""HTTP API (§75). Endpoints for later phases return 501 with an explicit reason rather
than fabricated output (§89 fail loudly, §97 no invented data)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, time
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from pitquant import __version__
from pitquant.backtest.labels import label_window
from pitquant.config.settings import Settings, get_settings
from pitquant.core.errors import (
    AmbiguousIdentifierError,
    CalendarRangeError,
    NaiveDatetimeError,
    UnknownSecurityError,
)
from pitquant.core.types import Horizon
from pitquant.data.calendars.market_calendar import get_calendar
from pitquant.data.point_in_time.context import PITContext
from pitquant.security_master.service import SecurityMaster
from pitquant.universe.index_membership import IndexUniverse


def get_db(request: Request) -> Iterator[Session]:
    factory: sessionmaker[Session] = request.app.state.session_factory
    s = factory()
    try:
        yield s
    finally:
        s.close()


DB = Annotated[Session, Depends(get_db)]


class AnalysisRequest(BaseModel):
    ticker: str
    exchange: str = "XNYS"
    as_of: str = Field(
        description="YYYY-MM-DD (after that day's close) or ISO datetime WITH offset"
    )

    def parsed_as_of(self) -> datetime | date:
        try:
            if len(self.as_of) == 10:
                return date.fromisoformat(self.as_of)
            return datetime.fromisoformat(self.as_of)
        except ValueError as e:
            raise HTTPException(422, f"invalid as_of {self.as_of!r}") from e

    horizons: list[Horizon] = Field(default_factory=lambda: [Horizon.M6, Horizon.M12])


def create_app(factory: sessionmaker[Session], settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()
    app = FastAPI(title="PITQuant", version=__version__)
    app.state.session_factory = factory

    def _as_of(value: datetime | date, exchange: str) -> datetime:
        """A bare date means: after that day's close in the market's own time zone."""
        if exchange not in cfg.markets:
            raise HTTPException(422, f"unknown exchange {exchange}")
        if isinstance(value, datetime):
            if value.tzinfo is None:
                raise HTTPException(422, "as_of datetime must include a UTC offset")
            return value
        cal = get_calendar(exchange)
        session = cal.session_on_or_before(value)
        if session == value:
            return cal.session_close(value)
        return datetime.combine(
            value, time(23, 59), tzinfo=ZoneInfo(cfg.markets[exchange].timezone)
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "version": __version__,
            "config_version": cfg.version,
            "config_hash": cfg.config_hash,
        }

    @app.get("/securities/{ticker}")
    def security(ticker: str, s: DB, as_of: date, exchange: str = "XNYS") -> dict[str, Any]:
        sm = SecurityMaster(s)
        try:
            sid = sm.resolve(ticker, exchange, as_of)
            v = sm.view(sid, as_of)
        except UnknownSecurityError as e:
            raise HTTPException(404, str(e)) from e
        except AmbiguousIdentifierError as e:
            raise HTTPException(409, str(e)) from e
        return {**v.__dict__, "synthetic_data": v.is_synthetic}

    @app.get("/universes/{index_code}/{on}")
    def universe(index_code: str, on: date, s: DB) -> dict[str, Any]:
        members = IndexUniverse(s).universe(index_code, on)
        sm = SecurityMaster(s)
        return {
            "index": index_code,
            "as_of": on.isoformat(),
            "count": len(members),
            "source_status": IndexUniverse(s).source_status(index_code) if members else None,
            "members": [
                {
                    "security_id": m.security_id,
                    "ticker": sm.ticker_as_of(m.security_id, on),
                    "since": m.effective_from.isoformat(),
                    "source_event_id": m.source_event_id,
                    "source_confidence": m.source_confidence,
                }
                for m in members
            ],
        }

    @app.post("/analysis")
    def analysis(req: AnalysisRequest, s: DB) -> dict[str, Any]:
        try:
            as_of = _as_of(req.parsed_as_of(), req.exchange)
            ctx = PITContext(s, as_of)
            sid = ctx.resolve(req.ticker, req.exchange)
            view = ctx.security(sid)
            cal = get_calendar(req.exchange)
            bars = ctx.raw_bars(sid)
            facts = ctx.facts(sid)
            windows = {
                h.value: label_window(
                    cal,
                    as_of,
                    h,
                    execution_mode=cfg.execution.mode,
                    delay_sessions=cfg.execution.delay_sessions,
                    data_lag_minutes=cfg.pit.label_data_lag_minutes,
                ).__dict__
                for h in req.horizons
            }
        except (UnknownSecurityError, AmbiguousIdentifierError) as e:
            raise HTTPException(404, str(e)) from e
        except (NaiveDatetimeError, CalendarRangeError) as e:
            raise HTTPException(422, str(e)) from e
        return {
            "status": "pit_reconstruction_only",
            "detail": "Scoring/probabilities arrive in Phase 5; no signal is fabricated.",
            "synthetic_data": view.is_synthetic,
            "as_of": as_of.isoformat(),
            "security": view.__dict__,
            "information_available": {
                "last_bar_session": str(bars.index[-1]) if not bars.empty else None,
                "n_bars": len(bars),
                "fundamental_facts": len(facts),
                "latest_fact_available_at": max(
                    (f.available_at for f in facts.values()), default=None
                ),
            },
            "label_windows": {k: {kk: str(vv) for kk, vv in w.items()} for k, w in windows.items()},
            "signal": None,
        }

    @app.post("/backtests")
    def backtests() -> None:
        raise HTTPException(501, "Backtest engine is Phase 7")

    return app
