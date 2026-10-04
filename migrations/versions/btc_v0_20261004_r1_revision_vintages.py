"""Preserve reverting source vintages and one frozen decision per cohort.

MUST_REBASE_MIGRATIONS_BEFORE_MERGE.
"""

from alembic import op

revision = "btc_v0_20261004_r1"
down_revision = "btc_v0_20261004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("btc_data") as batch:
        batch.drop_constraint("uq_btc_data_version", type_="unique")
        batch.create_unique_constraint(
            "uq_btc_data_version",
            ["source", "metric", "cohort", "exchange_timestamp", "value_hash", "retrieved_at"],
        )
    with op.batch_alter_table("btc_feature_snapshots") as batch:
        batch.create_unique_constraint(
            "uq_btc_frozen_decision", ["decision_at", "cohort", "feature_version"]
        )


def downgrade() -> None:
    with op.batch_alter_table("btc_feature_snapshots") as batch:
        batch.drop_constraint("uq_btc_frozen_decision", type_="unique")
    with op.batch_alter_table("btc_data") as batch:
        batch.drop_constraint("uq_btc_data_version", type_="unique")
        batch.create_unique_constraint(
            "uq_btc_data_version",
            ["source", "metric", "cohort", "exchange_timestamp", "value_hash"],
        )
