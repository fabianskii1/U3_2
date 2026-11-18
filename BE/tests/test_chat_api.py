"""Chat bridge contract against the local PostgreSQL schema."""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine, get_session
from app.main import app
from app.modules.chat import router as chat_router


@pytest.mark.asyncio
async def test_chat_session_cookie_ai_lookup_and_sse(monkeypatch):
    async def fake_lookup(message: str):
        if message == "원유 공급 펌프":
            return {"status": "found", "equipment_id": "P1", "candidates": []}
        assert message == "열교환기 공급 펌프"
        return {
            "status": "not_found",
            "equipment_id": None,
            "candidates": [
                {"equipment_id": "P1"},
                {"equipment_id": "P5"},
                {"equipment_id": "P2"},
            ],
        }

    monkeypatch.setattr(chat_router, "_lookup_equipment", fake_lookup)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        db = AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )

        async def test_session():
            yield db

        app.dependency_overrides[get_session] = test_session
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                created = await client.post("/api/chat/sessions", json={})
                assert created.status_code == 201
                session_id = created.json()["session_id"]
                assert "httponly" in created.headers["set-cookie"].lower()
                response = await client.post(
                    "/api/chat/stream",
                    json={
                        "request_id": str(uuid4()),
                        "session_id": session_id,
                        "message": "원유 공급 펌프",
                        "screen_context": {"page": "/equip"},
                    },
                )
                assert response.status_code == 200
                assert "event: message.delta" in response.text
                assert "P1" in response.text
                assert "event: citation" in response.text
                assert "event: done" in response.text
                messages = await client.get(f"/api/chat/sessions/{session_id}/messages")
                assert [item["role"] for item in messages.json()["items"]] == ["user", "llm"]

                ranked = await client.post(
                    "/api/chat/stream",
                    json={
                        "request_id": str(uuid4()),
                        "session_id": session_id,
                        "message": "열교환기 공급 펌프",
                    },
                )
                assert ranked.status_code == 200
                assert "1. P1" in ranked.text
                assert "2. P5" in ranked.text
                assert "3. P2" in ranked.text
                assert ranked.text.index("1. P1") < ranked.text.index("2. P5")
                assert "1순위 P1 설비 보기" in ranked.text

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as stranger:
                forbidden = await stranger.get(f"/api/chat/sessions/{session_id}/messages")
                assert forbidden.status_code == 403
        finally:
            app.dependency_overrides.clear()
            await db.close()
            await transaction.rollback()
    await engine.dispose()
