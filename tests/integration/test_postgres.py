"""PostgreSQL-only checks: migrations and DB-level immutability triggers (ADR-0010).
Runs in CI against a real PostgreSQL service; skipped locally unless PITQUANT_PG_URL is set."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

PG_URL = os.environ.get("PITQUANT_PG_URL")
pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not PG_URL, reason="PITQUANT_PG_URL not set"),
]


def _alembic(*args: str) -> None:
    env = {**os.environ, "PITQUANT_DATABASE_URL": PG_URL or ""}
    subprocess.run([sys.executable, "-m", "alembic", *args], check=True, env=env)


def test_migration_roundtrip_and_triggers() -> None:
    _alembic("upgrade", "head")
    eng = create_engine(PG_URL or "")
    with eng.begin() as c:
        c.execute(
            text(
                "INSERT INTO data_sources(name, provider_type, is_synthetic, is_point_in_time)"
                " VALUES ('t', 'x', true, true)"
            )
        )
        sid = c.execute(text("SELECT source_id FROM data_sources WHERE name='t'")).scalar_one()
        c.execute(
            text("INSERT INTO raw_records VALUES ('r1', :s, 'id', now(), '{}', 'h')"), {"s": sid}
        )
    with pytest.raises(DBAPIError), eng.begin() as c:
        c.execute(text("UPDATE raw_records SET payload_hash='x'"))
    with pytest.raises(DBAPIError), eng.begin() as c:
        c.execute(text("DELETE FROM raw_records"))
    _alembic("downgrade", "base")
