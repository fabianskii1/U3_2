import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";
import { http } from "../../../shared/api/http-client.ts";

const seriesSchema = z.object({
  sensorId: z.string(),
  start: z.string().datetime({ offset: true }),
  end: z.string().datetime({ offset: true }),
});

export const savedTrendSchema = z.object({
  viewId: z.string().uuid(),
  plantId: z.string(),
  equipmentGroupId: z.string(),
  equipmentId: z.string().nullable(),
  config: z.object({
    version: z.number().int().positive(),
    series: z.array(seriesSchema).min(1),
    showAnomalies: z.boolean(),
    interval: z.enum(["1m", "1h", "1d"]).nullable().optional(),
  }),
  createdAt: z.string(),
  expiresAt: z.string().nullable(),
});

export type TrendSeries = z.infer<typeof seriesSchema>;

export const savedTrendQuery = (viewId: string) =>
  queryOptions({
    queryKey: ["trend-view", viewId],
    queryFn: async ({ signal }) =>
      savedTrendSchema.parse(
        (await http.get(`/chat/trend-views/${viewId}`, { signal })).data,
      ),
    enabled: z.string().uuid().safeParse(viewId).success,
    retry: false,
  });
