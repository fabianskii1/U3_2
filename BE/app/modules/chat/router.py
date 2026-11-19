"""Token-owned chat sessions and workflow responses over SSE."""

import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session
from app.modules.chat import models as chat_models
from app.modules.chat.execution import run_chat_workflow
from app.modules.request_logs import models as log_models

router = APIRouter(prefix="/api/chat", tags=["채팅"])
COOKIE_NAME = "skadi_chat_session"


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
        secure=get_settings().force_secure_chat_cookie or request.url.scheme == "https",
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
            insert(log_models.chat_request_log)
            .values(
                api_request_log_id=api_log_id,
                status="processing",
                session_id=int(payload.session_id),
            )
            .returning(log_models.chat_request_log.c.chat_request_log_id)
        )
    ).scalar_one()
    await db.execute(
        insert(chat_models.session_detail).values(
            session_id=int(payload.session_id),
            type="user",
            content=payload.message,
            created_at=started_at,
        )
    )
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
        reply = await run_chat_workflow(
            db, payload.message, payload.screen_context, last_context or {}, _lookup_equipment
        )
        detail_id = (
            await db.execute(
                insert(chat_models.session_detail)
                .values(
                    session_id=int(payload.session_id),
                    type="llm",
                    content=reply.message,
                    agent_context=reply.context,
                    created_at=datetime.now(UTC),
                )
                .returning(chat_models.session_detail.c.session_detail_id)
            )
        ).scalar_one()
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
    except (httpx.HTTPError, ValueError) as exc:
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
                error_code="AI_UNAVAILABLE",
                error_message=type(exc).__name__,
            )
        )
        await db.commit()
        raise HTTPException(
            502, "AI 서비스에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요."
        ) from exc

    async def events():
        yield _sse("message.delta", {"text": reply.message})
        for link in reply.links:
            yield _sse("citation", link)
        if reply.navigation_href:
            yield _sse("navigate", {"href": reply.navigation_href})
        yield _sse("done", {"session_detail_id": str(detail_id)})

    return StreamingResponse(events(), media_type="text/event-stream")
