from unittest.mock import AsyncMock

import pytest
from skadi_agents.equipment_status import Entity
from skadi_agents.executor import Toolset, run_chat_workflow
from skadi_agents.reflector import reflect

P1 = Entity("equipment", "P1", "1번 펌프", "PLANT-01", "CDU-01")
P3 = Entity("equipment", "P3", "3번 펌프", "PLANT-01", "CDU-01")
P5 = Entity("equipment", "P5", "5번 펌프", "PLANT-01", "CDU-01")
CDU = Entity("unit", "CDU-01", "CDU", "PLANT-01")
AS_OF = "2026-11-19T05:00:00+00:00"


def candidate(rank, fault, score, diagnosis=False):
    return {
        "rank": rank,
        "fault": fault,
        "score": score,
        "is_diagnosis": diagnosis,
        "is_top_risk": diagnosis,
        "evidence": f"{fault} 근거 / 진동 +2.1",
    }


def detail(incident_id="INC-P1-202611190600", equipment=P1, candidates=None, **extra):
    return {
        "incident_id": incident_id,
        "equipment_id": equipment.id,
        "equipment_name": equipment.name,
        "status": "ongoing",
        "incident_start_time": "2026-11-18T21:00:00+00:00",
        "detect_time": "2026-11-18T23:59:00+00:00",
        "first_alarm_time": "2026-11-19T00:00:00+00:00",
        "incident_end_time": "2026-11-19T13:00:00+00:00",
        "peak_level": 3,
        "lead_sensor_id": "10-VT-1105",
        "lead_sensor_name": "진동",
        "diagnosis": "캐비테이션",
        "top_risk_fault": "캐비테이션",
        "top_cof": 1.67,
        "top_pof": 0.393,
        "incident_score": 7.3,
        "alarm_grade": "낮음",
        "grade_reason": "작음 × 24시간 이상",
        "actionable": True,
        "alarm_count": 1,
        "linked_alarm_count": 1,
        "alarms": [
            {
                "alarm_id": "81",
                "sensor_name": "흡입압",
                "event_type": "예측",
                "alarm_level": 2,
                "peak_level": 3,
                "alarm_start_time": "2026-11-19T01:00:00+00:00",
                "alarm_end_time": "2026-11-19T11:59:00+00:00",
            }
        ],
        "candidates": candidates
        if candidates is not None
        else [
            candidate(1, "캐비테이션", 7.3, True),
            candidate(2, "임펠러 불균형", 0.5),
        ],
        "trend_window": {
            "from": "2026-11-17T21:00:00+00:00",
            "to": "2026-11-19T05:00:00+00:00",
            "signals": [{"sensor_id": "10-VT-1105"}],
        },
        "data_coverage": "full",
        "warnings": [],
        **extra,
    }


def summary(item):
    return {key: item[key] for key in item if key not in {"alarms", "candidates"}}


def make_tools(**overrides):
    async def resolve(target, **kwargs):
        entity = {"P1": P1, "P3": P3, "P5": P5, "CDU": CDU, "CDU-01": CDU}.get(target)
        return ("found", [entity]) if entity else ("not_found", [])

    async def list_incidents(**kwargs):
        if kwargs.get("equipment_id") == "P5":
            return {"as_of": AS_OF, "items": [], "next_cursor": None}
        if kwargs.get("equipment_id") == "P3":
            return {"as_of": AS_OF, "items": [summary(p3)], "next_cursor": None}
        return {"as_of": AS_OF, "items": [summary(p1), summary(p3)], "next_cursor": None}

    p1 = detail()
    p3 = detail(
        "INC-P3-202611081300",
        P3,
        [candidate(1, "임펠러 마모", 0.4, True)],
        diagnosis="임펠러 마모",
        warnings=["분석기 alarm_count(3)와 연결된 알람 수(2)가 다릅니다."],
    )
    details = {p1["incident_id"]: p1, p3["incident_id"]: p3}
    tools = {
        "resolve_entity": AsyncMock(side_effect=resolve),
        "lookup_alias": AsyncMock(),
        "resolve_plant": AsyncMock(),
        "list_plant_units": AsyncMock(),
        "load_equipment": AsyncMock(return_value=P1),
        "equipment_of_type": AsyncMock(),
        "get_equipment_sensors": AsyncMock(),
        "get_alarm_priorities": AsyncMock(),
        "get_alarm": AsyncMock(return_value=None),
        "get_initial_alarm_report": AsyncMock(),
        "get_inspection_evidence": AsyncMock(),
        "list_incidents": AsyncMock(side_effect=list_incidents),
        "get_incident": AsyncMock(side_effect=lambda incident_id, **_: details.get(incident_id)),
    }
    tools.update(overrides)
    return Toolset(**tools)


@pytest.mark.parametrize(
    ("message", "target", "relative", "listing"),
    [
        ("P1 원인 뭐야?", "P1", None, False),
        ("P3 무슨 일이야?", "P3", None, False),
        ("지금 진행 중인 사건 있어?", None, None, True),
        ("이번 달 CDU 사건 목록", "CDU", None, True),
        ("이 알람 왜 떴어?", None, "이알람", False),
    ],
)
def test_incident_questions_are_recognized(message, target, relative, listing):
    request = reflect(message)
    assert (request.intent, request.target, request.relative, request.incident_list) == (
        "incident",
        target,
        relative,
        listing,
    )


def test_existing_intents_are_unchanged():
    assert reflect("P1 알람 우선순위").intent == "alarm_priority"
    assert reflect("P2 진동 트렌드").intent == "trend"
    report = reflect("이 사건으로 보고서 써줘")
    assert (report.intent, report.target) == ("maintenance_draft", None)


@pytest.mark.asyncio
async def test_equipment_cause_explains_latest_incident_as_estimate():
    tools = make_tools()
    reply = await run_chat_workflow(tools, "P1 원인 뭐야?", {}, {})
    tools.list_incidents.assert_awaited_once_with(equipment_id="P1", limit=1)
    assert "진단 **캐비테이션**(추정)" in reply.message
    assert "확정 원인이 아닙니다" in reply.message
    assert "판정 경고 · 최고 도달 위험" in reply.message
    assert "임펠러 불균형 · 점수 0.5" in reply.message
    assert reply.links[0]["href"] == "/incidents/INC-P1-202611190600"
    assert reply.links[1]["href"].startswith("/trend?equip_id=P1&sensor_id=10-VT-1105")
    assert reply.context == {"equipment_id": "P1", "incident_id": "INC-P1-202611190600"}


@pytest.mark.asyncio
async def test_single_candidate_and_warnings_are_disclosed():
    reply = await run_chat_workflow(make_tools(), "P3 무슨 일이야?", {}, {})
    assert "비교할 다른 원인 후보가 없습니다." in reply.message
    assert "주의 · 분석기 alarm\\_count" in reply.message


@pytest.mark.asyncio
async def test_equipment_without_incidents_and_listing():
    tools = make_tools()
    empty = await run_chat_workflow(tools, "P5 원인 뭐야?", {}, {})
    assert "기록된 이상 사건이 없습니다" in empty.message
    listed = await run_chat_workflow(tools, "지금 진행 중인 사건 있어?", {}, {})
    tools.list_incidents.assert_awaited_with(status="ongoing", limit=10)
    assert "**전체 설비 이상 사건**" in listed.message and "2건" in listed.message
    assert [link["href"] for link in listed.links][:2] == [
        "/incidents/INC-P1-202611190600",
        "/incidents/INC-P3-202611081300",
    ]
    none = await run_chat_workflow(tools, "P5 사건 있어?", {}, {})
    assert "해당하는 이상 사건이 없습니다" in none.message


@pytest.mark.asyncio
async def test_alarm_follow_up_uses_linked_incident():
    previous = {"equipment_id": "P1", "alarm_id": "81"}
    tools = make_tools(
        get_alarm=AsyncMock(return_value={"alarm_id": "81", "incident_id": "INC-P1-202611190600"})
    )
    reply = await run_chat_workflow(tools, "이 알람 왜 떴어?", {}, previous)
    tools.get_alarm.assert_awaited_once_with("P1", "81")
    assert "캐비테이션" in reply.message
    assert reply.context["alarm_id"] == "81"

    unlinked = make_tools(get_alarm=AsyncMock(return_value={"alarm_id": "81", "incident_id": None}))
    reply = await run_chat_workflow(unlinked, "이 알람 왜 떴어?", {}, previous)
    assert reply.message == "선택한 알람에 연결된 이상 사건이 없습니다."


@pytest.mark.asyncio
async def test_follow_up_action_question_reuses_incident_context():
    tools = make_tools()
    previous = {"equipment_id": "P1", "incident_id": "INC-P1-202611190600"}
    reply = await run_chat_workflow(tools, "조치해야 돼?", {}, previous)
    assert "조치 필요 예" in reply.message
    tools.list_incidents.assert_not_awaited()


@pytest.mark.asyncio
async def test_priority_adds_diagnosis_without_reordering():
    item = {
        "rank": 1,
        "alarm_id": "81",
        "equipment_id": "P1",
        "sensor_id": "10-VT-1105",
        "has_initial_report": False,
        "equipment_name": P1.name,
        "sensor_name": "진동",
        "alarm_start_time": AS_OF,
        "alarm_level": 2,
        "event_type": "예측",
        "setpoint_id": "SP",
        "cof_score": 1.67,
        "reason": "경고",
        "equipment_active_count": 1,
        "prediction_count": 1,
        "threshold_exceeded_count": 0,
        "condition_count": 1,
        "incident_id": "INC-P1-202611190600",
        "diagnosis": "캐비테이션",
        "incident_score": 7.3,
    }
    snapshot = {
        "as_of": AS_OF,
        "status": "ok",
        "active_count": 1,
        "affected_equipment_count": 1,
        "condition_count": 1,
        "unknown_count": 0,
        "unscored_count": 0,
        "items": [item],
    }
    tools = make_tools(get_alarm_priorities=AsyncMock(return_value=snapshot))
    reply = await run_chat_workflow(tools, "지금 알람 뭐부터 봐야 해?", {}, {})
    assert "CoF **1.67**" in reply.message
    assert "진단(추정) · 캐비테이션 · 사건 점수 7.3 (순위에는 쓰지 않음)" in reply.message
    assert {"title": "1번 펌프 이상 사건 보기", "href": "/incidents/INC-P1-202611190600"} in (
        reply.links
    )
    assert reply.context["incident_id"] == "INC-P1-202611190600"


@pytest.mark.asyncio
async def test_maintenance_draft_uses_incident_candidates_for_review():
    from skadi_agents.inspection_evidence import InspectionEvidence

    evidence = InspectionEvidence(equipment_id="P1", manuals=[], reports=[], maintenance=[])
    tools = make_tools(get_inspection_evidence=AsyncMock(return_value=evidence))
    previous = {"equipment_id": "P1", "incident_id": "INC-P1-202611190600"}
    reply = await run_chat_workflow(tools, "이 사건으로 보고서 써줘", {}, previous)
    assert "검토 필요 · 분석기 후보(추정) 캐비테이션(7.3); 임펠러 불균형(0.5)" in reply.message
    assert "흡입압 예측" in reply.message
    assert reply.links[0]["href"] == "/incidents/INC-P1-202611190600"
