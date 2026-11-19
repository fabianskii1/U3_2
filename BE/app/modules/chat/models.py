from sqlalchemy import JSON, Column, Table

from app.db.base import code_fk, fk, metadata, pk, text, time

session = Table(
    "session",
    metadata,
    pk("session_id"),
    fk("user_id", "user.user_id", True),
    text("token_hash", True),
)


session_detail = Table(
    "session_detail",
    metadata,
    pk("session_detail_id"),
    fk("session_id", "session.session_id"),
    text("type"),
    text("content"),
    Column("agent_context", JSON, nullable=True),
    time("created_at"),
    code_fk("plant_id", "plant.plant_id", True),
    text("plant_alias", True),
    code_fk("equipment_group_id", "equipment_group.equipment_group_id", True),
    text("equipment_group_alias", True),
    code_fk("equipment_id", "equipment.equipment_id", True),
    text("equipment_alias", True),
    code_fk("sensor_id", "sensor.sensor_id", True),
    text("sensor_alias", True),
    text("sensor_interval", True),
    time("sensor_start_time", True),
    time("sensor_end_time", True),
    fk("report_id", "report.report_id", True),
)
