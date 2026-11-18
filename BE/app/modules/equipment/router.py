from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.query import all_rows, grouped, now, serialize
from app.database import get_session
from app.modules.equipment import models as equipment_models

router = APIRouter(tags=["설비"])


@router.get("/api/equipment/{equipment_id}")
async def equipment_detail(equipment_id: str, db: AsyncSession = Depends(get_session)):
    item = (
        (
            await db.execute(
                select(equipment_models.equipment).where(
                    equipment_models.equipment.c.equipment_id == equipment_id
                )
            )
        )
        .mappings()
        .first()
    )
    if item is None:
        raise HTTPException(404, "설비를 찾을 수 없습니다.")
    result = serialize(item)
    result["aliases"] = await all_rows(
        db,
        select(
            equipment_models.equipment_alias.c.equipment_alias_id,
            equipment_models.equipment_alias.c.equipment_alias_name,
        ).where(equipment_models.equipment_alias.c.equipment_id == equipment_id),
    )
    sensors = await all_rows(
        db,
        select(equipment_models.sensor)
        .where(equipment_models.sensor.c.equipment_id == equipment_id)
        .order_by(equipment_models.sensor.c.sensor_id),
    )
    sensor_ids = [s["sensor_id"] for s in sensors]
    aliases = (
        grouped(
            await all_rows(
                db,
                select(equipment_models.sensor_alias).where(
                    equipment_models.sensor_alias.c.sensor_id.in_(sensor_ids)
                ),
            ),
            "sensor_id",
        )
        if sensor_ids
        else {}
    )
    for sensor in sensors:
        sensor["aliases"] = aliases.get(sensor["sensor_id"], [])
        sensor.update(current_value=None, measured_at=None, threshold_value=None)
    result["sensors"] = sensors
    result["as_of"] = now()
    return result
