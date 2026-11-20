import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";
import { http } from "../../../shared/api/http-client.ts";
import { beTrend, remoteApi } from "../../../shared/api/be-adapter.ts";
import { trendIncidentSchema } from "../../../shared/api/contracts/incident.ts";
import {
  MAX_TREND_POINTS,
  pointCount,
  remoteTrendIntervals,
  resolveInterval,
  type SensorInterval,
} from "../model/trend-interval.ts";
const schema = z.object({
  sensorId: z.string(),
  unit: z.string(),
  limit: z.number().nullable(),
  direction: z.string(),
  max: z.number().nullable(),
  points: z.array(z.object({ time: z.string(), value: z.number().nullable() })),
  setpoints: z
    .array(
      z.object({
        setpoint_id: z.string(),
        alarm_level: z.number().int().min(1).max(4),
        direction: z.enum(["HIGH", "LOW"]),
        operator: z.enum([">=", "<="]),
        value: z.number().nullable(),
        effective_from: z.string(),
        effective_to: z.string().nullable(),
      }),
    )
    .default([]),
  incidents: z.array(trendIncidentSchema).default([]),
});
export const trendQuery = (
  sensorId: string,
  from: string,
  to: string,
  requestedInterval: SensorInterval = "1h",
) => {
  const interval = resolveInterval(
    requestedInterval,
    from,
    to,
    remoteApi ? remoteTrendIntervals : undefined,
  );
  return queryOptions({
    queryKey: ["trend", { sensorId, from, to, interval }],
    queryFn: async ({ signal }) => {
      const data: unknown = (
        await http.get("/trend", {
          params: { sensor_id: sensorId, from, to, interval },
          signal,
        })
      ).data;
      if (!remoteApi) return schema.parse(data);
      const raw = beTrend.parse(data);
      return schema.parse({
        sensorId: raw.sensor_id,
        unit: raw.unit,
        limit: raw.threshold_value ?? null,
        direction: "",
        max: raw.points.reduce<number | null>(
          (max, point) =>
            point.value === null
              ? max
              : Math.max(max ?? point.value, point.value),
          null,
        ),
        points: raw.points,
        setpoints: raw.setpoints,
        incidents: raw.incidents,
      });
    },
    enabled:
      !!sensorId &&
      !!from &&
      !!to &&
      from < to &&
      pointCount(from, to, interval) <= MAX_TREND_POINTS,
    staleTime: 60000,
  });
};
