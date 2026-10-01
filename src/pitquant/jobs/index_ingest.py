"""Index-history ingestion: source → archived bytes → events → securities → build."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from pitquant.config.settings import Settings
from pitquant.db.models import DataQualityIssue, MembershipBuild
from pitquant.universe.events import (
    BuildReport,
    EventSource,
    IndexEventProvider,
    apply_ticker_changes,
    build_membership,
    events_hash,
)
from pitquant.universe.sources.common import register_event_securities


def ingest_event_source(
    session: Session,
    src: EventSource,
    *,
    exchange: str,
    currency: str,
    country: str,
    expected_size: tuple[int, int] | None,
) -> BuildReport:
    ev_hash = events_hash(src.events)
    existing = session.scalars(
        select(MembershipBuild).where(
            MembershipBuild.membership_source == src.membership_source,
            MembershipBuild.raw_source_hash == src.raw_source_hash,
            MembershipBuild.events_hash == ev_hash,
            MembershipBuild.status == "ok",
        )
    ).first()
    if existing is not None:  # same bytes, same parse -> same build (idempotent)
        return BuildReport(
            existing.build_id, "ok", existing.n_events, int(existing.report.get("n_intervals", 0))
        )
    keys, reg = register_event_securities(
        session, src, exchange=exchange, currency=currency, country=country
    )
    apply_ticker_changes(session, src, keys, exchange)
    for w in (*src.warnings, *reg.warnings):
        session.add(
            DataQualityIssue(
                entity="index_events",
                check_name="source_warning",
                severity="medium",
                details={"detail": w, "source": src.membership_source},
            )
        )
    rep = build_membership(session, src, keys, expected_size=expected_size)
    rep.warnings.extend([*src.warnings, *reg.warnings])
    return rep


def ingest_index_history(
    session: Session,
    provider: IndexEventProvider,
    index_code: str,
    settings: Settings,
    *,
    currency: str,
    country: str,
) -> BuildReport:
    cfg = settings.universe(index_code)
    src = provider.load(session, index_code)
    return ingest_event_source(
        session,
        src,
        exchange=cfg.calendar,
        currency=currency,
        country=country,
        expected_size=cfg.expected_size,
    )
