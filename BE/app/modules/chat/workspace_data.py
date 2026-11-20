"""Shared monitoring data for the dashboard and conversational queries."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.query import all_rows
from app.database import get_session
from app.modules.alarms.models import alarm
from app.modules.alarms.priorities import get_alarm_priorities
from app.modules.equipment.models import equipment
from app.modules.hierarchy.models import equipment_group, plant

router = APIRouter(tags=["대시보드"])


@router.get("/api/dashboard")
async def get_dashboard(
    db: Annotated[AsyncSession, Depends(get_session)],
    plant_id: str | None = None,
    equipment_group_id: str | None = None,
    equipment_id: str | None = None,
) -> dict:
    filters = [
        column == value
        for column, value in (
            (equipment.c.plant_id, plant_id),
            (equipment.c.equipment_group_id, equipment_group_id),
            (equipment.c.equipment_id, equipment_id),
        )
        if value is not None
    ]
    assets = await all_rows(db, select(equipment).where(*filters))
    ids = [a["equipment_id"] for a in assets]
    priorities = await get_alarm_priorities(
        db,
        plant_id=plant_id,
        equipment_group_id=equipment_group_id,
        equipment_id=equipment_id,
        limit=200,
    )
    summary = await all_rows(
        db,
        select(
            alarm.c.equipment_id,
            alarm.c.alarm_level,
            func.count().label("count"),
        )
        .where(
            alarm.c.equipment_id.in_(ids),
            alarm.c.is_active.is_(True),
            func.lower(alarm.c.alarm_type) == "setpoint",
            alarm.c.alarm_start_time <= datetime.fromisoformat(priorities["as_of"]),
        )
        .group_by(alarm.c.equipment_id, alarm.c.alarm_level)
        .order_by(alarm.c.equipment_id, alarm.c.alarm_level.desc()),
    )
    return {
        "equipment_count": len(assets),
        "normal_count": sum(a["equipment_status"] == 0 for a in assets),
        "plant_count": len({a["plant_id"] for a in assets})
        if filters
        else (await db.scalar(select(func.count()).select_from(plant))),
        "unit_count": len({a["equipment_group_id"] for a in assets})
        if filters
        else (await db.scalar(select(func.count()).select_from(equipment_group))),
        "priority": priorities,
        "high_count": sum(r["count"] for r in summary if (r["alarm_level"] or 0) >= 3),
        "alarm_summary": summary,
    }
