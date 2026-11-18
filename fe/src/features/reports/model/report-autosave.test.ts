import { beforeEach, afterEach, it, expect, vi } from "vitest";
import { QueryClient } from "@tanstack/react-query";
import { useReportDraftStore as store } from "./report-draft.store.ts";
import { flushReport, startAutosave } from "./report-autosave.ts";
import { saveReport } from "../api/reports.api.ts";
import type { Report } from "./report.schema.ts";
vi.mock("../api/reports.api", () => ({ saveReport: vi.fn() }));
beforeEach(() => {
  store.setState({ drafts: {}, activeReportId: null });
  vi.mocked(saveReport).mockReset();
});
afterEach(() => vi.useRealTimers());
it("진행 중 저장을 직렬화하고 추가 입력까지 저장한다", async () => {
  const client = new QueryClient();
  const id = store.getState().createDraft("P-1101A");
  let complete!: (r: Report) => void;
  vi.mocked(saveReport)
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          complete = resolve;
        }),
    )
    .mockImplementationOnce(async (_id, input) => ({
      id,
      equipmentId: input.equipmentId,
      values: input.values,
      version: 2,
      updatedAt: new Date().toISOString(),
    }));
  const snapshot = store.getState().drafts[id];
  const job = flushReport(id, client);
  store.getState().patch(id, { cause: "저장 도중 입력" });
  complete({
    id,
    equipmentId: "P-1101A",
    values: snapshot.values,
    version: 1,
    updatedAt: new Date().toISOString(),
  });
  await job;
  expect(saveReport).toHaveBeenCalledTimes(2);
  expect(vi.mocked(saveReport).mock.calls[1][1].expectedVersion).toBe(1);
  expect(store.getState().drafts[id].savedRevision).toBe(2);
  expect(client.getQueryData<Report>(["report", id])?.values.cause).toBe(
    "저장 도중 입력",
  );
});
it("저장 실패 시 초안을 유지하고 오류를 노출한다", async () => {
  const id = store
    .getState()
    .createDraft("P-1101A", { symptom: "복구할 입력" });
  vi.mocked(saveReport).mockRejectedValue(new Error("서버 연결 실패"));
  await expect(flushReport(id, new QueryClient())).rejects.toThrow();
  expect(store.getState().drafts[id].saveStatus).toBe("error");
  expect(store.getState().drafts[id].values.symptom).toBe("복구할 입력");
});
it("마지막 입력 뒤에 자동 저장한다", async () => {
  vi.useFakeTimers();
  const client = new QueryClient();
  vi.mocked(saveReport).mockImplementation(async (id, input) => ({
    id,
    equipmentId: input.equipmentId,
    values: input.values,
    version: 1,
    updatedAt: new Date().toISOString(),
  }));
  const service = startAutosave(client, 800);
  store.getState().createDraft("P-1101A");
  await vi.advanceTimersByTimeAsync(799);
  expect(saveReport).not.toHaveBeenCalled();
  await vi.advanceTimersByTimeAsync(1);
  expect(saveReport).toHaveBeenCalledOnce();
  service.stop();
});
