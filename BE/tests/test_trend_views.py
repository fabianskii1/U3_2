"""Stored trend views retain each sensor window and stay within their chat session."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from skadi_agents.executor import Reply
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.database import get_session
from app.db import models as m
from app.main import app
from app.modules.chat import router as chat_router


@pytest.mark.asyncio
async def test_chat_trend_view_round_trip_and_session_ownership(monkeypatch):
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    suffix = uuid4().hex[:8]
    plant_id, group_id, equipment_id = (f"TV-P-{suffix}", f"TV-G-{suffix}", f"TV-E-{suffix}")
    sensors = [f"TV-S-{suffix}-{index}" for index in range(3)]
    end = datetime.now(UTC).replace(microsecond=0)
    windows = [timedelta(days=7), timedelta(hours=24), timedelta(hours=24)]
    async with engine.connect() as connection:
        tx = await connection.begin()
        db = AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )

        async def test_session():
            yield db

        app.dependency_overrides[get_session] = test_session
        try:
            await db.execute(
                insert(m.plant).values(
                    plant_id=plant_id, plant_name="테스트 공장", location="테스트"
                )
            )
            await db.execute(
                insert(m.equipment_group).values(
                    equipment_group_id=group_id,
                    plant_id=plant_id,
                    equipment_group_name="테스트 그룹",
                )
            )
            await db.execute(
                insert(m.equipment).values(
                    equipment_id=equipment_id,
                    plant_id=plant_id,
                    equipment_group_id=group_id,
                    equipment_name="테스트 압축기",
                    equipment_type="압축기",
                    equipment_status=0,
                    equipment_level=1,
                )
            )
            for sensor_id, name in zip(sensors, ("진동", "전압", "전류"), strict=True):
                await db.execute(
                    insert(m.sensor).values(
                        sensor_id=sensor_id,
                        equipment_id=equipment_id,
                        measurement_name=name,
                        unit="unit",
                    )
                )
            await db.commit()

            async def fake_workflow(*_args, **_kwargs):
                return Reply(
                    "센서별 트렌드를 엽니다.",
                    trend_intent={
                        "equipmentGroupId": group_id,
                        "equipmentId": equipment_id,
                        "series": [
                            {
                                "sensorId": sensor_id,
                                "start": (end - duration).isoformat(),
                                "end": end.isoformat(),
                            }
                            for sensor_id, duration in zip(sensors, windows, strict=True)
                        ],
                        "showAnomalies": False,
                    },
                )

            monkeypatch.setattr(chat_router, "run_chat_workflow", fake_workflow)
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                session_id = (await client.post("/api/chat/sessions", json={})).json()["session_id"]
                request_payload = {
                    "request_id": str(uuid4()),
                    "session_id": session_id,
                    "message": "트렌드",
                }
                response = await client.post("/api/chat/stream", json=request_payload)
                assert response.status_code == 200, response.text
                assert "event: citation" in response.text
                replay = await client.post("/api/chat/stream", json=request_payload)
                assert replay.status_code == 200
                assert replay.text == response.text
                messages = (
                    (
                        await db.execute(
                            select(m.session_detail)
                            .where(m.session_detail.c.session_id == int(session_id))
                            .order_by(m.session_detail.c.session_detail_id)
                        )
                    )
                    .mappings()
                    .all()
                )
                assert [row["type"] for row in messages] == ["user", "llm"]
                assert messages[1]["reply_to_session_detail_id"] == messages[0]["session_detail_id"]
                result_response = (
                    await client.get(
                        f"/api/chat/messages/{messages[1]['session_detail_id']}/results"
                    )
                ).json()
                assert result_response["replyToMessageId"] == str(messages[0]["session_detail_id"])
                result = result_response["items"]
                assert len(result) == 1
                view_id = result[0]["viewId"]
                assert result[0]["url"] == f"/trend?viewId={view_id}"
                view = (await client.get(f"/api/chat/trend-views/{view_id}")).json()
                assert view["plantId"] == plant_id
                assert view["equipmentId"] == equipment_id
                assert [item["sensorId"] for item in view["config"]["series"]] == sensors
                assert [
                    datetime.fromisoformat(item["end"]) - datetime.fromisoformat(item["start"])
                    for item in view["config"]["series"]
                ] == windows
                invalid = await client.post(
                    "/api/chat/trend-views",
                    json={
                        "sessionId": int(session_id),
                        "equipmentGroupId": group_id,
                        "equipmentId": equipment_id,
                        "series": [
                            {
                                "sensorId": "UNKNOWN-SENSOR",
                                "start": (end - timedelta(days=1)).isoformat(),
                                "end": end.isoformat(),
                            }
                        ],
                        "messageId": messages[1]["session_detail_id"],
                    },
                )
                assert invalid.status_code == 400
                additional = await client.post(
                    "/api/chat/trend-views",
                    json={
                        "sessionId": int(session_id),
                        "equipmentGroupId": group_id,
                        "equipmentId": equipment_id,
                        "series": [
                            {
                                "sensorId": sensors[0],
                                "start": (end - timedelta(days=1)).isoformat(),
                                "end": end.isoformat(),
                            }
                        ],
                        "messageId": messages[1]["session_detail_id"],
                    },
                )
                assert additional.status_code == 201
                results = (
                    await client.get(
                        f"/api/chat/messages/{messages[1]['session_detail_id']}/results"
                    )
                ).json()["items"]
                assert len(results) == 2
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as stranger:
                    forbidden = await stranger.get(f"/api/chat/trend-views/{view_id}")
                    assert forbidden.status_code == 404
        finally:
            app.dependency_overrides.clear()
            await db.close()
            await tx.rollback()
    await engine.dispose()
