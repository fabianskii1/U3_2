import { devtoolsOptions } from "../../../shared/lib/devtools.ts";
import { create } from "zustand";
import { devtools } from "zustand/middleware";
import type { Selection } from "./hierarchy.schema.ts";
export const useSelectionStore = create<
  Selection & { setSelection: (next: Selection) => void }
>()(
  devtools(
    (set) => ({
      plantId: null,
      unitId: null,
      equipmentId: null,
      sensorIds: [],
      setSelection: (next) => set(next, false, "selection/set"),
    }),
    devtoolsOptions("Selection"),
  ),
);
