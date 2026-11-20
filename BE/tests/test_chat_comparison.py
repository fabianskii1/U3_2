"""Individual targets and the existing all-pump overlay are both selectable."""

from urllib.parse import parse_qs, urlsplit

import pytest
from skadi_agents.executor import run_chat_workflow
from test_chat_workspace import tools

__all__ = ["tools"]


@pytest.mark.parametrize("choice", ["전체", "전체 비교", "모두", "7번"])
async def test_comparison_choice_preserves_individual_targets_and_opens_overlay(tools, choice):
    first = await run_chat_workflow(tools, "진동 최근 3일 트렌드 보여줘", {}, {})
    assert len(first.context["workspace_pending"]["candidates"]) == 6
    assert len(first.choices) == 7 and first.choices[-1]["message"] == "전체 비교"
    reply = await run_chat_workflow(tools, choice, {}, first.context)
    assert reply.trend_intent is None
    params = parse_qs(urlsplit(reply.navigation_href).query)
    assert params["compare"] == ["all"] and params["compare_sensor"] == ["VIB"]
    assert params["compare_equipment_id"] == [f"P{i}" for i in range(1, 7)]
    assert len(reply.context["workspace"]["series"]) == 6


async def test_temperature_comparison_asks_for_sensor_before_opening_all_pumps(tools):
    first = await run_chat_workflow(tools, "온도 최근 3일 트렌드 보여줘", {}, {})
    sensors = await run_chat_workflow(tools, "전체 비교", {}, first.context)
    assert len(sensors.choices) == 2
    reply = await run_chat_workflow(tools, "베어링", {}, sensors.context)
    assert parse_qs(urlsplit(reply.navigation_href).query)["compare_sensor"] == ["TB"]


async def test_explicit_all_pump_comparison_and_interval_followup(tools):
    reply = await run_chat_workflow(tools, "전체 펌프 전류 최근 3일 트렌드 보여줘", {}, {})
    assert parse_qs(urlsplit(reply.navigation_href).query)["compare_sensor"] == ["AMP"]
    changed = await run_chat_workflow(tools, "최근 2일만", {}, reply.context)
    assert parse_qs(urlsplit(changed.navigation_href).query)["compare_sensor"] == ["AMP"]


async def test_api_delivers_group_comparison_link_and_replays_it():
    import json
    from uuid import uuid4

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.database import engine, get_session
    from app.main import app

    async with engine.connect() as connection:
        transaction = await connection.begin()
        db = AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )

        async def session():
            yield db

        app.dependency_overrides[get_session] = session
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                session_id = (await client.post("/api/chat/sessions", json={})).json()["session_id"]

                async def send(message, request_id=None):
                    response = await client.post(
                        "/api/chat/stream",
                        json={
                            "session_id": session_id,
                            "request_id": request_id or str(uuid4()),
                            "message": message,
                        },
                    )
                    assert response.status_code == 200, response.text
                    result = {}
                    for frame in response.text.strip().split("\n\n"):
                        name, payload = frame.split("\ndata: ", 1)
                        result.setdefault(name.removeprefix("event: "), []).append(
                            json.loads(payload)
                        )
                    return result

                choices = await send("진동 최근 3일 트렌드 보여줘")
                assert len(choices["choice"]) == 7
                request_id = str(uuid4())
                response = await send("전체 비교", request_id)
                href = response["navigate"][0]["href"]
                params = parse_qs(urlsplit(href).query)
                assert (
                    params["compare_sensor"] == ["VIB"] and len(params["compare_equipment_id"]) == 6
                )
                assert "+09:00" not in params["from"][0]
                replay = await send("전체 비교", request_id)
                assert replay["navigate"] == response["navigate"]
        finally:
            app.dependency_overrides.clear()
            await db.close()
            await transaction.rollback()
    await engine.dispose()
