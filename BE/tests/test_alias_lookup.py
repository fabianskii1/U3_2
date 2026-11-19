"""Registered alias Tool and chat bridge without an external database."""

from types import SimpleNamespace

import pytest
from skadi_agents.executor import run_chat_workflow
from sqlalchemy import create_engine, insert

from app.modules.chat.aliases import lookup_alias
from app.modules.chat.assets import resolve_entity, resolve_plant
from app.modules.chat.execution import run_chat_workflow as execute_chat
from app.modules.equipment import models as e
from app.modules.hierarchy import models as h


class AsyncSqlite:
    def __init__(self, connection):
        self.connection = connection

    async def execute(self, statement):
        return self.connection.execute(statement)


@pytest.mark.asyncio
async def test_registered_aliases_and_chat_selection():
    engine = create_engine("sqlite://")
    tables = (
        h.plant,
        h.plant_alias,
        h.equipment_group,
        h.equipment_group_alias,
        e.equipment,
        e.equipment_alias,
        e.sensor,
        e.sensor_alias,
    )
    h.plant.metadata.create_all(engine, tables=tables)
    with engine.begin() as connection:
        connection.execute(
            insert(h.plant),
            [
                {"plant_id": "PLANT-A", "plant_name": "A 공장", "location": "울산"},
                {"plant_id": "PLANT-B", "plant_name": "B 공장", "location": "서울"},
            ],
        )
        connection.execute(
            insert(h.plant_alias).values(
                plant_alias_id=1, plant_id="PLANT-A", plant_alias_name="울산"
            )
        )
        connection.execute(
            insert(h.equipment_group),
            [
                {
                    "equipment_group_id": "UNIT-A",
                    "plant_id": "PLANT-A",
                    "equipment_group_name": "1호기",
                },
                {
                    "equipment_group_id": "UNIT-B",
                    "plant_id": "PLANT-B",
                    "equipment_group_name": "1호기",
                },
            ],
        )
        connection.execute(
            insert(h.equipment_group_alias).values(
                equipment_group_alias_id=2,
                equipment_group_id="UNIT-A",
                equipment_group_alias_name="CDU 1호기",
            )
        )
        connection.execute(
            insert(e.equipment),
            [
                {
                    "equipment_id": "P1",
                    "plant_id": "PLANT-A",
                    "equipment_group_id": "UNIT-A",
                    "equipment_name": "원유 공급 펌프",
                    "equipment_type": "펌프",
                    "equipment_status": 0,
                    "equipment_level": 1,
                },
                {
                    "equipment_id": "P2",
                    "plant_id": "PLANT-B",
                    "equipment_group_id": "UNIT-B",
                    "equipment_name": "다른 펌프",
                    "equipment_type": "펌프",
                    "equipment_status": 0,
                    "equipment_level": 1,
                },
            ],
        )
        connection.execute(
            insert(e.equipment_alias),
            [
                {
                    "equipment_alias_id": 3,
                    "equipment_id": "P1",
                    "equipment_alias_name": "원유 펌프",
                },
                {
                    "equipment_alias_id": 4,
                    "equipment_id": "P2",
                    "equipment_alias_name": "원유 펌프",
                },
            ],
        )
        connection.execute(
            insert(e.sensor),
            [
                {
                    "sensor_id": "S1",
                    "equipment_id": "P1",
                    "measurement_name": "진동",
                    "unit": "mm/s",
                },
                {
                    "sensor_id": "S2",
                    "equipment_id": "P2",
                    "measurement_name": "진동",
                    "unit": "mm/s",
                },
            ],
        )
        connection.execute(
            insert(e.sensor_alias).values(
                sensor_alias_id=5, sensor_id="S1", sensor_alias_name="베어링 진동"
            )
        )
        db = AsyncSqlite(connection)

        plant = await lookup_alias(db, " 울 산 ", entity_type="plant")
        assert plant["status"] == "found"
        assert plant["candidates"][0]["alias_id"] == "1"
        assert (await resolve_plant(db, "울산"))[1][0].id == "PLANT-A"

        unit = await lookup_alias(db, "CDU 1호기", entity_type="equipment_group")
        assert unit["candidates"][0]["id"] == "UNIT-A"
        assert unit["candidates"][0]["plant_id"] == "PLANT-A"
        assert (await lookup_alias(db, "UNIT-B", entity_type="equipment_group"))["candidates"][0][
            "aliases"
        ] == []

        collision = await lookup_alias(db, "원유 펌프", entity_type="equipment")
        assert collision["status"] == "ambiguous"
        assert {item["id"] for item in collision["candidates"]} == {"P1", "P2"}
        scoped = await lookup_alias(db, "원유 펌프", entity_type="equipment", plant_id="PLANT-A")
        assert scoped["status"] == "found"
        assert scoped["candidates"][0]["id"] == "P1"
        assert (await resolve_entity(db, "원유 펌프", lambda *_: None, {"plant_id": "PLANT-A"}))[1][
            0
        ].id == "P1"

        sensor = await lookup_alias(db, "베어링 진동", entity_type="sensor")
        assert sensor["candidates"][0]["equipment_id"] == "P1"
        assert sensor["candidates"][0]["alias_name"] == "베어링 진동"
        assert (await lookup_alias(db, "진동", entity_type="sensor"))["status"] == "ambiguous"
        assert (await lookup_alias(db, "진동", entity_type="sensor", equipment_id="P1"))[
            "status"
        ] == "found"
        assert (await lookup_alias(db, "missing"))["status"] == "not_found"

        tools = SimpleNamespace(lookup_alias=lambda query, **kw: lookup_alias(db, query, **kw))
        first = await run_chat_workflow(tools, "원유 펌프 별칭 알려줘", {}, {})
        assert len(first.context["pending"]["candidates"]) == 2
        second = await run_chat_workflow(tools, "2번", {}, first.context)
        assert "P2" in second.message and "원유 펌프" in second.message
        assert "pending" not in second.context
        relative = await run_chat_workflow(tools, "이 센서 별칭 알려줘", {"sensor_id": "S1"}, {})
        assert "베어링 진동" in relative.message

        async def unused_lookup(*_):
            raise AssertionError("Exact aliases must not call the model")

        bridged = await execute_chat(db, "P1의 별칭 알려줘", {}, {}, unused_lookup)
        assert "원유 펌프" in bridged.message

        observed = []

        async def model_lookup(query, candidates):
            observed.extend(candidates)
            return {"status": "not_found", "candidates": []}

        await resolve_entity(db, "없는 펌프", model_lookup, {})
        assert {row["equipment_id"] for row in observed} == {"P1", "P2"}
        assert next(row for row in observed if row["equipment_id"] == "P1")["aliases"] == [
            "원유 펌프"
        ]
    engine.dispose()
