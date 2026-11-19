from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Table,
    UniqueConstraint,
)
from sqlalchemy import (
    text as sql_text,
)
from sqlalchemy.dialects.postgresql import UUID

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
    Column("reply_to_session_detail_id", BigInteger, nullable=True),
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
    UniqueConstraint("session_id", "session_detail_id", name="uq_session_detail_session_message"),
    ForeignKeyConstraint(
        ["session_id", "reply_to_session_detail_id"],
        ["session_detail.session_id", "session_detail.session_detail_id"],
        name="fk_session_detail_reply_same_session",
    ),
    CheckConstraint(
        "reply_to_session_detail_id IS NULL OR type = 'llm'",
        name="ck_session_detail_reply_llm",
    ),
    Index("ix_session_detail_reply_to", "reply_to_session_detail_id"),
)


chat_result = Table(
    "chat_result",
    metadata,
    Column(
        "result_id",
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sql_text("gen_random_uuid()"),
    ),
    fk("session_detail_id", "session_detail.session_detail_id"),
    text("result_type"),
    Column("trend_view_id", UUID(as_uuid=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=sql_text("now()")),
    ForeignKeyConstraint(["trend_view_id"], ["trend_view.view_id"]),
    CheckConstraint("result_type = 'trend'", name="ck_chat_result_trend_type"),
    UniqueConstraint("session_detail_id", "trend_view_id", name="uq_chat_result_message_trend"),
    Index("ix_chat_result_trend_view", "trend_view_id"),
)
