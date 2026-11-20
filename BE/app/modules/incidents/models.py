from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    func,
)
from sqlalchemy import text as sql_text

from app.db.base import code_fk, metadata, text, time


def _finite(*columns: str) -> str:
    return " AND ".join(f"{c} > '-Infinity' AND {c} < 'Infinity'" for c in columns)


incident = Table(
    "incident",
    metadata,
    Column("incident_id", String(64), primary_key=True),
    code_fk("plant_id", "plant.plant_id"),
    code_fk("equipment_group_id", "equipment_group.equipment_group_id"),
    code_fk("equipment_id", "equipment.equipment_id"),
    time("incident_start_time"),
    time("detect_time"),
    time("first_alarm_time", nullable=True),
    time("incident_end_time", nullable=True),
    Column("peak_level", Integer, nullable=False),
    code_fk("lead_sensor_id", "sensor.sensor_id", nullable=True),
    Column(
        "diagnosis_error_type_id",
        BigInteger,
        ForeignKey("error_type.error_type_id"),
        nullable=False,
    ),
    Column(
        "top_risk_error_type_id",
        BigInteger,
        ForeignKey("error_type.error_type_id"),
        nullable=False,
    ),
    Column("top_cof", Float, nullable=False),
    Column("top_pof", Float, nullable=False),
    Column("incident_score", Float, nullable=False),
    text("alarm_grade"),
    text("grade_reason"),
    Column("response_time_h", Float, nullable=False),
    Column("actionable", Boolean, nullable=False),
    Column("alarm_count", Integer, nullable=False),
    Column("trend_count", Integer, nullable=False),
    text("source_file"),
    Column("loaded_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("peak_level BETWEEN 0 AND 4", name="incident_peak_level_range"),
    CheckConstraint("detect_time >= incident_start_time", name="incident_detect_after_start"),
    CheckConstraint(
        "incident_end_time IS NULL OR incident_end_time > incident_start_time",
        name="incident_period",
    ),
    CheckConstraint(
        _finite("top_cof", "top_pof", "incident_score", "response_time_h"),
        name="incident_scores_finite",
    ),
    CheckConstraint("alarm_count >= 0 AND trend_count >= 0", name="incident_counts"),
    Index("ix_incident_equipment_start", "equipment_id", sql_text("incident_start_time DESC")),
)

incident_candidate = Table(
    "incident_candidate",
    metadata,
    Column(
        "incident_id",
        String(64),
        ForeignKey("incident.incident_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("rank", Integer, primary_key=True),
    Column("error_type_id", BigInteger, ForeignKey("error_type.error_type_id"), nullable=False),
    *(
        Column(name, Float, nullable=False)
        for name in ("rule_score_s", "s_top3_sum", "p", "cof", "p_trend", "pf_hours", "p_pf")
    ),
    Column("pof", Float, nullable=False),
    Column("score", Float, nullable=False),
    *(Column(name, Integer, nullable=False) for name in ("speed", "impact", "w")),
    Column("is_diagnosis", Boolean, nullable=False),
    Column("is_top_risk", Boolean, nullable=False),
    text("evidence"),
    CheckConstraint("rank >= 1", name="incident_candidate_rank_positive"),
    CheckConstraint(_finite("cof", "pof", "score"), name="incident_candidate_scores_finite"),
    Index(
        "uq_incident_candidate_diagnosis",
        "incident_id",
        unique=True,
        postgresql_where=sql_text("is_diagnosis"),
    ),
    Index(
        "uq_incident_candidate_top_risk",
        "incident_id",
        unique=True,
        postgresql_where=sql_text("is_top_risk"),
    ),
)
