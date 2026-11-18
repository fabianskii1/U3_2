from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.query import all_rows, page, serialize
from app.database import get_session
from app.modules.equipment import models as equipment_models
from app.modules.reports import models as reports_models

router = APIRouter(tags=["보고서"])


@router.get("/api/reports")
async def reports(
    plant_id: str | None = None,
    equipment_group_id: str | None = None,
    equipment_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    db: AsyncSession = Depends(get_session),
):
    stmt = select(reports_models.report)
    if plant_id is not None:
        stmt = stmt.join(
            equipment_models.equipment,
            reports_models.report.c.equipment_id == equipment_models.equipment.c.equipment_id,
        )
        stmt = stmt.where(equipment_models.equipment.c.plant_id == plant_id)
    if equipment_group_id is not None:
        stmt = stmt.where(reports_models.report.c.equipment_group_id == equipment_group_id)
    if equipment_id is not None:
        stmt = stmt.where(reports_models.report.c.equipment_id == equipment_id)
    return await page(
        db,
        stmt,
        reports_models.report.c.report_id,
        reports_models.report.c.updated_at,
        limit,
        cursor,
    )


@router.get("/api/reports/{report_id}")
async def report_detail(report_id: int, db: AsyncSession = Depends(get_session)):
    row = (
        (
            await db.execute(
                select(reports_models.report).where(reports_models.report.c.report_id == report_id)
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(404, "보고서를 찾을 수 없습니다.")
    result = serialize(row)
    for key, table, id_key in (
        ("symptoms", reports_models.report_symptoms, "report_symptoms_id"),
        ("suspected_causes", reports_models.report_suspected_causes, "report_suspected_causes_id"),
        (
            "chart_attachments",
            reports_models.report_chart_attachments,
            "report_chart_attachments_id",
        ),
        ("residual_risks", reports_models.report_residual_risks, "report_residual_risks_id"),
    ):
        result[key] = await all_rows(
            db, select(table).where(table.c.report_id == report_id).order_by(table.c[id_key])
        )
    return result
