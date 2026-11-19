from sqlalchemy import JSON, Boolean, CheckConstraint, Column, Float, Index, Integer, String, Table

from app.db.base import code_fk, fk, metadata, pk, text, time

alarm = Table(
    "alarm",
    metadata,
    pk("alarm_id"),
    code_fk("equipment_id", "equipment.equipment_id"),
    code_fk("sensor_id", "sensor.sensor_id"),
    text("alarm_type"),
    time("occurred_at"),
    Column("measured_value", Float, nullable=False),
    Column("threshold_value", Float, nullable=False),
    text("unit"),
    Column("alarm_level", Integer, nullable=False),
    text("user_message"),
    Column("is_active", Boolean, nullable=True),
    Column("cof_score", Float, nullable=True),
    CheckConstraint("alarm_level BETWEEN 0 AND 4", name="alarm_level_range"),
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
