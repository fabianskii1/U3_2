from sqlalchemy import CheckConstraint, Column, Float, Integer, Table

from app.db.base import code_fk, metadata, pk, text, time

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
    CheckConstraint("alarm_level BETWEEN 0 AND 4", name="alarm_level_range"),
)
