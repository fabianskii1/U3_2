import type { Selection, Hierarchy } from "../../features/hierarchy/index.ts";

export function savedTrendSelection(view: {
  plantId: string;
  equipmentGroupId: string;
  equipmentId: string | null;
}): Selection {
  return {
    plantId: view.plantId,
    unitId: view.equipmentGroupId,
    equipmentId: view.equipmentId,
  };
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
    };
  const unit = data.units.find((u) => u.id === params.get("unit_id"));
  if (unit)
    return { plantId: unit.plantId, unitId: unit.id, equipmentId: null };
  const plant = data.plants.find((p) => p.id === params.get("plant_id"));
  return { plantId: plant?.id ?? null, unitId: null, equipmentId: null };
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
    "viewId",
    "page",
  ])
    p.delete(key);
  if (selection.plantId) p.set("plant_id", selection.plantId);
  if (selection.unitId) p.set("unit_id", selection.unitId);
  if (selection.equipmentId) p.set("equip_id", selection.equipmentId);
  return p;
}
export function internalHref(href: string) {
  const url = new URL(href, window.location.origin);
  if (
    url.origin !== window.location.origin ||
    !/^\/(dashboard|equip|trend|reports|alarms)(\/|$)/.test(url.pathname)
  )
    throw new Error("지원하지 않는 화면 링크입니다.");
  return url.pathname + url.search;
}
