"""Sensor requests default to trends; grammatical scope replies retain their meaning."""

from urllib.parse import parse_qs, urlsplit

import pytest
from skadi_agents.executor import run_chat_workflow
from test_chat_workspace import tools

__all__ = ["tools"]


@pytest.mark.parametrize("page", ["/dashboard", "/equip", "/trend"])
@pytest.mark.parametrize("question", ["펌프 3 압력", "펌프 3 압렵", "펌프3 압력 보여주라"])
async def test_pressure_selection_defaults_to_trend_on_every_screen(tools, page, question):
    screen = {"page": page, "equipment_id": "P1"}
    first = await run_chat_workflow(tools, question, screen, {})
    assert len(first.choices) == 2
    chosen = await run_chat_workflow(tools, "흡입압", screen, first.context)
    assert chosen.navigation_href is None
    assert chosen.trend_intent["equipmentId"] == "P3"
    assert chosen.trend_intent["series"][0]["sensorId"] == "P3-PI"


@pytest.mark.parametrize(
    "sensor, tag",
    [
        ("전류", "I"),
        ("진동", "V"),
        ("베어링", "TB"),
        ("유체", "TF"),
        ("전압", "ET"),
        ("흡입", "PI"),
        ("토출", "PO"),
        ("회전", "S"),
    ],
)
async def test_all_sensor_names_default_to_trend_even_after_status(tools, sensor, tag):
    status = await run_chat_workflow(tools, "펌프3 현황", {}, {})
    reply = await run_chat_workflow(
        tools, f"펌프3 {sensor}", {"page": "/equip", "equipment_id": "P3"}, status.context
    )
    assert reply.trend_intent["series"][0]["sensorId"] == f"P3-{tag}"


@pytest.mark.parametrize(
    "question", ["펌프3 현황", "펌프3 설비 현황", "펌프3 전류 현황", "펌프3 상태"]
)
async def test_explicit_status_opens_equipment(tools, question):
    reply = await run_chat_workflow(tools, question, {"page": "/trend"}, {})
    assert reply.navigation_href.startswith("/equip?")
    assert parse_qs(urlsplit(reply.navigation_href).query)["equip_id"] == ["P3"]
    assert reply.trend_intent is None


async def test_explicit_pressure_status_keeps_view_after_sensor_selection(tools):
    first = await run_chat_workflow(tools, "펌프3 압렵 현황", {}, {})
    reply = await run_chat_workflow(tools, "흡입압", {}, first.context)
    assert reply.navigation_href.startswith("/equip?")
    assert "sensor_id=P3-PI" in reply.navigation_href


@pytest.mark.parametrize(
    "message",
    [
        "흡입압의 전체를 다 보여주라",
        "흡입압의 전체를 다 보여주라!",
        "흡입압 전체 보여줘",
        "전체 펌프의 흡입압 보여줘",
        "모든 펌프 흡입압",
        "흡입압을 모두 보여줘",
        "흡입압 전부 보여줘",
    ],
)
@pytest.mark.parametrize("pending", [False, True])
async def test_whole_sentence_scope_requests_open_all_pump_trend(tools, message, pending):
    context = {}
    if pending:
        first = await run_chat_workflow(tools, "흡입압 트렌드", {}, {})
        assert len(first.choices) == 7
        context = first.context
    reply = await run_chat_workflow(
        tools, message, {"page": "/equip", "equipment_id": "P3"}, context
    )
    params = parse_qs(urlsplit(reply.navigation_href).query)
    assert params["compare_sensor"] == ["PS"]
    assert params["compare_equipment_id"] == [f"P{i}" for i in range(1, 7)]


async def test_sensor_choice_can_expand_single_pump_to_all_pumps(tools):
    first = await run_chat_workflow(tools, "펌프3 압렵 최근 3일", {}, {})
    reply = await run_chat_workflow(tools, "흡입압의 전체를 다 보여주라", {}, first.context)
    assert parse_qs(urlsplit(reply.navigation_href).query)["compare_sensor"] == ["PS"]
    assert len(reply.context["workspace"]["series"]) == 6


async def test_all_choice_can_refine_sensor_in_same_sentence(tools):
    first = await run_chat_workflow(tools, "압력 트렌드", {}, {})
    reply = await run_chat_workflow(tools, "흡입압의 전체를 다 보여주라", {}, first.context)
    assert parse_qs(urlsplit(reply.navigation_href).query)["compare_sensor"] == ["PS"]


async def test_all_pressure_selection_and_explicit_all_status(tools):
    first = await run_chat_workflow(tools, "전체 펌프 압렵", {}, {})
    reply = await run_chat_workflow(tools, "흡입압", {}, first.context)
    assert parse_qs(urlsplit(reply.navigation_href).query)["compare_sensor"] == ["PS"]
    status = await run_chat_workflow(tools, "흡입압의 전체 현황을 다 보여주라", {}, {})
    assert status.navigation_href.startswith("/equip?")
    params = parse_qs(urlsplit(status.navigation_href).query)
    assert "equip_id" not in params and params["unit_id"] == ["CDU-01"]
    assert len(params["sensor_id"]) == 6


async def test_sensor_only_asks_which_pump_and_unknown_name_is_not_discarded(tools):
    reply = await run_chat_workflow(tools, "흡입압", {}, {})
    assert len(reply.choices) == 7
    unknown = await run_chat_workflow(tools, "없는펌프 흡입압의 전체를 다 보여주라", {}, {})
    assert unknown.navigation_href is None and unknown.trend_intent is None
    assert "찾지 못했습니다" in unknown.message


async def test_explicit_value_query_still_reads_values(tools):
    reply = await run_chat_workflow(tools, "펌프3 흡입압 얼마야", {}, {})
    assert "12.3 kPa" in reply.message
    assert reply.navigation_href is None and reply.trend_intent is None


async def test_new_pump_request_does_not_select_previous_pumps_sensor(tools):
    first = await run_chat_workflow(tools, "펌프3 압력", {}, {})
    reply = await run_chat_workflow(tools, "펌프2 흡입압", {}, first.context)
    assert reply.trend_intent["equipmentId"] == "P2"
    assert reply.trend_intent["series"][0]["sensorId"] == "P2-PI"


async def test_sensor_reply_can_explicitly_switch_to_status(tools):
    first = await run_chat_workflow(tools, "펌프3 압력", {}, {})
    reply = await run_chat_workflow(tools, "흡입압 현황", {}, first.context)
    assert reply.navigation_href.startswith("/equip?")
    assert "sensor_id=P3-PI" in reply.navigation_href


async def test_api_sensor_default_and_sentence_scope(monkeypatch):
    import json
    from uuid import uuid4

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.database import engine, get_session
    from app.main import app
    from app.modules.chat import router

    async def no_lookup(*args):
        raise AssertionError("Sensor/scope grammar must resolve without an equipment-name model")

    monkeypatch.setattr(router, "_lookup_equipment", no_lookup)
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

                async def send(message):
                    result = await client.post(
                        "/api/chat/stream",
                        json={
                            "session_id": session_id,
                            "request_id": str(uuid4()),
                            "message": message,
                            "screen_context": {"page": "/equip", "equipment_id": "P1"},
                        },
                    )
                    assert result.status_code == 200, result.text
                    events = {}
                    for frame in result.text.strip().split("\n\n"):
                        name, data = frame.split("\ndata: ", 1)
                        events.setdefault(name.removeprefix("event: "), []).append(json.loads(data))
                    assert "error" not in events, events
                    return events

                first = await send("펌프 3 압렵")
                assert len(first["choice"]) == 2
                chosen = await send("흡입압")
                href = chosen["navigate"][0]["href"]
                assert href.startswith("/trend?")
                view_id = parse_qs(urlsplit(href).query)["viewId"][0]
                view = (await client.get(f"/api/chat/trend-views/{view_id}")).json()
                assert view["equipmentId"] == "P3"
                assert view["config"]["series"][0]["sensorId"] == "10-PT-1306"
                await send("흡입압 트렌드")
                all_pumps = await send("흡입압의 전체를 다 보여주라")
                params = parse_qs(urlsplit(all_pumps["navigate"][0]["href"]).query)
                assert params["compare_sensor"] == ["PS"]
                assert len(params["compare_equipment_id"]) == 6
                status = await send("펌프3 현황")
                assert status["navigate"][0]["href"].startswith("/equip?")
                all_status = await send("흡입압의 전체 현황을 다 보여주라")
                href = all_status["navigate"][0]["href"]
                assert href.startswith("/equip?")
                assert len(parse_qs(urlsplit(href).query)["sensor_id"]) == 6
        finally:
            app.dependency_overrides.clear()
            await db.close()
            await transaction.rollback()
    await engine.dispose()
