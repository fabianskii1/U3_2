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

test("Up and Down recall sent messages and restore the current draft without sending", () => {
  for (const content of ["1호기 트렌드", "전류", "펌프3 현황"])
    useChatStore.getState().add({ role: "user", content });
  render(
    <MemoryRouter>
      <ChatPanel
        buildContext={() => {
          throw new Error("No request");
        }}
        onAction={vi.fn()}
      />
    </MemoryRouter>,
  );
  const input = screen.getByLabelText("채팅 메시지");
  fireEvent.change(input, { target: { value: "작성 중" } });
  fireEvent.keyDown(input, { key: "ArrowUp", isComposing: true });
  expect(input).toHaveValue("작성 중");
  fireEvent.keyDown(input, { key: "ArrowUp" });
  expect(input).toHaveValue("펌프3 현황");
  fireEvent.keyDown(input, { key: "ArrowUp" });
  expect(input).toHaveValue("전류");
  fireEvent.keyDown(input, { key: "ArrowDown" });
  expect(input).toHaveValue("펌프3 현황");
  fireEvent.keyDown(input, { key: "ArrowDown" });
  expect(input).toHaveValue("작성 중");
  expect(sendChat).not.toHaveBeenCalled();
});

test("a sole destination opens immediately after the answer", async () => {
  vi.mocked(sendChat).mockResolvedValue({
    message: "내부 목록",
    links: [{ title: "내부 목록", href: "/equip?unit_id=CDU-01" }],
  });
  const onAction = vi.fn().mockResolvedValue(undefined);
  render(
    <MemoryRouter>
      <ChatPanel
        buildContext={(message, sessionId) => ({
          message,
          sessionId,
          screenContext: { page: "/dashboard", equipmentId: null },
        })}
        onAction={onAction}
      />
    </MemoryRouter>,
  );
  fireEvent.change(screen.getByLabelText("채팅 메시지"), {
    target: { value: "1호기" },
  });
  fireEvent.keyDown(screen.getByLabelText("채팅 메시지"), { key: "Enter" });
  await waitFor(() =>
    expect(onAction).toHaveBeenCalledWith(
      expect.objectContaining({
        action: { type: "navigate", href: "/equip?unit_id=CDU-01" },
      }),
    ),
  );
});
