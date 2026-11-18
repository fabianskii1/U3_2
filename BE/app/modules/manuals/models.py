from sqlalchemy import Table

from app.db.base import code_fk, metadata, pk, text

equipment_manual = Table(
    "equipment_manual",
    metadata,
    pk("equipment_manual_id"),
    code_fk("equipment_id", "equipment.equipment_id"),
    text("equipment_manual_title"),
    text("equipment_manual_link"),
)
