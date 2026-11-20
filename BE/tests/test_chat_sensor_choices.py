"""Short sensor replies resolve against registered choices without losing the request."""

from datetime import datetime, timedelta

import pytest
from skadi_agents.equipment_status import matching_sensors
from skadi_agents.executor import run_chat_workflow
from skadi_agents.workspace.selection import matching_sensor_choices
from test_chat_workspace import tools

__all__ = ["tools"]


@pytest.mark.parametrize(
    "question, short, expected",
    [
        ("압력", "흡입", "PI"),
        ("압력", "토출", "PO"),
        ("압력", "흡입쪽", "PI"),
        ("압력", "토출측", "PO"),
        ("압력", "흡입으로", "PI"),
        ("압력", "토출요", "PO"),
        ("압력", "흡입 보여줘", "PI"),
        ("압력", "그중 토출", "PO"),
        ("온도", "베어링", "TB"),
        ("온도", "유체", "TF"),
        ("온도", "베어링쪽", "TB"),
        ("온도", "유체로", "TF"),
        ("온도", "배어링", "TB"),
        ("속도", "회전", "S"),
        ("속도", "진동", "V"),
    ],
)
async def test_short_selection_keeps_equipment_sensor_and_period(tools, question, short, expected):
    first = await run_chat_workflow(tools, f"펌프3번 {question} 최근 3일 트렌드 보여줘", {}, {})
    assert first.trend_intent is None and len(first.choices) == 2
    selected = await run_chat_workflow(tools, short, {"equipment_id": "P1"}, first.context)
    assert selected.trend_intent["equipmentId"] == "P3"
    (series,) = selected.trend_intent["series"]
    assert series["sensorId"] == "P3-" + expected
    assert datetime.fromisoformat(series["end"]) - datetime.fromisoformat(
        series["start"]
    ) == timedelta(days=3)


@pytest.mark.parametrize(
    "short, expected",
    [
        ("흡입", "PI"),
        ("토출", "PO"),
        ("베어링", "TB"),
        ("유체", "TF"),
        ("선간", "ET"),
        ("회전", "S"),
        ("진동 속도", "V"),
    ],
)
async def test_short_sensor_can_be_used_in_the_original_question(tools, short, expected):
    reply = await run_chat_workflow(tools, f"펌프3번 {short} 트렌드 보여줘", {}, {})
    assert reply.trend_intent["equipmentId"] == "P3"
    assert reply.trend_intent["series"][0]["sensorId"] == "P3-" + expected


async def test_pressure_choices_exclude_voltage_and_keep_context_on_unknown_reply(tools):
    reply = await run_chat_workflow(tools, "펌프3 압력", {}, {})
    assert [s["sensor_id"] for s in reply.context["workspace_pending"]["candidates"]] == [
        "P3-PI",
        "P3-PO",
    ]
    unknown = await run_chat_workflow(tools, "없는센서", {}, reply.context)
    assert len(unknown.choices) == 2 and unknown.navigation_href is None
    chosen = await run_chat_workflow(tools, "흡입", {}, unknown.context)
    assert chosen.trend_intent["equipmentId"] == "P3"
    assert chosen.trend_intent["series"][0]["sensorId"] == "P3-PI"
    trend = await run_chat_workflow(tools, "트렌드", {}, chosen.context)
    assert trend.trend_intent["series"][0]["sensorId"] == "P3-PI"


async def test_generic_reply_does_not_arbitrarily_pick_a_sensor(tools):
    reply = await run_chat_workflow(tools, "P3 온도 최근 3일 트렌드 보여줘", {}, {})
    repeated = await run_chat_workflow(tools, "온도", {}, reply.context)
    assert len(repeated.choices) == 2 and repeated.trend_intent is None
    selected = await run_chat_workflow(tools, "2번", {}, repeated.context)
    assert selected.trend_intent["series"][0]["sensorId"] == "P3-TB"


async def test_registered_alias_and_new_sensor_name_need_no_hardcoded_pattern(tools):
    original = tools.get_equipment_sensors

    async def sensors(code):
        return [
            *await original(code),
            {
                "sensor_id": code + "-AUX",
                "measurement_name": "기어박스 윤활유 온도",
                "unit": "°C",
                "aliases": ["윤활센서"],
            },
        ]

    tools.get_equipment_sensors = sensors
    reply = await run_chat_workflow(tools, "P3 온도 최근 3일 트렌드 보여줘", {}, {})
    assert len(reply.choices) == 3
    selected = await run_chat_workflow(tools, "윤활", {}, reply.context)
    assert selected.trend_intent["series"][0]["sensorId"] == "P3-AUX"


async def test_partial_matching_retains_all_possible_candidates(tools):
    rows = await tools.get_equipment_sensors("P3")
    assert {r["sensor_id"] for r in matching_sensor_choices("모터", rows)} == {"P3-I", "P3-ET"}
    assert {r["sensor_id"] for r in matching_sensors(rows, "압력", "pressure")} == {
        "P3-PI",
        "P3-PO",
    }
    assert [r["sensor_id"] for r in matching_sensor_choices("선간", rows)] == ["P3-ET"]
