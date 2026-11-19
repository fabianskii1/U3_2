"""Track client chat request IDs to prevent duplicate trend results.

Revision ID: 9d2e6a4f81b3
Revises: 81e2b7c4d9a0
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "9d2e6a4f81b3"
down_revision = "81e2b7c4d9a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_request_log",
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_unique_constraint(
        "uq_chat_request_session_request", "chat_request_log", ["session_id", "request_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_chat_request_session_request", "chat_request_log", type_="unique")
    op.drop_column("chat_request_log", "request_id")
