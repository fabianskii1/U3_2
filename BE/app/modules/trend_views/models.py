from sqlalchemy import CheckConstraint, Column, DateTime, Index, Table
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base import code_fk, fk, metadata, time

trend_view = Table(
    "trend_view",
    metadata,
    Column(
        "view_id",
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    ),
    fk("session_id", "session.session_id"),
    code_fk("plant_id", "plant.plant_id"),
    code_fk("equipment_group_id", "equipment_group.equipment_group_id"),
    code_fk("equipment_id", "equipment.equipment_id", True),
    Column("config", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=sql_text("now()")),
    time("expires_at", True),
    CheckConstraint("jsonb_typeof(config) = 'object'", name="ck_trend_view_config_object"),
    CheckConstraint(
        "COALESCE(jsonb_typeof(config->'version') = 'number', false) "
        "AND COALESCE(jsonb_typeof(config->'series') = 'array', false) "
        "AND COALESCE(jsonb_typeof(config->'showAnomalies') = 'boolean', false)",
        name="ck_trend_view_config_shape",
    ),
    CheckConstraint(
        "expires_at IS NULL OR expires_at > created_at",
        name="ck_trend_view_expiry_after_creation",
    ),
    Index("ix_trend_view_session_created", "session_id", "created_at"),
)
