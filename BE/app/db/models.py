"""Import all domain tables into shared Alembic metadata."""

from app.db.base import metadata
from app.modules.alarms.models import alarm, alarm_intake
from app.modules.chat.models import chat_result, session, session_detail
from app.modules.equipment.models import equipment, equipment_alias, sensor, sensor_alias
from app.modules.hierarchy.models import equipment_group, equipment_group_alias, plant, plant_alias
from app.modules.histories.models import (
    error_history,
    error_history_types,
    error_type,
    maintenance_history,
)
from app.modules.incidents.models import incident, incident_candidate
from app.modules.manuals.models import equipment_manual
from app.modules.reports.models import (
    report,
    report_chart_attachments,
    report_residual_risks,
    report_suspected_causes,
    report_symptoms,
)
from app.modules.request_logs.models import (
    api_request_error_log,
    api_request_log,
    chat_request_error_log,
    chat_request_log,
)
from app.modules.telemetry.models import equipment_run_state_1m, sensor_data_1m, sensor_signal
from app.modules.trend_views.models import trend_view
from app.modules.users.models import user

__all__ = [
    "alarm",
    "alarm_intake",
    "api_request_error_log",
    "api_request_log",
    "chat_request_error_log",
    "chat_request_log",
    "chat_result",
    "equipment",
    "equipment_alias",
    "equipment_group",
    "equipment_group_alias",
    "equipment_manual",
    "equipment_run_state_1m",
    "error_history",
    "error_history_types",
    "error_type",
    "incident",
    "incident_candidate",
    "maintenance_history",
    "metadata",
    "plant",
    "plant_alias",
    "report",
    "report_chart_attachments",
    "report_residual_risks",
    "report_suspected_causes",
    "report_symptoms",
    "sensor",
    "sensor_alias",
    "sensor_data_1m",
    "sensor_signal",
    "session",
    "session_detail",
    "trend_view",
    "user",
]
