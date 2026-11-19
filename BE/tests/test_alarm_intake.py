"""Monitor intake, initial report persistence, and explicit alarm clearing."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import engine, get_session
from app.db import models as m
from app.main import app
from app.modules.alarms.models import setpoint


@pytest.mark.asyncio
async def test_monitor_intake_replays_snapshot_and_closes_alarm(monkeypatch):
    async with engine.connect() as connection:
        transaction = await connection.begin()

        async def test_session():
            async with AsyncSession(
                bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
            ) as session:
                yield session

        monkeypatch.setitem(app.dependency_overrides, get_session, test_session)
        occurred_at = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=1)
        plant_id, group_id = "INTAKE-PLANT", "INTAKE-UNIT"
        equipment_id, sensor_id = "INTAKE-PUMP", "INTAKE-SENSOR"
        fixtures = (
            (m.plant, {"plant_id": plant_id, "plant_name": "수신 테스트", "location": "테스트"}),
            (
                m.equipment_group,
                {"plant_id": plant_id, "equipment_group_id": group_id, "equipment_group_name": "A"},
            ),
            (
                m.equipment,
                {
                    "plant_id": plant_id,
                    "equipment_group_id": group_id,
                    "equipment_id": equipment_id,
                    "equipment_name": "테스트 펌프",
                    "equipment_type": "펌프",
                    "equipment_status": 0,
                    "equipment_level": 1,
                },
            ),
            (
                m.sensor,
                {
                    "equipment_id": equipment_id,
                    "sensor_id": sensor_id,
                    "measurement_name": "진동 속도",
                    "unit": "mm/s",
                },
            ),
            (
                m.sensor_signal,
                {
                    "sensor_id": sensor_id,
                    "signal_id": "INTAKE-SIGNAL",
                    "measurement_name": "진동",
                    "unit": "mm/s",
                    "source_column": "vibration",
                },
            ),
            (
                setpoint,
                {
                    "setpoint_id": "INTAKE-RULE",
                    "equipment_id": equipment_id,
                    "sensor_id": sensor_id,
                    "signal_id": "INTAKE-SIGNAL",
                    "alarm_level": 2,
                    "direction": "HIGH",
                    "operator": ">=",
                    "calculation_type": "FIXED",
                    "parameter": 4.5,
                    "unit": "mm/s",
                    "filter_minutes": 10,
                    "effective_from": occurred_at,
                },
            ),
            (
                m.sensor_data_1m,
                {
                    "signal_id": "INTAKE-SIGNAL",
                    "measured_at": occurred_at - timedelta(hours=2),
                    "value": 4.1,
                },
            ),
        )
        event = {
            "source_event_id": "intake-test-start",
            "equipment_id": equipment_id,
            "sensor_id": sensor_id,
            "alarm_start_time": occurred_at.isoformat(),
            "setpoint_id": "INTAKE-RULE",
            "event_type": "예측",
            "is_active": True,
            "alarm_level": 2,
            "cof_score": 55,
            "unit": "mm/s",
            "user_message": "진동 기준 초과",
        }
        path = "/api/alarms/intake"
        headers = {"Authorization": "Bearer monitor-test-token"}
        try:
            for table, values in fixtures:
                await connection.execute(insert(table).values(**values))
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                monkeypatch.setattr(get_settings(), "alarm_ingest_token", None)
                assert (await client.post(path, json=event, headers=headers)).status_code == 503
                monkeypatch.setattr(
                    get_settings(), "alarm_ingest_token", SecretStr("monitor-test-token")
                )
                assert (await client.post(path, json=event)).status_code == 401
                wrong_sensor = {**event, "sensor_id": "MISSING-SENSOR"}
                assert (
                    await client.post(path, json=wrong_sensor, headers=headers)
                ).status_code == 400

                for overrides, status in (
                    ({"setpoint_id": "MISSING-RULE"}, 400),
                    ({"event_type": None}, 422),
                    ({"alarm_level": 3}, 400),
                    ({"unit": "V"}, 400),
                    ({"cof_score": "NaN"}, 422),
                    ({"alarm_start_time": (occurred_at - timedelta(seconds=1)).isoformat()}, 400),
                ):
                    rejected = await client.post(path, json={**event, **overrides}, headers=headers)
                    assert rejected.status_code == status, rejected.text

                received = await client.post(path, json=event, headers=headers)
                assert received.status_code == 201, received.text
                body = received.json()
                alarm_id = body["alarm"]["alarm_id"]
                report = body["initial_report"]
                assert body["priority"]["selected_alarm_id"] == report["alarm_id"] == alarm_id
                assert f"alarm_id={alarm_id}" in report["links"][0]["href"]
                assert report["trend"]["point_count"] == 1
                assert report["trend"]["min"] == pytest.approx(4.1)
                assert report["setpoint_id"] == "INTAKE-RULE"
                assert report["event_type"] == "예측"
                report_url = f"/api/alarms/{alarm_id}/initial-report"
                assert (await client.get(report_url)).json() == report

                replay = await client.post(path, json=event, headers=headers)
                assert replay.status_code == 200 and replay.json() == body
                changed = {**event, "user_message": "수정된 알람"}
                assert (await client.post(path, json=changed, headers=headers)).status_code == 409
                snapshot = (
                    await client.get("/api/alarms/priorities", params={"plant_id": plant_id})
                ).json()
                assert snapshot["items"][0]["has_initial_report"] is True

                expiry = occurred_at + timedelta(minutes=10)
                await connection.execute(
                    update(setpoint)
                    .where(setpoint.c.setpoint_id == event["setpoint_id"])
                    .values(effective_to=expiry)
                )
                expired = await client.post(
                    path,
                    json={
                        **event,
                        "source_event_id": "intake-test-expired",
                        "alarm_start_time": expiry.isoformat(),
                    },
                    headers=headers,
                )
                assert expired.status_code == 400

                closed = {
                    **event,
                    "source_event_id": "intake-test-close",
                    "closes_source_event_id": event["source_event_id"],
                    "is_active": False,
                    "alarm_start_time": (occurred_at + timedelta(minutes=30)).isoformat(),
                }
                clearing = await client.post(path, json=closed, headers=headers)
                assert clearing.status_code == 201, clearing.text
                cleared = clearing.json()
                assert cleared["closed_alarm_id"] == alarm_id
                assert cleared["priority"]["status"] == "empty"
                assert cleared["initial_report"] is None
                assert (await client.get(report_url)).json() == report
                assert (await client.post(path, json=closed, headers=headers)).json() == cleared

                assert (
                    await client.post(
                        path, json={**closed, "source_event_id": "second-close"}, headers=headers
                    )
                ).status_code == 409

                for instant, status in (
                    (occurred_at - timedelta(seconds=1), "no_data"),
                    (occurred_at, "ok"),
                    (occurred_at + timedelta(minutes=30), "empty"),
                ):
                    historical = await client.get(
                        "/api/alarms/priorities",
                        params={"plant_id": plant_id, "as_of": instant.isoformat()},
                    )
                    assert historical.status_code == 200, historical.text
                    result = historical.json()
                    assert result["status"] == status
                    if status == "ok":
                        assert result["items"][0]["alarm_id"] == alarm_id
                        assert result["items"][0]["is_active"] is True

                history = await client.get(
                    "/api/alarms/history",
                    params={
                        "plant_id": plant_id,
                        "equipment_group_id": group_id,
                        "alarm_level": 2,
                        "event_type": "예측",
                        "from": occurred_at.isoformat(),
                        "to": (occurred_at + timedelta(minutes=30)).isoformat(),
                    },
                )
                assert history.status_code == 200, history.text
                (item,) = history.json()["items"]
                assert item["alarm_id"] == alarm_id and item["is_active"] is False
                assert item["cof_score"] == 55 and item["setpoint_id"] == "INTAKE-RULE"
                assert not {"measured_value", "threshold_value"} & item.keys()

            count = (
                await connection.execute(
                    select(func.count())
                    .select_from(m.alarm)
                    .where(m.alarm.c.equipment_id == equipment_id)
                )
            ).scalar_one()
            assert count == 2
        finally:
            await transaction.rollback()
            await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_intake_replays_one_receipt(monkeypatch):
    suffix = uuid4().hex[:12]
    plant_id, group_id = f"test-plant-{suffix}", f"test-group-{suffix}"
    equipment_id, sensor_id = f"test-eq-{suffix}", f"test-sensor-{suffix}"
    event_id = f"test-concurrent-{suffix}"
    monkeypatch.setattr(get_settings(), "alarm_ingest_token", SecretStr("monitor-test-token"))
    try:
        # Separate sessions must see the same committed fixture to exercise the unique lock.
        async with engine.begin() as conn:
            await conn.execute(
                insert(m.plant).values(plant_id=plant_id, plant_name="test", location="test")
            )
            await conn.execute(
                insert(m.equipment_group).values(
                    plant_id=plant_id, equipment_group_id=group_id, equipment_group_name="test"
                )
            )
            await conn.execute(
                insert(m.equipment).values(
                    equipment_id=equipment_id,
                    plant_id=plant_id,
                    equipment_group_id=group_id,
                    equipment_name="test",
                    equipment_type="펌프",
                    equipment_status=0,
                    equipment_level=1,
                )
            )
            await conn.execute(
                insert(m.sensor).values(
                    sensor_id=sensor_id,
                    equipment_id=equipment_id,
                    measurement_name="test",
                    unit="mm/s",
                )
            )
        event = {
            "source_event_id": event_id,
            "equipment_id": equipment_id,
            "sensor_id": sensor_id,
            "alarm_start_time": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
            "is_active": True,
            "alarm_level": 2,
            "cof_score": 55,
            "unit": "mm/s",
            "user_message": "concurrent test",
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": "Bearer monitor-test-token"}
            first, second = await asyncio.wait_for(
                asyncio.gather(
                    client.post("/api/alarms/intake", json=event, headers=headers),
                    client.post("/api/alarms/intake", json=event, headers=headers),
                ),
                timeout=10,
            )
        assert sorted((first.status_code, second.status_code)) == [200, 201]
        assert first.json() == second.json()
        async with engine.connect() as conn:
            count = await conn.scalar(
                select(func.count())
                .select_from(m.alarm)
                .where(m.alarm.c.source_alarm_id == event_id)
            )
        assert count == 1
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                delete(m.alarm_intake).where(m.alarm_intake.c.source_event_id == event_id)
            )
            await conn.execute(delete(m.alarm).where(m.alarm.c.source_alarm_id == event_id))
            await conn.execute(delete(m.sensor).where(m.sensor.c.sensor_id == sensor_id))
            await conn.execute(
                delete(m.equipment).where(m.equipment.c.equipment_id == equipment_id)
            )
            await conn.execute(
                delete(m.equipment_group).where(m.equipment_group.c.equipment_group_id == group_id)
            )
            await conn.execute(delete(m.plant).where(m.plant.c.plant_id == plant_id))
        await engine.dispose()
