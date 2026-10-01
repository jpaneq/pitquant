"""Run the strict PostgreSQL suite against a local, embedded PostgreSQL 16 (no Docker).

Uses the `pgserver` wheel (PostgreSQL binaries inside the virtualenv). The data directory
lives under ``.pgdata/`` and is recreated on every run so migrations start from zero.

    python scripts/local_pg.py            # strict suite + alembic upgrade/check/downgrade
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / ".pgdata"


def main() -> int:
    try:
        import pgserver  # type: ignore[import-not-found]
    except ImportError:
        print("pgserver not installed: pip install -e '.[dev,postgres,localpg]'", file=sys.stderr)
        return 2
    shutil.rmtree(DATA, ignore_errors=True)
    server = pgserver.get_server(str(DATA), cleanup_mode="stop")
    server.psql("CREATE DATABASE pit;")
    url = f"postgresql+psycopg://postgres@/pit?host={DATA}"
    env = {**os.environ, "PITQUANT_PG_URL": url, "PITQUANT_REQUIRE_POSTGRES": "1"}
    steps = [
        [sys.executable, "-m", "pytest", "-m", "postgres", "-rA", "-p", "no:warnings"],
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        [sys.executable, "-m", "alembic", "check"],
        [sys.executable, "-m", "alembic", "downgrade", "base"],
    ]
    for cmd in steps:
        rc = subprocess.call(cmd, cwd=ROOT, env={**env, "PITQUANT_DATABASE_URL": url})
        if rc != 0:
            print(f"FAILED: {' '.join(cmd[1:])}", file=sys.stderr)
            return rc
    print("local PostgreSQL strict suite: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
