from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

import pytest
from skadi_agents.equipment_status import Entity
from skadi_agents.executor import Toolset, run_chat_workflow

AT = "2020-11-19T05:00:00+00:00"
P1 = Entity("equipment", "P1", "1번 펌프", "PLANT-01", "CDU-01")
P2 = Entity("equipment", "P2", "2번 펌프", "PLANT-01", "CDU-01")
SENSOR = "10-VT-1105"


def snapshot(*, status="ok", unknown=0, unscored=0):
    return {
        "as_of": AT,
        "status": status,
        "active_count": 2 if status == "ok" else unscored,
        "affected_equipment_count": 1 if status == "ok" else 0,
        "condition_count": 1 if status == "ok" else 0,
        "unknown_count": unknown,
        "unscored_count": unscored,
        "items": [
            {
                "rank": 1,
                "alarm_id": "15",
                "equipment_id": "P1",
                "sensor_id": SENSOR,
                "has_initial_report": True,
                "equipment_name": P1.name,
                "sensor_name": "진동 속도",
                "alarm_start_time": AT,
                "alarm_level": 2,
                "event_type": "임계치 초과",
                "setpoint_id": "SP-TEST",
                "cof_score": 1.6,
                "reason": "경고 경계",
                "equipment_active_count": 2,
                "prediction_count": 1,
                "threshold_exceeded_count": 1,
                "condition_count": 1,
            }
        ]
        if status == "ok"
        else [],
    }


def make_tools():
    async def resolve(target, **kwargs):
        entity = {"P1": P1, "P2": P2}.get(target)
        return ("found", [entity]) if entity else ("not_found", [])

    return Toolset(
        resolve_entity=AsyncMock(side_effect=resolve),
        lookup_alias=AsyncMock(),
        resolve_plant=AsyncMock(),
        list_plant_units=AsyncMock(),
        load_equipment=AsyncMock(return_value=P1),
        equipment_of_type=AsyncMock(),
        get_equipment_sensors=AsyncMock(
            return_value=[{"sensor_id": SENSOR, "measurement_name": "진동 속도 RMS"}]
        ),
        get_alarm_priorities=AsyncMock(return_value=snapshot()),
        get_alarm=AsyncMock(),
        get_initial_alarm_report=AsyncMock(
            return_value={
                "as_of": AT,
                "message": "저장한 관측 보고서",
                "links": [{"title": "근거", "href": "/equip"}],
            }
        ),
        get_inspection_evidence=AsyncMock(),
    )


async def test_historical_alarm_keeps_report_and_trend_context():
    tools = make_tools()
    reply = await run_chat_workflow(tools, "P1 2020년 11월 19일 14시 기준 알람 순위", {}, {})
    args = tools.get_alarm_priorities.await_args.kwargs
    assert args["equipment_id"] == "P1" and args["group_by"] == "equipment"
    assert args["as_of"].isoformat() == "2020-11-19T14:00:00+09:00"
    assert "임계치 초과" in reply.message and "고유 조건 1개" in reply.message
    assert "alarm_id=15" in reply.links[0]["href"]

    all_ranks = await run_chat_workflow(tools, "전체 순서", {}, reply.context)
    assert tools.get_alarm_priorities.await_args.kwargs["limit"] == 100
    assert all_ranks.context["alarm_as_of"] == AT
    report = await run_chat_workflow(tools, "그 알람 초기 보고서 보여줘", {}, reply.context)
    tools.get_initial_alarm_report.assert_awaited_once_with(P1.id, "15")
    assert "저장한 관측 보고서" in report.message
    trend = await run_chat_workflow(tools, "그 알람의 7일 추이 보여줘", {}, report.context)
    (series,) = trend.trend_intent["series"]
    assert series["sensorId"] == SENSOR
    assert series["end"] == "2020-11-19T14:00:00+09:00"
    assert series["start"] == "2020-11-12T14:00:00+09:00"
    options = await run_chat_workflow(tools, "그 설비 진동 보여줘", {}, report.context)
    assert "2020-11-19 14:00 KST" in options.message
    selected = await run_chat_workflow(tools, "트렌드", {}, options.context)
    assert selected.trend_intent["series"][0]["end"] == series["end"]


async def test_alarm_comparison_and_history_keep_requested_scope():
    tools = make_tools()
    await run_chat_workflow(tools, "P1과 P2 비교", {}, {})
    tools.get_alarm_priorities.assert_awaited_once_with(
        equipment_ids=["P1", "P2"], group_by="equipment", limit=3
    )
    await run_chat_workflow(tools, "개별 알람 순위", {"equipment_id": "P1"}, {})
    assert tools.get_alarm_priorities.await_args.kwargs["group_by"] == "alarm"
    assert tools.get_alarm_priorities.await_args.kwargs["equipment_id"] == "P1"

    history = await run_chat_workflow(tools, "P2 최근 7일 예측 알람 이력", {}, {})
    query = parse_qs(urlsplit(history.links[0]["href"]).query)
    assert query["equip_id"] == ["P2"] and query["event_type"] == ["예측"]
    assert query["from"] < query["to"]
    ambiguous = await run_chat_workflow(tools, "2020년 11월 19일 기준 알람 순위", {}, {})
    assert "날짜와 시각" in ambiguous.message
    assert tools.get_alarm_priorities.await_count == 2


@pytest.mark.parametrize(
    ("status", "phrase", "unknown", "unscored"),
    [
        ("unavailable", "활성 상태 미확인 이력 10건", 10, 0),
        ("unscored", "CoF 미평가 2건", 0, 2),
        ("empty", "활성 Setpoint 알람이 0건", 0, 0),
        ("no_data", "Setpoint 알람 이력이 없습니다", 0, 0),
    ],
)
async def test_alarm_state_replies_do_not_select_a_stale_alarm(status, phrase, unknown, unscored):
    tools = make_tools()
    tools.get_alarm_priorities.return_value = snapshot(
        status=status, unknown=unknown, unscored=unscored
    )
    reply = await run_chat_workflow(
        tools, "알람 순위", {}, {"alarm_id": "old", "equipment_id": "P1"}
    )
    assert phrase in reply.message
    assert "alarm_id" not in reply.context
