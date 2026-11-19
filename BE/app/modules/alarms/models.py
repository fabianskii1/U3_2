from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    literal_column,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint

from app.db.base import code_fk, fk, metadata, pk, text, time

setpoint = Table(
    "setpoint",
    metadata,
    Column("setpoint_id", String(128), primary_key=True),
    code_fk("equipment_id", "equipment.equipment_id"),
    code_fk("sensor_id", "sensor.sensor_id"),
    code_fk("signal_id", "sensor_signal.signal_id"),
    Column("alarm_level", Integer, nullable=False),
    text("direction"),
    text("operator"),
    text("calculation_type"),
    Column("parameter", Float, nullable=False),
    text("reference", nullable=True),
    text("unit"),
    Column("filter_minutes", Integer, nullable=False),
    time("effective_from"),
    time("effective_to", nullable=True),
    CheckConstraint("alarm_level BETWEEN 1 AND 4", name="setpoint_level_range"),
    CheckConstraint(
        """(direction = 'HIGH' AND operator = '>=') OR (direction = 'LOW' AND operator = '<=')""",
        name="setpoint_direction_operator",
    ),
    CheckConstraint(
        """(calculation_type = 'FIXED' AND reference IS NULL) OR
        (calculation_type IN ('BASELINE_RATIO', 'BASELINE_OFFSET', 'EXPECTED_OFFSET')
            AND reference IS NOT NULL)""",
        name="setpoint_calculation_reference",
    ),
    CheckConstraint(
        "parameter > '-Infinity' AND parameter < 'Infinity'", name="setpoint_parameter_finite"
    ),
    CheckConstraint("filter_minutes > 0", name="setpoint_filter_positive"),
    CheckConstraint("effective_to > effective_from", name="setpoint_effective_period"),
    ExcludeConstraint(
        ("sensor_id", "="),
        ("direction", "="),
        ("alarm_level", "="),
        (literal_column("tstzrange(effective_from, effective_to, '[)')"), "&&"),
        name="setpoint_no_overlap",
        using="gist",
    ),
)

alarm = Table(
    "alarm",
    metadata,
    pk("alarm_id"),
    code_fk("equipment_id", "equipment.equipment_id"),
    code_fk("sensor_id", "sensor.sensor_id"),
    text("alarm_type"),
    time("alarm_start_time"),
    Column("source_alarm_id", String(128), unique=True),
    Column("setpoint_id", String(128), ForeignKey("setpoint.setpoint_id")),
    text("event_type", nullable=True),
    time("alarm_end_time", nullable=True),
    time("sensor_start_time", nullable=True),
    time("sensor_end_time", nullable=True),
    text("unit"),
    Column("alarm_level", Integer, nullable=False),
    text("user_message"),
    Column("is_active", Boolean, nullable=True),
    Column("cof_score", Float, nullable=True),
    Column("incident_id", String(64), ForeignKey("incident.incident_id"), nullable=True),
    Column("peak_level", Integer, nullable=True),
    CheckConstraint("alarm_level BETWEEN 0 AND 4", name="alarm_level_range"),
    CheckConstraint("peak_level BETWEEN 0 AND 4", name="alarm_peak_level_range"),
    Index("ix_alarm_incident", "incident_id"),
    CheckConstraint("cof_score > '-Infinity' AND cof_score < 'Infinity'", name="alarm_cof_finite"),
)

alarm_intake = Table(
    "alarm_intake",
    metadata,
    Column("source_event_id", String(128), primary_key=True),
    Column("request_digest", String(64), nullable=False),
    fk("alarm_id", "alarm.alarm_id", nullable=True),
    fk("selected_alarm_id", "alarm.alarm_id", nullable=True),
    time("processed_at", nullable=True),
    Column("response", JSON, nullable=True),
    Index("ix_alarm_intake_report", "selected_alarm_id", "processed_at"),
)
