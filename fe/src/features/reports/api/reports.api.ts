import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";
import { http } from "../../../shared/api/http-client.ts";
import { reportSchema, type ReportFields } from "../model/report.schema.ts";
import {
  beReportList,
  mapReport,
  remoteApi,
} from "../../../shared/api/be-adapter.ts";
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
  serverId?: string,
) => {
  if (!remoteApi)
    return reportSchema.parse(
      (await http.put(`/reports/${encodeURIComponent(id)}`, input)).data,
    );
  const body = {
    equipment_id: input.equipmentId,
    title: input.values.title,
    symptom: input.values.symptom,
    cause: input.values.cause,
    action: input.values.action,
    chart_url: input.values.chartUrl || null,
    risk: input.values.risk,
    ...(serverId ? { expected_version: input.expectedVersion } : {}),
    request_id: input.requestId,
  };
  const data: unknown = serverId
    ? (await http.put(`/reports/${encodeURIComponent(serverId)}`, body)).data
    : (await http.post("/reports", body)).data;
  return mapReport(data);
};
