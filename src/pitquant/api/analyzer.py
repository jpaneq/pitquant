# ruff: noqa: E501
"""Analyzer HTTP surface (ADR-0029). Independent endpoints so panels load, cache and fail separately.

Every endpoint takes an optional ``as_of`` (ISO datetime WITH offset): default = now (CURRENT analysis);
dates inside the sealed holdout are refused (403). Nothing here computes finance: it calls
``pitquant.analyzer.service``.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session, sessionmaker

from pitquant.analyzer.search import search
from pitquant.analyzer.service import AnalyzerService, report_markdown
from pitquant.analyzer.trade_plan_v0 import position_size
from pitquant.config.settings import Settings
from pitquant.core.timeutils import utc_now


def get_db(request: Request) -> Iterator[Session]:
    factory: sessionmaker[Session] = request.app.state.session_factory
    s = factory()
    try:
        yield s
    finally:
        s.close()


DB = Annotated[Session, Depends(get_db)]


def make_analyzer_router(cfg: Settings) -> APIRouter:
    r = APIRouter(tags=["analyzer"])

    def now_for(as_of: str | None) -> datetime:
        if as_of is None:
            return utc_now()
        try:
            at = datetime.fromisoformat(as_of)
        except ValueError as e:
            raise HTTPException(422, f"invalid as_of {as_of!r}") from e
        if at.tzinfo is None:
            raise HTTPException(422, "as_of must include a UTC offset")
        ho = cfg.validation.final_holdout
        if ho.start <= at.date() <= ho.end:
            raise HTTPException(403, "as_of is inside the sealed final holdout")
        return at

    def resolve(s: Session, ident: str) -> str:
        res: dict[str, Any] = search(s, ident, limit=5)
        hits = [h for h in res["results"] if h["match_type"] in ("EXACT", "IDENTIFIER")]
        if len(hits) == 1:
            return str(hits[0]["security_id"])
        if len(hits) > 1:
            raise HTTPException(409, f"{ident!r} is ambiguous: {[h['ticker'] for h in hits]}")
        raise HTTPException(
            404,
            {
                "message": f"no security matches {ident!r}",
                "suggestions": [
                    {"ticker": h["ticker"], "name": h["name"], "match_type": h["match_type"]}
                    for h in res["results"]
                ],
            },
        )

    @r.get("/search")
    def _search(s: DB, q: str = Query(min_length=1), limit: int = 10) -> dict[str, Any]:
        return search(s, q, limit)

    @r.get("/analyzer/status")
    def status(s: DB) -> dict[str, Any]:
        svc = AnalyzerService(s, cfg)
        return {
            "as_of": utc_now().isoformat(),
            "providers": svc.providers(),
            "data_notice": svc.data_notice(),
            "engine_versions": svc.versions(),
            "holdout": {
                "state": "SEALED",
                "start": str(cfg.validation.final_holdout.start),
                "end": str(cfg.validation.final_holdout.end),
            },
        }

    def svc_for(
        s: Session, security: str, as_of: str | None
    ) -> tuple[AnalyzerService, str, datetime]:
        return AnalyzerService(s, cfg), resolve(s, security), now_for(as_of)

    @r.get("/analyzer/{security}/summary")
    def summary(security: str, s: DB, as_of: str | None = None) -> dict[str, Any]:
        v, sid, at = svc_for(s, security, as_of)
        return v.summary(sid, at)

    @r.get("/analyzer/{security}/quote")
    def quote(security: str, s: DB, as_of: str | None = None) -> dict[str, Any]:
        v, sid, at = svc_for(s, security, as_of)
        return v.quote(sid, at)

    @r.get("/analyzer/{security}/chart")
    def chart(security: str, s: DB, range: str = "1Y", as_of: str | None = None) -> dict[str, Any]:
        if range not in ("1M", "3M", "6M", "YTD", "1Y", "3Y", "5Y", "MAX"):
            raise HTTPException(
                422, "range must be one of 1M,3M,6M,YTD,1Y,3Y,5Y,MAX (no intraday data is ingested)"
            )
        v, sid, at = svc_for(s, security, as_of)
        return v.chart(sid, at, range)

    @r.get("/analyzer/{security}/explain")
    def explain(
        security: str, s: DB, panel: str = "analysis", as_of: str | None = None
    ) -> dict[str, Any]:
        if panel not in ("analysis", "trade-plan"):
            raise HTTPException(422, "panel must be 'analysis' or 'trade-plan'")
        v, sid, at = svc_for(s, security, as_of)
        return v.explain(sid, at, panel)

    @r.get("/analyzer/{security}/technicals")
    def technicals(security: str, s: DB, as_of: str | None = None) -> dict[str, Any]:
        v, sid, at = svc_for(s, security, as_of)
        return v.technicals(sid, at)

    @r.get("/analyzer/{security}/fundamentals")
    def fundamentals(security: str, s: DB, as_of: str | None = None) -> dict[str, Any]:
        v, sid, at = svc_for(s, security, as_of)
        return v.fundamentals(sid, at)

    @r.get("/analyzer/{security}/fundamental-history")
    def fundamental_history(
        security: str, s: DB, period: str = "quarterly", as_of: str | None = None
    ) -> dict[str, Any]:
        if period not in ("quarterly", "annual"):
            raise HTTPException(422, "period must be quarterly or annual")
        v, sid, at = svc_for(s, security, as_of)
        return v.fundamental_history(sid, at, period)

    @r.get("/analyzer/{security}/valuation")
    def valuation(security: str, s: DB, as_of: str | None = None) -> dict[str, Any]:
        v, sid, at = svc_for(s, security, as_of)
        return v.valuation(sid, at)

    @r.get("/analyzer/{security}/analysis")
    def analysis(security: str, s: DB, as_of: str | None = None) -> dict[str, Any]:
        v, sid, at = svc_for(s, security, as_of)
        return v.analysis(sid, at)

    @r.get("/analyzer/{security}/trade-plan")
    def trade_plan(security: str, s: DB, as_of: str | None = None) -> dict[str, Any]:
        v, sid, at = svc_for(s, security, as_of)
        return v.trade_plan(sid, at)

    @r.get("/analyzer/{security}/position-size")
    def pos_size(
        security: str, capital: float, risk_pct: float, entry: float, stop: float
    ) -> dict[str, Any]:
        return position_size(capital, risk_pct, entry, stop)

    @r.get("/analyzer/{security}/prediction")
    def prediction(security: str, s: DB, as_of: str | None = None) -> dict[str, Any]:
        v, sid, at = svc_for(s, security, as_of)
        return v.prediction(sid, at)

    @r.get("/analyzer/{security}/filings")
    def filings(security: str, s: DB, as_of: str | None = None, limit: int = 8) -> dict[str, Any]:
        v, sid, at = svc_for(s, security, as_of)
        return v.filings(sid, at, limit)

    @r.get("/analyzer/{security}/data-quality")
    def data_quality(security: str, s: DB, as_of: str | None = None) -> dict[str, Any]:
        v, sid, at = svc_for(s, security, as_of)
        return v.data_quality(sid, at)

    @r.get("/analyzer/{security}/report")
    def report(security: str, s: DB, format: str = "json", as_of: str | None = None) -> Any:
        v, sid, at = svc_for(s, security, as_of)
        rep = v.report(sid, at)
        if format == "markdown":
            return PlainTextResponse(
                report_markdown(rep), media_type="text/markdown; charset=utf-8"
            )
        return rep

    return r
