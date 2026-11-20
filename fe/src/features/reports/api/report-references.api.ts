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
const locationSchema = z.object({
  location: z.string().nullable().optional(),
  manufacturer: z.string().nullable().optional(),
  model_name: z.string().nullable().optional(),
  model: z.string().nullable().optional(),
});
export type ReportReferences = {
  location: string;
  manufacturer?: string;
  model?: string;
  fieldNotes?: Record<string, string>;
  manuals: MaintenanceReport["manuals"];
  history: string;
  historyIds: string;
  notes: string[];
};
export const reportReferencesQuery = (equipmentId: string, asOf?: string) =>
  queryOptions({
    queryKey: asOf
      ? ["report-references", equipmentId, asOf]
      : ["report-references", equipmentId],
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
            params: {
              equipment_id: equipmentId,
              limit: 3,
              ...(asOf ? { to: asOf } : {}),
            },
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
        manufacturer:
          equipment.status === "fulfilled"
            ? (equipment.value.manufacturer ?? "")
            : "",
        model:
          equipment.status === "fulfilled"
            ? (equipment.value.model_name ?? equipment.value.model ?? "")
            : "",
        fieldNotes: {
          location:
            equipment.status === "rejected"
              ? "설비 정보 조회 실패 · 다시 확인해 주세요."
              : equipment.value.location
                ? ""
                : "설비 위치가 등록되지 않았습니다.",
          manufacturer:
            equipment.status === "rejected"
              ? "설비 정보 조회 실패"
              : equipment.value.manufacturer
                ? ""
                : "펌프 제조사 미등록 · 센서 제조사와 구분하여 입력하세요.",
          model:
            equipment.status === "rejected"
              ? "설비 정보 조회 실패"
              : equipment.value.model_name || equipment.value.model
                ? ""
                : "펌프 모델 미등록 · 센서 모델과 구분하여 입력하세요.",
          recentMaintenance:
            histories.status === "rejected"
              ? "정비 이력 조회 실패 · 다시 확인해 주세요."
              : "",
        },
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
                    `${h.maintenance_history_id} · ${h.start_time} ~ ${asOf && (!h.end_time || Date.parse(h.end_time) > Date.parse(asOf)) ? "기준 시점 진행 중" : (h.end_time ?? "종료 미기록")}`,
                )
                .join("\n") ||
              (asOf
                ? "기준 시점 이전 등록된 정비 이력 없음"
                : "등록된 정비 이력 없음")
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
    original: {
      ...model.original,
      referenceNotes: references.notes,
      fieldNotes: { ...model.original.fieldNotes, ...references.fieldNotes },
    },
    incident: {
      ...model.incident,
      location: references.location,
      manufacturer: references.manufacturer ?? model.incident.manufacturer,
      model: references.model ?? model.incident.model,
      recentMaintenance: references.history,
    },
    manuals: references.manuals,
    review: { ...model.review, pastCaseIds: references.historyIds },
  };
}
