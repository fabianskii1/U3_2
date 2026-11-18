from sqlalchemy import Column, String, Table, UniqueConstraint

from app.db.base import code_fk, metadata, pk, text

user = Table(
    "user",
    metadata,
    pk("user_id"),
    code_fk("plant_id", "plant.plant_id"),
    text("role"),
    text("name"),
    text("user_number"),
    Column("login_id", String(255), nullable=False),
    text("login_pw"),
    UniqueConstraint("login_id", name="uq_user_login_id"),
)
