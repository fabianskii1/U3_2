import axios from "axios";
import { useReportDraftStore as store } from "./report-draft.store.ts";
import { saveReport } from "../api/reports.api.ts";
import { errorMessage } from "../../../shared/api/http-client.ts";
import type { QueryClient } from "@tanstack/react-query";
const inFlight = new Map<string, Promise<void>>();
export async function flushReport(
  id: string,
  client: QueryClient,
): Promise<void> {
  const existing = inFlight.get(id);
  if (existing) {
    await existing;
    return flushReport(id, client);
  }
  const snapshot = store.getState().drafts[id];
  if (!snapshot) throw new Error("저장할 보고서를 찾을 수 없습니다.");
  if (snapshot.localRevision === snapshot.savedRevision) return;
  if (snapshot.saveStatus === "conflict")
    throw new Error(snapshot.error ?? "서버 버전 충돌을 해결해 주세요.");
  const job = (async () => {
    store.getState().markSaving(id);
    try {
      const report = await saveReport(
        id,
        {
          equipmentId: snapshot.equipmentId,
          values: snapshot.values,
          expectedVersion: snapshot.serverVersion,
          requestId: `${id}-${snapshot.serverVersion}-${snapshot.localRevision}`,
        },
        snapshot.serverId,
      );
      store.getState().markSaved(id, snapshot.localRevision, report);
      client.setQueryData(["report", report.id], report);
      await client.invalidateQueries({ queryKey: ["reports"] });
    } catch (error) {
      store
        .getState()
        .markError(
          id,
          errorMessage(error),
          (axios.isAxiosError(error) && error.response?.status === 409) ||
            (error instanceof Error &&
              "code" in error &&
              error.code === "BROWSER_REPORT_CONFLICT"),
        );
      throw error;
    }
  })();
  inFlight.set(id, job);
  try {
    await job;
  } finally {
    inFlight.delete(id);
  }
  const latest = store.getState().drafts[id];
  if (latest && latest.localRevision !== latest.savedRevision)
    await flushReport(id, client);
}
export function startAutosave(client: QueryClient, delay = 800) {
  const timers = new Map<string, ReturnType<typeof setTimeout>>();
  const schedule = () => {
    for (const [id, d] of Object.entries(store.getState().drafts)) {
      if (
        !!d.values.maintenance ||
        d.localRevision === d.savedRevision ||
        d.saveStatus === "saving" ||
        d.saveStatus === "error" ||
        d.saveStatus === "conflict"
      )
        continue;
      if (timers.has(id)) clearTimeout(timers.get(id));
      timers.set(
        id,
        setTimeout(() => {
          timers.delete(id);
          if (!store.getState().drafts[id]?.values.maintenance)
            void flushReport(id, client).catch(() => {});
        }, delay),
      );
    }
  };
  const unsubscribe = store.subscribe((state, prev) => {
    if (
      Object.entries(state.drafts).some(
        ([id, d]) =>
          d.localRevision !== prev.drafts[id]?.localRevision ||
          d.saveStatus !== prev.drafts[id]?.saveStatus,
      )
    )
      schedule();
  });
  schedule();
  return {
    flushAll: () => {
      for (const timer of timers.values()) clearTimeout(timer);
      timers.clear();
      for (const [id, d] of Object.entries(store.getState().drafts))
        if (
          !d.values.maintenance &&
          d.localRevision !== d.savedRevision &&
          d.saveStatus !== "conflict"
        )
          void flushReport(id, client).catch(() => {});
    },
    stop: () => {
      unsubscribe();
      for (const timer of timers.values()) clearTimeout(timer);
    },
  };
}
