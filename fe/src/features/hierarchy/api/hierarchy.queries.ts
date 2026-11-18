import { queryOptions } from "@tanstack/react-query";
import { http } from "../../../shared/api/http-client.ts";
import { hierarchySchema } from "../model/hierarchy.schema.ts";
import { mapHierarchy, remoteApi } from "../../../shared/api/be-adapter.ts";
export const hierarchyQuery = queryOptions({
  queryKey: ["hierarchy"],
  queryFn: async () => {
    const data: unknown = (await http.get("/hierarchy")).data;
    return remoteApi ? mapHierarchy(data) : hierarchySchema.parse(data);
  },
  staleTime: 300000,
});
