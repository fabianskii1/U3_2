from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.query import all_rows, grouped
from app.database import get_session
from app.modules.equipment import models as equipment_models
from app.modules.hierarchy import models as hierarchy_models

router = APIRouter(tags=["계층"])


@router.get("/api/hierarchy")
async def hierarchy(db: AsyncSession = Depends(get_session)):
    plants = await all_rows(
        db, select(hierarchy_models.plant).order_by(hierarchy_models.plant.c.plant_id)
    )
    units = await all_rows(
        db,
        select(hierarchy_models.equipment_group).order_by(
            hierarchy_models.equipment_group.c.equipment_group_id
        ),
    )
    equipments = await all_rows(
        db, select(equipment_models.equipment).order_by(equipment_models.equipment.c.equipment_id)
    )
    sensors = await all_rows(
        db, select(equipment_models.sensor).order_by(equipment_models.sensor.c.sensor_id)
    )
    plant_aliases = grouped(await all_rows(db, select(hierarchy_models.plant_alias)), "plant_id")
    unit_aliases = grouped(
        await all_rows(db, select(hierarchy_models.equipment_group_alias)), "equipment_group_id"
    )
    equipment_aliases = grouped(
        await all_rows(db, select(equipment_models.equipment_alias)), "equipment_id"
    )
    sensor_aliases = grouped(await all_rows(db, select(equipment_models.sensor_alias)), "sensor_id")
    sensors_by_equipment: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sensor in sensors:
        sensor["aliases"] = sensor_aliases.get(sensor["sensor_id"], [])
        sensor.update(current_value=None, measured_at=None, threshold_value=None)
        sensors_by_equipment[sensor["equipment_id"]].append(sensor)
    for plant in plants:
        plant["aliases"] = plant_aliases.get(plant["plant_id"], [])
    for unit in units:
        unit["aliases"] = unit_aliases.get(unit["equipment_group_id"], [])
    for equipment in equipments:
        equipment["aliases"] = equipment_aliases.get(equipment["equipment_id"], [])
        equipment["sensors"] = sensors_by_equipment.get(equipment["equipment_id"], [])
    return {"plants": plants, "units": units, "equipment": equipments}
