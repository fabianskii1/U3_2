"""Trend reads each current and voltage sensor independently."""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.database import get_session
from app.db import models as m
from app.main import app
from app.modules.alarms.models import setpoint

KST = timezone(timedelta(hours=9))


@pytest.mark.asyncio
async def test_trend_raw_hour_day_and_split_current_voltage_sensors(monkeypatch):
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        db = AsyncSession(bind=connection, expire_on_commit=False)

        async def test_session():
            yield db

        app.dependency_overrides[get_session] = test_session
        try:
            await connection.execute(
                insert(m.plant).values(
                    plant_id="TEST-TREND-PLANT", plant_name="테스트 공장", location="테스트"
                )
            )
            await connection.execute(
                insert(m.equipment_group).values(
                    equipment_group_id="TEST-TREND-GROUP",
                    plant_id="TEST-TREND-PLANT",
                    equipment_group_name="테스트 그룹",
                )
            )
            await connection.execute(
                insert(m.equipment).values(
                    equipment_id="TEST-TREND-PUMP",
                    plant_id="TEST-TREND-PLANT",
                    equipment_group_id="TEST-TREND-GROUP",
                    equipment_name="테스트 펌프",
                    equipment_type="펌프",
                    equipment_status=0,
                    equipment_level=1,
                )
            )
            for sensor_id, name, unit in (
                ("TEST-TREND-TT", "베어링 온도", "°C"),
                ("TEST-TREND-IT", "모터 전류", "A RMS"),
                ("TEST-TREND-ET", "모터 선간전압", "V RMS"),
                ("TEST-TREND-ST", "회전수", "rpm"),
            ):
                await connection.execute(
                    insert(m.sensor).values(
                        sensor_id=sensor_id,
                        equipment_id="TEST-TREND-PUMP",
                        measurement_name=name,
                        unit=unit,
                    )
                )
            for signal_id, sensor_id, name, unit, source in (
                ("TEST-TREND-TT", "TEST-TREND-TT", "베어링 온도", "°C", "bearing_temp_c"),
                ("TEST-TREND-IT", "TEST-TREND-IT", "모터 전류", "A RMS", "motor_current_a"),
                ("TEST-TREND-ET", "TEST-TREND-ET", "모터 선간전압", "V RMS", "voltage_v"),
                ("TEST-TREND-ST", "TEST-TREND-ST", "회전수", "rpm", "motor_rpm"),
            ):
                await connection.execute(
                    insert(m.sensor_signal).values(
                        signal_id=signal_id,
                        sensor_id=sensor_id,
                        measurement_name=name,
                        unit=unit,
                        source_column=source,
                    )
                )
            times = [
                datetime(2026, 1, 1, 23, 59, tzinfo=KST),
                datetime(2026, 1, 2, 0, 0, tzinfo=KST),
                datetime(2026, 1, 2, 0, 1, tzinfo=KST),
            ]
            await connection.execute(
                insert(m.sensor_data_1m),
                [
                    {"signal_id": "TEST-TREND-TT", "measured_at": time, "value": value}
                    for time, value in zip(times, (2.0, 4.0, 6.0), strict=True)
                ]
                + [
                    {"signal_id": signal_id, "measured_at": times[0], "value": value}
                    for signal_id, value in (("TEST-TREND-IT", 10.0), ("TEST-TREND-ET", 380.0))
                ],
            )
            await connection.execute(
                insert(setpoint),
                [
                    {
                        "setpoint_id": "TEST-TREND-FIXED",
                        "equipment_id": "TEST-TREND-PUMP",
                        "sensor_id": "TEST-TREND-TT",
                        "signal_id": "TEST-TREND-TT",
                        "alarm_level": 2,
                        "direction": "HIGH",
                        "operator": ">=",
                        "calculation_type": "FIXED",
                        "parameter": 5.0,
                        "reference": None,
                        "unit": "°C",
                        "filter_minutes": 3,
                        "effective_from": datetime(2026, 1, 1, tzinfo=KST),
                        "effective_to": None,
                    },
                    {
                        "setpoint_id": "TEST-TREND-DYNAMIC",
                        "equipment_id": "TEST-TREND-PUMP",
                        "sensor_id": "TEST-TREND-TT",
                        "signal_id": "TEST-TREND-TT",
                        "alarm_level": 1,
                        "direction": "HIGH",
                        "operator": ">=",
                        "calculation_type": "EXPECTED_OFFSET",
                        "parameter": 10.0,
                        "reference": "E_TB",
                        "unit": "°C",
                        "filter_minutes": 3,
                        "effective_from": datetime(2026, 1, 1, tzinfo=KST),
                        "effective_to": None,
                    },
                ],
            )
            await connection.execute(
                insert(setpoint).values(
                    setpoint_id="TEST-TREND-RPM",
                    equipment_id="TEST-TREND-PUMP",
                    sensor_id="TEST-TREND-ST",
                    signal_id="TEST-TREND-ST",
                    alarm_level=1,
                    direction="LOW",
                    operator="<=",
                    calculation_type="BASELINE_OFFSET",
                    parameter=-5,
                    reference="B_RPM",
                    unit="rpm",
                    filter_minutes=3,
                    effective_from=datetime(2026, 1, 1, tzinfo=KST),
                )
            )

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                params = {
                    "sensor_id": "TEST-TREND-TT",
                    "from": "2026-01-01T23:59:00+09:00",
                    "to": "2026-01-02T00:02:00+09:00",
                }
                raw = (await client.get("/api/trend", params={**params, "interval": "1m"})).json()
                assert [point["value"] for point in raw["points"]] == [2.0, 4.0, 6.0]
                assert raw["signal_id"] == "TEST-TREND-TT"
                assert raw["points"][0]["quality"] is None
                assert {item["setpoint_id"]: item["value"] for item in raw["setpoints"]} == {
                    "TEST-TREND-FIXED": 5.0,
                    "TEST-TREND-DYNAMIC": None,
                }
                rpm_params = {**params, "sensor_id": "TEST-TREND-ST", "interval": "1h"}
                monkeypatch.setattr(get_settings(), "setpoint_reference_values", None)
                unconfigured = await client.get("/api/trend", params=rpm_params)
                assert unconfigured.json()["setpoints"][0]["value"] is None
                monkeypatch.setattr(
                    get_settings(), "setpoint_reference_values", {"TEST-TREND-RPM": 100.0}
                )
                configured = await client.get("/api/trend", params=rpm_params)
                assert configured.json()["setpoints"][0]["value"] == 95

                for interval in ("1h", "1d"):
                    grouped = (
                        await client.get("/api/trend", params={**params, "interval": interval})
                    ).json()
                    assert [point["value"] for point in grouped["points"]] == [2.0, 5.0]
                    assert grouped["points"][1]["time"] == "2026-01-01T15:00:00+00:00"

                current = (
                    await client.get(
                        "/api/trend",
                        params={
                            **params,
                            "sensor_id": "TEST-TREND-IT",
                            "interval": "1m",
                        },
                    )
                ).json()
                assert current["unit"] == "A RMS"
                assert [point["value"] for point in current["points"]] == [10.0]
                voltage = (
                    await client.get(
                        "/api/trend",
                        params={**params, "sensor_id": "TEST-TREND-ET", "interval": "1d"},
                    )
                ).json()
                assert voltage["sensor_id"] == "TEST-TREND-ET"
                assert voltage["signal_id"] == "TEST-TREND-ET"
                assert voltage["unit"] == "V RMS"
                assert [point["value"] for point in voltage["points"]] == [380.0]
                unsupported = await client.get("/api/trend", params={**params, "interval": "1s"})
                assert unsupported.status_code == 400
        finally:
            app.dependency_overrides.clear()
            await db.close()
            await transaction.rollback()
    await engine.dispose()
