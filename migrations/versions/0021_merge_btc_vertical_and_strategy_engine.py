"""merge btc vertical and strategy engine

Revision ID: 0021
Revises: btc_v0_20261004_r1, 0020
Create Date: 2026-10-04 14:19:33.611746
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = '0021'
down_revision = ('btc_v0_20261004_r1', '0020')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
