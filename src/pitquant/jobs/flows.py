"""Prefect wrappers (ADR-0006).

The logic lives in plain, idempotent functions in ``pitquant.jobs.ingest``; this module
only schedules them. Requires ``pip install .[orchestration]``.
"""

from __future__ import annotations

from datetime import date, timedelta

from pitquant.config.settings import get_settings
from pitquant.data.providers.base import (
    CorporateActionsProvider,
    FundamentalProvider,
    PriceProvider,
)
from pitquant.db.session import make_engine, make_session_factory, session_scope
from pitquant.jobs import ingest

try:
    from prefect import flow, task
except ImportError:  # pragma: no cover - orchestration extra not installed

    def flow(*_a, **_k):  # type: ignore[no-untyped-def]
        return lambda f: f

    def task(*_a, **_k):  # type: ignore[no-untyped-def]
        return lambda f: f


@task(retries=3, retry_delay_seconds=[60, 300, 900])  # exponential-ish backoff
def _prices(provider: PriceProvider, start: date, end: date) -> int:
    factory = make_session_factory(make_engine(get_settings().database.url))
    with session_scope(factory) as s:
        return ingest.ingest_prices(s, provider, None, start, end).inserted


@task(retries=3, retry_delay_seconds=[60, 300, 900])
def _corporate_actions(provider: CorporateActionsProvider, start: date, end: date) -> int:
    factory = make_session_factory(make_engine(get_settings().database.url))
    with session_scope(factory) as s:
        return ingest.ingest_corporate_actions(s, provider, start, end).inserted


@task(retries=3, retry_delay_seconds=[60, 300, 900])
def _fundamentals(provider: FundamentalProvider, start: date, end: date) -> int:
    cfg = get_settings()
    factory = make_session_factory(make_engine(cfg.database.url))
    with session_scope(factory) as s:
        return ingest.ingest_fundamentals(
            s, provider, start, end, cfg.pit.default_publication_lag_minutes
        ).inserted


@flow(name="daily-ingestion")
def daily_ingestion(
    price_provider: PriceProvider,
    ca_provider: CorporateActionsProvider,
    fundamental_provider: FundamentalProvider,
    run_date: date,
    lookback_days: int = 7,
) -> dict[str, int]:
    """Re-ingests a short trailing window every day; idempotency makes overlap harmless.
    Corporate actions run BEFORE prices so split days are not flagged as price jumps."""
    start = run_date - timedelta(days=lookback_days)
    return {
        "corporate_actions": _corporate_actions(ca_provider, start, run_date),
        "prices": _prices(price_provider, start, run_date),
        "fundamentals": _fundamentals(fundamental_provider, start, run_date),
    }
