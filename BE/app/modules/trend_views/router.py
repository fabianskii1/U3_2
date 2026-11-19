"""Session-owned trend view and chat result APIs."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.modules.chat.models import chat_result, session_detail
from app.modules.chat.router import _owned_session
from app.modules.trend_views.models import trend_view
from app.modules.trend_views.service import TrendViewCreate, create_trend_view

router = APIRouter(prefix="/api/chat", tags=["채팅"])


@router.post("/trend-views", status_code=201)
async def create_view(
    payload: TrendViewCreate,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    await _owned_session(request, db, str(payload.sessionId))
    view_id, url = await create_trend_view(db, payload)
    await db.commit()
    return {"viewId": str(view_id), "url": url}


@router.get("/trend-views/{view_id}")
async def read_view(view_id: UUID, request: Request, db: AsyncSession = Depends(get_session)):
    row = (
        (await db.execute(select(trend_view).where(trend_view.c.view_id == view_id)))
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(404, "트렌드 조회 설정을 찾을 수 없습니다.")
    try:
        await _owned_session(request, db, str(row["session_id"]))
    except HTTPException as exc:
        raise HTTPException(404, "트렌드 조회 설정을 찾을 수 없습니다.") from exc
    if row["expires_at"] is not None and row["expires_at"] <= datetime.now(UTC):
        raise HTTPException(410, "만료된 트렌드 조회 설정입니다.")
    return {
        "viewId": str(row["view_id"]),
        "messageId": str(row["session_detail_id"]) if row["session_detail_id"] else None,
        "plantId": row["plant_id"],
        "equipmentGroupId": row["equipment_group_id"],
        "equipmentId": row["equipment_id"],
        "config": row["config"],
        "createdAt": row["created_at"].isoformat(),
        "expiresAt": row["expires_at"].isoformat() if row["expires_at"] else None,
    }


@router.get("/messages/{message_id}/results")
async def message_results(
    message_id: int, request: Request, db: AsyncSession = Depends(get_session)
):
    message = (
        await db.execute(
            select(session_detail.c.session_id, session_detail.c.reply_to_session_detail_id).where(
                session_detail.c.session_detail_id == message_id,
                session_detail.c.type == "llm",
            )
        )
    ).first()
    if message is None:
        raise HTTPException(404, "AI 응답을 찾을 수 없습니다.")
    await _owned_session(request, db, str(message.session_id))
    rows = (
        await db.execute(
            select(chat_result.c.result_id, chat_result.c.result_type, chat_result.c.trend_view_id)
            .where(chat_result.c.session_detail_id == message_id)
            .order_by(chat_result.c.created_at, chat_result.c.result_id)
        )
    ).all()
    return {
        "messageId": str(message_id),
        "replyToMessageId": (
            str(message.reply_to_session_detail_id)
            if message.reply_to_session_detail_id is not None
            else None
        ),
        "items": [
            {
                "resultId": str(row.result_id),
                "resultType": row.result_type,
                "viewId": str(row.trend_view_id),
                "url": f"/trend?viewId={row.trend_view_id}",
            }
            for row in rows
        ],
    }
