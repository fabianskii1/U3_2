import { http } from "../../../shared/api/http-client.ts";
import { remoteApi } from "../../../shared/api/be-adapter.ts";
import { useReportDraftStore } from "../../reports/model/report-draft.store.ts";
import { useChatStore } from "../model/chat-session.store.ts";
import {
  chatRequestSchema,
  chatResponseSchema,
  type ChatRequest,
  type ChatResponse,
} from "../model/chat.schema.ts";
export const sendChat = async (
  input: ChatRequest,
  signal: AbortSignal,
  onDelta?: (text: string) => void,
) => {
  const request = chatRequestSchema.parse(input);
  if (!remoteApi)
    return chatResponseSchema.parse(
      (await http.post("/chat", request, { signal })).data,
    );
  let sessionId = useChatStore.getState().serverSessionId;
  if (!sessionId) {
    const created = await http.post<{ session_id: string }>(
      "/chat/sessions",
      {},
      { signal },
    );
    sessionId = created.data.session_id;
    useChatStore.getState().setServerSessionId(sessionId);
  }
  const context = request.screenContext;
  const draft = request.reportContext
    ? Object.values(useReportDraftStore.getState().drafts).find(
        (item) => item.serverId === request.reportContext?.reportId,
      )
    : undefined;
  const payload = {
    request_id: crypto.randomUUID(),
    session_id: sessionId,
    message: request.message,
    screen_context: {
      page: context.page,
      query: context.query ?? "",
      section: context.section ?? null,
      incident_id: context.incidentId ?? null,
      as_of: context.asOf ?? null,
      replay_hour: context.replayHour ?? null,
      replay_max: context.replayMax ?? null,
      plant_id: context.plantId ?? null,
      equipment_group_id: context.unitId ?? null,
      equipment_id: context.equipmentId,
      sensor_id: context.sensorId ?? null,
      sensor_ids: context.sensorIds ?? [],
      trend_series: context.trendSeries ?? [],
      alarm_id: context.alarmId ?? null,
      sensor_interval: context.sensor_interval ?? null,
      sensor_start_time: context.from ?? null,
      sensor_end_time: context.to ?? null,
    },
    report_context: request.reportContext
      ? {
          report_id: request.reportContext.reportId,
          version: draft?.serverVersion ?? null,
          values: {
            title: request.reportContext.values.title,
            symptom: request.reportContext.values.symptom,
            cause: request.reportContext.values.cause,
            action: request.reportContext.values.action,
            chart_url: request.reportContext.values.chartUrl,
            risk: request.reportContext.values.risk,
          },
        }
      : null,
  };
  const base = (http.defaults.baseURL ?? "/api").replace(/\/$/, "");
  const response = await fetch(`${base}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    credentials: "include",
    body: JSON.stringify(payload),
    signal,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(
      error?.message ??
        error?.detail?.message ??
        `채팅 요청 실패 (${response.status})`,
    );
  }
  if (!response.body) throw new Error("채팅 스트림을 열 수 없습니다.");
  let message = "";
  const links: { title: string; href: string }[] = [];
  const choices: { label: string; message: string }[] = [];
  let action: ChatResponse["action"];
  let done = false;
  let buffer = "";
  const decoder = new TextDecoder();
  const reader = response.body.getReader();
  try {
    while (true) {
      const next = await reader.read();
      if (next.done) break;
      buffer += decoder.decode(next.value, { stream: true });
      buffer = buffer.replace(/\r\n/g, "\n");
      let boundary: number;
      while ((boundary = buffer.indexOf("\n\n")) >= 0) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const type = frame
          .split("\n")
          .find((line) => line.startsWith("event:"))
          ?.slice(6)
          .trim();
        const data = frame
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trimStart())
          .join("\n");
        if (!data) continue;
        const value = JSON.parse(data);
        if (type === "message.delta") {
          message += String(value.text ?? "");
          onDelta?.(message);
        }
        if (type === "citation" && typeof value.href === "string")
          links.push({
            title: String(value.title ?? "근거"),
            href: value.href,
          });
        if (
          type === "choice" &&
          typeof value.label === "string" &&
          typeof value.message === "string"
        )
          choices.push({ label: value.label, message: value.message });
        if (type === "navigate" && typeof value.href === "string")
          action = { type: "navigate", href: value.href };
        if (type === "report.patch") {
          const draft = Object.values(
            useReportDraftStore.getState().drafts,
          ).find((item) => item.serverId === value.report_id);
          if (!draft || draft.serverVersion !== value.base_version)
            throw new Error(
              "보고서 버전이 변경되었습니다. 다시 요청해 주세요.",
            );
          const patch = { ...value.patch };
          if ("chart_url" in patch) {
            patch.chartUrl = patch.chart_url;
            delete patch.chart_url;
          }
          action = {
            type: "patch-draft",
            reportId: draft.id,
            baseLocalRevision: draft.localRevision,
            patch,
          };
        }
        if (type === "error")
          throw new Error(String(value.message ?? "채팅 처리 오류"));
        if (type === "done") done = true;
      }
    }
  } finally {
    reader.releaseLock();
  }
  if (!done)
    throw new Error("채팅 응답이 완료되기 전에 연결이 종료되었습니다.");
  return chatResponseSchema.parse({ message, links, choices, action });
};
