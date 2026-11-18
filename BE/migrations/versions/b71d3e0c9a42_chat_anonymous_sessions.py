"""Allow token-owned chat sessions before login is available.

Revision ID: b71d3e0c9a42
Revises: 9c2e7d4a1b63
"""

import sqlalchemy as sa
from alembic import op

revision = "b71d3e0c9a42"
down_revision = "9c2e7d4a1b63"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("session", "user_id", existing_type=sa.BigInteger(), nullable=True)
    op.add_column("session", sa.Column("token_hash", sa.Text(), nullable=True))


def downgrade() -> None:
    op.execute(sa.text('DELETE FROM "session" WHERE user_id IS NULL'))
    op.drop_column("session", "token_hash")
    op.alter_column("session", "user_id", existing_type=sa.BigInteger(), nullable=False)
