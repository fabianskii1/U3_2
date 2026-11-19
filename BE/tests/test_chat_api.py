"""Chat bridge contract against the local PostgreSQL schema."""

import json
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine, get_session
from app.db import models as m
from app.main import app
from app.modules.chat import router as chat_router


def event_data(stream: str, event_name: str) -> list[dict]:
    prefix = f"event: {event_name}\ndata: "
    return [
        json.loads(frame.removeprefix(prefix))
        for frame in stream.split("\n\n")
        if frame.startswith(prefix)
    ]


@pytest.mark.asyncio
async def test_chat_session_cookie_ai_lookup_and_sse(monkeypatch):
    async def fake_lookup(message: str, candidates: list[dict]):
        assert candidates
        if message == "원유 공급 펌프":
            return {"status": "found", "equipment_id": "P1", "candidates": []}
        assert message == "열교환기 공급 펌프"
        return {
            "status": "not_found",
            "equipment_id": None,
            "candidates": [
                {"equipment_id": "P1"},
                {"equipment_id": "P5"},
                {"equipment_id": "P2"},
            ],
        }

    monkeypatch.setattr(chat_router, "_lookup_equipment", fake_lookup)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        db = AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )

        async def test_session():
            yield db

        app.dependency_overrides[get_session] = test_session
        try:
            await db.execute(
                insert(m.equipment_alias).values(
                    equipment_id="P1", equipment_alias_name="통합 테스트 별칭"
                )
            )
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                created = await client.post("/api/chat/sessions", json={})
                assert created.status_code == 201
                session_id = created.json()["session_id"]
                assert "httponly" in created.headers["set-cookie"].lower()
                response = await client.post(
                    "/api/chat/stream",
                    json={
                        "request_id": str(uuid4()),
                        "session_id": session_id,
                        "message": "원유 공급 펌프",
                        "screen_context": {"page": "/equip"},
                    },
                )
                assert response.status_code == 200
                assert "event: message.delta" in response.text
                assert "P1" in response.text
                assert "event: citation" in response.text
                assert "event: done" in response.text
                alias_reply = await client.post(
                    "/api/chat/stream",
                    json={
                        "request_id": str(uuid4()),
                        "session_id": session_id,
                        "message": "P1의 별칭 알려줘",
                    },
                )
                assert alias_reply.status_code == 200
                assert "통합 테스트 별칭" in event_data(alias_reply.text, "message.delta")[0]["text"]
                messages = await client.get(f"/api/chat/sessions/{session_id}/messages")
                assert [item["role"] for item in messages.json()["items"]] == [
                    "user", "llm", "user", "llm"
                ]

                ranked = await client.post(
                    "/api/chat/stream",
                    json={
                        "request_id": str(uuid4()),
                        "session_id": session_id,
                        "message": "열교환기 공급 펌프",
                    },
                )
                assert ranked.status_code == 200
                assert "1. P1" in ranked.text
                assert "2. P5" in ranked.text
                assert "3. P2" in ranked.text
                assert ranked.text.index("1. P1") < ranked.text.index("2. P5")
                assert "1순위 P1 설비 보기" in ranked.text

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as stranger:
                forbidden = await stranger.get(f"/api/chat/sessions/{session_id}/messages")
                assert forbidden.status_code == 403
        finally:
            app.dependency_overrides.clear()
            await db.close()
            await transaction.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_chat_routes_to_rankings_and_sensor_links_with_followup_context(monkeypatch):
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import insert

    from app.db import models

    lookups = []

    async def fake_lookup(query: str, candidates: list[dict]):
        assert candidates
        lookups.append(query)
        if query == "이송 펌프":
            return {
                "status": "ambiguous",
                "candidates": [{"equipment_id": "P2"}, {"equipment_id": "P3"}],
            }
        pump_aliases = {f"{i}번 펌프": f"P{i}" for i in range(1, 7)}
        assert query in pump_aliases
        return {
            "status": "found",
            "equipment_id": pump_aliases[query],
            "matched_name": query,
            "candidates": [],
        }

    monkeypatch.setattr(chat_router, "_lookup_equipment", fake_lookup)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        db = AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )

        async def test_session():
            yield db

        app.dependency_overrides[get_session] = test_session
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                session_id = (await client.post("/api/chat/sessions", json={})).json()["session_id"]

                async def send(message, **screen):
                    response = await client.post(
                        "/api/chat/stream",
                        json={
                            "request_id": str(uuid4()),
                            "session_id": session_id,
                            "message": message,
                            "screen_context": screen,
                        },
                    )
                    assert response.status_code == 200, response.text
                    return response.text

                weather = await send("오늘 날씨 정보", equipment_id="P2")
                assert "Skadi에서는 설비 현황, 센서 추이, 알람" in weather
                vague = await send("요청")
                assert "어떤 내용을 확인할까요?" in vague
                for reply in (weather, vague):
                    assert event_data(reply, "done")
                    assert not event_data(reply, "citation")
                    assert not event_data(reply, "navigate")

                plant = await send("울산 clx는 몇호기까지 있는지")
                assert "울산CLX 공정은 1개" in plant and "내부 설비 6대" in plant
                assert event_data(plant, "citation")[0]["href"] == "/equip?unit_id=CDU-01"
                assert not event_data(plant, "navigate")
                await db.execute(
                    insert(models.equipment_group).values(
                        equipment_group_id="TEST-CLX-02",
                        plant_id="PLANT-01",
                        equipment_group_name="검증 공정 8호기",
                    )
                )
                changed_plant = await send("울산 CLX에는 공정이 몇 개 있어?")
                assert "울산CLX 공정은 2개" in changed_plant
                assert "검증 공정 8호기 · 내부 설비 0대" in changed_plant
                unknown_plant = await send("파주 CLX가 몇 호기까지 있는지", plant_id="PLANT-01")
                assert "해당하는 플랜트를 찾지 못했습니다" in unknown_plant
                assert not event_data(unknown_plant, "citation")
                assert lookups == []

                assert "event: citation" not in await send("2호기 압축기 진동현황 보여줘")
                unit_href = "/equip?unit_id=CDU-01"
                for query in ("1호기", "CDU 1호기"):
                    reply = await send(query)
                    assert r"상압증류\(CDU\) 1호기" in event_data(reply, "message.delta")[0]["text"]
                    assert event_data(reply, "citation") == [
                        {"title": "내부 설비 목록 열기", "href": unit_href}
                    ]
                unit_status = await send("1호기 내부 펌프 목록 보여줘")
                assert event_data(unit_status, "navigate") == [{"href": unit_href}]
                unit_sensor = await send("1호기 전류")
                assert "펌프를 선택해 주세요" in unit_sensor and unit_href in unit_sensor
                assert not event_data(unit_sensor, "navigate")
                for number in range(2, 7):
                    assert not event_data(await send(f"{number}호기"), "citation")
                    assert not event_data(await send(f"{number}호기 진동 추이"), "citation")
                assert lookups == []
                for number in range(1, 7):
                    sensor_id = f"10-VT-1{number}05"
                    assert f"/equip?equip_id=P{number}&sensor_id={sensor_id}" in await send(
                        f"{number}번 펌프 진동 현황 보여줘"
                    )
                unit_sensor = await send("진동 추이", equipment_group_id="CDU-01")
                assert "펌프를 선택해 주세요" in unit_sensor and unit_href in unit_sensor
                assert not event_data(unit_sensor, "navigate")
                await db.execute(
                    insert(models.sensor).values(
                        sensor_id="TEST-VIB-ACC",
                        equipment_id="P3",
                        measurement_name="진동 가속도",
                        unit="m/s²",
                    )
                )
                rms = await send("진동 현황", equipment_id="P3")
                assert "진동 속도 RMS 현황 열기" in rms
                assert "/equip?equip_id=P3&sensor_id=10-VT-1305" in rms
                assert "TEST-VIB-ACC" not in rms
                (rms_link,) = event_data(rms, "citation")
                assert event_data(rms, "navigate") == [{"href": rms_link["href"]}]

                async def assert_trend(url, expected_sensor, days=7, *, equipment_id="P3"):
                    parsed = urlsplit(url)
                    assert parsed.path == "/trend"
                    params = parse_qs(parsed.query)
                    assert "viewId" in params
                    response = await client.get(f"/api/chat/trend-views/{params['viewId'][0]}")
                    assert response.status_code == 200
                    view = response.json()
                    assert view["equipmentId"] == equipment_id
                    (series,) = view["config"]["series"]
                    assert series["sensorId"] == expected_sensor
                    start = datetime.fromisoformat(series["start"])
                    end = datetime.fromisoformat(series["end"])
                    assert end - start == timedelta(days=days)

                trend = await send("3번 펌프 진동 추이 보여줘", equipment_id="P2")
                assert "진동 속도 RMS 최근 7일 추이 열기" in trend
                (trend_link,) = event_data(trend, "citation")
                await assert_trend(trend_link["href"], "10-VT-1305")
                assert event_data(trend, "navigate") == [{"href": trend_link["href"]}]

                for question, days in (
                    ("p2 진동 트렌드", 7),
                    ("p2 트렌드 진동", 7),
                    ("트렌드 P2 진동", 7),
                    ("P2 트렌드 분석 진동 최근 14일", 14),
                ):
                    trend = await send(question, equipment_id="P3")
                    (trend_link,) = event_data(trend, "citation")
                    await assert_trend(trend_link["href"], "10-VT-1205", days, equipment_id="P2")
                    assert event_data(trend, "navigate") == [{"href": trend_link["href"]}]

                current_href = "/equip?equip_id=P3&sensor_id=10-IT-1304"
                current = await send("3번 펌프 전류", equipment_id="P2")
                assert "모터 전류** 데이터를 볼까요?" in current
                assert not event_data(current, "navigate")
                status_choice, trend_choice = event_data(current, "citation")
                assert status_choice == {"title": "설비 현황 열기", "href": current_href}
                await assert_trend(trend_choice["href"], "10-IT-1304")
                status = await send("설비 현황", equipment_id="P2")
                assert event_data(status, "navigate") == [{"href": current_href}]
                assert (event_data(status, "citation")[0]["href"]) == current_href

                await send("3번 펌프 모터 전류", equipment_id="P2")
                trend = await send("트렌드 분석", equipment_id="P2")
                (trend_link,) = event_data(trend, "citation")
                await assert_trend(trend_link["href"], "10-IT-1304")
                assert event_data(trend, "navigate") == [{"href": trend_link["href"]}]
                assert unit_href in await send("CDU 1호기 상태 보여줘")
                assert '"/alarms"' in await send("알람 관련 데이터 보여줘")
                assert "/equip?equip_id=P2&sensor_id=10-VT-1205" in await send(
                    "2번 펌프의 진동 현황 보여줘"
                )
                choices = await send("이송 펌프 진동 현황 보여줘")
                assert "1. P2" in choices and "2. P3" in choices
                assert "event: citation" not in choices
                assert "/equip?equip_id=P3&sensor_id=10-VT-1305" in await send("두 번째요")
                assert "/alarms?equipment_type=" in await send("펌프 알람관련 데이터 보여줘")
                assert "/alarms?equip_id=P2" in await send("P2 알람 이력 보여줘")

                alarm_ids = []
                measured_at = datetime.now(UTC) - timedelta(seconds=1)
                await db.execute(
                    insert(models.sensor_data_1m).values(
                        signal_id="10-VT-1205", measured_at=measured_at, value=4.7
                    )
                )
                for eq, sensor, score, level in (
                    ("P1", "10-VT-1105", 20, 4),
                    ("P2", "10-VT-1205", 95, 2),
                ):
                    alarm_ids.append(
                        (
                            await db.execute(
                                insert(models.alarm)
                                .values(
                                    equipment_id=eq,
                                    sensor_id=sensor,
                                    cof_score=score,
                                    is_active=True,
                                    alarm_type="Setpoint",
                                    occurred_at=measured_at,
                                    measured_value=7.1,
                                    threshold_value=4.5,
                                    unit="mm/s",
                                    alarm_level=level,
                                    user_message="진동 상한 초과",
                                )
                                .returning(models.alarm.c.alarm_id)
                            )
                        ).scalar_one()
                    )
                await db.commit()

                priority = await send("지금 알람 뭐부터 봐야 해?")
                assert priority.index("CoF **95**") < priority.index("CoF **20**")
                assert (
                    f"/equip?equip_id=P2&sensor_id=10-VT-1205&alarm_id={alarm_ids[1]}" in priority
                )
                assert "진동 상한 초과" in priority
                first = await send("지금 1순위 알람 설비 열어줘")
                assert "CoF **95**" in first and "CoF **20**" not in first
                same_alarm_trend = await send(
                    "그 알람의 7일 추이 보여줘",
                    equipment_id="P2",
                    sensor_id="10-ST-1203",
                )
                (alarm_trend_link,) = event_data(same_alarm_trend, "citation")
                await assert_trend(alarm_trend_link["href"], "10-VT-1205", equipment_id="P2")

                grounded = await send("이걸로 정비 보고서 써줘", equipment_id="P1")
                assert str(alarm_ids[1]) in grounded and "나프타" in grounded
                grounded_from_screen = await send(
                    "이 알람의 정비 보고서 써줘",
                    equipment_id="P1",
                    sensor_id="10-VT-1105",
                    alarm_id=str(alarm_ids[0]),
                )
                assert "원유 공급 펌프" in grounded_from_screen
                detail = await client.get("/api/equipment/P2")
                vibration = next(
                    item for item in detail.json()["sensors"] if item["sensor_id"] == "10-VT-1205"
                )
                assert vibration["current_value"] == 4.7
                assert datetime.fromisoformat(vibration["measured_at"]) == measured_at
        finally:
            app.dependency_overrides.clear()
            await db.close()
            await transaction.rollback()
    await engine.dispose()
