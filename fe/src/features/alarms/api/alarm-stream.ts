import type { QueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { http } from "../../../shared/api/http-client.ts";
import { mapAlarm } from "../../../shared/api/be-adapter.ts";
import type { Hierarchy } from "../../../shared/api/contracts/hierarchy.ts";
import type { Alarm } from "../../../shared/api/contracts/alarm.ts";
import { alarmsResponseSchema } from "./alarms.schema.ts";

const change = z.object({ cursor: z.string(), alarm: z.unknown() });
const cleared = z.object({ cursor: z.string(), alarm_id: z.string() });
function priority(alarms: Alarm[], hierarchy: Hierarchy): Alarm[] {
  const levels = new Map(
    hierarchy.equipment.map((item) => [item.id, item.equipmentLevel ?? 0]),
  );
  return [...alarms].sort(
    (a, b) =>
      (b.alarmLevel ?? 0) - (a.alarmLevel ?? 0) ||
      (levels.get(b.equipmentId) ?? 0) - (levels.get(a.equipmentId) ?? 0) ||
      a.occurredAt.localeCompare(b.occurredAt) ||
      a.id.localeCompare(b.id),
  );
}
export function subscribeAlarms(client: QueryClient): () => void {
  const snapshot = client.getQueryData<{ cursor?: string }>(["alarms", "live"]);
  const base = (http.defaults.baseURL ?? "/api").replace(/\/$/, "");
  const url = `${base}/alarms/stream${snapshot?.cursor ? `?cursor=${encodeURIComponent(snapshot.cursor)}` : ""}`;
  const source = new EventSource(url, { withCredentials: true });
  const update = (event: Event) => {
    try {
      const detail = change.parse(JSON.parse((event as MessageEvent).data));
      const hierarchy = client.getQueryData<Hierarchy>(["hierarchy"]);
      if (!hierarchy) return reset();
      const alarm = mapAlarm(detail.alarm, hierarchy);
      client.setQueryData(["alarms", "live"], (previous: unknown) => {
        const current = alarmsResponseSchema.parse(previous);
        return {
          ...current,
          cursor: detail.cursor,
          asOf: new Date().toISOString(),
          alarms: priority(
            [...current.alarms.filter((a) => a.id !== alarm.id), alarm],
            hierarchy,
          ),
        };
      });
    } catch {
      reset();
    }
  };
  const clear = (event: Event) => {
    try {
      const detail = cleared.parse(JSON.parse((event as MessageEvent).data));
      client.setQueryData(["alarms", "live"], (previous: unknown) => {
        const current = alarmsResponseSchema.parse(previous);
        return {
          ...current,
          cursor: detail.cursor,
          asOf: new Date().toISOString(),
          alarms: current.alarms.filter((a) => a.id !== detail.alarm_id),
        };
      });
    } catch {
      reset();
    }
  };
  const reset = () =>
    void client.invalidateQueries({ queryKey: ["alarms", "live"] });
  source.addEventListener("alarm.created", update);
  source.addEventListener("alarm.updated", update);
  source.addEventListener("alarm.cleared", clear);
  source.addEventListener("reset", reset);
  source.onerror = reset;
  return () => source.close();
}
