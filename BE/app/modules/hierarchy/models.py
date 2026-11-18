from sqlalchemy import Table

from app.db.base import code_fk, code_pk, metadata, pk, text

plant = Table("plant", metadata, code_pk("plant_id"), text("plant_name"), text("location"))


plant_alias = Table(
    "plant_alias",
    metadata,
    pk("plant_alias_id"),
    code_fk("plant_id", "plant.plant_id"),
    text("plant_alias_name"),
)


equipment_group = Table(
    "equipment_group",
    metadata,
    code_pk("equipment_group_id"),
    code_fk("plant_id", "plant.plant_id"),
    text("equipment_group_name"),
)


equipment_group_alias = Table(
    "equipment_group_alias",
    metadata,
    pk("equipment_group_alias_id"),
    code_fk("equipment_group_id", "equipment_group.equipment_group_id"),
    text("equipment_group_alias_name"),
)
