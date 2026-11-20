"""Read-only asset hierarchy queries and equipment lookup for the chat workflow."""

import re
from collections.abc import Awaitable, Callable

from skadi_agents.equipment_status import Entity
from skadi_agents.reflector import EQUIPMENT_TYPES, normalize
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.query import all_rows
from app.modules.chat.aliases import lookup_alias
from app.modules.equipment import models as equipment
from app.modules.hierarchy import models as hierarchy

LookupEquipment = Callable[[str, list[dict]], Awaitable[dict[str, object]]]


async def get_equipment_sensors(db: AsyncSession, equipment_id: str) -> list[dict]:
    sensors = await all_rows(
        db,
        select(equipment.sensor)
        .where(equipment.sensor.c.equipment_id == equipment_id)
        .order_by(equipment.sensor.c.sensor_id),
    )
    if not sensors:
        return sensors
    aliases = await all_rows(
        db,
        select(equipment.sensor_alias).where(
            equipment.sensor_alias.c.sensor_id.in_([row["sensor_id"] for row in sensors])
        ),
    )
    by_id = {row["sensor_id"]: row for row in sensors}
    for alias in aliases:
        by_id[alias["sensor_id"]].setdefault("aliases", []).append(alias["sensor_alias_name"])
    return sensors


async def load_equipment(db: AsyncSession, equipment_id: object) -> Entity | None:
    if not isinstance(equipment_id, str) or not equipment_id or len(equipment_id) > 30:
        return None
    row = (
        (
            await db.execute(
                select(equipment.equipment).where(
                    equipment.equipment.c.equipment_id == equipment_id
                )
            )
        )
        .mappings()
        .first()
    )
    return _equipment_entity(row) if row else None


def _equipment_entity(row) -> Entity:
    return Entity(
        "equipment",
        row["equipment_id"],
        row["equipment_name"],
        row["plant_id"],
        row["equipment_group_id"],
        row["equipment_type"],
    )


def _narrow(candidates: list[Entity], screen: dict[str, object]) -> list[Entity]:
    if len(candidates) > 1:
        for key, attr in (("equipment_group_id", "unit_id"), ("plant_id", "plant_id")):
            scope = screen.get(key)
            if not isinstance(scope, str) or not scope:
                continue
            scoped = [entry for entry in candidates if scope == getattr(entry, attr)]
            if scoped:
                candidates = scoped
    return candidates


async def resolve_plant(db: AsyncSession, query: str) -> tuple[str, list[Entity]]:
    """Resolve an exact registered plant ID, name, or alias."""
    result = await lookup_alias(db, query, entity_type="plant")
    matches = [
        Entity("plant", row["id"], row["name"], row["plant_id"]) for row in result["candidates"]
    ]
    return result["status"], matches


async def list_plant_units(db: AsyncSession, plant_id: str) -> list[dict]:
    unit, asset = hierarchy.equipment_group, equipment.equipment
    return await all_rows(
        db,
        select(
            unit.c.equipment_group_id,
            unit.c.equipment_group_name,
            func.count(asset.c.equipment_id).label("equipment_count"),
        )
        .outerjoin(
            asset,
            and_(
                unit.c.equipment_group_id == asset.c.equipment_group_id,
                unit.c.plant_id == asset.c.plant_id,
            ),
        )
        .where(unit.c.plant_id == plant_id)
        .group_by(unit.c.equipment_group_id, unit.c.equipment_group_name)
        .order_by(unit.c.equipment_group_id),
    )


async def resolve_entity(
    db: AsyncSession,
    query: str,
    lookup_equipment: LookupEquipment,
    screen: dict[str, object],
    *,
    equipment_only: bool = False,
) -> tuple[str, list[Entity]]:
    key = normalize(query)
    if not key or len(query) > 200:
        return "not_found", []

    assets = await all_rows(
        db, select(equipment.equipment).order_by(equipment.equipment.c.equipment_id)
    )
    numbered = re.fullmatch(r"펌프0*(\d+)(?:번|호)?|0*(\d+)(?:번|호)펌프", key)
    if numbered:
        code = f"P{int(numbered[1] or numbered[2])}"
        candidates = [
            row for row in assets if row["equipment_id"] == code and row["equipment_type"] == "펌프"
        ]
        if candidates:
            return "found", [_equipment_entity(candidates[0])]
        return "not_found", []
    by_id = {row["equipment_id"]: _equipment_entity(row) for row in assets}
    aliases = await all_rows(db, select(equipment.equipment_alias))
    found = []
    kinds = ("equipment",) if equipment_only else ("plant", "equipment_group", "equipment")
    for kind in kinds:
        result = await lookup_alias(db, query, entity_type=kind)
        found.extend(result["candidates"])
    matches = [
        Entity(
            "unit" if row["entity_type"] == "equipment_group" else row["entity_type"],
            row["id"],
            row["name"],
            row["plant_id"],
            row["equipment_group_id"],
        )
        for row in found
    ]
    numbered_units = []
    if not equipment_only:
        rows = await all_rows(db, select(hierarchy.equipment_group))
        for row in rows:
            code, name = row["equipment_group_id"], row["equipment_group_name"]
            numbered_unit = re.fullmatch(r"\d+호기?", key) and re.search(
                rf"(?<!\d){re.escape(key.rstrip('기'))}기?$", normalize(name)
            )
            if numbered_unit:
                numbered_units.append(Entity("unit", code, name, row["plant_id"], code))
    matches = matches or numbered_units
    if matches:
        matches = _narrow(list(dict.fromkeys(matches)), screen)
        return ("found" if len(matches) == 1 else "ambiguous"), matches

    requested_type = next((kind for kind in EQUIPMENT_TYPES if key.endswith(kind)), None)
    eligible = {
        code: entity
        for code, entity in by_id.items()
        if not requested_type or normalize(entity.equipment_type or "") == requested_type
    }
    if not eligible or re.fullmatch(r"\d+호기?", key):
        return "not_found", []

    aliases_by_equipment: dict[str, list[str]] = {code: [] for code in by_id}
    for alias in aliases:
        if alias["equipment_id"] in aliases_by_equipment:
            aliases_by_equipment[alias["equipment_id"]].append(alias["equipment_alias_name"])
    catalog = [
        {
            "equipment_id": row["equipment_id"],
            "equipment_name": row["equipment_name"],
            "aliases": aliases_by_equipment[row["equipment_id"]],
        }
        for row in assets
    ]
    result = await lookup_equipment(query, catalog)
    status = result.get("status")
    found = result.get("equipment_id")
    if status == "found" and isinstance(found, str) and found in eligible:
        entity = eligible[found]
        number = re.search(r"(?<!\d)(\d+)(?:호기?|번)", key)
        matched_name = result.get("matched_name") or entity.name
        if not number or re.search(
            rf"(?<!\d){number[1]}(?:호기?|번)", normalize(str(matched_name))
        ):
            return "found", [entity]
        return "not_found", []
    candidates = result.get("candidates")
    ids = (
        [item.get("equipment_id") for item in candidates if isinstance(item, dict)]
        if isinstance(candidates, list)
        else []
    )
    resolved = [
        eligible[code]
        for code in dict.fromkeys(code for code in ids if isinstance(code, str))
        if code in eligible
    ]
    if status == "ambiguous":
        scoped = _narrow(resolved, screen)
        if len(scoped) == 1 and len(resolved) > 1:
            return "found", scoped
    return ("ambiguous" if status == "ambiguous" and resolved else "not_found"), resolved


async def equipment_of_type(db: AsyncSession, equipment_type: str) -> list[Entity]:
    rows = await all_rows(
        db,
        select(equipment.equipment)
        .where(equipment.equipment.c.equipment_type == equipment_type)
        .order_by(equipment.equipment.c.equipment_id),
    )
    return [_equipment_entity(row) for row in rows]


async def equipment_for_sensors(db: AsyncSession, sensor_ids: list[str]) -> list[Entity]:
    rows = await all_rows(
        db,
        select(equipment.equipment)
        .join(equipment.sensor)
        .where(equipment.sensor.c.sensor_id.in_(sensor_ids))
        .distinct()
        .order_by(equipment.equipment.c.equipment_id),
    )
    return [_equipment_entity(row) for row in rows]
