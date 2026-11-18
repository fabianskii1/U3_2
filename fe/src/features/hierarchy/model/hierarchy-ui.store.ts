import { devtoolsOptions } from "../../../shared/lib/devtools.ts";
import { create } from "zustand";
import { devtools, persist } from "zustand/middleware";

export const useHierarchyUiStore = create<{
  open: boolean;
  toggle: () => void;
}>()(
  devtools(
    persist(
      (set) => ({
        open: true,
        toggle: () => set((state) => ({ open: !state.open })),
      }),
      { name: "skadi-hierarchy-ui-v1", version: 1 },
    ),
    {
      ...devtoolsOptions("Hierarchy UI"),
      anonymousActionType: "hierarchy-ui/update",
    },
  ),
);
