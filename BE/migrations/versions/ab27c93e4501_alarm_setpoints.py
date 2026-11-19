"""Store versioned setpoints and the alarm timeline."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ExcludeConstraint

revision = "ab27c93e4501"
down_revision = "5e1c8a42d7b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.create_table(
        "setpoint",
        sa.Column("setpoint_id", sa.String(128), primary_key=True),
        sa.Column(
            "equipment_id", sa.String(30), sa.ForeignKey("equipment.equipment_id"), nullable=False
        ),
        sa.Column("sensor_id", sa.String(30), sa.ForeignKey("sensor.sensor_id"), nullable=False),
        sa.Column(
            "signal_id", sa.String(30), sa.ForeignKey("sensor_signal.signal_id"), nullable=False
        ),
        sa.Column("alarm_level", sa.Integer(), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("operator", sa.Text(), nullable=False),
        sa.Column("calculation_type", sa.Text(), nullable=False),
        sa.Column("parameter", sa.Float(), nullable=False),
        sa.Column("reference", sa.Text()),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("filter_minutes", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True)),
        sa.CheckConstraint("alarm_level BETWEEN 1 AND 4", name="setpoint_level_range"),
        sa.CheckConstraint(
            """(direction = 'HIGH' AND operator = '>=') OR (direction = 'LOW' AND operator = '<=')""",
            name="setpoint_direction_operator",
        ),
        sa.CheckConstraint(
            """(calculation_type = 'FIXED' AND reference IS NULL) OR
            (calculation_type IN ('BASELINE_RATIO', 'BASELINE_OFFSET', 'EXPECTED_OFFSET')
                AND reference IS NOT NULL)""",
            name="setpoint_calculation_reference",
        ),
        sa.CheckConstraint(
            "parameter > '-Infinity' AND parameter < 'Infinity'", name="setpoint_parameter_finite"
        ),
        sa.CheckConstraint("filter_minutes > 0", name="setpoint_filter_positive"),
        sa.CheckConstraint("effective_to > effective_from", name="setpoint_effective_period"),
        ExcludeConstraint(
            ("sensor_id", "="),
            ("direction", "="),
            ("alarm_level", "="),
            (sa.literal_column("tstzrange(effective_from, effective_to, '[)')"), "&&"),
            name="setpoint_no_overlap",
            using="gist",
        ),
    )
    op.alter_column("alarm", "occurred_at", new_column_name="alarm_start_time")
    op.drop_column("alarm", "measured_value")
    op.drop_column("alarm", "threshold_value")
    op.add_column("alarm", sa.Column("source_alarm_id", sa.String(128)))
    op.create_unique_constraint("uq_alarm_source_alarm_id", "alarm", ["source_alarm_id"])
    op.add_column("alarm", sa.Column("setpoint_id", sa.String(128)))
    op.create_foreign_key(
        "fk_alarm_setpoint", "alarm", "setpoint", ["setpoint_id"], ["setpoint_id"]
    )
    op.add_column("alarm", sa.Column("event_type", sa.Text()))
    for column in ("alarm_end_time", "sensor_start_time", "sensor_end_time"):
        op.add_column("alarm", sa.Column(column, sa.DateTime(timezone=True)))


def downgrade() -> None:
    raise RuntimeError("Restore a backup to recover the dropped alarm measurement columns")
