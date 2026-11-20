"""Incident API checks on uncommitted rows that are rolled back after the run."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.database import get_session
from app.db import models as m
from app.main import app

START = datetime(2026, 11, 8, 4, tzinfo=UTC)
END = START + timedelta(days=11)
INC = "INC-T9-202611081300"
OTHER = "INC-T9-202611010000"


async def seed(connection) -> dict:
    await connection.execute(
        insert(m.plant).values(plant_id="T-PLANT", plant_name="테스트 공장", location="X")
    )
    await connection.execute(
        insert(m.equipment_group).values(
            equipment_group_id="T-UNIT",
            plant_id="T-PLANT",
            equipment_group_name="테스트 Unit",
            process_type="CDU",
        )
    )
    await connection.execute(
        insert(m.equipment).values(
            equipment_id="T9",
            plant_id="T-PLANT",
            equipment_group_id="T-UNIT",
            equipment_name="테스트 펌프",
            equipment_type="펌프",
            equipment_status=0,
            equipment_level=3,
        )
    )
    await connection.execute(
        insert(m.sensor).values(
            sensor_id="T9-PD", equipment_id="T9", measurement_name="토출압", unit="kPa"
        )
    )
    await connection.execute(
        insert(m.sensor_signal).values(
            signal_id="T9-PD",
            sensor_id="T9-PD",
            measurement_name="토출압",
            unit="kPa",
            source_column="test_pd",
        )
    )
    types = {}
    for name in ("테스트 임펠러 마모", "테스트 베어링 마모"):
        types[name] = (
            await connection.execute(
                insert(m.error_type)
                .values(error_type_name=name)
                .returning(m.error_type.c.error_type_id)
            )
        ).scalar_one()
    common = {
        "plant_id": "T-PLANT",
        "equipment_group_id": "T-UNIT",
        "equipment_id": "T9",
        "lead_sensor_id": "T9-PD",
        "top_cof": 1.0,
        "top_pof": 0.033,
        "alarm_grade": "낮음",
        "grade_reason": "작음 × 24시간 이상",
        "response_time_h": 203.4,
        "actionable": True,
        "trend_count": 3,
        "source_file": "test.csv",
        "diagnosis_error_type_id": types["테스트 임펠러 마모"],
        "top_risk_error_type_id": types["테스트 임펠러 마모"],
    }
    await connection.execute(
        insert(m.incident).values(
            incident_id=INC,
            incident_start_time=START,
            detect_time=START + timedelta(hours=12),
            first_alarm_time=START + timedelta(days=11, hours=-3),
            incident_end_time=END,
            peak_level=2,
            incident_score=0.4,
            alarm_count=3,
            **common,
        )
    )
    await connection.execute(
        insert(m.incident).values(
            incident_id=OTHER,
            incident_start_time=START - timedelta(days=7),
            detect_time=START - timedelta(days=7),
            incident_end_time=START - timedelta(days=6),
            peak_level=3,
            incident_score=5.0,
            alarm_count=0,
            **{**common, "actionable": False},
        )
    )
    for rank, (name, diagnosis) in enumerate(
        (("테스트 임펠러 마모", True), ("테스트 베어링 마모", False)), start=1
    ):
        await connection.execute(
            insert(m.incident_candidate).values(
                incident_id=INC,
                rank=rank,
                error_type_id=types[name],
                rule_score_s=5.0,
                s_top3_sum=8.0,
                p=0.6,
                speed=1,
                impact=1,
                w=1,
                cof=1.0,
                p_trend=0.0,
                pf_hours=720.0,
                p_pf=0.033,
                pof=0.033,
                score=0.4 if diagnosis else 0.1,
                is_diagnosis=diagnosis,
                is_top_risk=diagnosis,
                evidence="차압 -33 % / 10일 넘게 천천히",
            )
        )
    alarm_ids = []
    for hours, event_type in ((-3, "예측"), (-1, "임계치 초과")):
        alarm_ids.append(
            (
                await connection.execute(
                    insert(m.alarm)
                    .values(
                        equipment_id="T9",
                        sensor_id="T9-PD",
                        alarm_type="Setpoint",
                        event_type=event_type,
                        alarm_start_time=END + timedelta(hours=hours),
                        alarm_end_time=END - timedelta(minutes=1),
                        unit="kPa",
                        alarm_level=2,
                        peak_level=2,
                        cof_score=1.0,
                        incident_id=INC,
                        user_message="토출압 경고",
                    )
                    .returning(m.alarm.c.alarm_id)
                )
            ).scalar_one()
        )
    for minute in range(60):
        await connection.execute(
            insert(m.sensor_data_1m).values(
                signal_id="T9-PD", measured_at=END - timedelta(hours=2, minutes=-minute), value=400
            )
        )
    return {"alarm_ids": alarm_ids}


@pytest.mark.asyncio
async def test_incident_list_detail_draft_and_alarm_links():
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        db = AsyncSession(bind=connection, expire_on_commit=False)

        async def test_session():
            yield db

        app.dependency_overrides[get_session] = test_session
        try:
            seeded = await seed(connection)
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                during = (START + timedelta(days=3)).isoformat()
                listed = await client.get(
                    "/api/incidents", params={"equipment_id": "T9", "as_of": during}
                )
                assert listed.status_code == 200
                items = listed.json()["items"]
                assert [(i["incident_id"], i["status"]) for i in items] == [
                    (INC, "ongoing"),
                    (OTHER, "closed"),
                ]
                assert items[0]["diagnosis"] == "테스트 임펠러 마모"
                assert items[0]["linked_alarm_count"] == 2 and items[0]["alarm_count"] == 3
                for search in ("임펠러", "T9-PD", "토출", "테스트펌프"):
                    searched = await client.get(
                        "/api/incidents", params={"search": search, "as_of": during}
                    )
                    assert searched.status_code == 200
                    assert INC in {item["incident_id"] for item in searched.json()["items"]}
                literal = await client.get(
                    "/api/incidents", params={"search": "%_", "as_of": during}
                )
                assert literal.status_code == 200 and literal.json()["items"] == []

                before = (START - timedelta(days=10)).isoformat()
                hidden = await client.get(
                    "/api/incidents", params={"equipment_id": "T9", "as_of": before}
                )
                assert hidden.json()["items"] == []
                upcoming = await client.get(
                    "/api/incidents",
                    params={"equipment_id": "T9", "as_of": before, "status": "upcoming"},
                )
                assert len(upcoming.json()["items"]) == 2

                filtered = await client.get(
                    "/api/incidents",
                    params={"equipment_id": "T9", "actionable": "false", "as_of": during},
                )
                assert [i["incident_id"] for i in filtered.json()["items"]] == [OTHER]

                first = await client.get(
                    "/api/incidents", params={"equipment_id": "T9", "limit": 1, "as_of": during}
                )
                cursor = first.json()["next_cursor"]
                second = await client.get(
                    "/api/incidents",
                    params={"equipment_id": "T9", "limit": 1, "as_of": during, "cursor": cursor},
                )
                assert second.json()["items"][0]["incident_id"] == OTHER
                assert second.json()["next_cursor"] is None
                bad = await client.get("/api/incidents", params={"cursor": "nope"})
                assert bad.status_code == 400

                after = (END + timedelta(days=1)).isoformat()
                detail = (await client.get(f"/api/incidents/{INC}", params={"as_of": after})).json()
                assert detail["status"] == "closed"
                assert [c["fault"] for c in detail["candidates"]] == [
                    "테스트 임펠러 마모",
                    "테스트 베어링 마모",
                ]
                assert [a["alarm_id"] for a in detail["alarms"]] == [
                    str(i) for i in seeded["alarm_ids"]
                ]
                assert detail["alarms"][0]["sensor_name"] == "토출압"
                assert detail["trend_window"]["signals"][0]["signal_id"] == "T9-PD"
                assert detail["data_coverage"] == "partial"
                assert any("alarm_count(3)" in w for w in detail["warnings"])

                draft = (await client.get(f"/api/incidents/{INC}/report-draft")).json()
                assert "검토 필요" in draft["cause"] and "진단(추정)" in draft["cause"]
                assert draft["action"] == "현장 점검 후 입력"
                assert len(draft["suspected_error_type_ids"]) == 2

                assert (await client.get("/api/incidents/INC-NONE")).status_code == 404
                assert (await client.get("/api/incidents/INC-NONE/report-draft")).status_code == 404

                history = (
                    await client.get("/api/alarms/history", params={"incident_id": INC})
                ).json()["items"]
                assert {a["incident_id"] for a in history} == {INC}
                assert {a["peak_level"] for a in history} == {2}

                trend = (
                    await client.get(
                        "/api/trend",
                        params={
                            "sensor_id": "T9-PD",
                            "from": (END - timedelta(days=1)).isoformat(),
                            "to": END.isoformat(),
                            "interval": "1h",
                        },
                    )
                ).json()
                assert [i["incident_id"] for i in trend["incidents"]] == [INC]

                await connection.execute(
                    update(m.alarm)
                    .where(m.alarm.c.alarm_id == seeded["alarm_ids"][0])
                    .values(is_active=True)
                )
                ranked = (
                    await client.get("/api/alarms/priorities", params={"equipment_id": "T9"})
                ).json()["items"][0]
                assert ranked["incident_id"] == INC
                assert ranked["diagnosis"] == "테스트 임펠러 마모"
                assert ranked["incident_score"] == 0.4

            linked = await connection.scalar(
                select(m.alarm.c.incident_id).where(m.alarm.c.alarm_id == seeded["alarm_ids"][0])
            )
            assert linked == INC
        finally:
            app.dependency_overrides.clear()
            await db.close()
            await transaction.rollback()
    await engine.dispose()
