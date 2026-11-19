import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";
import { http } from "../../../shared/api/http-client.ts";
import { reportSchema, type ReportFields } from "../model/report.schema.ts";
import {
  beReportList,
  mapReport,
  remoteApi,
} from "../../../shared/api/be-adapter.ts";
const browserReportsKey = "skadi-maintenance-saved-v1";
export function readBrowserReports() {
  try {
    return z
      .array(reportSchema)
      .parse(JSON.parse(localStorage.getItem(browserReportsKey) ?? "[]"));
  } catch {
    return [];
  }
}
export const reportsQuery = queryOptions({
  queryKey: ["reports"],
  queryFn: async ({ signal }) => {
    if (!remoteApi)
      return z
        .array(reportSchema)
        .parse((await http.get("/reports", { signal })).data);
    const items = [];
    let cursor: string | null = null;
    do {
      const page = beReportList.parse(
        (
          await http.get("/reports", {
            params: cursor ? { cursor } : undefined,
            signal,
          })
        ).data,
      );
      items.push(...page.items.map(mapReport));
      cursor = page.next_cursor;
    } while (cursor);
    return items;
  },
});
export const reportQuery = (id: string) =>
  queryOptions({
    queryKey: ["report", id],
    queryFn: async () => {
      const saved = remoteApi
        ? readBrowserReports().find((r) => r.id === id)
        : undefined;
      if (saved) return saved;
      const data: unknown = (
        await http.get(`/reports/${encodeURIComponent(id)}`)
      ).data;
      return remoteApi ? mapReport(data) : reportSchema.parse(data);
    },
    retry: false,
  });
export const saveReport = async (
  id: string,
  input: {
    equipmentId: string;
    values: ReportFields;
    expectedVersion: number;
    requestId: string;
  },
  _serverId?: string,
) => {
  if (!remoteApi)
    return reportSchema.parse(
      (await http.put(`/reports/${encodeURIComponent(id)}`, input)).data,
    );
  if (!input.values.maintenance)
    throw new Error(
      "보고서 저장 API가 연결되지 않았습니다. 상세 양식에서 브라우저 저장을 사용해 주세요.",
    );
  const existing = readBrowserReports();
  const previous = existing.find((r) => r.id === id);
  if (previous && previous.version !== input.expectedVersion)
    throw Object.assign(
      new Error("다른 탭에서 보고서를 저장했습니다. 저장본과 비교해 주세요."),
      { code: "BROWSER_REPORT_CONFLICT" },
    );
  const saved = reportSchema.parse({
    id,
    equipmentId: input.equipmentId,
    values: input.values,
    version: input.expectedVersion + 1,
    updatedAt: new Date().toISOString(),
  });
  const serialized = JSON.stringify([
    ...existing.filter((r) => r.id !== id),
    saved,
  ]);
  localStorage.setItem(browserReportsKey, serialized);
  if (localStorage.getItem(browserReportsKey) !== serialized)
    throw new Error("브라우저 저장을 확인하지 못했습니다.");
  return saved;
};
