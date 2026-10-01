"""Shared fixtures.

All market data used in tests is SYNTHETIC (see pitquant.data.providers.synthetic).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.orm import Session, sessionmaker

from pitquant.config.settings import Settings, load_settings
from pitquant.db.session import create_all, make_engine, make_session_factory
from pitquant.jobs.demo import load_synthetic_market

NY = ZoneInfo("America/New_York")
MAD = ZoneInfo("Europe/Madrid")


def ny(*a: int) -> datetime:
    return datetime(*a, tzinfo=NY)  # type: ignore[misc]


def utc(*a: int) -> datetime:
    return datetime(*a, tzinfo=UTC)  # type: ignore[misc]


def sid(session: Session, provider_key: str) -> str:
    """security_id of a synthetic security by its provider key (e.g. 'S-A')."""
    from sqlalchemy import select

    from pitquant.db.models import ProviderKey

    return session.scalars(
        select(ProviderKey.security_id).where(ProviderKey.provider_key == provider_key)
    ).one()


@pytest.fixture(scope="session")
def settings() -> Settings:
    return load_settings()


@pytest.fixture
def factory() -> sessionmaker[Session]:
    """Fresh empty in-memory database per test."""
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_all(engine)
    return make_session_factory(engine)


@pytest.fixture
def session(factory: sessionmaker[Session]) -> Iterator[Session]:
    s = factory()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture(scope="session")
def market_factory(settings: Settings) -> sessionmaker[Session]:
    """In-memory database loaded ONCE with the synthetic market. Treat as read-only."""
    engine = make_engine("sqlite+pysqlite:///:memory:")
    create_all(engine)
    f = make_session_factory(engine)
    load_synthetic_market(f, settings)
    return f


@pytest.fixture
def market(market_factory: sessionmaker[Session]) -> Iterator[Session]:
    s = market_factory()
    try:
        yield s
    finally:
        s.rollback()
        s.close()
