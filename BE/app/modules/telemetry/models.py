from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Table,
    UniqueConstraint,
)

from app.db.base import code_fk, code_pk, metadata

sensor_signal = Table(
    "sensor_signal",
    metadata,
    code_pk("signal_id"),
    code_fk("sensor_id", "sensor.sensor_id"),
    Column("measurement_name", String(100), nullable=False),
    Column("unit", String(30), nullable=False),
    Column("source_column", String(100), nullable=False),
    UniqueConstraint("sensor_id", "source_column", name="uq_sensor_signal_source"),
)

sensor_data_1m = Table(
    "sensor_data_1m",
    metadata,
    Column("signal_id", String(30), ForeignKey("sensor_signal.signal_id"), primary_key=True),
    Column("measured_at", DateTime(timezone=True), primary_key=True),
    Column("value", Float, nullable=False),
)

equipment_run_state_1m = Table(
    "equipment_run_state_1m",
    metadata,
    Column("equipment_id", String(30), ForeignKey("equipment.equipment_id"), primary_key=True),
    Column("measured_at", DateTime(timezone=True), primary_key=True),
    Column("run_status", String(16), nullable=False),
    CheckConstraint("run_status IN ('RUNNING', 'STOPPED')", name="run_status_allowed"),
)

# TimescaleDB creates these descending time indexes with each hypertable.
Index("sensor_data_1m_measured_at_idx", sensor_data_1m.c.measured_at.desc())
Index("equipment_run_state_1m_measured_at_idx", equipment_run_state_1m.c.measured_at.desc())
