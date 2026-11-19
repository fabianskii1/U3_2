import { useEffect } from "react";
import {
  useSelectionStore,
  type Selection,
} from "../../features/hierarchy/index.ts";

export function SelectionUrlSync({ selection }: { selection: Selection }) {
  const set = useSelectionStore((s) => s.setSelection);
  const { plantId, unitId, equipmentId, sensorIds } = selection;
  const sensorKey = sensorIds.join("\u0000");
  useEffect(() => {
    set({
      plantId,
      unitId,
      equipmentId,
      sensorIds: sensorKey ? sensorKey.split("\u0000") : [],
    });
  }, [plantId, unitId, equipmentId, sensorKey, set]);
  return null;
}
