import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, test, vi } from "vitest";
vi.mock("../api/chat.api.ts", () => ({ sendChat: vi.fn() }));
import { sendChat } from "../api/chat.api.ts";
import { useChatStore } from "../model/chat-session.store.ts";
import { ChatPanel } from "./ChatPanel.tsx";
afterEach(() => {
  cleanup();
  useChatStore.getState().reset();
  vi.clearAllMocks();
});
test("Enter follows the latest single link without an empty chat API request", async () => {
  useChatStore.getState().reset();
  useChatStore.getState().add({
    role: "assistant",
    content: "내부 목록",
    links: [{ title: "내부 설비 목록 열기", href: "/equip?unit_id=CDU-01" }],
  });
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
    configurable: true,
    value: vi.fn(),
  });
  const onAction = vi.fn().mockResolvedValue(undefined);
  render(
    <MemoryRouter>
      <ChatPanel
        buildContext={() => {
          throw new Error("No chat request expected");
        }}
        onAction={onAction}
      />
    </MemoryRouter>,
  );
  const input = screen.getByLabelText("채팅 메시지");
  fireEvent.keyDown(input, { key: "Enter", shiftKey: true });
  fireEvent.keyDown(input, { key: "Enter", isComposing: true });
  fireEvent.keyDown(input, { key: "Enter", keyCode: 229 });
  expect(onAction).not.toHaveBeenCalled();
  fireEvent.keyDown(input, { key: "Enter" });
  await waitFor(() =>
    expect(onAction).toHaveBeenCalledWith({
      message: "",
      action: { type: "navigate", href: "/equip?unit_id=CDU-01" },
    }),
  );
  expect(sendChat).not.toHaveBeenCalled();
});
