"""AG-02 Action Planner for selecting the approved tools for a request."""

from dataclasses import dataclass
from typing import Literal

from ..reflector import EQUIPMENT_TYPES, Reflection, normalize


@dataclass(frozen=True)
class ActionPlan:
    request: Reflection
    tools: tuple[str, ...]
    target_kind: Literal["entity", "equipment_type"] = "entity"


def plan(reflection: Reflection) -> ActionPlan:
    """Restrict each intent to its own fixed tool sequence."""
    tools = {
        "alias_lookup": ("lookup_alias",),
        "equipment_lookup": ("resolve_entity",),
        "equipment_status": ("resolve_entity", "get_equipment_sensors", "build_link"),
        "sensor_options": ("resolve_entity", "get_equipment_sensors", "build_link"),
        "alarm_history": ("resolve_entity", "build_link"),
        "alarm_priority": ("resolve_entity", "get_alarm_priorities"),
        "trend": ("resolve_entity", "get_equipment_sensors", "build_link"),
        "inspection_evidence": ("resolve_entity", "get_inspection_evidence"),
        "maintenance_draft": (
            "resolve_entity",
            "get_inspection_evidence",
            "build_maintenance_draft",
        ),
        "out_of_scope": (),
        "clarify": (),
        "plant_units": ("resolve_plant", "list_plant_units"),
    }
    target_kind = (
        "equipment_type"
        if reflection.target and normalize(reflection.target) in EQUIPMENT_TYPES
        else "entity"
    )
    return ActionPlan(reflection, tools[reflection.intent], target_kind)
