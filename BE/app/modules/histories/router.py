from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.query import all_rows, page, valid_range
from app.database import get_session
from app.modules.histories import models as histories_models

router = APIRouter(tags=["고장·정비 이력"])


@router.get("/api/error-types")
async def error_types(db: AsyncSession = Depends(get_session)):
    return await all_rows(
        db,
        select(histories_models.error_type).order_by(histories_models.error_type.c.error_type_id),
    )


@router.get("/api/error-histories")
async def error_histories(
    equipment_id: str | None = None,
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    db: AsyncSession = Depends(get_session),
):
    valid_range(from_time, to_time)
    stmt = select(histories_models.error_history)
    if equipment_id is not None:
        stmt = stmt.where(histories_models.error_history.c.equipment_id == equipment_id)
    if from_time:
        stmt = stmt.where(histories_models.error_history.c.start_time >= from_time)
    if to_time:
        stmt = stmt.where(histories_models.error_history.c.start_time < to_time)
    result = await page(
        db,
        stmt,
        histories_models.error_history.c.error_history_id,
        histories_models.error_history.c.start_time,
        limit,
        cursor,
    )
    ids = [int(item["error_history_id"]) for item in result["items"]]
    type_map: dict[str, list[str]] = defaultdict(list)
    if ids:
        rows = await all_rows(
            db,
            select(histories_models.error_history_types).where(
                histories_models.error_history_types.c.error_history_id.in_(ids)
            ),
        )
        for row in rows:
            type_map[row["error_history_id"]].append(row["error_type_id"])
    for item in result["items"]:
        item["error_type_ids"] = sorted(type_map.get(item["error_history_id"], []), key=int)
    return result


@router.get("/api/maintenance-histories")
async def maintenance_histories(
    equipment_id: str | None = None,
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    db: AsyncSession = Depends(get_session),
):
    valid_range(from_time, to_time)
    stmt = select(histories_models.maintenance_history)
    if equipment_id is not None:
        stmt = stmt.where(histories_models.maintenance_history.c.equipment_id == equipment_id)
    if from_time:
        stmt = stmt.where(histories_models.maintenance_history.c.start_time >= from_time)
    if to_time:
        stmt = stmt.where(histories_models.maintenance_history.c.start_time < to_time)
    return await page(
        db,
        stmt,
        histories_models.maintenance_history.c.maintenance_history_id,
        histories_models.maintenance_history.c.start_time,
        limit,
        cursor,
    )
