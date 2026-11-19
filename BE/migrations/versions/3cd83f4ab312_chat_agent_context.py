"""Preserve confirmed chat targets and pending choices between turns."""

import sqlalchemy as sa
from alembic import op

revision = "3cd83f4ab312"
down_revision = "f2a7c41d9e06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("session_detail", sa.Column("agent_context", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("session_detail", "agent_context")
