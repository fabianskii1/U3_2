import { useEffect } from "react";
import {
  useSelectionStore,
  type Selection,
} from "../../features/hierarchy/index.ts";

export function SelectionUrlSync({ selection }: { selection: Selection }) {
  const set = useSelectionStore((s) => s.setSelection);
  const { plantId, unitId, equipmentId } = selection;
  useEffect(() => {
    set({ plantId, unitId, equipmentId });
  }, [plantId, unitId, equipmentId, set]);
  return null;
}
