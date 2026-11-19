import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";
import { http } from "../../../shared/api/http-client.ts";
import { remoteApi } from "../../../shared/api/be-adapter.ts";
import type { MaintenanceReport } from "../../../shared/api/contracts/maintenance-report.ts";

const manualSchema = z.array(
  z.object({
    equipment_manual_id: z.string(),
    equipment_manual_title: z.string(),
    equipment_manual_link: z.string(),
  }),
);
const historiesSchema = z.object({
  items: z.array(
    z.object({
      maintenance_history_id: z.string(),
      start_time: z.string(),
      end_time: z.string().nullable(),
    }),
  ),
});
const locationSchema = z.object({ location: z.string().nullable().optional() });
export type ReportReferences = {
  location: string;
  manuals: MaintenanceReport["manuals"];
  history: string;
  historyIds: string;
  notes: string[];
};
export const reportReferencesQuery = (equipmentId: string) =>
  queryOptions({
    queryKey: ["report-references", equipmentId],
    enabled: remoteApi && !!equipmentId,
    staleTime: 60000,
    queryFn: async ({ signal }): Promise<ReportReferences> => {
      const requests = await Promise.allSettled([
        http
          .get(`/equipment/${encodeURIComponent(equipmentId)}`, { signal })
          .then((r) => locationSchema.parse(r.data)),
        http
          .get(`/equipment/${encodeURIComponent(equipmentId)}/manuals`, {
            signal,
          })
          .then((r) => manualSchema.parse(r.data)),
        http
          .get("/maintenance-histories", {
            params: { equipment_id: equipmentId, limit: 3 },
            signal,
          })
          .then((r) => historiesSchema.parse(r.data)),
      ]);
      const [equipment, manuals, histories] = requests;
      return {
        location:
          equipment.status === "fulfilled"
            ? (equipment.value.location ?? "")
            : "",
        manuals:
          manuals.status === "fulfilled"
            ? manuals.value.map((manual) => ({
                id: manual.equipment_manual_id,
                title: manual.equipment_manual_title,
                href: manual.equipment_manual_link,
                revision: "",
                section: "",
                recommendation: "",
              }))
            : [],
        history:
          histories.status === "fulfilled"
            ? histories.value.items
                .map(
                  (h) =>
                    `${h.maintenance_history_id} · ${h.start_time} ~ ${h.end_time ?? "종료 미기록"}`,
                )
                .join("\n")
            : "",
        historyIds:
          histories.status === "fulfilled"
            ? histories.value.items
                .map((h) => h.maintenance_history_id)
                .join(", ")
            : "",
        notes: requests.flatMap((result, i) =>
          result.status === "rejected"
            ? [`${["설비 위치", "등록 매뉴얼", "정비 이력"][i]} 조회 실패`]
            : [],
        ),
      };
    },
  });
export function applyReportReferences(
  model: MaintenanceReport,
  references?: ReportReferences,
): MaintenanceReport {
  if (!references) return model;
  return {
    ...model,
    original: { ...model.original, referenceNotes: references.notes },
    incident: {
      ...model.incident,
      location: references.location,
      recentMaintenance: references.history,
    },
    manuals: references.manuals,
    review: { ...model.review, pastCaseIds: references.historyIds },
  };
}
