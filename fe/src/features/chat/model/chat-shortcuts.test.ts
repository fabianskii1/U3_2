import { expect, test } from "vitest";
import { chatShortcut } from "./chat-shortcuts.ts";
import type { Message } from "./chat-session.store.ts";
const answer: Message = {
  id: "a",
  role: "assistant",
  content: "확인",
  links: [{ title: "내부 설비 목록 열기", href: "/equip?unit_id=CDU-01" }],
};
test("empty Enter opens a single screen link; natural-language input remains a query", () => {
  expect(chatShortcut("", answer)).toMatchObject({
    type: "navigate",
    href: "/equip?unit_id=CDU-01",
  });
  expect(chatShortcut("전류 트렌드", answer)).toBeUndefined();
  expect(chatShortcut("", { ...answer, role: "user" })).toBeUndefined();
});
test("multiple links require an explicit numbered choice", () => {
  const multiple = {
    ...answer,
    links: [...answer.links!, { title: "트렌드", href: "/trend?viewId=abc" }],
  };
  expect(chatShortcut("", multiple)).toBeUndefined();
  expect(chatShortcut("2번", multiple)).toMatchObject({
    type: "navigate",
    href: "/trend?viewId=abc",
  });
  expect(chatShortcut("3번", multiple)).toBeUndefined();
});
test("target choices take precedence over screen links and support all comparison by number", () => {
  const question = {
    ...answer,
    choices: [
      { label: "P1", message: "1번" },
      { label: "전체 펌프 비교", message: "전체 비교" },
    ],
  };
  expect(chatShortcut("", question)).toBeUndefined();
  expect(chatShortcut("2", question)).toMatchObject({
    type: "choose",
    message: "전체 비교",
  });
  expect(
    chatShortcut("", { ...question, choices: [question.choices[0]] }),
  ).toMatchObject({ type: "choose", message: "1번" });
});
