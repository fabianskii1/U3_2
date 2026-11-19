from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.query import page, valid_range
from app.database import get_session
from app.modules.alarms import models as alarms_models
from app.modules.alarms.intake import router as intake_router
from app.modules.alarms.priorities import get_alarm_priorities

router = APIRouter(tags=["알람"])
router.include_router(intake_router)


@router.get("/api/alarms/priorities")
async def alarm_priorities(
    equipment_id: str | None = None,
    equipment_group_id: str | None = None,
    plant_id: str | None = None,
    equipment_type: str | None = None,
    limit: int = Query(default=3, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
):
    return await get_alarm_priorities(
        db,
        equipment_id=equipment_id,
        equipment_group_id=equipment_group_id,
        plant_id=plant_id,
        equipment_type=equipment_type,
        limit=limit,
    )


@router.get("/api/alarms/history")
async def alarm_history(
    equipment_id: str | None = None,
    sensor_id: str | None = None,
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    db: AsyncSession = Depends(get_session),
):
    valid_range(from_time, to_time)
    stmt = select(
        *(
            column
            for column in alarms_models.alarm.c
            if column.name not in {"is_active", "cof_score"}
        )
    )
    if equipment_id is not None:
        stmt = stmt.where(alarms_models.alarm.c.equipment_id == equipment_id)
    if sensor_id is not None:
        stmt = stmt.where(alarms_models.alarm.c.sensor_id == sensor_id)
    if from_time:
        stmt = stmt.where(alarms_models.alarm.c.occurred_at >= from_time)
    if to_time:
        stmt = stmt.where(alarms_models.alarm.c.occurred_at < to_time)
    return await page(
        db, stmt, alarms_models.alarm.c.alarm_id, alarms_models.alarm.c.occurred_at, limit, cursor
    )
