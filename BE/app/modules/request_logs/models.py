from sqlalchemy import BigInteger, Column, Integer, Table
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import code_fk, fk, metadata, pk, text, time

api_request_log = Table(
    "api_request_log",
    metadata,
    pk("api_request_log_id"),
    time("started_at"),
    time("finished_at", True),
    Column("duration_ms", BigInteger, nullable=True),
    text("http_method"),
    text("api_path"),
    Column("http_status_code", Integer, nullable=True),
)


api_request_error_log = Table(
    "api_request_error_log",
    metadata,
    pk("api_request_error_log_id"),
    fk("api_request_log_id", "api_request_log.api_request_log_id"),
    Column("request_body", JSONB, nullable=True),
    Column("response_body", JSONB, nullable=True),
    text("error_code"),
    text("error_message"),
    Column("query_params", JSONB, nullable=True),
    text("exception_type", True),
    text("stack_trace", True),
)


chat_request_log = Table(
    "chat_request_log",
    metadata,
    pk("chat_request_log_id"),
    fk("api_request_log_id", "api_request_log.api_request_log_id"),
    text("status"),
    fk("user_id", "user.user_id", True),
    fk("session_id", "session.session_id", True),
    fk("session_detail_id", "session_detail.session_detail_id", True),
    code_fk("plant_id", "plant.plant_id", True),
    code_fk("equipment_group_id", "equipment_group.equipment_group_id", True),
    code_fk("equipment_id", "equipment.equipment_id", True),
    code_fk("sensor_id", "sensor.sensor_id", True),
    text("sensor_interval", True),
    time("sensor_start_time", True),
    time("sensor_end_time", True),
    fk("report_id", "report.report_id", True),
    Column("report_version", Integer, nullable=True),
)


chat_request_error_log = Table(
    "chat_request_error_log",
    metadata,
    pk("chat_request_error_log_id"),
    fk("chat_request_log_id", "chat_request_log.chat_request_log_id"),
    Column("request_body", JSONB, nullable=True),
    Column("response_body", JSONB, nullable=True),
    time("occurred_at"),
    text("error_stage"),
    text("error_code"),
    text("error_message"),
    text("exception_type", True),
    text("stack_trace", True),
)
