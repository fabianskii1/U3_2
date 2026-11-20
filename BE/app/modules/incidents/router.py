from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.query import valid_range
from app.database import get_session
from app.modules.incidents.schemas import (
    IncidentDetail,
    IncidentList,
    IncidentReportDraft,
    IncidentStatus,
)
from app.modules.incidents.service import get_incident, incident_report_draft, list_incidents

router = APIRouter(tags=["이상 사건"])


@router.get("/api/incidents", response_model=IncidentList)
async def incidents(
    plant_id: str | None = None,
    equipment_group_id: str | None = None,
    equipment_id: str | None = None,
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    min_level: int | None = Query(default=None, ge=0, le=4),
    actionable: bool | None = None,
    status: IncidentStatus | None = Query(
        default=None, description="생략하면 as_of 기준으로 시작된 사건(진행 중·종료)만 반환"
    ),
    as_of: datetime | None = Query(default=None, description="상태 판정 기준 시각"),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None, max_length=256),
    db: AsyncSession = Depends(get_session),
):
    valid_range(from_time, to_time)
    valid_range(as_of, None)
    return await list_incidents(
        db,
        plant_id=plant_id,
        equipment_group_id=equipment_group_id,
        equipment_id=equipment_id,
        from_time=from_time,
        to_time=to_time,
        min_level=min_level,
        actionable=actionable,
        status=status,
        as_of=as_of,
        limit=limit,
        cursor=cursor,
    )


@router.get("/api/incidents/{incident_id}", response_model=IncidentDetail)
async def incident_detail(
    incident_id: str,
    as_of: datetime | None = Query(default=None, description="상태 판정 기준 시각"),
    db: AsyncSession = Depends(get_session),
):
    valid_range(as_of, None)
    detail = await get_incident(db, incident_id, as_of=as_of)
    if detail is None:
        raise HTTPException(404, "사건을 찾을 수 없습니다.")
    return detail


@router.get("/api/incidents/{incident_id}/report-draft", response_model=IncidentReportDraft)
async def incident_draft(incident_id: str, db: AsyncSession = Depends(get_session)):
    draft = await incident_report_draft(db, incident_id)
    if draft is None:
        raise HTTPException(404, "사건을 찾을 수 없습니다.")
    return draft
