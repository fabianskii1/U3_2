import { afterEach, expect, test, vi } from "vitest";
vi.mock("../../../shared/api/be-adapter.ts", () => ({ remoteApi: true }));
import { sendChat } from "./chat.api.ts";
import { useChatStore } from "../model/chat-session.store.ts";

afterEach(() => {
  vi.unstubAllGlobals();
  useChatStore.getState().reset();
});
test("SSE navigation is returned as an executable action after completion", async () => {
  useChatStore.getState().setServerSessionId("123");
  const fetch = vi
    .fn()
    .mockResolvedValue(
      new Response(
        [
          'event: message.delta\ndata: {"text":"P1 현황을 엽니다."}\n\n',
          'event: citation\ndata: {"title":"현황","href":"/equip?equip_id=P1"}\n\n',
          'event: navigate\ndata: {"href":"/equip?equip_id=P1"}\n\n',
          'event: done\ndata: {"session_detail_id":"42"}\n\n',
        ].join(""),
      ),
    );
  vi.stubGlobal("fetch", fetch);
  const response = await sendChat(
    {
      message: "펌프1번 보여줘",
      sessionId: "local",
      screenContext: { page: "/dashboard", equipmentId: null },
    },
    new AbortController().signal,
  );
  expect(response.action).toEqual({
    type: "navigate",
    href: "/equip?equip_id=P1",
  });
  expect(response.links).toHaveLength(1);
  expect(fetch.mock.calls[0][1].credentials).toBe("include");
});
test("an interrupted stream cannot navigate to an incomplete result", async () => {
  useChatStore.getState().setServerSessionId("123");
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response(
          'event: navigate\ndata: {"href":"/trend?viewId=incomplete"}\n\n',
        ),
      ),
  );
  await expect(
    sendChat(
      {
        message: "트렌드",
        sessionId: "local",
        screenContext: { page: "/equip", equipmentId: "P1" },
      },
      new AbortController().signal,
    ),
  ).rejects.toThrow("완료되기 전에");
});

test("pump choice events survive streaming without navigating", async () => {
  useChatStore.getState().setServerSessionId("123");
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response(
          'event: message.delta\ndata: {"text":"어느 펌프를 확인할까요?"}\n\n' +
            'event: choice\ndata: {"label":"P1 · 원유 공급 펌프","message":"1번"}\n\n' +
            'event: choice\ndata: {"label":"P2 · 나프타 제품 이송 펌프","message":"2번"}\n\n' +
            'event: done\ndata: {"session_detail_id":"43"}\n\n',
        ),
      ),
  );
  const result = await sendChat(
    {
      message: "전압 트렌드 보여줘",
      sessionId: "local",
      screenContext: { page: "/equip", equipmentId: "P4" },
    },
    new AbortController().signal,
  );
  expect(result.choices).toEqual([
    { label: "P1 · 원유 공급 펌프", message: "1번" },
    { label: "P2 · 나프타 제품 이송 펌프", message: "2번" },
  ]);
  expect(result.action).toBeUndefined();
});
