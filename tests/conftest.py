"""Shared fixtures.

All market data used in tests is SYNTHETIC (see pitquant.data.providers.synthetic).
"""

from __future__ import annotations

import os as _os
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


# ───────────────────── strict PostgreSQL mode (CI job "postgres") ─────────────────────
# With PITQUANT_REQUIRE_POSTGRES=1 the run FAILS if: the URL is missing or not PostgreSQL,
# zero postgres tests are collected/executed, or any postgres test is skipped.


_REQUIRE_PG = _os.environ.get("PITQUANT_REQUIRE_POSTGRES") == "1"
_pg_executed: list[str] = []


def pytest_configure(config: pytest.Config) -> None:
    if _REQUIRE_PG:
        url = _os.environ.get("PITQUANT_PG_URL", "")
        if not url.startswith("postgresql"):
            raise pytest.UsageError(
                "PITQUANT_REQUIRE_POSTGRES=1 but PITQUANT_PG_URL is not a PostgreSQL URL "
                "(SQLite is not an acceptable substitute)"
            )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if _REQUIRE_PG and not any(i.get_closest_marker("postgres") for i in items):
        raise pytest.UsageError("strict PostgreSQL mode: zero postgres tests collected")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]):  # type: ignore[no-untyped-def]
    outcome = yield
    rep = outcome.get_result()
    if item.get_closest_marker("postgres") is None:
        return
    if rep.when == "call" and rep.passed:
        _pg_executed.append(item.nodeid)
    if _REQUIRE_PG and rep.skipped:
        rep.outcome = "failed"
        rep.longrepr = f"strict PostgreSQL mode: {item.nodeid} was skipped"


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if _REQUIRE_PG and not _pg_executed and exitstatus == 0:
        session.exitstatus = 1
