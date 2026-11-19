"""Put the numbered unit aliases on the CDU process hierarchy."""

from alembic import op

revision = "7f4d54dc99b2"
down_revision = "59828e8d9a1c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM equipment_alias
        USING generate_series(1, 6) AS pump(number)
        WHERE equipment_alias.equipment_id = 'P' || pump.number
          AND equipment_alias.equipment_alias_name = pump.number || '호기'
        """
    )
    op.execute(
        """
        UPDATE equipment_group
        SET equipment_group_name = '상압증류(CDU) 1호기'
        WHERE equipment_group_id = 'CUD-01'
          AND equipment_group_name = '상압증류(CUD) 1호기'
        """
    )
    op.execute(
        """
        INSERT INTO equipment_group_alias (equipment_group_id, equipment_group_alias_name)
        SELECT unit.equipment_group_id, alias.name
        FROM equipment_group AS unit
        CROSS JOIN (VALUES ('1호기'), ('CDU'), ('CDU 1호기'), ('상압증류 1호기')) AS alias(name)
        WHERE unit.equipment_group_id = 'CUD-01'
          AND NOT EXISTS (
              SELECT 1 FROM equipment_group_alias AS existing
              WHERE existing.equipment_group_id = unit.equipment_group_id
                AND existing.equipment_group_alias_name = alias.name
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM equipment_group_alias
        WHERE equipment_group_id = 'CUD-01'
          AND equipment_group_alias_name IN ('1호기', 'CDU', 'CDU 1호기', '상압증류 1호기')
        """
    )
    op.execute(
        """
        UPDATE equipment_group
        SET equipment_group_name = '상압증류(CUD) 1호기'
        WHERE equipment_group_id = 'CUD-01'
          AND equipment_group_name = '상압증류(CDU) 1호기'
        """
    )
    op.execute(
        """
        INSERT INTO equipment_alias (equipment_id, equipment_alias_name)
        SELECT equipment.equipment_id, pump.number || '호기'
        FROM generate_series(1, 6) AS pump(number)
        JOIN equipment ON equipment.equipment_id = 'P' || pump.number
        WHERE equipment.equipment_type = '펌프'
          AND NOT EXISTS (
              SELECT 1 FROM equipment_alias
              WHERE equipment_alias.equipment_id = equipment.equipment_id
                AND equipment_alias.equipment_alias_name = pump.number || '호기'
          )
        """
    )
