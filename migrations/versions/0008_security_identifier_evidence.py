"""security identifier evidence (CUSIP & co, with evidence class)

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-02 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from pitquant.db.base import UTCDateTime

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

ADDED_IMMUTABLE_TABLES = ("security_identifier_evidence",)


def upgrade() -> None:
    op.create_table(
        "security_identifier_evidence",
        sa.Column("evidence_id", sa.String(length=36), nullable=False),
        sa.Column("security_id", sa.String(length=36), nullable=False),
        sa.Column("id_type", sa.String(length=10), nullable=False),
        sa.Column("value", sa.String(length=20), nullable=False),
        sa.Column("kind", sa.String(length=12), nullable=False),
        sa.Column("observed_on", sa.Date(), nullable=False),
        sa.Column("source_kind", sa.String(length=40), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("archive_id", sa.String(length=36), nullable=True),
        sa.Column("source_sha256", sa.String(length=64), nullable=True),
        sa.Column("excerpt", sa.String(length=600), nullable=True),
        sa.Column("parser_version", sa.String(length=50), nullable=False),
        sa.Column("ingested_at", UTCDateTime(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('OFFICIAL','DERIVED','VENDOR','UNRESOLVED')",
            name=op.f("ck_security_identifier_evidence_kind_values"),
        ),
        sa.ForeignKeyConstraint(
            ["archive_id"],
            ["raw_source_archive.archive_id"],
            name=op.f("fk_security_identifier_evidence_archive_id_raw_source_archive"),
        ),
        sa.ForeignKeyConstraint(
            ["security_id"],
            ["securities.security_id"],
            name=op.f("fk_security_identifier_evidence_security_id_securities"),
        ),
        sa.PrimaryKeyConstraint("evidence_id", name=op.f("pk_security_identifier_evidence")),
        sa.UniqueConstraint(
            "security_id", "id_type", "value", "observed_on", "source_url", name="uq_sec_ident_ev"
        ),
    )
    with op.batch_alter_table("security_identifier_evidence", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_security_identifier_evidence_security_id"), ["security_id"], unique=False
        )
    if op.get_bind().dialect.name == "postgresql":
        for t in ADDED_IMMUTABLE_TABLES:
            op.execute(
                f"CREATE TRIGGER {t}_append_only BEFORE UPDATE OR DELETE ON {t} "
                f"FOR EACH ROW EXECUTE FUNCTION pitquant_forbid_mutation();"
            )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for t in ADDED_IMMUTABLE_TABLES:
            op.execute(f"DROP TRIGGER IF EXISTS {t}_append_only ON {t};")
    with op.batch_alter_table("security_identifier_evidence", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_security_identifier_evidence_security_id"))
    op.drop_table("security_identifier_evidence")
