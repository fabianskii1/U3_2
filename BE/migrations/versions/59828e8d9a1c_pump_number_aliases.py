"""Seed confirmed Korean number aliases for the six CDU pumps."""

from alembic import op

revision = "59828e8d9a1c"
down_revision = "4be3617a210d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO equipment_alias (equipment_id, equipment_alias_name)
        SELECT equipment.equipment_id, pump.number || '호기'
        FROM generate_series(1, 6) AS pump(number)
        JOIN equipment ON equipment.equipment_id = 'P' || pump.number
        WHERE equipment.equipment_type = '펌프'
          AND NOT EXISTS (
              SELECT 1
              FROM equipment_alias
              WHERE equipment_alias.equipment_id = equipment.equipment_id
                AND equipment_alias.equipment_alias_name = pump.number || '호기'
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM equipment_alias
        USING generate_series(1, 6) AS pump(number)
        WHERE equipment_alias.equipment_id = 'P' || pump.number
          AND equipment_alias.equipment_alias_name = pump.number || '호기'
        """
    )
