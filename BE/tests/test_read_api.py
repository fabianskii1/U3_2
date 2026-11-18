"""Read-contract integration checks; rows are rolled back after each run."""

from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert
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
            occurred_at = datetime(2026, 11, 16, tzinfo=UTC)
            for value in (5.1, 5.2):
                await connection.execute(
                    insert(m.alarm).values(
                        equipment_id=equipment_id,
                        sensor_id=sensor_id,
                        alarm_type="Setpoint",
                        occurred_at=occurred_at,
                        measured_value=value,
                        threshold_value=4.5,
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

                detail = (await client.get(f"/api/equipment/{equipment_id}")).json()
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
