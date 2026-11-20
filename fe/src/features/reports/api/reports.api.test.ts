import { beforeEach, expect, it, vi } from "vitest";
import { readBrowserReports, reportQuery, saveReport } from "./reports.api.ts";
import { http } from "../../../shared/api/http-client.ts";
import { createExample } from "../model/maintenance-report.ts";
import { emptyFields, type Report } from "../model/report.schema.ts";
vi.mock("../../../shared/api/be-adapter.ts", async (original) => ({
  ...(await original<object>()),
  remoteApi: true,
}));
beforeEach(() => localStorage.clear());
const report: Report = {
  id: "local-report",
  equipmentId: "P1",
  values: { ...emptyFields },
  version: 0,
  updatedAt: "2026-11-19T00:00:00Z",
};
const model = () =>
  createExample(report, {
    id: "P1",
    name: "펌프",
    type: "펌프",
    grade: "1",
    plantId: "PLANT-01",
    unitId: "CUD-01",
    tags: [],
  });
it("확장 보고서의 다섯 영역을 브라우저에 저장하며 미구현 서버 쓰기 API를 호출하지 않는다", async () => {
  const post = vi.spyOn(http, "post");
  const put = vi.spyOn(http, "put");
  const maintenance = model();
  maintenance.work.description = "현장 수행 작업";
  const saved = await saveReport(report.id, {
    equipmentId: "P1",
    values: { ...emptyFields, maintenance },
    expectedVersion: 0,
    requestId: "request-1",
  });
  expect(saved.version).toBe(1);
  expect(readBrowserReports()[0].values.maintenance?.work.description).toBe(
    "현장 수행 작업",
  );
  expect(post).not.toHaveBeenCalled();
  expect(put).not.toHaveBeenCalled();
  const query = reportQuery(report.id);
  const restored = await (query.queryFn as () => Promise<Report>)();
  expect(restored.values.maintenance).toEqual(maintenance);
});
it("브라우저 기록 실패를 성공으로 표시하지 않는다", async () => {
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new DOMException("저장 공간 부족", "QuotaExceededError");
  });
  await expect(
    saveReport(report.id, {
      equipmentId: "P1",
      values: { ...emptyFields, maintenance: model() },
      expectedVersion: 0,
      requestId: "request-2",
    }),
  ).rejects.toThrow();
});

it("다른 탭의 최신 저장본을 오래된 버전으로 덮어쓰지 않는다", async () => {
  const input = {
    equipmentId: "P1",
    values: { ...emptyFields, maintenance: model() },
    expectedVersion: 0,
    requestId: "request-3",
  };
  await saveReport(report.id, input);
  await expect(
    saveReport(report.id, {
      ...input,
      values: { ...input.values, title: "충돌 편집본" },
    }),
  ).rejects.toMatchObject({ code: "BROWSER_REPORT_CONFLICT" });
  expect(readBrowserReports()[0].values.title).toBe("");
});
