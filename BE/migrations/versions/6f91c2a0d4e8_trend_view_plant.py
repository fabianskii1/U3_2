"""Keep the plant context on persisted trend views.

Revision ID: 6f91c2a0d4e8
Revises: 9d2e6a4f81b3
"""

import sqlalchemy as sa
from alembic import op

revision = "6f91c2a0d4e8"
down_revision = "9d2e6a4f81b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trend_view", sa.Column("plant_id", sa.String(length=30), nullable=True))
    op.execute(
        """
        UPDATE trend_view AS view
        SET plant_id = group_row.plant_id
        FROM equipment_group AS group_row
        WHERE view.equipment_group_id = group_row.equipment_group_id
        """
    )
    op.alter_column("trend_view", "plant_id", existing_type=sa.String(length=30), nullable=False)
    op.create_foreign_key("fk_trend_view_plant", "trend_view", "plant", ["plant_id"], ["plant_id"])


def downgrade() -> None:
    op.drop_constraint("fk_trend_view_plant", "trend_view", type_="foreignkey")
    op.drop_column("trend_view", "plant_id")
