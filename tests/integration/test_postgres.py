"""PostgreSQL-only: migrations and DB-level immutability triggers (ADR-0010).

Locally these are skipped without ``PITQUANT_PG_URL``. In CI the dedicated job sets
``PITQUANT_REQUIRE_POSTGRES=1``: then a missing/non-PostgreSQL URL, any skip, or zero
collected postgres tests FAILS the run (tests/conftest.py) — no false green.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pitquant.db.models import IMMUTABLE_TABLES
from pitquant.db.session import make_session_factory

PG_URL = os.environ.get("PITQUANT_PG_URL", "")
pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not PG_URL, reason="PITQUANT_PG_URL not set"),
]
ROOT = Path(__file__).resolve().parents[2]
T = datetime(2020, 6, 15, 20, 0, tzinfo=UTC)


def _alembic(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PITQUANT_DATABASE_URL": PG_URL, "PYTHONPATH": str(ROOT / "src")}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        check=True,
        env=env,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="module")
def pg() -> Iterator[Engine]:
    assert PG_URL.startswith("postgresql"), "SQLite is not a substitute for these tests"
    _alembic("downgrade", "base")
    _alembic("upgrade", "head")
    eng = create_engine(PG_URL)
    _seed(eng)
    yield eng
    eng.dispose()
    _alembic("downgrade", "base")


def _seed(eng: Engine) -> None:
    from pitquant.db.models import (
        DataSource,
        FeatureSnapshotRow,
        FundamentalFact,
        IndexEvent,
        ModelRow,
        ModelVersion,
        Prediction,
        Security,
    )

    with make_session_factory(eng)() as s:
        s.add_all(
            [
                Security(security_id="sec-1", name="PG TEST", exchange="XNYS", currency="USD"),
                DataSource(source_id=1, name="pg-test", provider_type="x"),
                ModelRow(model_id="m", horizon="12m", kind="baseline"),
            ]
        )
        s.flush()
        s.add_all(
            [
                ModelVersion(
                    model_version="frozen",
                    model_id="m",
                    scoring_version="s",
                    feature_version="f",
                    code_version="c",
                    config_hash="h",
                    seed=1,
                    frozen=True,
                ),
                ModelVersion(
                    model_version="draft",
                    model_id="m",
                    scoring_version="s",
                    feature_version="f",
                    code_version="c",
                    config_hash="h",
                    seed=1,
                    frozen=False,
                ),
                FeatureSnapshotRow(
                    snapshot_id="snap-1",
                    security_id="sec-1",
                    as_of=T,
                    feature_version="f",
                    data_version="d",
                    code_version="c",
                    features={},
                    availability={},
                    missing_mask={},
                    imputed_mask={},
                    dq_warnings=[],
                    max_available_at=T,
                    content_hash="h",
                ),
                FundamentalFact(
                    fact_id="fact-1",
                    security_id="sec-1",
                    concept="Revenues",
                    period_end=T.date(),
                    value=1.0,
                    unit="USD",
                    available_at=T,
                ),
                IndexEvent(
                    event_id="ev-1",
                    index_code="SP500",
                    event_type="INDEX_ADD",
                    effective_date=T.date(),
                    membership_source="t",
                    source_event_id="1",
                    source_confidence="CANONICAL",
                    raw_source_hash="h",
                ),
            ]
        )
        s.flush()
        s.add(
            Prediction(
                prediction_id="pred-1",
                snapshot_id="snap-1",
                snapshot_hash="h",
                security_id="sec-1",
                as_of=T,
                execution_at=datetime(2020, 6, 16, 13, 30, tzinfo=UTC),
                horizon="12m",
                model_version="frozen",
                signal="HOLD",
                probability=0.5,
                scores={},
                explanation={},
                data_version="d",
                feature_version="f",
                scoring_version="s",
                config_hash="h",
                code_version="c",
                seed=1,
            )
        )
        s.commit()


def _rejected(eng: Engine, sql: str) -> None:
    with pytest.raises(DBAPIError) as exc, eng.begin() as c:
        c.execute(text(sql))
    assert "append-only" in str(exc.value) or "frozen" in str(exc.value)


def test_migration_matches_models(pg: Engine) -> None:
    out = _alembic("check")
    assert "No new upgrade operations detected" in (out.stdout + out.stderr)


def test_trigger_list_matches_models() -> None:
    path = next((ROOT / "migrations" / "versions").glob("0001_*.py"))
    spec = importlib.util.spec_from_file_location("m0001", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert set(mod.IMMUTABLE_TABLES) == set(IMMUTABLE_TABLES)


def test_triggers_installed_on_every_immutable_table(pg: Engine) -> None:
    with pg.connect() as c:
        rows = (
            c.execute(
                text(
                    "SELECT event_object_table FROM information_schema.triggers "
                    "WHERE trigger_name LIKE '%_append_only'"
                )
            )
            .scalars()
            .all()
        )
    assert set(rows) == set(IMMUTABLE_TABLES)


def test_prediction_update_rejected(pg: Engine) -> None:
    _rejected(pg, "UPDATE predictions SET signal='BUY' WHERE prediction_id='pred-1'")


def test_prediction_delete_rejected(pg: Engine) -> None:
    _rejected(pg, "DELETE FROM predictions WHERE prediction_id='pred-1'")


def test_snapshot_update_rejected(pg: Engine) -> None:
    _rejected(pg, "UPDATE feature_snapshots SET content_hash='x' WHERE snapshot_id='snap-1'")


def test_snapshot_delete_rejected(pg: Engine) -> None:
    _rejected(pg, "DELETE FROM feature_snapshots WHERE snapshot_id='snap-1'")


def test_fundamental_fact_update_rejected(pg: Engine) -> None:
    _rejected(pg, "UPDATE fundamental_facts SET value=2 WHERE fact_id='fact-1'")


def test_index_event_delete_rejected(pg: Engine) -> None:
    _rejected(pg, "DELETE FROM index_events WHERE event_id='ev-1'")


def test_frozen_model_version_update_rejected(pg: Engine) -> None:
    _rejected(pg, "UPDATE model_versions SET params='{}' WHERE model_version='frozen'")


def test_draft_model_version_can_be_frozen(pg: Engine) -> None:
    with pg.begin() as c:
        c.execute(text("UPDATE model_versions SET frozen=true WHERE model_version='draft'"))
    _rejected(pg, "UPDATE model_versions SET seed=2 WHERE model_version='draft'")


def test_timestamps_round_trip_as_utc(pg: Engine) -> None:
    from pitquant.db.models import FeatureSnapshotRow

    with Session(pg) as s:
        row = s.get_one(FeatureSnapshotRow, "snap-1")
        assert row.as_of == T and row.as_of.utcoffset().total_seconds() == 0  # type: ignore[union-attr]


def test_identity_status_check_and_default(pg: Engine) -> None:
    with pg.connect() as c:
        status = c.execute(
            text("SELECT identity_status FROM index_events WHERE event_id='ev-1'")
        ).scalar_one()
    assert status == "RESOLVED"  # server default for rows predating 0002
    with pytest.raises(DBAPIError), pg.begin() as c:
        c.execute(
            text(
                "INSERT INTO index_events (event_id, index_code, event_type, effective_date, "
                "membership_source, source_event_id, source_confidence, raw_source_hash, "
                "ingested_at, identity_status) VALUES ('ev-bad', 'X', 'INDEX_ADD', "
                "'2020-01-02', 'S', 'bad', 'CANONICAL', 'h', now(), 'PROBABLY_SAME')"
            )
        )


def test_new_build_not_eligible_by_default(pg: Engine) -> None:
    with pg.begin() as c:
        c.execute(
            text(
                "INSERT INTO membership_builds (build_id, index_code, membership_source, "
                "source_confidence, raw_source_hash, events_hash, n_events, status, report, "
                "built_at) VALUES ('b-default', 'X', 'S', 'CANONICAL', 'h', 'e', 0, 'ok', "
                "'{}', now())"
            )
        )
        eligible = c.execute(
            text(
                "SELECT eligible_for_final_model_validation FROM membership_builds "
                "WHERE build_id='b-default'"
            )
        ).scalar_one()
    assert eligible is False
