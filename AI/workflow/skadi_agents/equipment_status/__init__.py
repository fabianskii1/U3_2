"""SA-01 equipment identity, sensor matching, and navigation links."""

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlencode

from skadi_agents.reflector import SIGNALS, normalize

EntityKind = Literal["equipment", "unit", "plant", "equipment_type"]
URL_KEYS = {
    "equipment": "equip_id",
    "unit": "unit_id",
    "plant": "plant_id",
    "equipment_type": "equipment_type",
}


@dataclass(frozen=True)
class Entity:
    kind: EntityKind
    id: str
    name: str
    plant_id: str | None = None
    unit_id: str | None = None
    equipment_type: str | None = None

    def link(self, path: Literal["/equip", "/alarms", "/trend"], **filters: str) -> str:
        params = {URL_KEYS[self.kind]: self.id, **filters}
        return f"{path}?{urlencode(params)}"

    def alarm_scope(self) -> dict[str, str]:
        key = {
            "equipment": "equipment_id",
            "unit": "equipment_group_id",
            "plant": "plant_id",
            "equipment_type": "equipment_type",
        }[self.kind]
        return {key: self.id}


def matching_sensors(rows: list[dict], query: str, signal: str | None) -> list[dict]:
    key = normalize(query)
    exact = [
        row
        for row in rows
        if key
        in {
            normalize(value)
            for value in (row["sensor_id"], row["measurement_name"], *row.get("aliases", []))
        }
    ]
    if exact:
        return exact
    if signal is None:
        return []
    candidates = [
        row
        for row in rows
        if key in normalize(row["measurement_name"])
        or any(key in normalize(alias) for alias in row.get("aliases", []))
    ]
    if candidates or signal != "vibration":
        return candidates
    if key in {"베어링진동", "모터진동", "축진동"}:
        location = key.removesuffix("진동")
        return [
            row
            for row in rows
            if "진동" in row["measurement_name"]
            and location in normalize(row.get("installation_location") or "")
        ]
    return []


def sensor_signal(name: str) -> str | None:
    if "흡입압" in name or "토출압" in name:
        return "pressure"
    return next((value for key, value in SIGNALS.items() if key in name), None)
