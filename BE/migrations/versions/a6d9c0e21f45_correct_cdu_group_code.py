"""Correct the CDU equipment group code and process type."""

from alembic import op

revision = "a6d9c0e21f45"
down_revision = ("7f4d54dc99b2", "e4c7a1b29d63")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep the old row until every foreign key has been moved to the new ID.
    op.execute(
        """
        INSERT INTO equipment_group (equipment_group_id, plant_id, equipment_group_name, process_type)
        SELECT 'CDU-01', plant_id, equipment_group_name, 'CDU'
        FROM equipment_group
        WHERE equipment_group_id = 'CUD-01'
        ON CONFLICT (equipment_group_id) DO NOTHING
        """
    )
    op.execute(
        """
        DO $$
        DECLARE ref record;
        BEGIN
          FOR ref IN
            SELECT con.conrelid::regclass AS table_name, att.attname AS column_name
            FROM pg_constraint AS con
            JOIN pg_attribute AS att
              ON att.attrelid = con.conrelid AND att.attnum = con.conkey[1]
            WHERE con.contype = 'f'
              AND con.confrelid = 'equipment_group'::regclass
              AND array_length(con.conkey, 1) = 1
          LOOP
            EXECUTE format('UPDATE %s SET %I = $1 WHERE %I = $2',
                           ref.table_name, ref.column_name, ref.column_name)
              USING 'CDU-01', 'CUD-01';
          END LOOP;
        END $$
        """
    )
    op.execute("DELETE FROM equipment_group WHERE equipment_group_id = 'CUD-01'")
    op.execute(
        """
        UPDATE equipment_group
        SET process_type = 'CDU', equipment_group_name = '상압증류(CDU) 1호기'
        WHERE equipment_group_id = 'CDU-01'
          AND (process_type IS NULL OR process_type = 'CUD'
               OR equipment_group_name = '상압증류(CUD) 1호기')
        """
    )
    op.execute(
        """
        DELETE FROM equipment_group_alias AS old
        WHERE old.equipment_group_id = 'CDU-01'
          AND old.equipment_group_alias_name = 'CUD 1호기'
          AND EXISTS (
            SELECT 1 FROM equipment_group_alias AS corrected
            WHERE corrected.equipment_group_id = old.equipment_group_id
              AND corrected.equipment_group_alias_name = 'CDU 1호기'
          )
        """
    )
    op.execute(
        """
        UPDATE equipment_group_alias
        SET equipment_group_alias_name = 'CDU 1호기'
        WHERE equipment_group_id = 'CDU-01'
          AND equipment_group_alias_name = 'CUD 1호기'
        """
    )


def downgrade() -> None:
    raise RuntimeError("The corrected equipment group code cannot be safely restored")
