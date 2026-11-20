import { queryOptions } from "@tanstack/react-query";
import { http } from "../../../shared/api/http-client.ts";
import {
  incidentDetailSchema,
  incidentDraftSchema,
  incidentListSchema,
  type IncidentStatus,
} from "../../../shared/api/contracts/incident.ts";

export type IncidentFilters = {
  plant_id?: string;
  equipment_group_id?: string;
  equipment_id?: string;
  from?: string;
  to?: string;
  as_of?: string;
  min_level?: string;
  actionable?: string;
  status?: IncidentStatus;
  cursor?: string;
  limit?: number;
};

function clean(filters: IncidentFilters) {
  return Object.fromEntries(
    Object.entries(filters).filter(
      ([, value]) => value !== undefined && value !== "",
    ),
  );
}

export const incidentsQuery = (filters: IncidentFilters = {}) =>
  queryOptions({
    queryKey: ["incidents", "list", clean(filters)],
    queryFn: async ({ signal }) =>
      incidentListSchema.parse(
        (await http.get("/incidents", { params: clean(filters), signal })).data,
      ),
    refetchInterval: 60000,
    staleTime: 30000,
  });

export const incidentQuery = (incidentId: string) =>
  queryOptions({
    queryKey: ["incidents", "detail", incidentId],
    queryFn: async ({ signal }) =>
      incidentDetailSchema.parse(
        (
          await http.get(`/incidents/${encodeURIComponent(incidentId)}`, {
            signal,
          })
        ).data,
      ),
    enabled: !!incidentId,
    staleTime: 30000,
  });

export const incidentDraftQuery = (incidentId: string) =>
  queryOptions({
    queryKey: ["incidents", "draft", incidentId],
    queryFn: async ({ signal }) =>
      incidentDraftSchema.parse(
        (
          await http.get(
            `/incidents/${encodeURIComponent(incidentId)}/report-draft`,
            { signal },
          )
        ).data,
      ),
    enabled: !!incidentId,
    staleTime: 60000,
  });
