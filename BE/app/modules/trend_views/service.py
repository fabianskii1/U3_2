"""Validate and persist immutable trend view definitions."""

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from pydantic import AwareDatetime, BaseModel, Field, model_validator
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chat.models import chat_result, session_detail
from app.modules.equipment.models import equipment, sensor
from app.modules.hierarchy.models import equipment_group
from app.modules.trend_views.models import trend_view

MAX_SERIES = 24
MAX_DURATION = timedelta(days=90)


class TrendSeries(BaseModel):
    sensorId: str = Field(min_length=1, max_length=30)
    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def valid_window(self) -> "TrendSeries":
        if self.start >= self.end or self.end - self.start > MAX_DURATION:
            raise ValueError("센서 조회 기간은 0일 초과, 90일 이하여야 합니다.")
        if self.end > datetime.now(UTC) + timedelta(minutes=5):
            raise ValueError("미래 시각까지 조회할 수 없습니다.")
        return self


class TrendViewCreate(BaseModel):
    sessionId: int
    equipmentGroupId: str = Field(min_length=1, max_length=30)
    equipmentId: str | None = Field(default=None, max_length=30)
    series: list[TrendSeries] = Field(min_length=1, max_length=MAX_SERIES)
    showAnomalies: bool = False
    messageId: int | None = None
    interval: Literal["1m", "1h", "1d"] | None = None


async def create_trend_view(db: AsyncSession, payload: TrendViewCreate) -> tuple[UUID, str]:
    group_id = payload.equipmentGroupId
    plant_id = (
        await db.execute(
            select(equipment_group.c.plant_id).where(
                equipment_group.c.equipment_group_id == group_id
            )
        )
    ).scalar_one_or_none()
    if plant_id is None:
        raise HTTPException(400, "설비 그룹을 찾을 수 없습니다.")
    if payload.equipmentId:
        asset = (
            await db.execute(
                select(equipment.c.equipment_id).where(
                    equipment.c.equipment_id == payload.equipmentId,
                    equipment.c.equipment_group_id == group_id,
                    equipment.c.plant_id == plant_id,
                )
            )
        ).scalar_one_or_none()
        if asset is None:
            raise HTTPException(400, "설비가 선택한 그룹에 속하지 않습니다.")
    sensor_ids = {item.sensorId for item in payload.series}
    registered = (
        (
            await db.execute(
                select(sensor.c.sensor_id)
                .join(equipment, sensor.c.equipment_id == equipment.c.equipment_id)
                .where(
                    sensor.c.sensor_id.in_(sensor_ids),
                    equipment.c.equipment_group_id == group_id,
                    equipment.c.plant_id == plant_id,
                    *(
                        (equipment.c.equipment_id == payload.equipmentId,)
                        if payload.equipmentId
                        else ()
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    if set(registered) != sensor_ids:
        raise HTTPException(400, "조회 대상에 속하지 않는 센서가 있습니다.")
    if payload.messageId is not None:
        message = (
            await db.execute(
                select(session_detail.c.session_detail_id).where(
                    session_detail.c.session_detail_id == payload.messageId,
                    session_detail.c.session_id == payload.sessionId,
                    session_detail.c.type == "llm",
                )
            )
        ).scalar_one_or_none()
        if message is None:
            raise HTTPException(400, "연결할 AI 응답을 찾을 수 없습니다.")
    config = {
        "version": 1,
        "series": [
            {
                "sensorId": item.sensorId,
                "start": item.start.isoformat(),
                "end": item.end.isoformat(),
            }
            for item in payload.series
        ],
        "showAnomalies": payload.showAnomalies,
        "interval": payload.interval,
    }
    view_id = (
        await db.execute(
            insert(trend_view)
            .values(
                session_id=payload.sessionId,
                session_detail_id=payload.messageId,
                plant_id=plant_id,
                equipment_group_id=group_id,
                equipment_id=payload.equipmentId,
                config=config,
            )
            .returning(trend_view.c.view_id)
        )
    ).scalar_one()
    if payload.messageId is not None:
        await db.execute(
            insert(chat_result).values(
                session_detail_id=payload.messageId,
                result_type="trend",
                trend_view_id=view_id,
            )
        )
    return view_id, f"/trend?viewId={view_id}"
