import type { Selection, Hierarchy } from "../../features/hierarchy/index.ts";

export function savedTrendSelection(
  view: {
    plantId: string;
    equipmentGroupId: string;
    equipmentId: string | null;
    config: { series: { sensorId: string }[] };
  },
  params = new URLSearchParams(),
): Selection {
  return {
    plantId: view.plantId,
    unitId: view.equipmentGroupId,
    equipmentId: view.equipmentId,
    sensorIds: selectedSensorIds(
      params,
      view.config.series.map((item) => item.sensorId),
      "selected_sensor_id",
    ),
  };
}

function selectedSensorIds(
  params: URLSearchParams,
  available: string[],
  key = "sensor_id",
) {
  const requested = params.has(key) ? params.getAll(key) : available;
  return [...new Set(requested.filter((id) => available.includes(id)))];
}

export function resolveSelection(
  params: URLSearchParams,
  data: Hierarchy,
): Selection {
  const equipment = data.equipment.find((e) => e.id === params.get("equip_id"));
  if (equipment)
    return {
      plantId: equipment.plantId,
      unitId: equipment.unitId,
      equipmentId: equipment.id,
      sensorIds: selectedSensorIds(
        params,
        equipment.tags.map((tag) => tag.id),
      ),
    };
  const unit = data.units.find((u) => u.id === params.get("unit_id"));
  if (unit)
    return {
      plantId: unit.plantId,
      unitId: unit.id,
      equipmentId: null,
      sensorIds: [],
    };
  const plant = data.plants.find((p) => p.id === params.get("plant_id"));
  return {
    plantId: plant?.id ?? null,
    unitId: null,
    equipmentId: null,
    sensorIds: [],
  };
}
export function selectionParams(
  selection: Selection,
  previous?: URLSearchParams,
) {
  const p = new URLSearchParams(previous);
  for (const key of [
    "plant_id",
    "unit_id",
    "equip_id",
    "sensor",
    "sensor_id",
    "selected_sensor_id",
    "viewId",
    "page",
    "section",
    "mode",
    "fault",
    "incident_id",
  ])
    p.delete(key);
  if (selection.plantId) p.set("plant_id", selection.plantId);
  if (selection.unitId) p.set("unit_id", selection.unitId);
  if (selection.equipmentId) p.set("equip_id", selection.equipmentId);
  if (selection.equipmentId) {
    if (selection.sensorIds.length === 0) p.append("sensor_id", "");
    else selection.sensorIds.forEach((id) => p.append("sensor_id", id));
  }
  return p;
}
export function internalHref(href: string) {
  const url = new URL(href, window.location.origin);
  if (
    url.origin !== window.location.origin ||
    !/^\/(dashboard|equip|trend|reports|alarms|incidents)(\/|$)/.test(
      url.pathname,
    )
  )
    throw new Error("지원하지 않는 화면 링크입니다.");
  return url.pathname + url.search;
}
