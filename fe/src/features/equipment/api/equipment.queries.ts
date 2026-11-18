import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";
import {
  equipmentSchema,
  tagSchema,
} from "../../../shared/api/contracts/hierarchy.ts";
import { http } from "../../../shared/api/http-client.ts";
import { mapEquipment, remoteApi } from "../../../shared/api/be-adapter.ts";
const schema = equipmentSchema.extend({
  tags: z.array(tagSchema.extend({ current: z.number().nullable() })),
  asOf: z.string(),
});
export const equipmentQuery = (id: string) =>
  queryOptions({
    queryKey: ["equipment", id],
    queryFn: async ({ signal }) => {
      const data: unknown = (
        await http.get(`/equipment/${encodeURIComponent(id)}`, { signal })
      ).data;
      if (!remoteApi) return schema.parse(data);
      const equipment = mapEquipment(data);
      return schema.parse({
        ...equipment,
        asOf: z.object({ as_of: z.string() }).parse(data).as_of,
        tags: equipment.tags.map((tag) => ({
          ...tag,
          current: tag.currentValue ?? null,
        })),
      });
    },
    enabled: !!id,
    refetchInterval: remoteApi ? 10_000 : 1000,
    retry: 1,
  });
