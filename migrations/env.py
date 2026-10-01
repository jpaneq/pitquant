"""Alembic environment. The URL comes from PITQUANT_DATABASE_URL when set."""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import engine_from_config, pool

from pitquant.db import models  # noqa: F401  (register tables)
from pitquant.db.base import Base

config = context.config
if os.environ.get("PITQUANT_DATABASE_URL"):
    config.set_main_option("sqlalchemy.url", os.environ["PITQUANT_DATABASE_URL"])

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
