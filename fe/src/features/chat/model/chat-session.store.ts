import { devtoolsOptions } from "../../../shared/lib/devtools.ts";
import { remoteApi } from "../../../shared/api/be-adapter.ts";
import { create } from "zustand";
import { devtools, persist } from "zustand/middleware";
export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  links?: { title: string; href: string }[];
  choices?: { label: string; message: string }[];
};
export const useChatStore = create<{
  sessionId: string;
  serverSessionId: string | null;
  messages: Message[];
  setServerSessionId: (id: string) => void;
  add: (message: Omit<Message, "id">) => void;
  reset: () => void;
}>()(
  devtools(
    persist(
      (set) => ({
        sessionId: crypto.randomUUID(),
        serverSessionId: null,
        messages: [],
        setServerSessionId: (serverSessionId) => set({ serverSessionId }),
        add: (m) =>
          set((s) => ({
            messages: [...s.messages, { ...m, id: crypto.randomUUID() }].slice(
              -80,
            ),
          })),
        reset: () =>
          set({
            sessionId: crypto.randomUUID(),
            serverSessionId: null,
            messages: [],
          }),
      }),
      {
        name: remoteApi ? "skadi-chat-remote-v1" : "skadi-chat-v1",
        version: 1,
      },
    ),
    {
      ...devtoolsOptions("Chat Session"),
      anonymousActionType: "chat-session/update",
    },
  ),
);
