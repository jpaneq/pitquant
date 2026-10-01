"""Engine/session factory and the ORM-level append-only guard (ADR-0010).

The PostgreSQL migration installs an equivalent trigger so the guarantee also holds for
raw SQL. Here we block UPDATE/DELETE of immutable rows at flush time, and also block
bulk ``session.execute(update(...))`` / ``delete(...)`` statements against those tables.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import ORMExecuteState, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from pitquant.core.errors import ImmutableRecordError
from pitquant.db.base import Base
from pitquant.db.models import IMMUTABLE_TABLES, ModelVersion


def _is_immutable(obj: Any) -> bool:
    table = getattr(obj, "__tablename__", None)
    if table in IMMUTABLE_TABLES:
        return True
    # A frozen model version can never change again (it is what predictions reference).
    # Freezing itself (False -> True) is allowed; anything after that is not.
    if isinstance(obj, ModelVersion):
        committed = inspect(obj).committed_state
        return bool(committed.get("frozen", obj.frozen))
    return False


def _before_flush(session: Session, _ctx: Any, _instances: Any) -> None:
    for obj in session.dirty:
        if session.is_modified(obj, include_collections=False) and _is_immutable(obj):
            raise ImmutableRecordError(
                f"{type(obj).__name__} is append-only; create a superseding record instead"
            )
    for obj in session.deleted:
        if _is_immutable(obj):
            raise ImmutableRecordError(f"{type(obj).__name__} rows cannot be deleted")


def _do_orm_execute(state: ORMExecuteState) -> None:
    if not (state.is_update or state.is_delete):
        return
    table_obj = getattr(state.statement, "table", None)
    name = getattr(table_obj, "name", None)
    if name in IMMUTABLE_TABLES:
        raise ImmutableRecordError(f"bulk UPDATE/DELETE on {name} is forbidden")


def install_immutability_guard(factory: sessionmaker[Session]) -> None:
    event.listen(factory, "before_flush", _before_flush)
    event.listen(factory, "do_orm_execute", _do_orm_execute)


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite") and ":memory:" in url:
        engine = create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    else:
        engine = create_engine(url, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn: Any, _rec: Any) -> None:
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    install_immutability_guard(factory)
    return factory


def create_all(engine: Engine) -> None:
    """For tests/dev only. Production schema is managed exclusively by Alembic."""
    Base.metadata.create_all(engine)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
