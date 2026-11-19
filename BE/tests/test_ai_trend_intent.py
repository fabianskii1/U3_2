"""The chat workflow keeps each requested sensor's own absolute time window."""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from skadi_agents.equipment_status import Entity
from skadi_agents.executor import _multi_trend_reply
from skadi_agents.reflector import reflect


def test_single_sensor_hours_are_kept_as_hours():
    request = reflect("P2 전압 트렌드 최근 24시간 보여줘")
    assert request.intent == "trend"
    assert request.target == "P2"
    assert request.sensor == "전압"
    assert request.hours == 24
    assert request.days is None


def test_anomaly_display_intent_is_separate_from_trend_data():
    request = reflect("P2 전압 트렌드 이상 구간 최근 24시간 보여줘")
    assert request.intent == "trend"
    assert request.target == "P2"
    assert request.sensor == "전압"
    assert request.show_anomalies is True


@pytest.mark.asyncio
async def test_multi_sensor_duration_is_resolved_to_registered_ids():
    async def resolve_entity(target, **kwargs):
        assert target == "2호기 압축기"
        assert kwargs["equipment_only"] is True
        return "found", [Entity("equipment", "P2", "2호기 압축기", "PLANT-01", "CDU-01")]

    async def get_equipment_sensors(equipment_id):
        assert equipment_id == "P2"
        return [
            {"sensor_id": "VIB-01", "measurement_name": "진동 속도 RMS"},
            {"sensor_id": "VOLT-01", "measurement_name": "모터 전압"},
            {"sensor_id": "CURR-01", "measurement_name": "모터 전류"},
        ]

    reply = await _multi_trend_reply(
        SimpleNamespace(
            resolve_entity=resolve_entity,
            get_equipment_sensors=get_equipment_sensors,
        ),
        "2호기 압축기 진동은 최근 7일, 전압과 전류는 최근 24시간 보여줘",
        {},
    )
    assert reply is not None and reply.trend_intent is not None
    intent = reply.trend_intent
    assert intent["equipmentId"] == "P2"
    assert [item["sensorId"] for item in intent["series"]] == ["VIB-01", "VOLT-01", "CURR-01"]
    assert [
        datetime.fromisoformat(item["end"]) - datetime.fromisoformat(item["start"])
        for item in intent["series"]
    ] == [timedelta(days=7), timedelta(hours=24), timedelta(hours=24)]


@pytest.mark.asyncio
async def test_multi_sensor_request_asks_for_ambiguous_registered_sensor():
    async def resolve_entity(*_args, **_kwargs):
        return "found", [Entity("equipment", "P2", "2호기 압축기", "PLANT-01", "CDU-01")]

    async def get_equipment_sensors(*_args):
        return [
            {"sensor_id": "VIB-01", "measurement_name": "진동 속도 RMS"},
            {"sensor_id": "VOLT-01", "measurement_name": "모터 전압"},
            {"sensor_id": "VOLT-02", "measurement_name": "보조 전압"},
            {"sensor_id": "CURR-01", "measurement_name": "모터 전류"},
        ]

    reply = await _multi_trend_reply(
        SimpleNamespace(
            resolve_entity=resolve_entity,
            get_equipment_sensors=get_equipment_sensors,
        ),
        "2호기 압축기 진동은 최근 7일, 전압과 전류는 최근 24시간 보여줘",
        {},
    )
    assert reply is not None and reply.trend_intent is None
    assert "전압 센서를 하나로 확정할 수 없습니다" in reply.message
