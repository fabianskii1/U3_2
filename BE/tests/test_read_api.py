"""Read-contract integration checks; rows are rolled back after each run."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine, get_session
from app.db import models as m
from app.main import app


@pytest.mark.asyncio
async def test_read_contract_with_uncommitted_sample_rows():
    async with engine.connect() as connection:
        transaction = await connection.begin()
        db = AsyncSession(bind=connection, expire_on_commit=False)

        async def test_session():
            yield db

        app.dependency_overrides[get_session] = test_session
        try:
            plant_id = "TEST-PLANT"
            await connection.execute(
                insert(m.plant).values(
                    plant_id=plant_id, plant_name="테스트 공장", location="테스트 위치"
                )
            )
            await connection.execute(
                insert(m.plant_alias).values(plant_id=plant_id, plant_alias_name="별칭 공장")
            )
            unit_id = "TEST-UNIT"
            await connection.execute(
                insert(m.equipment_group).values(
                    equipment_group_id=unit_id,
                    plant_id=plant_id,
                    equipment_group_name="테스트 Unit",
                    process_type="CDU",
                )
            )
            equipment_id = "TEST-PUMP"
            await connection.execute(
                insert(m.equipment).values(
                    equipment_id=equipment_id,
                    plant_id=plant_id,
                    equipment_group_id=unit_id,
                    equipment_name="테스트 펌프",
                    equipment_type="펌프",
                    equipment_status=0,
                    equipment_level=3,
                )
            )
            sensor_id = "TEST-SENSOR"
            await connection.execute(
                insert(m.sensor).values(
                    sensor_id=sensor_id,
                    equipment_id=equipment_id,
                    measurement_name="베어링 진동",
                    unit="mm/s",
                )
            )
            await connection.execute(
                insert(m.sensor_signal).values(
                    signal_id="TEST-SIGNAL",
                    sensor_id=sensor_id,
                    measurement_name="베어링 진동",
                    unit="mm/s",
                    source_column="test_vibration",
                )
            )
            telemetry_at = datetime.now(UTC) - timedelta(minutes=2)
            for minute, value in enumerate((5.1, 5.2)):
                await connection.execute(
                    insert(m.sensor_data_1m).values(
                        signal_id="TEST-SIGNAL",
                        measured_at=telemetry_at + timedelta(minutes=minute),
                        value=value,
                    )
                )
            await connection.execute(
                insert(m.sensor_data_1m).values(
                    signal_id="TEST-SIGNAL",
                    measured_at=telemetry_at + timedelta(days=1),
                    value=99.9,
                )
            )
            occurred_at = datetime(2026, 11, 16, tzinfo=UTC)
            for _ in range(2):
                await connection.execute(
                    insert(m.alarm).values(
                        equipment_id=equipment_id,
                        sensor_id=sensor_id,
                        alarm_type="Setpoint",
                        alarm_start_time=occurred_at,
                        unit="mm/s",
                        alarm_level=3,
                        user_message="진동 위험",
                    )
                )
            report_id = (
                await connection.execute(
                    insert(m.report)
                    .values(
                        equipment_id=equipment_id,
                        equipment_name="테스트 펌프",
                        equipment_group_id=unit_id,
                        equipment_group_name="테스트 Unit",
                        title="점검",
                        symptom="진동",
                        cause="미확인",
                        action="점검 권장",
                        risk="추가 관찰",
                        version=1,
                        created_at=occurred_at,
                        updated_at=occurred_at,
                    )
                    .returning(m.report.c.report_id)
                )
            ).scalar_one()
            await connection.execute(
                insert(m.report_symptoms).values(
                    report_id=report_id,
                    sensor_id=sensor_id,
                    sensor_interval="1h",
                    sensor_start_time=occurred_at,
                    sensor_end_time=occurred_at,
                )
            )

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                hierarchy = (await client.get("/api/hierarchy")).json()
                item = next(
                    e for e in hierarchy["equipment"] if e["equipment_id"] == str(equipment_id)
                )
                assert item["sensors"][0]["sensor_id"] == str(sensor_id)
                assert item["sensors"][0]["measurement_name"] == "베어링 진동"
                assert item["sensors"][0]["current_value"] is None
                plant = next(p for p in hierarchy["plants"] if p["plant_id"] == str(plant_id))
                assert plant["aliases"][0]["plant_alias_name"] == "별칭 공장"
                unit = next(u for u in hierarchy["units"] if u["equipment_group_id"] == unit_id)
                assert unit["process_type"] == "CDU"

                detail = (await client.get(f"/api/equipment/{equipment_id}")).json()
                assert detail["sensors"][0]["current_value"] == 5.2
                assert (
                    detail["sensors"][0]["measured_at"]
                    == (telemetry_at + timedelta(minutes=1)).isoformat()
                )
                assert detail["sensors"][0]["threshold_value"] is None
                trend = (
                    await client.get(
                        "/api/trend",
                        params={
                            "sensor_id": sensor_id,
                            "from": "2026-11-15T00:00:00+09:00",
                            "to": "2026-11-16T00:00:00+09:00",
                            "interval": "1h",
                        },
                    )
                ).json()
                assert trend["points"] == []
                assert trend["unit"] == "mm/s"

                first = (
                    await client.get(
                        "/api/alarms/history",
                        params={
                            "equipment_id": equipment_id,
                            "limit": 1,
                        },
                    )
                ).json()
                assert len(first["items"]) == 1 and first["next_cursor"]
                second = (
                    await client.get(
                        "/api/alarms/history",
                        params={
                            "equipment_id": equipment_id,
                            "limit": 1,
                            "cursor": first["next_cursor"],
                        },
                    )
                ).json()
                assert len(second["items"]) == 1
                assert second["items"][0]["alarm_id"] != first["items"][0]["alarm_id"]

                priority_params = {"equipment_id": equipment_id, "limit": 1}
                unavailable = (
                    await client.get("/api/alarms/priorities", params=priority_params)
                ).json()
                assert unavailable["status"] == "unavailable"
                assert unavailable["unknown_count"] == 2

                for result, level, score in ((first, 1, 80), (second, 4, 40)):
                    await connection.execute(
                        update(m.alarm)
                        .where(m.alarm.c.alarm_id == int(result["items"][0]["alarm_id"]))
                        .values(is_active=True, alarm_level=level, cof_score=score)
                    )
                priorities = (
                    await client.get("/api/alarms/priorities", params=priority_params)
                ).json()
                assert priorities["status"] == "ok"
                assert priorities["active_count"] == 2
                assert priorities["unknown_count"] == priorities["unscored_count"] == 0
                assert len(priorities["items"]) == 1
                assert priorities["items"][0]["alarm_id"] == first["items"][0]["alarm_id"]
                assert priorities["items"][0]["cof_score"] == 80
                assert priorities["items"][0]["rank"] == 1
                assert priorities["affected_equipment_count"] == 1
                assert priorities["condition_count"] == 1
                assert priorities["items"][0]["equipment_active_count"] == 2

                by_alarm = (
                    await client.get(
                        "/api/alarms/priorities",
                        params={"equipment_id": equipment_id, "group_by": "alarm"},
                    )
                ).json()
                assert [row["cof_score"] for row in by_alarm["items"]] == [80, 40]

                await connection.execute(
                    update(m.alarm)
                    .where(m.alarm.c.equipment_id == equipment_id)
                    .values(cof_score=80)
                )
                tied = (await client.get("/api/alarms/priorities", params=priority_params)).json()
                assert tied["items"][0]["alarm_id"] == second["items"][0]["alarm_id"]

                await connection.execute(
                    update(m.alarm)
                    .where(m.alarm.c.equipment_id == equipment_id)
                    .values(cof_score=None)
                )
                unscored = (
                    await client.get("/api/alarms/priorities", params=priority_params)
                ).json()
                assert unscored["status"] == "unscored"
                assert unscored["active_count"] == unscored["unscored_count"] == 2
                assert unscored["items"] == []

                reports = (
                    await client.get(
                        "/api/reports",
                        params={
                            "plant_id": plant_id,
                            "equipment_id": equipment_id,
                        },
                    )
                ).json()
                assert any(r["report_id"] == str(report_id) for r in reports["items"])
                report = (await client.get(f"/api/reports/{report_id}")).json()
                assert report["symptoms"][0]["sensor_id"] == str(sensor_id)
                assert report["suspected_causes"] == []

                bad = await client.get(
                    "/api/trend",
                    params={
                        "sensor_id": sensor_id,
                        "from": "2026-11-16T00:00:00+09:00",
                        "to": "2026-11-15T00:00:00+09:00",
                        "interval": "1h",
                    },
                )
                assert bad.status_code == 400 and bad.json()["code"] == "BAD_REQUEST"
        finally:
            app.dependency_overrides.clear()
            await db.close()
            await transaction.rollback()
