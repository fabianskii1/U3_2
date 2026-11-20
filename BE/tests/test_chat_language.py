"""Spelling variations preserve monitoring intent, targets and query conditions."""

from datetime import datetime, timedelta

import pytest
from skadi_agents.executor import run_chat_workflow
from skadi_agents.language import normalize_request
from skadi_agents.reflector import reflect
from test_chat_workspace import named_tools, tools

__all__ = ["named_tools", "tools"]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("온도 트랜드 보여줘", "온도 트렌드 보여줘"),
        ("대쉬보드 보여죠", "대시보드 보여줘"),
        ("데시보드 보여조", "대시보드 보여줘"),
        ("설비 현항 보여쥐", "설비 현황 보여줘"),
        ("설피 현왕 보여저", "설비 현황 보여줘"),
        ("진둥 트랜트 보여조", "진동 트렌드 보여줘"),
        ("진덩 트렌데 보야줘", "진동 트렌드 보여줘"),
        ("베아링 온두 트렌트 보여줘", "베어링 온도 트렌드 보여줘"),
        ("배어링 온됴", "베어링 온도"),
        ("전루 트랜드", "전류 트렌드"),
        ("전앞 추세", "전압 트렌드"),
        ("회전 속도 차트", "회전수 차트"),
        ("회전슈 챠트", "회전수 트렌드"),
        ("흡입 압력 보여줘", "흡입압 보여줘"),
        ("토출압녁 알려조", "토출압 알려줘"),
        ("펌푸4번 진둥 보여죠", "펌프4번 진동 보여줘"),
        ("진동 트렌드 좀 보여줘요", "진동 트렌드 보여줘"),
        ("대 쉬 보드 보여 주세요", "대시보드 보여줘"),
        ("온 도 트 랜 드 보 여 줘", "온도 트렌드 보여줘"),
        ("P4 vibration trend 보여줘", "P4 진동 트렌드 보여줘"),
    ],
)
def test_known_variants_and_single_key_typos(text, expected):
    assert normalize_request(text) == expected
    assert normalize_request(expected) == expected


def test_never_changes_sensor_identity_dates_or_numbers():
    text = "P4 10-IT-1404 10-RPM-1403 전압 전류 온도 2026-11-10 2026-11-15 최근 3일 1분 간격"
    assert normalize_request(text) == text
    assert normalize_request("P1 P2 2번 7번 0일 91일") == "P1 P2 2번 7번 0일 91일"


@pytest.mark.parametrize("message", ["대쉬보드 보여죠", "데시보드 보여쥐", "대 쉬 보드 열어주라"])
async def test_dashboard_typos_navigate(tools, message):
    reply = await run_chat_workflow(tools, message, {"page": "/equip"}, {})
    assert reply.navigation_href == "/dashboard"


@pytest.mark.parametrize("message", ["설비 현항 보여쥐", "현왕 보여조", "설피 현황 열어줘", "설비 상태 보여줘", "상태 보여줘"])
async def test_equipment_page_typos_navigate_without_an_asset(tools, message):
    reply = await run_chat_workflow(tools, message, {"page": "/dashboard"}, {})
    assert reply.navigation_href == "/equip"


@pytest.mark.parametrize(
    "sensor, expected",
    [
        ("진둥", "V"),
        ("온두", "TB"),
        ("전루", "I"),
        ("전앞", "ET"),
        ("회전 속도", "S"),
        ("흡입압녁", "PI"),
        ("토출압녁", "PO"),
        ("베아링온두", "TB"),
    ],
)
async def test_all_sensor_variants_keep_pump_selection_and_period(tools, sensor, expected):
    reply = await run_chat_workflow(
        tools, f"{sensor} 최근 3일 트랜드 보여조", {"equipment_id": "P1"}, {}
    )
    assert len(reply.choices) == 7 and reply.navigation_href is None
    reply = await run_chat_workflow(tools, "펌푸4번", {}, reply.context)
    if reply.trend_intent is None:
        reply = await run_chat_workflow(tools, "베아링온두", {}, reply.context)
    assert reply.trend_intent["equipmentId"] == "P4"
    (series,) = reply.trend_intent["series"]
    assert series["sensorId"] == "P4-" + expected
    assert datetime.fromisoformat(series["end"]) - datetime.fromisoformat(
        series["start"]
    ) == timedelta(days=3)


@pytest.mark.parametrize("misspelled, expected", [("경유 츠류", "P4"), ("나푸타", "P2")])
async def test_uncertain_equipment_spelling_is_confirmed_before_navigation(
    named_tools, misspelled, expected
):
    reply = await run_chat_workflow(named_tools, "진둥 최근 3일 트랜드 보여줘", {}, {})
    suggested = await run_chat_workflow(named_tools, misspelled, {}, reply.context)
    assert suggested.navigation_href is None and suggested.trend_intent is None
    assert len(suggested.choices) == 1
    assert suggested.context["workspace_pending"]["candidates"][0]["id"] == expected
    confirmed = await run_chat_workflow(named_tools, "1번", {}, suggested.context)
    assert confirmed.trend_intent["equipmentId"] == expected


async def test_spelling_suggestion_retains_multiple_candidates(named_tools):
    reply = await run_chat_workflow(named_tools, "전루 트랜드 보여줘", {}, {})
    reply = await run_chat_workflow(named_tools, "측루", {}, reply.context)
    assert reply.navigation_href is None and reply.trend_intent is None
    assert [c["id"] for c in reply.context["workspace_pending"]["candidates"]] == ["P3", "P4"]


def test_reflector_and_followup_support_common_spelling():
    request = reflect("P4 전루 최근 3일 트랜드 보여죠")
    assert request.intent == "trend" and request.target == "P4"
    assert request.signal == "current" and request.days == 3
