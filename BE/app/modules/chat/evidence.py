"""Read-only inspection evidence for the chat workflow."""

from skadi_agents.inspection_evidence import (
    InspectionEvidence,
    format_inspection_evidence,
    markdown_text,
)
from skadi_agents.maintenance_report import build_maintenance_draft
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.query import all_rows
from app.modules.histories.models import maintenance_history
from app.modules.manuals.models import equipment_manual
from app.modules.reports.models import report

__all__ = [
    "InspectionEvidence",
    "build_maintenance_draft",
    "format_inspection_evidence",
    "get_inspection_evidence",
    "markdown_text",
]

EVIDENCE_LIMIT = 3


async def get_inspection_evidence(db: AsyncSession, equipment_id: str) -> InspectionEvidence:
    manuals = await all_rows(
        db,
        select(
            equipment_manual.c.equipment_manual_id,
            equipment_manual.c.equipment_manual_title,
            equipment_manual.c.equipment_manual_link,
        )
        .where(equipment_manual.c.equipment_id == equipment_id)
        .order_by(equipment_manual.c.equipment_manual_id)
        .limit(EVIDENCE_LIMIT),
    )
    reports = await all_rows(
        db,
        select(report.c.report_id, report.c.title, report.c.version, report.c.updated_at)
        .where(report.c.equipment_id == equipment_id)
        .order_by(report.c.updated_at.desc(), report.c.report_id.desc())
        .limit(EVIDENCE_LIMIT),
    )
    maintenance = await all_rows(
        db,
        select(
            maintenance_history.c.maintenance_history_id,
            maintenance_history.c.start_time,
            maintenance_history.c.end_time,
        )
        .where(maintenance_history.c.equipment_id == equipment_id)
        .order_by(
            maintenance_history.c.start_time.desc(),
            maintenance_history.c.maintenance_history_id.desc(),
        )
        .limit(EVIDENCE_LIMIT),
    )
    return InspectionEvidence(equipment_id, manuals, reports, maintenance)
