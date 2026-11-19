"""Read current registered names and aliases for chat identity resolution."""

from typing import Literal

from skadi_agents.reflector import normalize
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.query import all_rows
from app.modules.equipment import models as equipment
from app.modules.hierarchy import models as hierarchy

EntityType = Literal["plant", "equipment_group", "equipment", "sensor"]


async def lookup_alias(
    db: AsyncSession,
    query: str,
    *,
    entity_type: EntityType | None = None,
    plant_id: str | None = None,
    equipment_group_id: str | None = None,
    equipment_id: str | None = None,
) -> dict:
    """Match an ID, registered name, or alias without guessing between entities."""
    key = normalize(query)
    if not key or len(query) > 200:
        return {"status": "not_found", "candidates": []}

    p, pa = hierarchy.plant, hierarchy.plant_alias
    g, ga = hierarchy.equipment_group, hierarchy.equipment_group_alias
    e, ea = equipment.equipment, equipment.equipment_alias
    s, sa = equipment.sensor, equipment.sensor_alias
    statements = {
        "plant": select(
            p.c.plant_id.label("id"),
            p.c.plant_name.label("name"),
            p.c.plant_id,
            pa.c.plant_alias_id.label("alias_id"),
            pa.c.plant_alias_name.label("alias_name"),
        )
        .select_from(p.outerjoin(pa))
        .where(*([p.c.plant_id == plant_id] if plant_id else [])),
        "equipment_group": select(
            g.c.equipment_group_id.label("id"),
            g.c.equipment_group_name.label("name"),
            g.c.plant_id,
            g.c.equipment_group_id,
            ga.c.equipment_group_alias_id.label("alias_id"),
            ga.c.equipment_group_alias_name.label("alias_name"),
        )
        .select_from(g.outerjoin(ga))
        .where(
            *([g.c.plant_id == plant_id] if plant_id else []),
            *([g.c.equipment_group_id == equipment_group_id] if equipment_group_id else []),
        ),
        "equipment": select(
            e.c.equipment_id.label("id"),
            e.c.equipment_name.label("name"),
            e.c.plant_id,
            e.c.equipment_group_id,
            e.c.equipment_id,
            ea.c.equipment_alias_id.label("alias_id"),
            ea.c.equipment_alias_name.label("alias_name"),
        )
        .select_from(e.outerjoin(ea))
        .where(
            *([e.c.plant_id == plant_id] if plant_id else []),
            *([e.c.equipment_group_id == equipment_group_id] if equipment_group_id else []),
            *([e.c.equipment_id == equipment_id] if equipment_id else []),
        ),
        "sensor": select(
            s.c.sensor_id.label("id"),
            s.c.measurement_name.label("name"),
            e.c.plant_id,
            e.c.equipment_group_id,
            s.c.equipment_id,
            sa.c.sensor_alias_id.label("alias_id"),
            sa.c.sensor_alias_name.label("alias_name"),
        )
        .select_from(s.join(e, s.c.equipment_id == e.c.equipment_id).outerjoin(sa))
        .where(
            *([e.c.plant_id == plant_id] if plant_id else []),
            *([e.c.equipment_group_id == equipment_group_id] if equipment_group_id else []),
            *([s.c.equipment_id == equipment_id] if equipment_id else []),
        ),
    }
    candidates = []
    for kind in (entity_type,) if entity_type else tuple(statements):
        by_id = {}
        for row in await all_rows(db, statements[kind]):
            item = by_id.setdefault(
                row["id"],
                {
                    "entity_type": kind,
                    "id": row["id"],
                    "name": row["name"],
                    "plant_id": row["plant_id"],
                    "equipment_group_id": row.get("equipment_group_id"),
                    "equipment_id": row.get("equipment_id"),
                    "aliases": [],
                },
            )
            if row["alias_id"] is not None:
                item["aliases"].append(
                    {"alias_id": row["alias_id"], "alias_name": row["alias_name"]}
                )
        for item in by_id.values():
            matched_alias = next(
                (alias for alias in item["aliases"] if normalize(alias["alias_name"]) == key), None
            )
            if normalize(item["id"]) == key:
                matched_by = "id"
            elif normalize(item["name"]) == key:
                matched_by = "name"
            elif matched_alias:
                matched_by = "alias"
            else:
                continue
            item.update(
                matched_by=matched_by,
                alias_id=matched_alias["alias_id"] if matched_by == "alias" else None,
                alias_name=matched_alias["alias_name"] if matched_by == "alias" else None,
            )
            item["aliases"].sort(key=lambda alias: int(alias["alias_id"]))
            candidates.append(item)
    candidates.sort(key=lambda item: (item["entity_type"], item["id"]))
    return {
        "status": "not_found"
        if not candidates
        else "found"
        if len(candidates) == 1
        else "ambiguous",
        "candidates": candidates,
    }
