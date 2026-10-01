"""CNMV filings (D-04 vertical slice, ADR-0018)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from pitquant.db.base import UTCDateTime

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# Append-only tables introduced by this revision (union with 0001's list = models).
ADDED_IMMUTABLE_TABLES = ("cnmv_filings",)


def upgrade() -> None:
    op.create_table(
        "cnmv_filings",
        sa.Column("filing_id", sa.String(length=36), nullable=False),
        sa.Column("nreg", sa.String(length=20), nullable=False),
        sa.Column("doc_kind", sa.String(length=30), nullable=False),
        sa.Column("cif", sa.String(length=20), nullable=False),
        sa.Column("company", sa.String(length=300), nullable=False),
        sa.Column("security_id", sa.String(length=36), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("period_label", sa.String(length=60), nullable=True),
        sa.Column("publication_date", sa.Date(), nullable=False),
        sa.Column("publication_time", sa.String(length=8), nullable=True),
        sa.Column("last_modification_date", sa.Date(), nullable=True),
        sa.Column("modifications", sa.JSON(), nullable=False),
        sa.Column("availability_precision", sa.String(length=20), nullable=False),
        sa.Column("effective_available_at", UTCDateTime(), nullable=False),
        sa.Column("availability_rule", sa.String(length=80), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("detail_archive_id", sa.String(length=36), nullable=False),
        sa.Column("data_archive_id", sa.String(length=36), nullable=True),
        sa.Column("data_sha256", sa.String(length=64), nullable=True),
        sa.Column("parser_version", sa.String(length=50), nullable=False),
        sa.Column("ingested_at", UTCDateTime(), nullable=False),
        sa.CheckConstraint(
            "availability_precision IN ('DATE_ONLY','DATETIME')",
            name=op.f("ck_cnmv_filings_precision_values"),
        ),
        sa.ForeignKeyConstraint(
            ["data_archive_id"],
            ["raw_source_archive.archive_id"],
            name=op.f("fk_cnmv_filings_data_archive_id_raw_source_archive"),
        ),
        sa.ForeignKeyConstraint(
            ["detail_archive_id"],
            ["raw_source_archive.archive_id"],
            name=op.f("fk_cnmv_filings_detail_archive_id_raw_source_archive"),
        ),
        sa.ForeignKeyConstraint(
            ["security_id"],
            ["securities.security_id"],
            name=op.f("fk_cnmv_filings_security_id_securities"),
        ),
        sa.PrimaryKeyConstraint("filing_id", name=op.f("pk_cnmv_filings")),
        sa.UniqueConstraint("nreg", "data_sha256", name="uq_cnmv_nreg_content"),
    )
    op.create_index(op.f("ix_cnmv_filings_nreg"), "cnmv_filings", ["nreg"], unique=False)
    with op.batch_alter_table("fundamental_facts") as batch:
        batch.add_column(sa.Column("cnmv_filing_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            op.f("fk_fundamental_facts_cnmv_filing_id_cnmv_filings"),
            "cnmv_filings",
            ["cnmv_filing_id"],
            ["filing_id"],
        )
        batch.create_index(
            op.f("ix_fundamental_facts_cnmv_filing_id"), ["cnmv_filing_id"], unique=False
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
    with op.batch_alter_table("fundamental_facts") as batch:
        batch.drop_index(op.f("ix_fundamental_facts_cnmv_filing_id"))
        batch.drop_constraint(
            op.f("fk_fundamental_facts_cnmv_filing_id_cnmv_filings"), type_="foreignkey"
        )
        batch.drop_column("cnmv_filing_id")
    op.drop_index(op.f("ix_cnmv_filings_nreg"), table_name="cnmv_filings")
    op.drop_table("cnmv_filings")
