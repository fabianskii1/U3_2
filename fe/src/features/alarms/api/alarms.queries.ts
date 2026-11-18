import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";
import { http } from "../../../shared/api/http-client.ts";
import { alarmsResponseSchema } from "./alarms.schema.ts";
import { mapAlarm, remoteApi } from "../../../shared/api/be-adapter.ts";
import { hierarchyQuery } from "../../hierarchy/api/hierarchy.queries.ts";
import { queryClient } from "../../../app/providers/query-client.ts";
export const alarmsQuery = queryOptions({
  queryKey: ["alarms", "live"],
  queryFn: async ({ signal }) => {
    if (!remoteApi) {
      const data: unknown = (await http.get("/alarms", { signal })).data;
      return alarmsResponseSchema.parse(data);
    }
    const hierarchy = await queryClient.ensureQueryData(hierarchyQuery);
    const rows: unknown[] = [];
    let cursor: string | null = null;
    do {
      const page = z
        .object({
          items: z.array(z.unknown()),
          next_cursor: z.string().nullable(),
        })
        .parse(
          (
            await http.get("/alarms/history", {
              params: cursor ? { cursor, limit: 200 } : { limit: 200 },
              signal,
            })
          ).data,
        );
      rows.push(...page.items);
      cursor = page.next_cursor;
    } while (cursor);
    return {
      alarms: rows.map((alarm) => mapAlarm(alarm, hierarchy)),
      asOf: new Date().toISOString(),
      sequence: 0,
      cursor: "",
    };
  },
  refetchInterval: remoteApi ? 60000 : 1000,
  refetchIntervalInBackground: true,
  staleTime: 0,
  retry: 1,
});
