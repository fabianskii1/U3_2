"""Token-owned chat sessions and workflow responses over SSE."""

import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session
from app.modules.chat import models as chat_models
from app.modules.chat.execution import run_chat_workflow
from app.modules.equipment.models import equipment, sensor
from app.modules.request_logs import models as log_models
from app.modules.trend_views.service import TrendViewCreate, create_trend_view

router = APIRouter(prefix="/api/chat", tags=["채팅"])
COOKIE_NAME = "skadi_chat_session"
KST = ZoneInfo("Asia/Seoul")


class ChatRequest(BaseModel):
    request_id: UUID
    session_id: str
    message: str = Field(min_length=1, max_length=5000)
    screen_context: dict[str, object] = Field(default_factory=dict)
    report_context: dict[str, object] | None = None


def _cookie_value(session_id: str, token: str) -> str:
    return f"{session_id}:{token}"


async def _owned_session(request: Request, db: AsyncSession, session_id: str) -> None:
    cookie = request.cookies.get(COOKIE_NAME, "")
    cookie_id, separator, token = cookie.partition(":")
    if not separator or cookie_id != session_id or not token:
        raise HTTPException(403, "채팅 세션에 접근할 수 없습니다.")
    row = (
        await db.execute(
            select(chat_models.session.c.token_hash).where(
                chat_models.session.c.session_id == int(session_id)
            )
        )
    ).first()
    if (
        row is None
        or row.token_hash is None
        or not hmac.compare_digest(row.token_hash, hashlib.sha256(token.encode()).hexdigest())
    ):
        raise HTTPException(403, "채팅 세션에 접근할 수 없습니다.")


def _sse(event: str, payload: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _link_time(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=KST)).isoformat()


async def _persist_trend_links(db: AsyncSession, reply, session_id: int, message_id: int) -> None:
    if reply.trend_intent:
        payload = TrendViewCreate.model_validate(
            {**reply.trend_intent, "sessionId": session_id, "messageId": message_id}
        )
        _, href = await create_trend_view(db, payload)
        trend_title = next(
            (link["title"] for link in reply.links if urlsplit(link["href"]).path == "/trend"),
            "트렌드 보기",
        )
        reply.links = [link for link in reply.links if urlsplit(link["href"]).path != "/trend"] + [
            {"title": trend_title, "href": href}
        ]
        reply.navigation_href = href
        return

    converted = []
    navigation = reply.navigation_href
    for link in reply.links:
        url = urlsplit(link["href"])
        if url.path != "/trend":
            converted.append(link)
            continue
        params = parse_qs(url.query)
        sensor_id = params.get("sensor_id", [None])[0]
        start = params.get("from", [None])[0]
        end = params.get("to", [None])[0]
        if not sensor_id or not start or not end:
            continue
        asset = (
            await db.execute(
                select(equipment.c.equipment_id, equipment.c.equipment_group_id)
                .join(sensor, sensor.c.equipment_id == equipment.c.equipment_id)
                .where(sensor.c.sensor_id == sensor_id)
            )
        ).first()
        if asset is None:
            continue
        payload = TrendViewCreate.model_validate(
            {
                "sessionId": session_id,
                "equipmentGroupId": asset.equipment_group_id,
                "equipmentId": asset.equipment_id,
                "series": [
                    {"sensorId": sensor_id, "start": _link_time(start), "end": _link_time(end)}
                ],
                "showAnomalies": params.get("show_anomalies", ["0"])[0] == "1",
                "messageId": message_id,
            }
        )
        _, href = await create_trend_view(db, payload)
        converted.append({**link, "href": href})
        if navigation == link["href"]:
            navigation = href
    reply.links = converted
    reply.navigation_href = (
        navigation if navigation and urlsplit(navigation).path != "/trend" else None
    )


async def _existing_request_response(db: AsyncSession, session_id: int, request_id: UUID):
    row = (
        await db.execute(
            select(
                log_models.chat_request_log.c.status,
                log_models.chat_request_log.c.session_detail_id,
            ).where(
                log_models.chat_request_log.c.session_id == session_id,
                log_models.chat_request_log.c.request_id == request_id,
            )
        )
    ).first()
    if row is None:
        return None
    if row.status != "completed" or row.session_detail_id is None:
        raise HTTPException(409, "같은 채팅 요청이 처리 중이거나 이미 실패했습니다.")
    message = (
        await db.execute(
            select(
                chat_models.session_detail.c.content, chat_models.session_detail.c.agent_context
            ).where(chat_models.session_detail.c.session_detail_id == row.session_detail_id)
        )
    ).first()
    if message is None:
        raise HTTPException(500, "저장된 채팅 응답을 찾을 수 없습니다.")
    delivery = (message.agent_context or {}).get("_delivery", {})

    async def events():
        yield _sse("message.delta", {"text": message.content})
        for link in delivery.get("links", []):
            yield _sse("citation", link)
        if delivery.get("navigation_href"):
            yield _sse("navigate", {"href": delivery["navigation_href"]})
        yield _sse("done", {"session_detail_id": str(row.session_detail_id)})

    return StreamingResponse(events(), media_type="text/event-stream")


async def _lookup_equipment(message: str, candidates: list[dict]) -> dict[str, object]:
    async with httpx.AsyncClient(timeout=25.0) as client:
        response = await client.post(
            f"{get_settings().ai_base_url.rstrip('/')}/agents/find-equipment-id/invoke",
            json={"equipment_name": message, "candidates": candidates},
        )
        response.raise_for_status()
        return response.json()


@router.post("/sessions", status_code=201)
async def create_session(
    request: Request, response: Response, db: AsyncSession = Depends(get_session)
):
    token = secrets.token_urlsafe(32)
    session_id = (
        await db.execute(
            insert(chat_models.session)
            .values(user_id=None, token_hash=hashlib.sha256(token.encode()).hexdigest())
            .returning(chat_models.session.c.session_id)
        )
    ).scalar_one()
    await db.commit()
    response.set_cookie(
        COOKIE_NAME,
        _cookie_value(str(session_id), token),
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        max_age=30 * 24 * 60 * 60,
        path="/api/chat",
    )
    return {"session_id": str(session_id)}


@router.get("/sessions/{session_id}/messages")
async def list_messages(session_id: str, request: Request, db: AsyncSession = Depends(get_session)):
    if not session_id.isascii() or not session_id.isdecimal():
        raise HTTPException(404, "채팅 세션을 찾을 수 없습니다.")
    await _owned_session(request, db, session_id)
    rows = (
        (
            await db.execute(
                select(chat_models.session_detail)
                .where(chat_models.session_detail.c.session_id == int(session_id))
                .order_by(chat_models.session_detail.c.session_detail_id)
                .limit(200)
            )
        )
        .mappings()
        .all()
    )
    return {
        "items": [
            {
                "session_detail_id": str(row["session_detail_id"]),
                "reply_to_session_detail_id": (
                    str(row["reply_to_session_detail_id"])
                    if row["reply_to_session_detail_id"] is not None
                    else None
                ),
                "role": row["type"],
                "content": row["content"],
                "created_at": row["created_at"].isoformat(),
            }
            for row in rows
        ]
    }


@router.post("/stream")
async def chat_stream(
    payload: ChatRequest, request: Request, db: AsyncSession = Depends(get_session)
):
    if not payload.session_id.isascii() or not payload.session_id.isdecimal():
        raise HTTPException(404, "채팅 세션을 찾을 수 없습니다.")
    await _owned_session(request, db, payload.session_id)
    existing = await _existing_request_response(db, int(payload.session_id), payload.request_id)
    if existing is not None:
        return existing
    started_at = datetime.now(UTC)
    api_log_id = (
        await db.execute(
            insert(log_models.api_request_log)
            .values(started_at=started_at, http_method="POST", api_path="/api/chat/stream")
            .returning(log_models.api_request_log.c.api_request_log_id)
        )
    ).scalar_one()
    chat_log_id = (
        await db.execute(
            pg_insert(log_models.chat_request_log)
            .values(
                api_request_log_id=api_log_id,
                status="processing",
                session_id=int(payload.session_id),
                request_id=payload.request_id,
            )
            .on_conflict_do_nothing(constraint="uq_chat_request_session_request")
            .returning(log_models.chat_request_log.c.chat_request_log_id)
        )
    ).scalar_one_or_none()
    if chat_log_id is None:
        await db.rollback()
        existing = await _existing_request_response(db, int(payload.session_id), payload.request_id)
        if existing is not None:
            return existing
        raise HTTPException(409, "같은 채팅 요청을 다시 시도해 주세요.")
    user_detail_id = (
        await db.execute(
            insert(chat_models.session_detail)
            .values(
                session_id=int(payload.session_id),
                type="user",
                content=payload.message,
                created_at=started_at,
            )
            .returning(chat_models.session_detail.c.session_detail_id)
        )
    ).scalar_one()
    await db.commit()

    try:
        last_context = (
            await db.execute(
                select(chat_models.session_detail.c.agent_context)
                .where(
                    chat_models.session_detail.c.session_id == int(payload.session_id),
                    chat_models.session_detail.c.type == "llm",
                )
                .order_by(chat_models.session_detail.c.session_detail_id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        previous = {key: value for key, value in (last_context or {}).items() if key != "_delivery"}
        reply = await run_chat_workflow(
            db, payload.message, payload.screen_context, previous, _lookup_equipment
        )
        detail_id = (
            await db.execute(
                insert(chat_models.session_detail)
                .values(
                    session_id=int(payload.session_id),
                    type="llm",
                    content=reply.message,
                    reply_to_session_detail_id=user_detail_id,
                    agent_context=reply.context,
                    created_at=datetime.now(UTC),
                )
                .returning(chat_models.session_detail.c.session_detail_id)
            )
        ).scalar_one()
        await _persist_trend_links(db, reply, int(payload.session_id), detail_id)
        await db.execute(
            update(chat_models.session_detail)
            .where(chat_models.session_detail.c.session_detail_id == detail_id)
            .values(
                agent_context={
                    **reply.context,
                    "_delivery": {
                        "links": reply.links,
                        "navigation_href": reply.navigation_href,
                    },
                }
            )
        )
        finished_at = datetime.now(UTC)
        await db.execute(
            update(log_models.chat_request_log)
            .where(log_models.chat_request_log.c.chat_request_log_id == chat_log_id)
            .values(status="completed", session_detail_id=detail_id)
        )
        await db.execute(
            update(log_models.api_request_log)
            .where(log_models.api_request_log.c.api_request_log_id == api_log_id)
            .values(
                finished_at=finished_at,
                duration_ms=int((finished_at - started_at).total_seconds() * 1000),
                http_status_code=200,
            )
        )
        await db.commit()
    except (httpx.HTTPError, ValueError, SQLAlchemyError, HTTPException) as exc:
        await db.rollback()
        finished_at = datetime.now(UTC)
        await db.execute(
            update(log_models.chat_request_log)
            .where(log_models.chat_request_log.c.chat_request_log_id == chat_log_id)
            .values(status="failed")
        )
        await db.execute(
            update(log_models.api_request_log)
            .where(log_models.api_request_log.c.api_request_log_id == api_log_id)
            .values(
                finished_at=finished_at,
                duration_ms=int((finished_at - started_at).total_seconds() * 1000),
                http_status_code=502,
            )
        )
        await db.execute(
            insert(log_models.chat_request_error_log).values(
                chat_request_log_id=chat_log_id,
                occurred_at=finished_at,
                error_stage="llm",
                error_code="CHAT_RESULT_FAILED",
                error_message=type(exc).__name__,
            )
        )
        await db.commit()
        raise HTTPException(
            502, "채팅 결과를 생성하지 못했습니다. 잠시 후 다시 시도해 주세요."
        ) from exc

    async def events():
        yield _sse("message.delta", {"text": reply.message})
        for link in reply.links:
            yield _sse("citation", link)
        if reply.navigation_href:
            yield _sse("navigate", {"href": reply.navigation_href})
        yield _sse("done", {"session_detail_id": str(detail_id)})

    return StreamingResponse(events(), media_type="text/event-stream")
