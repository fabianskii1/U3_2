"""Persist trend view snapshots and link chat responses to results.

Revision ID: 81e2b7c4d9a0
Revises: c73a9d2e1f40
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "81e2b7c4d9a0"
down_revision = "c73a9d2e1f40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "session_detail",
        sa.Column("reply_to_session_detail_id", sa.BigInteger(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_session_detail_session_message",
        "session_detail",
        ["session_id", "session_detail_id"],
    )
    op.create_foreign_key(
        "fk_session_detail_reply_same_session",
        "session_detail",
        "session_detail",
        ["session_id", "reply_to_session_detail_id"],
        ["session_id", "session_detail_id"],
    )
    op.create_check_constraint(
        "ck_session_detail_reply_llm",
        "session_detail",
        "reply_to_session_detail_id IS NULL OR type = 'llm'",
    )
    op.create_index("ix_session_detail_reply_to", "session_detail", ["reply_to_session_detail_id"])

    op.create_table(
        "trend_view",
        sa.Column(
            "view_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("equipment_group_id", sa.String(length=30), nullable=False),
        sa.Column("equipment_id", sa.String(length=30), nullable=True),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["session.session_id"]),
        sa.ForeignKeyConstraint(["equipment_group_id"], ["equipment_group.equipment_group_id"]),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.equipment_id"]),
        sa.CheckConstraint("jsonb_typeof(config) = 'object'", name="ck_trend_view_config_object"),
        sa.CheckConstraint(
            "COALESCE(jsonb_typeof(config->'version') = 'number', false) "
            "AND COALESCE(jsonb_typeof(config->'series') = 'array', false) "
            "AND COALESCE(jsonb_typeof(config->'showAnomalies') = 'boolean', false)",
            name="ck_trend_view_config_shape",
        ),
        sa.CheckConstraint(
            "expires_at IS NULL OR expires_at > created_at",
            name="ck_trend_view_expiry_after_creation",
        ),
    )
    op.create_index("ix_trend_view_session_created", "trend_view", ["session_id", "created_at"])

    op.create_table(
        "chat_result",
        sa.Column(
            "result_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("session_detail_id", sa.BigInteger(), nullable=False),
        sa.Column("result_type", sa.Text(), nullable=False),
        sa.Column("trend_view_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_detail_id"], ["session_detail.session_detail_id"]),
        sa.ForeignKeyConstraint(["trend_view_id"], ["trend_view.view_id"]),
        sa.CheckConstraint("result_type = 'trend'", name="ck_chat_result_trend_type"),
        sa.UniqueConstraint(
            "session_detail_id", "trend_view_id", name="uq_chat_result_message_trend"
        ),
    )
    op.create_index("ix_chat_result_trend_view", "chat_result", ["trend_view_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_result_trend_view", table_name="chat_result")
    op.drop_table("chat_result")
    op.drop_index("ix_trend_view_session_created", table_name="trend_view")
    op.drop_table("trend_view")
    op.drop_index("ix_session_detail_reply_to", table_name="session_detail")
    op.drop_constraint("ck_session_detail_reply_llm", "session_detail", type_="check")
    op.drop_constraint("fk_session_detail_reply_same_session", "session_detail", type_="foreignkey")
    op.drop_constraint("uq_session_detail_session_message", "session_detail", type_="unique")
    op.drop_column("session_detail", "reply_to_session_detail_id")
