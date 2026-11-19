from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.query import page, valid_range
from app.database import get_session
from app.modules.alarms.intake import router as intake_router
from app.modules.alarms.models import alarm
from app.modules.alarms.priorities import get_alarm_priorities
from app.modules.alarms.schemas import AlarmEventType, AlarmHistory, AlarmPriorities, PriorityGroup
from app.modules.equipment.models import equipment

router = APIRouter(tags=["알람"])
router.include_router(intake_router)


@router.get("/api/alarms/priorities", response_model=AlarmPriorities)
async def alarm_priorities(
    equipment_id: str | None = None,
    equipment_group_id: str | None = None,
    plant_id: str | None = None,
    equipment_type: str | None = None,
    group_by: PriorityGroup = "equipment",
    as_of: datetime | None = Query(
        default=None, description="시간대가 포함된 재생 기준 시각. 생략하면 현재 상태 조회."
    ),
    limit: int = Query(default=3, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
):
    valid_range(as_of, None)
    if as_of is not None and as_of > datetime.now(UTC):
        raise HTTPException(400, "as_of는 현재 시각 이후일 수 없습니다.")
    return await get_alarm_priorities(
        db,
        equipment_id=equipment_id,
        equipment_group_id=equipment_group_id,
        plant_id=plant_id,
        equipment_type=equipment_type,
        group_by=group_by,
        as_of=as_of,
        limit=limit,
    )


@router.get("/api/alarms/history", response_model=AlarmHistory)
async def alarm_history(
    plant_id: str | None = None,
    equipment_group_id: str | None = None,
    equipment_type: str | None = None,
    equipment_id: str | None = None,
    sensor_id: str | None = None,
    alarm_level: int | None = Query(default=None, ge=0, le=4),
    event_type: AlarmEventType | None = None,
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None, max_length=256),
    db: AsyncSession = Depends(get_session),
):
    valid_range(from_time, to_time)
    if from_time and to_time and to_time - from_time > timedelta(days=366):
        raise HTTPException(400, "이력 조회 기간은 최대 366일입니다.")

    stmt = select(alarm).join(equipment, alarm.c.equipment_id == equipment.c.equipment_id)
    for column, value in (
        (equipment.c.plant_id, plant_id),
        (equipment.c.equipment_group_id, equipment_group_id),
        (equipment.c.equipment_type, equipment_type),
        (alarm.c.equipment_id, equipment_id),
        (alarm.c.sensor_id, sensor_id),
        (alarm.c.alarm_level, alarm_level),
        (alarm.c.event_type, event_type),
    ):
        if value is not None:
            stmt = stmt.where(column == value)
    if from_time is not None:
        stmt = stmt.where(alarm.c.alarm_start_time >= from_time)
    if to_time is not None:
        stmt = stmt.where(alarm.c.alarm_start_time < to_time)
    return await page(db, stmt, alarm.c.alarm_id, alarm.c.alarm_start_time, limit, cursor)
