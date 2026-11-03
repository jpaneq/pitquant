"""Append-only forward pilot journal, independent of prior research manifests."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from pitquant.db.base import UTCDateTime

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None
ADDED_IMMUTABLE_TABLES = ("forward_pilot_records",)


def upgrade() -> None:
    op.create_table(
        "forward_pilot_records",
        sa.Column("record_id", sa.String(36), primary_key=True),
        sa.Column("record_key", sa.String(250), nullable=False, unique=True),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("market", sa.String(10), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("created_at", UTCDateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_forward_pilot_records_kind", "forward_pilot_records", ["kind"])
    op.create_index("ix_forward_pilot_records_market", "forward_pilot_records", ["market"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "CREATE TRIGGER forward_pilot_records_append_only BEFORE UPDATE OR DELETE ON forward_pilot_records FOR EACH ROW EXECUTE FUNCTION pitquant_forbid_mutation();"
        )
    elif op.get_bind().dialect.name == "sqlite":
        for action in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER forward_pilot_records_no_{action.lower()} BEFORE {action} ON forward_pilot_records BEGIN SELECT RAISE(ABORT, 'forward pilot journal is append-only'); END;"
            )


def downgrade() -> None:
    op.drop_table("forward_pilot_records")
