from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.query import all_rows
from app.database import get_session
from app.modules.equipment import models as equipment_models
from app.modules.manuals import models as manuals_models

router = APIRouter(tags=["매뉴얼"])


@router.get("/api/equipment/{equipment_id}/manuals")
async def manuals(equipment_id: str, db: AsyncSession = Depends(get_session)):
    exists = (
        await db.execute(
            select(equipment_models.equipment.c.equipment_id).where(
                equipment_models.equipment.c.equipment_id == equipment_id
            )
        )
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(404, "설비를 찾을 수 없습니다.")
    return await all_rows(
        db,
        select(
            manuals_models.equipment_manual.c.equipment_manual_id,
            manuals_models.equipment_manual.c.equipment_manual_title,
            manuals_models.equipment_manual.c.equipment_manual_link,
        )
        .where(manuals_models.equipment_manual.c.equipment_id == equipment_id)
        .order_by(manuals_models.equipment_manual.c.equipment_manual_id),
    )
