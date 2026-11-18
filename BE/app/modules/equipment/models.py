from sqlalchemy import CheckConstraint, Column, Integer, String, Table

from app.db.base import code_fk, code_pk, metadata, pk, text

equipment = Table(
    "equipment",
    metadata,
    code_pk("equipment_id"),
    code_fk("plant_id", "plant.plant_id"),
    code_fk("equipment_group_id", "equipment_group.equipment_group_id"),
    text("equipment_name"),
    text("equipment_type"),
    Column("equipment_status", Integer, nullable=False),
    Column("equipment_level", Integer, nullable=False),
    text("location", nullable=True),
    CheckConstraint("equipment_status BETWEEN 0 AND 4", name="equipment_status_range"),
)


equipment_alias = Table(
    "equipment_alias",
    metadata,
    pk("equipment_alias_id"),
    code_fk("equipment_id", "equipment.equipment_id"),
    text("equipment_alias_name"),
)


sensor = Table(
    "sensor",
    metadata,
    code_pk("sensor_id"),
    code_fk("equipment_id", "equipment.equipment_id"),
    Column("measurement_name", String(100), nullable=False),
    text("installation_location", nullable=True),
    Column("unit", String(30), nullable=False),
    text("manufacturer", nullable=True),
    text("model_name", nullable=True),
    text("measurement_range", nullable=True),
    text("pid_drawing_number", nullable=True),
    text("management_grade", nullable=True),
)


sensor_alias = Table(
    "sensor_alias",
    metadata,
    pk("sensor_alias_id"),
    code_fk("sensor_id", "sensor.sensor_id"),
    text("sensor_alias_name"),
)
