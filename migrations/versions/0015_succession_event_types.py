"""succession event types: name/ticker/identifier changes of the same security

Revision ID: 0015
Revises: 0014
"""

from __future__ import annotations

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

NAME = "ck_security_succession_event_type_values"
OLD = "event_type IN ('NAME_CHANGE_SAME_SECURITY','TICKER_CHANGE_SAME_SECURITY','SECURITY_REPLACEMENT_SUCCESSOR','SHARE_CLASS_CHANGE','TRUE_INDEX_EXIT','TRUE_INDEX_ENTRY','SAME_SECURITY_IDENTITY_LINK')"
NEW = "event_type IN ('NAME_CHANGE_SAME_SECURITY','TICKER_CHANGE_SAME_SECURITY','NAME_TICKER_CHANGE_SAME_SECURITY','NAME_TICKER_IDENTIFIER_CHANGE_SAME_SECURITY','IDENTIFIER_CHANGE_SAME_SECURITY','SECURITY_REPLACEMENT_SUCCESSOR','SHARE_CLASS_CHANGE','TRUE_INDEX_EXIT','TRUE_INDEX_ENTRY','SAME_SECURITY_IDENTITY_LINK')"


def _swap(old: str, new: str) -> None:
    with op.batch_alter_table("security_succession", schema=None) as b:
        b.drop_constraint(op.f(NAME), type_="check")
        b.create_check_constraint(op.f(NAME), new)


def upgrade() -> None:
    _swap(OLD, NEW)


def downgrade() -> None:
    _swap(NEW, OLD)
