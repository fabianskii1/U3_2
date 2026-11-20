"""Bind the AG-03 workflow to the backend's existing DB session and lookup client."""

from functools import partial

from skadi_agents.executor import Reply, Toolset
from skadi_agents.executor import run_chat_workflow as execute_workflow
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.query import serialize
from app.modules.alarms.intake import get_initial_alarm_report
from app.modules.alarms.models import alarm as alarm_table
from app.modules.alarms.priorities import get_alarm_priorities
from app.modules.chat.aliases import lookup_alias
from app.modules.chat.assets import (
    LookupEquipment,
    equipment_for_sensors,
    equipment_of_type,
    get_equipment_sensors,
    list_plant_units,
    load_equipment,
    resolve_entity,
    resolve_plant,
)
from app.modules.chat.evidence import get_inspection_evidence
from app.modules.chat.workspace_data import get_dashboard
from app.modules.equipment.router import equipment_detail
from app.modules.incidents.service import get_incident, list_incidents


async def _saved_alarm(db: AsyncSession, equipment_id: str, alarm_id: object) -> dict | None:
    if (
        not isinstance(alarm_id, str)
        or not alarm_id.isascii()
        or not alarm_id.isdecimal()
        or len(alarm_id) > 19
        or int(alarm_id) >= 2**63
    ):
        return None
    row = (
        (
            await db.execute(
                select(alarm_table).where(
                    alarm_table.c.alarm_id == int(alarm_id),
                    alarm_table.c.equipment_id == equipment_id,
                )
            )
        )
        .mappings()
        .first()
    )
    return serialize(row) if row else None


async def _saved_initial_report(
    db: AsyncSession, equipment_id: str, alarm_id: object
) -> dict | None:
    alarm = await _saved_alarm(db, equipment_id, alarm_id)
    return await get_initial_alarm_report(db, int(alarm["alarm_id"])) if alarm else None


async def run_chat_workflow(
    db: AsyncSession,
    message: str,
    screen: dict[str, object],
    previous: dict,
    lookup_equipment: LookupEquipment,
) -> Reply:
    tools = Toolset(
        lookup_alias=partial(lookup_alias, db),
        resolve_entity=partial(resolve_entity, db, lookup_equipment=lookup_equipment),
        resolve_plant=partial(resolve_plant, db),
        list_plant_units=partial(list_plant_units, db),
        load_equipment=partial(load_equipment, db),
        equipment_of_type=partial(equipment_of_type, db),
        equipment_for_sensors=partial(equipment_for_sensors, db),
        get_equipment_sensors=partial(get_equipment_sensors, db),
        get_alarm_priorities=partial(get_alarm_priorities, db),
        get_alarm=partial(_saved_alarm, db),
        get_initial_alarm_report=partial(_saved_initial_report, db),
        get_inspection_evidence=partial(get_inspection_evidence, db),
        list_incidents=partial(list_incidents, db),
        get_incident=partial(get_incident, db),
        get_dashboard=partial(get_dashboard, db=db),
        get_equipment_readings=partial(equipment_detail, db=db),
    )
    return await execute_workflow(tools, message, screen, previous)
