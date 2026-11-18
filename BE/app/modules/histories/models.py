from sqlalchemy import BigInteger, Column, ForeignKey, Table

from app.db.base import code_fk, fk, metadata, pk, text, time

error_type = Table("error_type", metadata, pk("error_type_id"), text("error_type_name"))


error_history = Table(
    "error_history",
    metadata,
    pk("error_history_id"),
    time("start_time"),
    time("end_time", nullable=True),
    code_fk("plant_id", "plant.plant_id"),
    code_fk("equipment_group_id", "equipment_group.equipment_group_id"),
    code_fk("equipment_id", "equipment.equipment_id"),
)


error_history_types = Table(
    "error_history_types",
    metadata,
    Column(
        "error_history_id",
        BigInteger,
        ForeignKey("error_history.error_history_id"),
        primary_key=True,
    ),
    Column("error_type_id", BigInteger, ForeignKey("error_type.error_type_id"), primary_key=True),
)


maintenance_history = Table(
    "maintenance_history",
    metadata,
    pk("maintenance_history_id"),
    code_fk("equipment_id", "equipment.equipment_id"),
    time("start_time"),
    time("end_time", nullable=True),
    fk("error_history_id", "error_history.error_history_id", True),
)
