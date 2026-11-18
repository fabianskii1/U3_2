from sqlalchemy import Column, Integer, Table

from app.db.base import code_fk, fk, metadata, pk, text, time

report = Table(
    "report",
    metadata,
    pk("report_id"),
    code_fk("equipment_id", "equipment.equipment_id"),
    text("equipment_name"),
    fk("equipment_alias_id", "equipment_alias.equipment_alias_id", True),
    text("equipment_alias_name", True),
    code_fk("equipment_group_id", "equipment_group.equipment_group_id"),
    text("equipment_group_name"),
    fk("equipment_group_alias_id", "equipment_group_alias.equipment_group_alias_id", True),
    text("equipment_group_alias_name", True),
    fk("error_history_id", "error_history.error_history_id", True),
    fk("maintenance_history_id", "maintenance_history.maintenance_history_id", True),
    text("title"),
    text("symptom"),
    text("cause"),
    text("action"),
    text("chart_url", True),
    text("risk"),
    Column("version", Integer, nullable=False),
    time("created_at"),
    time("updated_at"),
)


report_symptoms = Table(
    "report_symptoms",
    metadata,
    pk("report_symptoms_id"),
    fk("report_id", "report.report_id"),
    code_fk("sensor_id", "sensor.sensor_id"),
    text("sensor_interval"),
    time("sensor_start_time"),
    time("sensor_end_time"),
)


report_suspected_causes = Table(
    "report_suspected_causes",
    metadata,
    pk("report_suspected_causes_id"),
    fk("report_id", "report.report_id"),
    fk("error_type_id", "error_type.error_type_id"),
)


report_chart_attachments = Table(
    "report_chart_attachments",
    metadata,
    pk("report_chart_attachments_id"),
    fk("report_id", "report.report_id"),
    code_fk("sensor_id", "sensor.sensor_id"),
    text("sensor_interval"),
    time("sensor_start_time"),
    time("sensor_end_time"),
)


report_residual_risks = Table(
    "report_residual_risks",
    metadata,
    pk("report_residual_risks_id"),
    fk("report_id", "report.report_id"),
    fk("error_type_id", "error_type.error_type_id"),
)
