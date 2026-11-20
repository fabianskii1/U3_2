import type { Message } from "./chat-session.store.ts";

type Shortcut =
  | { type: "navigate"; href: string; title: string }
  | { type: "choose"; message: string; title: string };
export function chatShortcut(
  input: string,
  last?: Message,
): Shortcut | undefined {
  if (!last || last.role !== "assistant") return;
  const text = input.trim();
  const number = /^(\d+)(?:번|번째)?$/.exec(text);
  if (last.choices?.length) {
    const choice =
      text === "" && last.choices.length === 1
        ? last.choices[0]
        : number
          ? last.choices[Number(number[1]) - 1]
          : undefined;
    return choice
      ? { type: "choose", message: choice.message, title: choice.label }
      : undefined;
  }
  const link =
    text === "" && last.links?.length === 1
      ? last.links[0]
      : number
        ? last.links?.[Number(number[1]) - 1]
        : undefined;
  return link
    ? { type: "navigate", href: link.href, title: link.title }
    : undefined;
}
