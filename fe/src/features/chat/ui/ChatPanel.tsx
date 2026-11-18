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
  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [messages.length, pending]);
  useEffect(() => () => controller.current?.abort(), []);
  const send = async (text = input) => {
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
    add({ role: "user", content: text });
    try {
      const context = buildContext(text, useChatStore.getState().sessionId);
      const result = await sendChat(context, abort.signal, setStreamText);
      if (abort.signal.aborted) return;
      await onAction(result);
      add({
        role: "assistant",
        content:
          result.action?.type === "save-draft"
            ? "보고서 저장이 완료되었습니다."
            : result.message,
        links: result.links,
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
        {remoteApi ? "설비 ID 조회 AI 연결됨" : "규칙 기반 Mock 응답 · 실제 AI 미연결"}
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
                ? ["원유 공급 펌프", "납사 이송 펌프", "열교환기 공급 펌프"]
                : [
                    "지금 알람 뭐부터 봐야 해?",
                    "원유 공급 펌프 A 진동 현황 보여줘",
                    "보고서 초안 생성해줘",
                  ]
              ).map((text) => (
                <button
                  key={text}
                  onClick={() => void send(text)}
                >
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
              {m.links?.map((link) => (
                <Link
                  key={link.href}
                  className="chat-screen-link"
                  to={link.href}
                >
                  {link.title}
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
            onClick={reset}
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
            aria-label="채팅 메시지"
            value={input}
            maxLength={5000}
            placeholder={
              remoteApi
                ? "설비 이름이나 별칭을 입력해 보세요…"
                : "설비 상태를 질문해 보세요…"
            }
            rows={3}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (
                e.key === "Enter" &&
                !e.shiftKey &&
                !e.nativeEvent.isComposing
              ) {
                e.preventDefault();
                void send();
              }
            }}
          />
          <div className="compose-bottom">
            <span>Enter 전송 · Shift + Enter 줄바꿈</span>
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
                disabled={!input.trim()}
              >
                <ArrowUp size={17} />
              </Button>
            )}
          </div>
        </form>
        <p className="chat-disclaimer">
          {remoteApi
            ? "현재는 설비 ID 조회를 지원합니다. 모호한 이름은 후보를 보여줍니다."
            : "데모 답변은 현장 진단을 대체하지 않습니다."}
        </p>
      </div>
    </>
  );
}
