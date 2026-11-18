"""Correct vibration sensor unit from mm/s RMS to mm/s RMS.

Revision ID: 86d9e2184a37
Revises: 6f4c2a91b730
"""

import sqlalchemy as sa
from alembic import op

revision = "86d9e2184a37"
down_revision = "6f4c2a91b730"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE sensor SET unit = 'mm/s RMS' WHERE unit = 'mm/s RMS'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE sensor SET unit = 'mm/s RMS' WHERE unit = 'mm/s RMS'"))
