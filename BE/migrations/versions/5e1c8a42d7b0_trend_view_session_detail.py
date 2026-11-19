"""Record the originating chat response on each trend view.

Revision ID: 5e1c8a42d7b0
Revises: 6f91c2a0d4e8
"""

import sqlalchemy as sa
from alembic import op

revision = "5e1c8a42d7b0"
down_revision = "6f91c2a0d4e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trend_view", sa.Column("session_detail_id", sa.BigInteger(), nullable=True))
    op.execute(
        """
        UPDATE trend_view AS view
        SET session_detail_id = linked.session_detail_id
        FROM (
            SELECT result.trend_view_id, MIN(result.session_detail_id) AS session_detail_id
            FROM chat_result AS result
            JOIN session_detail AS message
              ON message.session_detail_id = result.session_detail_id
            JOIN trend_view AS linked_view
              ON linked_view.view_id = result.trend_view_id
             AND linked_view.session_id = message.session_id
            GROUP BY result.trend_view_id
            HAVING COUNT(DISTINCT result.session_detail_id) = 1
        ) AS linked
        WHERE view.view_id = linked.trend_view_id
        """
    )
    op.create_foreign_key(
        "fk_trend_view_message_same_session",
        "trend_view",
        "session_detail",
        ["session_id", "session_detail_id"],
        ["session_id", "session_detail_id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_trend_view_message_same_session", "trend_view", type_="foreignkey")
    op.drop_column("trend_view", "session_detail_id")
