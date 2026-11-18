"""Create CDU signal definitions and 1-minute telemetry hypertables.

Revision ID: 9c2e7d4a1b63
Revises: 4b8e6f1c2a90
"""

import sqlalchemy as sa
from alembic import op

revision = "9c2e7d4a1b63"
down_revision = "4b8e6f1c2a90"
branch_labels = None
depends_on = None

# signal tag, instrument tag, measurement name, unit, CSV column
SIGNALS = (
    ("TT", "TT", "01", "유체 온도", "°C", "fluid_temp_c"),
    ("TT", "TT", "02", "베어링 온도", "°C", "bearing_temp_c"),
    ("ST", "ST", "03", "회전수", "rpm", "motor_rpm"),
    ("IT", "UT", "04", "모터 전류", "A RMS", "motor_current_a"),
    ("ET", "UT", "04", "모터 선간전압", "V RMS", "voltage_v"),
    ("VT", "VT", "05", "진동 속도 RMS", "mm/s RMS", "vibration_rms_mm_s"),
    ("PT", "PT", "06", "흡입압", "kPa(g)", "suction_pressure_kpa_g"),
    ("PT", "PT", "07", "토출압", "kPa(g)", "discharge_pressure_kpa_g"),
)


def upgrade() -> None:
    op.create_table(
        "sensor_signal",
        sa.Column("signal_id", sa.String(30), primary_key=True),
        sa.Column("sensor_id", sa.String(30), sa.ForeignKey("sensor.sensor_id"), nullable=False),
        sa.Column("measurement_name", sa.String(100), nullable=False),
        sa.Column("unit", sa.String(30), nullable=False),
        sa.Column("source_column", sa.String(100), nullable=False),
        sa.UniqueConstraint("sensor_id", "source_column", name="uq_sensor_signal_source"),
    )
    signal = sa.table(
        "sensor_signal",
        sa.column("signal_id", sa.String(30)),
        sa.column("sensor_id", sa.String(30)),
        sa.column("measurement_name", sa.String(100)),
        sa.column("unit", sa.String(30)),
        sa.column("source_column", sa.String(100)),
    )
    op.bulk_insert(
        signal,
        [
            {
                "signal_id": f"10-{signal_tag}-1{pump}{suffix}",
                "sensor_id": f"10-{sensor_tag}-1{pump}{suffix}",
                "measurement_name": name,
                "unit": unit,
                "source_column": source,
            }
            for pump in range(1, 7)
            for signal_tag, sensor_tag, suffix, name, unit, source in SIGNALS
        ],
    )
    op.create_table(
        "sensor_data_1m",
        sa.Column(
            "signal_id", sa.String(30), sa.ForeignKey("sensor_signal.signal_id"), nullable=False
        ),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("signal_id", "measured_at"),
    )
    op.create_table(
        "equipment_run_state_1m",
        sa.Column(
            "equipment_id", sa.String(30), sa.ForeignKey("equipment.equipment_id"), nullable=False
        ),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_status", sa.String(16), nullable=False),
        sa.CheckConstraint("run_status IN ('RUNNING', 'STOPPED')", name="run_status_allowed"),
        sa.PrimaryKeyConstraint("equipment_id", "measured_at"),
    )
    op.execute(
        sa.text(
            "SELECT create_hypertable('sensor_data_1m', "
            "by_range('measured_at', INTERVAL '7 days'), if_not_exists => TRUE)"
        )
    )
    op.execute(
        sa.text(
            "SELECT create_hypertable('equipment_run_state_1m', "
            "by_range('measured_at', INTERVAL '7 days'), if_not_exists => TRUE)"
        )
    )


def downgrade() -> None:
    op.drop_table("equipment_run_state_1m")
    op.drop_table("sensor_data_1m")
    op.drop_table("sensor_signal")
