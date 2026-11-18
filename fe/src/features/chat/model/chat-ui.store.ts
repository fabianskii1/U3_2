import { devtoolsOptions } from "../../../shared/lib/devtools.ts";
import { create } from "zustand";
import { devtools, persist } from "zustand/middleware";
export const useChatUiStore = create<{
  open: boolean;
  width: number;
  toggle: () => void;
  setWidth: (width: number) => void;
}>()(
  devtools(
    persist(
      (set) => ({
        open: true,
        width: 300,
        toggle: () => set((s) => ({ open: !s.open })),
        setWidth: (width) =>
          set({ width: Math.max(200, Math.min(520, width)) }),
      }),
      { name: "skadi-chat-ui-v1", version: 1 },
    ),
    {
      ...devtoolsOptions("Chat UI"),
      anonymousActionType: "chat-ui/update",
    },
  ),
);
