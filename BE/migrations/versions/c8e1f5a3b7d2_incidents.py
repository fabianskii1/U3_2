"""Store analyzer incidents, their fault candidates and alarm links."""

import sqlalchemy as sa
from alembic import op

revision = "c8e1f5a3b7d2"
down_revision = "ab27c93e4501"
branch_labels = None
depends_on = None

FINITE = "{0} > '-Infinity' AND {0} < 'Infinity'"


def upgrade() -> None:
    op.create_unique_constraint("uq_error_type_name", "error_type", ["error_type_name"])
    op.create_table(
        "incident",
        sa.Column("incident_id", sa.String(64), primary_key=True),
        sa.Column("plant_id", sa.String(30), sa.ForeignKey("plant.plant_id"), nullable=False),
        sa.Column(
            "equipment_group_id",
            sa.String(30),
            sa.ForeignKey("equipment_group.equipment_group_id"),
            nullable=False,
        ),
        sa.Column(
            "equipment_id", sa.String(30), sa.ForeignKey("equipment.equipment_id"), nullable=False
        ),
        sa.Column("incident_start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detect_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_alarm_time", sa.DateTime(timezone=True)),
        sa.Column("incident_end_time", sa.DateTime(timezone=True)),
        sa.Column("peak_level", sa.Integer(), nullable=False),
        sa.Column("lead_sensor_id", sa.String(30), sa.ForeignKey("sensor.sensor_id")),
        sa.Column(
            "diagnosis_error_type_id",
            sa.BigInteger(),
            sa.ForeignKey("error_type.error_type_id"),
            nullable=False,
        ),
        sa.Column(
            "top_risk_error_type_id",
            sa.BigInteger(),
            sa.ForeignKey("error_type.error_type_id"),
            nullable=False,
        ),
        sa.Column("top_cof", sa.Float(), nullable=False),
        sa.Column("top_pof", sa.Float(), nullable=False),
        sa.Column("incident_score", sa.Float(), nullable=False),
        sa.Column("alarm_grade", sa.Text(), nullable=False),
        sa.Column("grade_reason", sa.Text(), nullable=False),
        sa.Column("response_time_h", sa.Float(), nullable=False),
        sa.Column("actionable", sa.Boolean(), nullable=False),
        sa.Column("alarm_count", sa.Integer(), nullable=False),
        sa.Column("trend_count", sa.Integer(), nullable=False),
        sa.Column("source_file", sa.Text(), nullable=False),
        sa.Column(
            "loaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("peak_level BETWEEN 0 AND 4", name="incident_peak_level_range"),
        sa.CheckConstraint(
            "detect_time >= incident_start_time", name="incident_detect_after_start"
        ),
        sa.CheckConstraint(
            "incident_end_time IS NULL OR incident_end_time > incident_start_time",
            name="incident_period",
        ),
        sa.CheckConstraint(
            " AND ".join(
                FINITE.format(c)
                for c in ("top_cof", "top_pof", "incident_score", "response_time_h")
            ),
            name="incident_scores_finite",
        ),
        sa.CheckConstraint("alarm_count >= 0 AND trend_count >= 0", name="incident_counts"),
    )
    op.create_index(
        "ix_incident_equipment_start",
        "incident",
        ["equipment_id", sa.text("incident_start_time DESC")],
    )
    op.create_table(
        "incident_candidate",
        sa.Column(
            "incident_id",
            sa.String(64),
            sa.ForeignKey("incident.incident_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("rank", sa.Integer(), primary_key=True),
        sa.Column(
            "error_type_id",
            sa.BigInteger(),
            sa.ForeignKey("error_type.error_type_id"),
            nullable=False,
        ),
        *(
            sa.Column(name, sa.Float(), nullable=False)
            for name in (
                "rule_score_s",
                "s_top3_sum",
                "p",
                "cof",
                "p_trend",
                "pf_hours",
                "p_pf",
                "pof",
                "score",
            )
        ),
        *(sa.Column(name, sa.Integer(), nullable=False) for name in ("speed", "impact", "w")),
        sa.Column("is_diagnosis", sa.Boolean(), nullable=False),
        sa.Column("is_top_risk", sa.Boolean(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.CheckConstraint("rank >= 1", name="incident_candidate_rank_positive"),
        sa.CheckConstraint(
            " AND ".join(FINITE.format(c) for c in ("cof", "pof", "score")),
            name="incident_candidate_scores_finite",
        ),
    )
    op.create_index(
        "uq_incident_candidate_diagnosis",
        "incident_candidate",
        ["incident_id"],
        unique=True,
        postgresql_where=sa.text("is_diagnosis"),
    )
    op.create_index(
        "uq_incident_candidate_top_risk",
        "incident_candidate",
        ["incident_id"],
        unique=True,
        postgresql_where=sa.text("is_top_risk"),
    )
    op.add_column("alarm", sa.Column("incident_id", sa.String(64)))
    op.create_foreign_key(
        "fk_alarm_incident", "alarm", "incident", ["incident_id"], ["incident_id"]
    )
    op.create_index("ix_alarm_incident", "alarm", ["incident_id"])
    op.add_column("alarm", sa.Column("peak_level", sa.Integer()))
    op.create_check_constraint("alarm_peak_level_range", "alarm", "peak_level BETWEEN 0 AND 4")


def downgrade() -> None:
    op.drop_constraint("alarm_peak_level_range", "alarm", type_="check")
    op.drop_column("alarm", "peak_level")
    op.drop_index("ix_alarm_incident", table_name="alarm")
    op.drop_constraint("fk_alarm_incident", "alarm", type_="foreignkey")
    op.drop_column("alarm", "incident_id")
    op.drop_index("uq_incident_candidate_top_risk", table_name="incident_candidate")
    op.drop_index("uq_incident_candidate_diagnosis", table_name="incident_candidate")
    op.drop_table("incident_candidate")
    op.drop_index("ix_incident_equipment_start", table_name="incident")
    op.drop_table("incident")
    op.drop_constraint("uq_error_type_name", "error_type", type_="unique")
