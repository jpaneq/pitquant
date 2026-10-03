# ruff: noqa: E501
"""Migration 0019 (ADR-0037): existing simulations / events / counterfactuals are backfilled DETERMINISTICALLY to engine v1 / schema 1 without any UPDATE."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[2]


def dummy(col: sa.Column) -> object:  # type: ignore[type-arg]
    t = col.type
    if isinstance(t, sa.JSON):
        return {}
    if isinstance(t, sa.Boolean):
        return 0
    if isinstance(t, sa.Integer):
        return 1
    if isinstance(t, sa.Float):
        return 1.5
    if isinstance(t, sa.Date):
        return date(2016, 6, 30)
    if "DateTime" in type(t).__name__ or isinstance(t, sa.DateTime):
        return datetime(2016, 6, 30, 23, tzinfo=UTC)
    return "x"


def insert(conn: sa.Connection, table: str, **fixed: object) -> None:
    t = sa.Table(table, sa.MetaData(), autoload_with=conn)
    row = {
        c.name: fixed.get(c.name, dummy(c))
        for c in t.columns
        if (not c.nullable and c.server_default is None) or c.name in fixed
    }
    conn.execute(t.insert().values(**row))


def test_existing_rows_are_backfilled_to_v1_by_the_migration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = f"sqlite:///{tmp_path / 'm.db'}"
    monkeypatch.setenv("PITQUANT_DATABASE_URL", url)
    cfg = Config(str(ROOT / "alembic.ini"))
    command.upgrade(cfg, "0018")
    eng = sa.create_engine(url)
    with eng.begin() as c:
        insert(
            c,
            "simulations",
            simulation_id="sim-old",
            mode="MANUAL_SIMULATION",
            asset_type="EQUITY",
            plan_origin="PITQUANT",
            side="LONG",
            created_at=datetime(2016, 6, 30, 23, tzinfo=UTC),
            decision_at=datetime(2016, 6, 30, 23, tzinfo=UTC),
        )
        insert(
            c,
            "simulation_events",
            event_id="ev-old",
            simulation_id="sim-old",
            sequence_number=0,
            event_type="SIMULATION_CREATED",
            engine_version="sim-engine-2",
        )
        insert(c, "simulation_counterfactuals", counterfactual_id="cf-old", simulation_id="sim-old")
    command.upgrade(cfg, "0019")
    with eng.connect() as c:
        assert (
            c.execute(
                sa.text(
                    "SELECT simulation_engine_version FROM simulations WHERE simulation_id='sim-old'"
                )
            ).scalar_one()
            == "v1"
        )
        assert c.execute(
            sa.text(
                "SELECT event_schema_version, engine_version FROM simulation_events WHERE event_id='ev-old'"
            )
        ).one() == (1, "sim-engine-2")  # the event row itself is untouched
        assert (
            c.execute(
                sa.text("SELECT simulation_engine_version FROM simulation_counterfactuals")
            ).scalar_one()
            == "v1"
        )
    command.downgrade(cfg, "0018")
    command.upgrade(cfg, "0019")  # reversible and re-appliable
