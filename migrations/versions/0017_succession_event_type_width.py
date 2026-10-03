"""Allow the long corporate identity event types introduced in 0015.

Revision ID: 0017
Revises: 0016
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("security_succession") as batch:
        batch.alter_column(
            "event_type", existing_type=sa.String(32), type_=sa.String(64), existing_nullable=False
        )


def downgrade() -> None:
    # Refuse lossy rollback instead of truncating immutable historical facts.
    count = (
        op.get_bind()
        .execute(sa.text("SELECT count(*) FROM security_succession WHERE length(event_type) > 32"))
        .scalar_one()
    )
    if count:
        raise RuntimeError("Cannot narrow event_type: immutable event values exceed 32 characters")
    with op.batch_alter_table("security_succession") as batch:
        batch.alter_column(
            "event_type", existing_type=sa.String(64), type_=sa.String(32), existing_nullable=False
        )
