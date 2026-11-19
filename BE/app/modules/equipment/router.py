from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.query import all_rows, grouped, now, serialize
from app.database import get_session
from app.modules.equipment import models as equipment_models
from app.modules.telemetry.models import sensor_data_1m, sensor_signal

router = APIRouter(tags=["설비"])


async def _latest_readings(db: AsyncSession, sensor_ids: list[str]) -> dict:
    if not sensor_ids:
        return {}
    signals = await all_rows(
        db,
        select(sensor_signal.c.sensor_id, sensor_signal.c.signal_id).where(
            sensor_signal.c.sensor_id.in_(sensor_ids)
        ),
    )
    by_sensor = grouped(signals, "sensor_id")
    single_signal_ids = [
        entries[0]["signal_id"] for entries in by_sensor.values() if len(entries) == 1
    ]
    if not single_signal_ids:
        return {}
    latest = (
        select(sensor_data_1m.c.measured_at, sensor_data_1m.c.value.label("current_value"))
        .where(
            sensor_data_1m.c.signal_id == sensor_signal.c.signal_id,
            sensor_data_1m.c.measured_at <= datetime.now(UTC),
        )
        .order_by(sensor_data_1m.c.measured_at.desc())
        .limit(1)
        .lateral("latest")
    )
    readings = await all_rows(
        db,
        select(sensor_signal.c.sensor_id, latest.c.measured_at, latest.c.current_value)
        .join(latest, true())
        .where(sensor_signal.c.signal_id.in_(single_signal_ids)),
    )
    return {row["sensor_id"]: row for row in readings}


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
    readings = await _latest_readings(db, sensor_ids)
    for sensor in sensors:
        sensor["aliases"] = aliases.get(sensor["sensor_id"], [])
        sensor.update(current_value=None, measured_at=None, threshold_value=None)
        sensor.update(readings.get(sensor["sensor_id"], {}))
    result["sensors"] = sensors
    result["as_of"] = now()
    return result
