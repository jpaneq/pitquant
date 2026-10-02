"""Developer UI V0.1 backend: thin read-only endpoints under ``/dev`` (ADR-0028).

All logic lives here and in the engines; the HTML page is a dumb client. Nothing here produces a
signal, BUY/HOLD/SELL, a trade plan or any holdout outcome. Holdout dates are refused.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from pitquant.config.settings import Settings
from pitquant.core.errors import HoldoutAccessError
from pitquant.db.models import (
    IdentifierHistory,
    Issuer,
    Security,
    SecurityIdentifierEvidence,
    SP500MembershipEvent,
    TickerHistory,
)
from pitquant.reconstruct import UnknownSecurityRef, reconstruct, resolve_security

STATIC = Path(__file__).parent / "static"


def get_db(request: Request) -> Iterator[Session]:
    factory: sessionmaker[Session] = request.app.state.session_factory
    s = factory()
    try:
        yield s
    finally:
        s.close()


DB = Annotated[Session, Depends(get_db)]


def make_dev_router(settings: Settings) -> APIRouter:
    r = APIRouter(prefix="/dev", tags=["developer-ui"])

    @r.get("/", include_in_schema=False)
    def page() -> FileResponse:
        return FileResponse(STATIC / "dev.html")

    @r.get("/status")
    def status(s: DB) -> dict[str, Any]:
        from pitquant.readiness import data_readiness
        from pitquant.research_readiness import research_readiness

        rep = data_readiness(s, settings)
        rf = research_readiness(s, settings)
        ho = settings.validation.final_holdout
        comps = {c.name: {"status": str(c.status), "gaps": c.gaps[:3]} for c in rep.components}
        return {
            "components": comps,
            "research": {
                "flags": rf.flags,
                "status": rf.status,
                "reasons": rf.reasons,
                "metrics": rf.metrics,
            },
            "holdout": {
                "state": "SEALED",
                "start": str(ho.start),
                "end": str(ho.end),
                "outcomes_exposed": False,
            },
            "model": {"baseline_built": False},
            "note": "No signals, no BUY/HOLD/SELL, no trade plan in this UI.",
        }

    @r.get("/security/search")
    def search(q: str, s: DB) -> list[dict[str, Any]]:
        ql = q.strip()
        ids: set[str] = set()
        ids |= set(
            s.scalars(select(TickerHistory.security_id).where(TickerHistory.ticker == ql.upper()))
        )
        ids |= set(
            s.scalars(
                select(IdentifierHistory.security_id).where(IdentifierHistory.value == ql.upper())
            )
        )
        ids |= set(
            s.scalars(
                select(SecurityIdentifierEvidence.security_id).where(
                    SecurityIdentifierEvidence.value == ql.upper()
                )
            )
        )
        like = f"%{ql}%"
        ids |= set(s.scalars(select(Security.security_id).where(Security.name.ilike(like))))
        ids |= set(
            s.scalars(
                select(Security.security_id)
                .join(Issuer, Issuer.issuer_id == Security.issuer_id)
                .where(Issuer.name.ilike(like))
            )
        )
        if ql.upper().startswith("CIK:"):
            with contextlib.suppress(UnknownSecurityRef):
                ids.add(resolve_security(s, ql).security_id)
        out = []
        for sid in sorted(ids)[:25]:
            sec = s.get_one(Security, sid)
            issuer = s.get(Issuer, sec.issuer_id) if sec.issuer_id else None
            out.append(
                {
                    "security_id": sid,
                    "name": sec.name,
                    "issuer_id": sec.issuer_id,
                    "issuer": issuer.name if issuer else None,
                    "exchange": sec.exchange,
                    "role": sec.role,
                    "identifiers": [
                        f"{i.id_type}={i.value} [{i.valid_from}..{i.valid_to or ''}]"
                        for i in s.scalars(
                            select(IdentifierHistory).where(IdentifierHistory.security_id == sid)
                        )
                    ]
                    + [
                        f"{e.id_type}={e.value} ({e.kind}, {e.observed_on})"
                        for e in s.scalars(
                            select(SecurityIdentifierEvidence)
                            .where(SecurityIdentifierEvidence.security_id == sid)
                            .order_by(SecurityIdentifierEvidence.observed_on.desc())
                            .limit(3)
                        )
                    ],
                    "ticker_history": [
                        f"{t.ticker} {t.valid_from}..{t.valid_to or ''}"
                        for t in s.scalars(
                            select(TickerHistory).where(TickerHistory.security_id == sid)
                        )
                    ],
                }
            )
        return out

    @r.get("/time-machine/{security}/{on}")
    def time_machine(security: str, on: date, s: DB) -> dict[str, Any]:
        ho = settings.validation.final_holdout
        if ho.start <= on <= ho.end:
            raise HTTPException(403, "date inside the sealed final holdout")
        try:
            return asdict(reconstruct(s, security, on))
        except UnknownSecurityRef as e:
            raise HTTPException(404, str(e)) from e

    @r.get("/features/{security}/{on}")
    def features(security: str, on: date, s: DB, benchmark: str | None = None) -> dict[str, Any]:
        from pitquant.features.v0.engine import FEATURE_VERSION, compute_features

        try:
            sec = resolve_security(s, security)
            bench = resolve_security(s, benchmark).security_id if benchmark else None
            res = compute_features(s, sec.security_id, on, benchmark_security_id=bench)
        except UnknownSecurityRef as e:
            raise HTTPException(404, str(e)) from e
        except HoldoutAccessError as e:
            raise HTTPException(403, str(e)) from e
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        return {
            "security_id": sec.security_id,
            "decision_session": str(on),
            "feature_version": FEATURE_VERSION,
            "features": [
                {
                    "name": f.name,
                    "value": f.value,
                    "coverage_status": f.coverage_status,
                    "reason": f.reason,
                    "formula": f.formula,
                    "available_at": f.available_at.isoformat() if f.available_at else None,
                    "provenance": f.provenance,
                }
                for f in res
            ],
        }

    @r.get("/universe/SP500/{on}")
    def universe(on: date, s: DB) -> dict[str, Any]:
        from pitquant.db.models import IndexCurrentAnchor
        from pitquant.universe.sp500_cohorts import _members_at, us_cohort_readiness

        ho = settings.validation.final_holdout
        summ = us_cohort_readiness(s)
        row = next((x for x in summ.rows if x.date >= on), None)
        anchor = s.scalars(
            select(IndexCurrentAnchor)
            .where(IndexCurrentAnchor.index_code == "SP500")
            .order_by(IndexCurrentAnchor.ingested_at.desc())
        ).first()
        members = None
        if (
            anchor is not None
            and row is not None
            and row.membership_ready
            and not (ho.start <= on <= ho.end)
        ):
            m = _members_at(s, anchor, summ.d02, on)
            members = sorted(m) if m is not None else None
        run_id = s.scalars(
            select(SP500MembershipEvent.run_id).order_by(SP500MembershipEvent.created_at.desc())
        ).first()
        near = (
            s.scalars(
                select(SP500MembershipEvent).where(
                    SP500MembershipEvent.run_id == run_id,
                    or_(
                        SP500MembershipEvent.discovery_date.between(
                            date(on.year, on.month, 1),
                            date(on.year + (on.month // 12), on.month % 12 + 1, 1),
                        )
                    ),
                )
            ).all()
            if run_id
            else []
        )
        return {
            "date": str(on),
            "anchor_status": anchor.status if anchor else "BLOCKED",
            "membership_proven": bool(row and row.membership_ready),
            "members": members,
            "readiness_row": asdict(row) if row else None,
            "evidence_events_this_month": [
                {
                    "added": e.added_ticker,
                    "removed": e.removed_ticker,
                    "status": e.status,
                    "tier": e.source_tier,
                    "source_url": e.source_url,
                    "reason": e.reason,
                }
                for e in near
            ],
            "d02": {
                "research_ready": summ.d02.d02_research_ready,
                "longest_run_cohorts": len(summ.d02.longest_run),
                "unconfirmed_events": len(summ.d02.breaks),
            },
        }

    return r
