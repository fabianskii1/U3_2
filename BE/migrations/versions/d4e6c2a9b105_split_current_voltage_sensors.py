"""Manage motor current and voltage as separate IT and ET sensors.

Revision ID: d4e6c2a9b105
Revises: b71d3e0c9a42
"""

import sqlalchemy as sa
from alembic import op

revision = "d4e6c2a9b105"
down_revision = "b71d3e0c9a42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    for pump in range(1, 7):
        ut = f"10-UT-1{pump}04"
        for tag, name, unit, measurement_range in (
            ("IT", "모터 전류", "A RMS", "1~100 A RMS"),
            ("ET", "모터 선간전압", "V RMS", "20~600 V L-L"),
        ):
            sensor_id = f"10-{tag}-1{pump}04"
            conn.execute(
                sa.text(
                    """INSERT INTO sensor (
                           sensor_id, equipment_id, measurement_name,
                           installation_location, unit, manufacturer, model_name,
                           measurement_range, pid_drawing_number, management_grade
                       )
                       SELECT :sensor_id, equipment_id, :name,
                              installation_location, :unit, manufacturer, model_name,
                              :measurement_range, pid_drawing_number, management_grade
                       FROM sensor WHERE sensor_id = :ut
                       ON CONFLICT (sensor_id) DO NOTHING"""
                ),
                {
                    "sensor_id": sensor_id,
                    "name": name,
                    "unit": unit,
                    "measurement_range": measurement_range,
                    "ut": ut,
                },
            )
            result = conn.execute(
                sa.text(
                    """UPDATE sensor_signal SET sensor_id = :sensor_id
                       WHERE signal_id = :sensor_id AND sensor_id = :ut"""
                ),
                {"sensor_id": sensor_id, "ut": ut},
            )
            if result.rowcount != 1:
                raise RuntimeError(f"Expected one signal to move from {ut} to {sensor_id}")

    # Foreign keys protect any UT references that cannot be assigned to IT or ET.
    result = conn.execute(sa.text("DELETE FROM sensor WHERE sensor_id LIKE '10-UT-1_04'"))
    if result.rowcount != 6:
        raise RuntimeError(f"Expected six UT sensors, deleted {result.rowcount}")


def downgrade() -> None:
    raise RuntimeError("Cannot safely merge separate IT and ET sensor references")
