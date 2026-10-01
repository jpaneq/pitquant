"""identity status and final-validation eligibility

Membership and security identity are tracked separately (IDENTITY_UNRESOLVED intervals
are built but never backtested) and each build states whether it may feed final model
validation / the sealed holdout.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

_IDENTITY_CHECK = "identity_status IN ('RESOLVED','IDENTITY_UNRESOLVED')"


def upgrade() -> None:
    # Existing rows predate the distinction: they keep the old semantics (RESOLVED) and no
    # existing build is eligible until rebuilt (server_default false).
    for table in ("index_events", "index_membership"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(
                sa.Column(
                    "identity_status",
                    sa.String(length=30),
                    server_default="RESOLVED",
                    nullable=False,
                )
            )
            batch.create_check_constraint("identity_status_values", _IDENTITY_CHECK)
    with op.batch_alter_table("membership_builds") as batch:
        batch.add_column(
            sa.Column(
                "eligible_for_final_model_validation",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("membership_builds") as batch:
        batch.drop_column("eligible_for_final_model_validation")
    for table in ("index_membership", "index_events"):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(op.f(f"ck_{table}_identity_status_values"), type_="check")
            batch.drop_column("identity_status")
