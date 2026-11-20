import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import ReactMarkdown from "react-markdown";
import {
  ArrowUp,
  ArrowUpRight,
  Sparkles,
  RotateCcw,
  Square,
  MessageSquare,
  FilePenLine,
} from "lucide-react";
import { useChatStore } from "../model/chat-session.store.ts";
import { chatShortcut } from "../model/chat-shortcuts.ts";
import { sendChat } from "../api/chat.api.ts";
import type { ChatRequest, ChatResponse } from "../model/chat.schema.ts";
import { Button } from "../../../shared/ui/button.tsx";
import { Textarea } from "../../../shared/ui/textarea.tsx";
import { errorMessage } from "../../../shared/api/http-client.ts";
import { remoteApi } from "../../../shared/api/be-adapter.ts";
export function ChatPanel({
  buildContext,
  onAction,
  reportTitle,
}: {
  buildContext: (message: string, sessionId: string) => ChatRequest;
  onAction: (response: ChatResponse) => Promise<void>;
  reportTitle?: string;
}) {
  const messages = useChatStore((s) => s.messages);
  const add = useChatStore((s) => s.add);
  const reset = useChatStore((s) => s.reset);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [streamText, setStreamText] = useState("");
  const controller = useRef<AbortController | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const historyIndex = useRef<number | null>(null);
  const historyDraft = useRef("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [messages.length, pending]);
  useEffect(() => () => controller.current?.abort(), []);
  const lastMessage = messages.at(-1);
  const defaultShortcut = chatShortcut("", lastMessage);
  const send = async (text = input) => {
    if (pending || (controller.current && !controller.current.signal.aborted))
      return;
    const shortcut = chatShortcut(
      text,
      useChatStore.getState().messages.at(-1),
    );
    if (shortcut?.type === "navigate") {
      try {
        await onAction({
          message: "",
          action: { type: "navigate", href: shortcut.href },
        });
        setInput("");
      } catch (error) {
        add({
          role: "assistant",
          content: `이동하지 못했습니다. ${errorMessage(error)}`,
        });
      }
      return;
    }
    if (shortcut?.type === "choose") text = shortcut.message;
    if (
      !text.trim() ||
      pending ||
      (controller.current && !controller.current.signal.aborted)
    )
      return;
    const abort = new AbortController();
    controller.current = abort;
    setPending(true);
    setStreamText("");
    setInput("");
    historyIndex.current = null;
    historyDraft.current = "";
    add({ role: "user", content: text });
    try {
      const context = buildContext(text, useChatStore.getState().sessionId);
      const result = await sendChat(context, abort.signal, setStreamText);
      if (abort.signal.aborted) return;
      const resolved =
        !result.action && !result.choices?.length && result.links?.length === 1
          ? {
              ...result,
              action: { type: "navigate" as const, href: result.links[0].href },
            }
          : result;
      await onAction(resolved);
      add({
        role: "assistant",
        content:
          result.action?.type === "save-draft"
            ? "보고서 저장이 완료되었습니다."
            : result.message,
        links: result.links,
        choices: result.choices,
      });
    } catch (error) {
      if (!abort.signal.aborted)
        add({
          role: "assistant",
          content: `요청을 완료하지 못했습니다. ${errorMessage(error)}`,
        });
    } finally {
      setStreamText("");
      if (controller.current === abort) {
        setPending(false);
        controller.current = null;
      }
    }
  };
  return (
    <>
      <div className="chat-header">
        <div className="chat-icon">
          <Sparkles size={16} />
        </div>
        <div>
          <strong>Skadi Assistant</strong>
          <small>현장을 이해하는 업무 파트너</small>
        </div>
      </div>
      <div className="chat-mode">
        <span className="status-dot" />
        {remoteApi
          ? "설비 조회 · 화면 이동 연결됨"
          : "규칙 기반 Mock 응답 · 실제 AI 미연결"}
      </div>
      {reportTitle ? (
        <div className="chat-report-context">
          <FilePenLine size={14} />
          <span title={reportTitle}>편집 대상 · {reportTitle}</span>
        </div>
      ) : null}
      <div
        className="chat-messages"
        aria-label="대화 메시지"
        aria-busy={pending}
      >
        {!messages.length ? (
          <div className="chat-welcome">
            <div className="welcome-symbol">
              <Sparkles size={26} />
            </div>
            <span className="eyebrow">YOUR OPERATION PARTNER</span>
            <h2>무엇을 도와드릴까요?</h2>
            <p>
              알람 확인부터 보고서 작성까지,
              <br />
              설비 업무를 함께 정리해 보세요.
            </p>
            <div className="suggestions">
              {(remoteApi
                ? [
                    "대시보드 상황 알려줘",
                    "펌프1번 현황 보여줘",
                    "펌프1번 전류 최근 3일 트렌드 보여줘",
                  ]
                : [
                    "지금 알람 뭐부터 봐야 해?",
                    "원유 공급 펌프 A 진동 현황 보여줘",
                    "보고서 초안 생성해줘",
                  ]
              ).map((text) => (
                <button key={text} onClick={() => void send(text)}>
                  <MessageSquare size={14} />
                  <span>{text}</span>
                  <ArrowUpRight size={13} />
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m) => (
            <div key={m.id} className={`chat-message message-${m.role}`}>
              <span className="message-role">
                {m.role === "user" ? "나" : "SKADI"}
              </span>
              <div className="message-body">
                <ReactMarkdown
                  components={{
                    a: ({ href, children }) =>
                      href?.startsWith("/") && !href.startsWith("//") ? (
                        <Link to={href}>{children}</Link>
                      ) : (
                        <span>{children}</span>
                      ),
                  }}
                >
                  {m.content}
                </ReactMarkdown>
              </div>
              {m.id === messages.at(-1)?.id && m.choices?.length ? (
                <div
                  className="suggestions"
                  role="group"
                  aria-label="조회 대상 선택"
                >
                  {m.choices.map((choice) => (
                    <button
                      key={choice.message}
                      type="button"
                      disabled={pending}
                      onClick={() => void send(choice.message)}
                    >
                      <span>{choice.label}</span>
                      <ArrowUpRight size={13} />
                    </button>
                  ))}
                </div>
              ) : null}
              {m.links?.map((link, index) => (
                <Link
                  key={link.href}
                  className="chat-screen-link"
                  to={link.href}
                >
                  {m.links!.length > 1 ? `${index + 1}. ` : ""}
                  {link.title}
                  {m.id === lastMessage?.id &&
                  defaultShortcut?.type === "navigate" &&
                  m.links!.length === 1 ? (
                    <kbd>Enter</kbd>
                  ) : null}
                  <ArrowUpRight size={13} />
                </Link>
              ))}
            </div>
          ))
        )}
        {pending ? (
          <div role="status" className="thinking">
            {streamText || (
              <>
                <span />
                <span />
                <span /> 요청을 처리하고 있습니다
              </>
            )}
          </div>
        ) : null}
        <div ref={end} />
      </div>
      <div className="chat-compose">
        <div className="inline between">
          <span className="small muted">
            현재 화면의 조건과 초안을 참조합니다.
          </span>
          <Button
            variant="ghost"
            size="icon"
            disabled={pending || !messages.length}
            onClick={() => {
              reset();
              historyIndex.current = null;
              historyDraft.current = "";
              setInput("");
            }}
            aria-label="대화 초기화"
          >
            <RotateCcw size={14} />
          </Button>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void send();
          }}
        >
          <Textarea
            ref={inputRef}
            aria-label="채팅 메시지"
            value={input}
            maxLength={5000}
            placeholder={
              remoteApi
                ? "예: 펌프1번 전류 트렌드 보여줘"
                : "설비 상태를 질문해 보세요…"
            }
            rows={3}
            onChange={(e) => {
              setInput(e.target.value);
              historyIndex.current = null;
            }}
            onKeyDown={(e) => {
              if (e.nativeEvent.isComposing || e.nativeEvent.keyCode === 229)
                return;
              if (
                (e.key === "ArrowUp" || e.key === "ArrowDown") &&
                !e.shiftKey &&
                !e.altKey &&
                !e.ctrlKey &&
                !e.metaKey
              ) {
                const node = e.currentTarget;
                const boundary =
                  e.key === "ArrowUp"
                    ? !input.slice(0, node.selectionStart).includes("\n")
                    : !input.slice(node.selectionEnd).includes("\n");
                const history = messages
                  .filter((message) => message.role === "user")
                  .map((message) => message.content);
                if (
                  boundary &&
                  history.length &&
                  (e.key === "ArrowUp" || historyIndex.current !== null)
                ) {
                  e.preventDefault();
                  if (historyIndex.current === null) {
                    historyDraft.current = input;
                    historyIndex.current = history.length;
                  }
                  historyIndex.current = Math.max(
                    0,
                    Math.min(
                      history.length,
                      historyIndex.current + (e.key === "ArrowUp" ? -1 : 1),
                    ),
                  );
                  const value =
                    historyIndex.current === history.length
                      ? historyDraft.current
                      : history[historyIndex.current];
                  setInput(value);
                  requestAnimationFrame(() =>
                    inputRef.current?.setSelectionRange(
                      value.length,
                      value.length,
                    ),
                  );
                }
                return;
              }
              if (
                e.key === "Enter" &&
                !e.shiftKey &&
                !e.nativeEvent.isComposing &&
                e.nativeEvent.keyCode !== 229
              ) {
                e.preventDefault();
                void send();
              }
            }}
          />
          <div className="compose-bottom">
            <span>
              {input.trim()
                ? "Enter 전송 · Shift + Enter 줄바꿈"
                : defaultShortcut
                  ? `Enter → ${defaultShortcut.title}`
                  : lastMessage?.choices?.length
                    ? "번호 또는 이름 입력 후 Enter로 선택"
                    : (lastMessage?.links?.length ?? 0) > 1
                      ? "링크 번호 입력 후 Enter로 이동"
                      : "Enter 전송 · Shift + Enter 줄바꿈"}
            </span>
            {pending ? (
              <Button
                type="button"
                size="icon"
                aria-label="응답 중지"
                onClick={() => {
                  controller.current?.abort();
                  setPending(false);
                  add({ role: "assistant", content: "응답을 중지했습니다." });
                }}
              >
                <Square size={12} />
              </Button>
            ) : (
              <Button
                type="submit"
                size="icon"
                aria-label="메시지 전송"
                disabled={!input.trim() && !defaultShortcut}
              >
                <ArrowUp size={17} />
              </Button>
            )}
          </div>
        </form>
        <p className="chat-disclaimer">
          {remoteApi
            ? "설비·센서·기간을 말하면 조회하거나 해당 화면으로 이동합니다."
            : "데모 답변은 현장 진단을 대체하지 않습니다."}
        </p>
      </div>
    </>
  );
}
