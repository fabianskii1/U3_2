"""Journeys through actual console sections and short contextual follow-ups."""

from urllib.parse import parse_qs, urlsplit

import pytest
from skadi_agents.executor import run_chat_workflow
from test_chat_workspace import tools

__all__ = ["tools"]


@pytest.mark.parametrize("word", ["상세", "상세 보기", "자세히"])
async def test_short_detail_opens_current_diagnosis_incident(console_tools, word):
    reply = await run_chat_workflow(
        console_tools,
        word,
        {
            "page": "/equip",
            "equipment_id": "P3",
            "query": "?section=diagnosis",
            "as_of": "2026-11-19T00:00:00+00:00",
        },
        {},
    )
    assert urlsplit(reply.navigation_href).path == "/incidents/INC-P3"


@pytest.mark.parametrize(
    "screen",
    [
        {"page": "/incidents/INC-P3", "equipment_id": "P3"},
        {"page": "/equip", "equipment_id": "P3", "query": "?section=diagnosis"},
    ],
)
async def test_final_report_command_opens_creation_route_not_draft_section(console_tools, screen):
    reply = await run_chat_workflow(console_tools, "최종 보고서 작성", screen, {})
    url = urlsplit(reply.navigation_href)
    assert url.path == "/reports/new"
    assert parse_qs(url.query)["incident_id"] == ["INC-P3"]
    assert parse_qs(url.query)["equip_id"] == ["P3"]


async def test_detail_in_closed_incident_keeps_the_open_incident(console_tools):
    reply = await run_chat_workflow(console_tools, "상세", {"page": "/incidents/INC-P1"}, {})
    assert urlsplit(reply.navigation_href).path == "/incidents/INC-P1"


@pytest.mark.parametrize(
    "message", ["장비 보여줘", "부품 보여줘", "장비를 보여줘", "부품", "장비 보기"]
)
@pytest.mark.parametrize("page", ["/equip", "/alarms"])
async def test_equipment_and_part_words_open_selected_pumps_3d(console_tools, message, page):
    reply = await run_chat_workflow(
        console_tools, message, {"page": page, "equipment_id": "P3"}, {}
    )
    params = parse_qs(urlsplit(reply.navigation_href).query)
    assert urlsplit(reply.navigation_href).path == "/equip"
    assert params["equip_id"] == ["P3"] and params["section"] == ["3d"]


async def test_part_request_without_selected_pump_asks_which_pump(console_tools):
    reply = await run_chat_workflow(console_tools, "부품 보여줘", {}, {})
    assert len(reply.choices) == 6 and reply.navigation_href is None
    chosen = await run_chat_workflow(console_tools, "3번", {}, reply.context)
    assert parse_qs(urlsplit(chosen.navigation_href).query)["equip_id"] == ["P3"]


def screen_for(reply):
    url = urlsplit(reply.navigation_href)
    p = parse_qs(url.query)
    return {
        "page": url.path,
        "query": url.query,
        "equipment_id": p.get("equip_id", [None])[0],
        "equipment_group_id": p.get("unit_id", ["CDU-01"])[0],
        "plant_id": "PLANT-01",
        "as_of": "2026-11-19T00:00:00+00:00",
        "replay_hour": 441,
        "replay_max": 720,
    }


@pytest.fixture
def console_tools(tools):
    items = [
        {
            "incident_id": f"INC-P{i}",
            "equipment_id": f"P{i}",
            "status": "ongoing",
            "diagnosis": "캐비테이션",
            "lead_sensor_id": f"P{i}-PI",
        }
        for i in range(1, 4)
    ]

    async def listing(**kw):
        rows = [
            r
            for r in items
            if not kw.get("equipment_id") or kw["equipment_id"] == r["equipment_id"]
        ]
        return {"items": rows, "next_cursor": None}

    async def detail(key, **kw):
        row = next((r for r in items if r["incident_id"] == key), None)
        return (
            {
                **row,
                "candidates": [
                    {"rank": i, "fault": name}
                    for i, name in enumerate(["캐비테이션", "임펠러 불균형", "씰 누설"], 1)
                ],
            }
            if row
            else None
        )

    tools.list_incidents = listing
    tools.get_incident = detail
    return tools


async def test_unit_trend_is_graph_and_sensor_followups_retain_group_and_period(tools):
    reply = await run_chat_workflow(tools, "1호기 트렌드", {}, {})
    assert urlsplit(reply.navigation_href).path == "/trend"
    assert parse_qs(urlsplit(reply.navigation_href).query)["compare_sensor"] == ["VIB"]
    changed = await run_chat_workflow(tools, "전류", screen_for(reply), reply.context)
    assert parse_qs(urlsplit(changed.navigation_href).query)["compare_sensor"] == ["AMP"]
    assert len(changed.context["workspace"]["series"]) == 6
    temperature = await run_chat_workflow(tools, "온도", screen_for(changed), changed.context)
    assert len(temperature.choices) == 2
    chosen = await run_chat_workflow(tools, "베어링", screen_for(changed), temperature.context)
    assert parse_qs(urlsplit(chosen.navigation_href).query)["compare_sensor"] == ["TB"]
    status = await run_chat_workflow(tools, "1호기 현황", screen_for(chosen), chosen.context)
    assert status.navigation_href == "/equip?unit_id=CDU-01"


async def test_selected_pump_sensor_followup_uses_actual_screen_not_old_history(tools):
    old = {"workspace": {"page": "/trend", "equipment_id": "P1"}}
    reply = await run_chat_workflow(tools, "전류", {"page": "/equip", "equipment_id": "P3"}, old)
    assert reply.trend_intent["equipmentId"] == "P3"
    assert reply.trend_intent["series"][0]["sensorId"] == "P3-I"


async def test_unit_graph_after_eight_sensor_status_starts_with_vibration(tools):
    status = await run_chat_workflow(tools, "펌프3 현황", {}, {})
    reply = await run_chat_workflow(
        tools, "1호기 트렌드", {"page": "/equip", "equipment_id": "P3"}, status.context
    )
    assert parse_qs(urlsplit(reply.navigation_href).query)["compare_sensor"] == ["VIB"]
    assert len(reply.context["workspace"]["series"]) == 6


async def test_saved_mixed_graph_sensor_change_keeps_only_its_equipment(tools):
    async def owners(ids):
        return [await tools.load_equipment("P1"), await tools.load_equipment("P2")]

    tools.equipment_for_sensors = owners
    reply = await run_chat_workflow(
        tools,
        "진동",
        {
            "page": "/trend",
            "query": "?viewId=saved",
            "equipment_group_id": "CDU-01",
            "trend_series": [{"sensorId": "P1-I"}, {"sensorId": "P2-I"}],
        },
        {},
    )
    assert {s["sensorId"] for s in reply.trend_intent["series"]} == {"P1-V", "P2-V"}


async def test_3d_short_modes_risk_and_fault_name_change_real_controls(console_tools):
    reply = await run_chat_workflow(console_tools, "펌프3 3D", {}, {})
    assert len(reply.choices) == 3
    assert parse_qs(urlsplit(reply.navigation_href).query)["section"] == ["3d"]
    for word, mode in [("고장 부품만", "only"), ("강조", "ghost"), ("전체 보기", "all")]:
        reply = await run_chat_workflow(console_tools, word, screen_for(reply), reply.context)
        assert parse_qs(urlsplit(reply.navigation_href).query)["mode"] == [mode]
    reply = await run_chat_workflow(console_tools, "위험 2", screen_for(reply), reply.context)
    assert parse_qs(urlsplit(reply.navigation_href).query)["fault"] == ["임펠러 불균형"]
    reply = await run_chat_workflow(console_tools, "씰", screen_for(reply), reply.context)
    assert parse_qs(urlsplit(reply.navigation_href).query)["fault"] == ["씰 누설"]
    invalid = await run_chat_workflow(console_tools, "위험 12", screen_for(reply), reply.context)
    assert invalid.navigation_href is None and "후보가 없습니다" in invalid.message


async def test_3d_without_pump_offers_registered_choices_and_number_selection(console_tools):
    reply = await run_chat_workflow(console_tools, "3D", {}, {})
    assert len(reply.choices) == 6
    chosen = await run_chat_workflow(console_tools, "3번", {}, reply.context)
    assert parse_qs(urlsplit(chosen.navigation_href).query)["equip_id"] == ["P3"]


async def test_replay_feed_and_short_replay_commands(console_tools):
    reply = await run_chat_workflow(console_tools, "기록 재생", {}, {})
    assert parse_qs(urlsplit(reply.navigation_href).query)["section"] == ["replay"]
    reply = await run_chat_workflow(console_tools, "현재", screen_for(reply), reply.context)
    assert parse_qs(urlsplit(reply.navigation_href).query)["replay"] == ["live"]
    reply = await run_chat_workflow(console_tools, "예시 시각", screen_for(reply), reply.context)
    assert parse_qs(urlsplit(reply.navigation_href).query)["replay"] == ["example"]
    reply = await run_chat_workflow(console_tools, "다음", screen_for(reply), reply.context)
    assert parse_qs(urlsplit(reply.navigation_href).query)["replay"] == ["442"]
    reply = await run_chat_workflow(
        console_tools, "지금 봐야할 알림", screen_for(reply), reply.context
    )
    assert parse_qs(urlsplit(reply.navigation_href).query)["section"] == ["feed"]


async def test_alarm_followup_filters_keep_current_scope_and_can_exit(console_tools):
    reply = await run_chat_workflow(console_tools, "펌프3 알람 이력", {}, {})
    reply = await run_chat_workflow(console_tools, "흡입", screen_for(reply), reply.context)
    p = parse_qs(urlsplit(reply.navigation_href).query)
    assert p["equip_id"] == ["P3"] and p["q"] == ["흡입"]
    reply = await run_chat_workflow(console_tools, "경고", screen_for(reply), reply.context)
    p = parse_qs(urlsplit(reply.navigation_href).query)
    assert p["severity"] == ["2"] and p["q"] == ["흡입"]
    trend = await run_chat_workflow(
        console_tools, "펌프3 흡입 트렌드", screen_for(reply), reply.context
    )
    assert trend.trend_intent is not None


async def test_incident_selection_sections_and_draft_generation(console_tools):
    reply = await run_chat_workflow(console_tools, "이상 사건", {}, {})
    assert len(reply.choices) == 3 and urlsplit(reply.navigation_href).path == "/incidents"
    reply = await run_chat_workflow(console_tools, "2번", screen_for(reply), reply.context)
    assert urlsplit(reply.navigation_href).path == "/incidents/INC-P2"
    for word, section in [
        ("경과", "timeline"),
        ("원인", "causes"),
        ("관련 알람", "alarms"),
        ("구간 트렌드", "trend"),
        ("초안 만들기", "draft"),
    ]:
        reply = await run_chat_workflow(console_tools, word, screen_for(reply), reply.context)
        p = parse_qs(urlsplit(reply.navigation_href).query)
        assert p["section"] == [section]
        if section == "draft":
            assert p["draft"] == ["open"]


async def test_single_filtered_incident_opens_detail_without_extra_choice(console_tools):
    reply = await run_chat_workflow(console_tools, "펌프3 이상 사건", {}, {})
    assert urlsplit(reply.navigation_href).path == "/incidents/INC-P3"
