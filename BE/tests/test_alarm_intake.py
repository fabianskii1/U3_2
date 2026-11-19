"""Monitor intake, initial report persistence, and explicit alarm clearing."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import engine, get_session
from app.db import models as m
from app.main import app


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

                received = await client.post(path, json=event, headers=headers)
                assert received.status_code == 201, received.text
                body = received.json()
                alarm_id = body["alarm"]["alarm_id"]
                report = body["initial_report"]
                assert body["priority"]["selected_alarm_id"] == report["alarm_id"] == alarm_id
                assert f"alarm_id={alarm_id}" in report["links"][0]["href"]
                assert report["trend"]["point_count"] == 1
                assert report["trend"]["min"] == pytest.approx(4.1)
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
