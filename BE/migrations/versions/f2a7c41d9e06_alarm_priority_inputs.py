"""Record active state and supplied CoF without inferring either for past alarms.

Revision ID: f2a7c41d9e06
Revises: d4e6c2a9b105
"""

import sqlalchemy as sa
from alembic import op

revision = "f2a7c41d9e06"
down_revision = "d4e6c2a9b105"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("alarm", sa.Column("is_active", sa.Boolean(), nullable=True))
    op.add_column("alarm", sa.Column("cof_score", sa.Float(), nullable=True))
    op.create_check_constraint(
        "alarm_cof_finite", "alarm", "cof_score > '-Infinity' AND cof_score < 'Infinity'"
    )


def downgrade() -> None:
    op.drop_constraint("alarm_cof_finite", "alarm", type_="check")
    op.drop_column("alarm", "cof_score")
    op.drop_column("alarm", "is_active")
