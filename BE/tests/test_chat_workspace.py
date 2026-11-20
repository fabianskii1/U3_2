"""User journeys across dashboard, equipment and trend, without model calls."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from skadi_agents.equipment_status import Entity
from skadi_agents.executor import run_chat_workflow
from skadi_agents.workspace import canonical_pumps


@pytest.fixture
def tools():
    assets = {
        f"P{i}": Entity("equipment", f"P{i}", f"펌프 {i}", "PLANT-01", "CDU-01", "펌프")
        for i in range(1, 7)
    }

    async def resolve(query, **kwargs):
        query = canonical_pumps(query)
        if query in assets:
            return "found", [assets[query]]
        if query in {"CDU 1호기", "CDU-01", "1호기"}:
            return "found", [Entity("unit", "CDU-01", "CDU 1호기", "PLANT-01", "CDU-01")]
        if query == "이송 펌프":
            return "ambiguous", [assets["P2"], assets["P3"]]
        return "not_found", []

    async def load(code):
        return assets.get(code)

    async def sensors(code):
        return [
            {"sensor_id": f"{code}-I", "measurement_name": "모터 전류", "unit": "A"},
            {"sensor_id": f"{code}-V", "measurement_name": "진동 속도 RMS", "unit": "mm/s RMS"},
            {"sensor_id": f"{code}-TF", "measurement_name": "유체 온도", "unit": "°C"},
            {"sensor_id": f"{code}-TB", "measurement_name": "베어링 온도", "unit": "°C"},
            {"sensor_id": f"{code}-ET", "measurement_name": "모터 선간전압", "unit": "V"},
            {"sensor_id": f"{code}-PI", "measurement_name": "흡입압", "unit": "kPa"},
            {"sensor_id": f"{code}-PO", "measurement_name": "토출압", "unit": "kPa"},
            {"sensor_id": f"{code}-S", "measurement_name": "회전수", "unit": "rpm"},
        ]

    async def readings(code):
        return {
            "sensors": [
                {**s, "current_value": 12.3, "measured_at": "2026-11-19T00:00:00+00:00"}
                for s in await sensors(code)
            ]
        }

    async def dashboard(**scope):
        return {
            "equipment_count": 6,
            "normal_count": 5,
            "alarm_summary": [],
            "priority": {
                "status": "no_data",
                "active_count": 0,
                "affected_equipment_count": 0,
                "unknown_count": 0,
                "unscored_count": 0,
                "items": [],
            },
        }

    async def equipment_of_type(_kind):
        return list(assets.values())

    return SimpleNamespace(
        resolve_entity=resolve,
        load_equipment=load,
        get_equipment_sensors=sensors,
        get_equipment_readings=readings,
        get_dashboard=dashboard,
        equipment_of_type=equipment_of_type,
    )


@pytest.mark.parametrize("name", ["펌프1번", "펌프 1번", "1번 펌프", "펌프1", "P1", "p1"])
async def test_natural_pump_names_navigate(tools, name):
    reply = await run_chat_workflow(
        tools, f"{name} 현황 보여줘", {"page": "/dashboard", "equipment_id": "P4"}, {}
    )
    assert parse_qs(urlsplit(reply.navigation_href).query)["equip_id"] == ["P1"]


async def test_complete_navigation_and_followup_journey(tools):
    reply = await run_chat_workflow(tools, "펌프1번 현황 보여줘", {"page": "/dashboard"}, {})
    assert reply.navigation_href == "/equip?equip_id=P1"
    reply = await run_chat_workflow(
        tools,
        "이 설비 전류랑 진동 최근 3일 보여줘",
        {"page": "/equip", "equipment_id": "P1"},
        reply.context,
    )
    assert [s["sensorId"] for s in reply.trend_intent["series"]] == ["P1-I", "P1-V"]
    for s in reply.trend_intent["series"]:
        assert datetime.fromisoformat(s["end"]) - datetime.fromisoformat(s["start"]) == timedelta(
            days=3
        )
    reply = await run_chat_workflow(
        tools, "이번에는 2번 펌프", {"page": "/trend", "equipment_id": "P1"}, reply.context
    )
    assert [s["sensorId"] for s in reply.trend_intent["series"]] == ["P2-I", "P2-V"]
    reply = await run_chat_workflow(
        tools, "현재 값은?", {"page": "/trend", "equipment_id": "P2"}, reply.context
    )
    assert "12.3 A" in reply.message and "KST" in reply.message
    assert reply.navigation_href is None
    reply = await run_chat_workflow(
        tools, "이 설비 현황으로 가줘", {"page": "/trend", "equipment_id": "P2"}, reply.context
    )
    assert reply.navigation_href.startswith("/equip?equip_id=P2")
    reply = await run_chat_workflow(
        tools, "전체 대시보드로 돌아가줘", {"page": "/equip", "equipment_id": "P2"}, reply.context
    )
    assert reply.navigation_href == "/dashboard"
    assert "데이터가 없습니다" in reply.message
    assert "equipment_id" not in reply.context


async def test_ambiguous_temperature_selection_keeps_original_period(tools):
    reply = await run_chat_workflow(tools, "펌프1번 온도 최근 3일 트렌드 보여줘", {}, {})
    assert "여러 개" in reply.message and reply.trend_intent is None
    chosen = await run_chat_workflow(tools, "2번", {}, reply.context)
    assert chosen.trend_intent["series"][0]["sensorId"] == "P1-TB"
    assert datetime.fromisoformat(chosen.trend_intent["series"][0]["end"]) - datetime.fromisoformat(
        chosen.trend_intent["series"][0]["start"]
    ) == timedelta(days=3)


async def test_comparison_and_append_retain_existing_series(tools):
    reply = await run_chat_workflow(tools, "P1과 P2 전류 비교해줘", {}, {})
    assert reply.trend_intent["equipmentId"] is None
    assert [s["sensorId"] for s in reply.trend_intent["series"]] == ["P1-I", "P2-I"]
    first = await run_chat_workflow(tools, "P1 전류 최근 3일 트렌드 보여줘", {}, {})
    added = await run_chat_workflow(
        tools, "P2 전류도 비교해줘", {"page": "/trend", "equipment_id": "P1"}, first.context
    )
    assert {s["sensorId"] for s in added.trend_intent["series"]} == {"P1-I", "P2-I"}
    assert added.trend_intent["equipmentId"] is None


@pytest.mark.parametrize(
    "question",
    [
        "P1 전류 최근 0일 트렌드 보여줘",
        "P1 전류 최근 91일 트렌드 보여줘",
        "P1 전류 2027-01-01부터 2027-01-02까지 트렌드 보여줘",
        "P1 전류 1초 단위 트렌드 보여줘",
        "P1 전류 11월 31일부터 12월 1일까지 트렌드 보여줘",
    ],
)
async def test_invalid_periods_are_explained_without_navigation(tools, question):
    reply = await run_chat_workflow(tools, question, {}, {})
    assert reply.trend_intent is None and reply.navigation_href is None
    assert reply.message


async def test_absolute_dates_and_interval_followup(tools):
    reply = await run_chat_workflow(tools, "P1 전류 11월 10일부터 15일까지 트렌드 보여줘", {}, {})
    series = reply.trend_intent["series"][0]
    assert series["start"].endswith("11-10T00:00:00+09:00")
    assert series["end"].endswith("11-16T00:00:00+09:00")
    changed = await run_chat_workflow(
        tools, "1분 단위로 자세히 보여줘", {"page": "/trend", "equipment_id": "P1"}, reply.context
    )
    assert changed.trend_intent["interval"] == "1m"
    assert changed.trend_intent["series"] == reply.trend_intent["series"]


async def test_per_sensor_periods_and_manual_screen_changes(tools):
    reply = await run_chat_workflow(tools, "P1 전류는 3일, 진동은 7일 보여줘", {}, {})
    assert [
        datetime.fromisoformat(s["end"]) - datetime.fromisoformat(s["start"])
        for s in reply.trend_intent["series"]
    ] == [timedelta(days=3), timedelta(days=7)]
    changed = await run_chat_workflow(
        tools, "이 설비 전류 트렌드 보여줘", {"page": "/equip", "equipment_id": "P3"}, reply.context
    )
    assert changed.trend_intent["equipmentId"] == "P3"


async def test_scoped_dashboard_and_unit_navigation(tools):
    reply = await run_chat_workflow(tools, "CDU 1호기 대시보드 보여줘", {}, {})
    assert reply.navigation_href == "/dashboard?unit_id=CDU-01"
    reply = await run_chat_workflow(tools, "CDU 1호기 설비 전부 보여줘", {}, {})
    assert reply.navigation_href == "/equip?unit_id=CDU-01"


async def test_workspace_api_persists_comparison_and_matches_dashboard(monkeypatch):
    import json
    from uuid import uuid4

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import insert
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.database import engine, get_session
    from app.db import models
    from app.main import app
    from app.modules.chat import router as chat_router

    async def no_model(*_args):
        raise AssertionError("Numbered pumps and screen followups must not need an LLM")

    monkeypatch.setattr(chat_router, "_lookup_equipment", no_model)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        db = AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )

        async def dependency():
            yield db

        app.dependency_overrides[get_session] = dependency
        try:
            await db.execute(
                insert(models.sensor_data_1m).values(
                    signal_id="10-IT-1104",
                    value=12.3,
                    measured_at=datetime.now().astimezone() - timedelta(seconds=1),
                )
            )
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                session = (await client.post("/api/chat/sessions", json={})).json()["session_id"]

                async def send(message, screen=None, request_id=None):
                    payload = {
                        "request_id": request_id or str(uuid4()),
                        "session_id": session,
                        "message": message,
                        "screen_context": screen or {},
                    }
                    result = await client.post("/api/chat/stream", json=payload)
                    assert result.status_code == 200, result.text
                    events = {}
                    for frame in result.text.strip().split("\n\n"):
                        name, data = frame.split("\ndata: ", 1)
                        events.setdefault(name.removeprefix("event: "), []).append(json.loads(data))
                    return events

                data = (await client.get("/api/dashboard")).json()
                summary = await send("전체 설비 몇 대야?")
                assert str(data["equipment_count"]) + "대" in summary["message.delta"][0]["text"]
                assert "navigate" not in summary
                selection_request = str(uuid4())
                selection = await send(
                    "다른 펌프 진동 최근 3일 트렌드 보여줘",
                    {"page": "/equip", "equipment_id": "P4"},
                    request_id=selection_request,
                )
                assert len(selection["choice"]) == 7 and "navigate" not in selection
                replayed_selection = await send(
                    "다른 펌프 진동 최근 3일 트렌드 보여줘", request_id=selection_request
                )
                assert replayed_selection["choice"] == selection["choice"]
                selected = await send("2번")
                selected_view_id = parse_qs(urlsplit(selected["navigate"][0]["href"]).query)[
                    "viewId"
                ][0]
                selected_view = (
                    await client.get(f"/api/chat/trend-views/{selected_view_id}")
                ).json()
                assert selected_view["equipmentId"] == "P2"
                assert selected_view["config"]["series"][0]["sensorId"] == "10-VT-1205"
                values = await send("펌프1번 전류 얼마야?")
                assert "12.3 A" in values["message.delta"][0]["text"]
                assert "navigate" not in values
                question_id = str(uuid4())
                trend = await send("P1과 펌프2번 전류 최근 3일 비교해줘", request_id=question_id)
                href = trend["navigate"][0]["href"]
                view_id = parse_qs(urlsplit(href).query)["viewId"][0]
                view = (await client.get(f"/api/chat/trend-views/{view_id}")).json()
                assert view["equipmentId"] is None
                assert {s["sensorId"] for s in view["config"]["series"]} == {
                    "10-IT-1104",
                    "10-IT-1204",
                }
                replay = await send("P1과 펌프2번 전류 최근 3일 비교해줘", request_id=question_id)
                assert replay["navigate"] == trend["navigate"]
                interval = await send(
                    "1시간 단위로 보여줘",
                    {
                        "page": "/trend",
                        "trend_series": view["config"]["series"],
                        "equipment_group_id": "CDU-01",
                    },
                )
                assert "navigate" in interval
        finally:
            app.dependency_overrides.clear()
            await db.close()
            await transaction.rollback()
    await engine.dispose()


@pytest.mark.parametrize(
    "sensor", ["전류", "전압", "진동", "회전수", "흡입압", "토출압", "유체 온도", "베어링 온도"]
)
@pytest.mark.parametrize("mode", ["트렌드 보여줘", "현황 보여줘", "얼마야?"])
async def test_short_sensor_request_retains_current_screen_scope(tools, sensor, mode):
    previous = {"equipment_id": "P1", "workspace": {"page": "/trend", "equipment_id": "P1"}}
    screen = {
        "page": "/equip",
        "plant_id": "PLANT-01",
        "equipment_group_id": "CDU-01",
        "equipment_id": "P4",
    }
    reply = await run_chat_workflow(tools, f"{sensor} {mode}", screen, previous)
    assert not reply.choices
    if "트렌드" in mode:
        assert reply.trend_intent["equipmentId"] == "P4"
        assert all(s["sensorId"].startswith("P4-") for s in reply.trend_intent["series"])
    elif "현황" in mode:
        assert "equip_id=P4" in reply.navigation_href
    else:
        assert "펌프 4" in reply.message and "12.3" in reply.message


async def test_pump_choice_then_sensor_choice_preserves_period(tools):
    reply = await run_chat_workflow(
        tools, "온도 최근 3일 트렌드 보여줘", {"equipment_id": "P4"}, {}
    )
    assert len(reply.choices) == 7
    reply = await run_chat_workflow(tools, "2번", {}, reply.context)
    assert len(reply.choices) == 2 and reply.trend_intent is None
    reply = await run_chat_workflow(tools, "베어링 온도", {}, reply.context)
    series = reply.trend_intent["series"][0]
    assert series["sensorId"] == "P2-TB"
    assert datetime.fromisoformat(series["end"]) - datetime.fromisoformat(
        series["start"]
    ) == timedelta(days=3)


@pytest.fixture
def named_tools(tools):
    names = [
        "원유 공급 펌프",
        "나프타 제품 이송 펌프",
        "등유 측류 이송 펌프",
        "경유 측류 이송 펌프",
        "펌프어라운드 순환 펌프",
        "상압잔사유 이송 펌프",
    ]

    async def equipment_of_type(_kind):
        return [
            Entity("equipment", f"P{i}", name, "PLANT-01", "CDU-01", "펌프")
            for i, name in enumerate(names, 1)
        ]

    async def lookup_alias(code, **_kwargs):
        aliases = [{"alias_name": "등록된 납사 펌프"}] if code == "P2" else []
        return {"candidates": [{"id": code, "aliases": aliases}]}

    tools.equipment_of_type = equipment_of_type
    tools.lookup_alias = lookup_alias
    return tools


@pytest.mark.parametrize(
    "short, expected",
    [
        ("원유", "P1"),
        ("원유공급", "P1"),
        ("나프타", "P2"),
        ("나프타펌프", "P2"),
        ("등유 측류", "P3"),
        ("경유 측류", "P4"),
        ("경유측류", "P4"),
        ("경유 펌프", "P4"),
        ("경유 측류로", "P4"),
        ("경유측류요", "P4"),
        ("경유 측류로 보여줘", "P4"),
        ("순환", "P5"),
        ("잔사유", "P6"),
        ("등록된 납사", "P2"),
        ("펌프4번", "P4"),
    ],
)
async def test_short_choice_keeps_sensor_and_period(named_tools, short, expected):
    reply = await run_chat_workflow(named_tools, "진동 최근 3일 트렌드 보여줘", {}, {})
    reply = await run_chat_workflow(named_tools, short, {}, reply.context)
    assert reply.trend_intent["equipmentId"] == expected
    (series,) = reply.trend_intent["series"]
    assert series["sensorId"] == expected + "-V"
    assert datetime.fromisoformat(series["end"]) - datetime.fromisoformat(
        series["start"]
    ) == timedelta(days=3)


async def test_ambiguous_fragment_narrows_and_reindexes_choices(named_tools):
    reply = await run_chat_workflow(named_tools, "전류 최근 3일 트렌드 보여줘", {}, {})
    narrowed = await run_chat_workflow(named_tools, "이송", {}, reply.context)
    assert narrowed.trend_intent is None and narrowed.navigation_href is None
    assert [c["id"] for c in narrowed.context["workspace_pending"]["candidates"]] == [
        "P2",
        "P3",
        "P4",
        "P6",
    ]
    chosen = await run_chat_workflow(named_tools, "경유 측류", {}, narrowed.context)
    assert chosen.trend_intent["equipmentId"] == "P4"
    numbered = await run_chat_workflow(named_tools, "2번", {}, narrowed.context)
    assert numbered.trend_intent["equipmentId"] == "P3"


async def test_short_equipment_choice_then_sensor_clarification(named_tools):
    reply = await run_chat_workflow(named_tools, "온도 최근 3일 트렌드 보여줘", {}, {})
    reply = await run_chat_workflow(named_tools, "경유 측류", {}, reply.context)
    assert reply.trend_intent is None and len(reply.choices) == 2
    reply = await run_chat_workflow(named_tools, "베어링 온도", {}, reply.context)
    assert reply.trend_intent["series"][0]["sensorId"] == "P4-TB"
