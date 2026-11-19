"""Persist alarm intake receipts and initial report snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "4be3617a210d"
down_revision = "3cd83f4ab312"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alarm_intake",
        sa.Column("source_event_id", sa.String(128), primary_key=True),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("alarm_id", sa.BigInteger(), sa.ForeignKey("alarm.alarm_id")),
        sa.Column("selected_alarm_id", sa.BigInteger(), sa.ForeignKey("alarm.alarm_id")),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("response", sa.JSON()),
    )
    op.create_index("ix_alarm_intake_report", "alarm_intake", ["selected_alarm_id", "processed_at"])


def downgrade() -> None:
    op.drop_index("ix_alarm_intake_report", table_name="alarm_intake")
    op.drop_table("alarm_intake")
