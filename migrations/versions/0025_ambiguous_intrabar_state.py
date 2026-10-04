"""routine evaluations: AMBIGUOUS_INTRABAR state (plan de mejora P0)

Revision ID: 0025
Revises: 0024
"""

from __future__ import annotations

from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None

OLD = "state IN ('IN_PROGRESS','TARGET_HIT','STOP_HIT','AMBIGUOUS_STOP','EXPIRED')"
NEW = "state IN ('IN_PROGRESS','TARGET_HIT','STOP_HIT','AMBIGUOUS_STOP','AMBIGUOUS_INTRABAR','EXPIRED')"
TABLES = ("daily_evaluations", "daily_virtual_evaluations")


def _swap(expr: str) -> None:
    for t in TABLES:
        name = f"ck_{t}_state_values"
        with op.batch_alter_table(t, schema=None) as batch:
            batch.drop_constraint(op.f(name), type_="check")
            batch.create_check_constraint(op.f(name), expr)


def upgrade() -> None:
    _swap(NEW)


def downgrade() -> None:
    _swap(OLD)
