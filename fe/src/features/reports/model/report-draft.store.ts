import { devtoolsOptions } from "../../../shared/lib/devtools.ts";
import { create } from "zustand";
import { devtools, persist, createJSONStorage } from "zustand/middleware";
import { z } from "zod";
import type { ReportSensor } from "../../../shared/api/contracts/maintenance-report.ts";
import { invalidateCause } from "./maintenance-report.ts";
import {
  emptyFields,
  reportFieldsSchema,
  reportPatchSchema,
  type ReportFields,
  type Report,
} from "./report.schema.ts";
export type ReportDraft = {
  id: string;
  serverId?: string;
  equipmentId: string;
  values: ReportFields;
  savedValues?: ReportFields;
  localRevision: number;
  savedRevision: number;
  serverVersion: number;
  updatedAt: string;
  saveStatus: "idle" | "saving" | "error" | "conflict";
  error?: string;
};
const persistedDraftSchema = z.object({
  id: z.string(),
  serverId: z.string().optional(),
  equipmentId: z.string(),
  values: reportFieldsSchema,
  localRevision: z.number().int().nonnegative(),
  savedRevision: z.number().int().nonnegative(),
  serverVersion: z.number().int().nonnegative(),
  updatedAt: z.string(),
  savedValues: reportFieldsSchema.optional(),
});
type State = {
  activeReportId: string | null;
  drafts: Record<string, ReportDraft>;
  createDraft: (equipmentId: string, values?: Partial<ReportFields>) => string;
  openReport: (report: Report) => void;
  activate: (id: string) => void;
  initializeMaintenance: (
    id: string,
    maintenance: NonNullable<ReportFields["maintenance"]>,
  ) => void;
  restoreSaved: (id: string) => void;
  captureSensors: (id: string, sensors: ReportSensor[]) => void;
  reopen: (id: string, reason: string) => void;
  patch: (
    id: string,
    patch: Partial<ReportFields>,
    baseRevision?: number,
  ) => boolean;
  markSaving: (id: string) => void;
  markSaved: (id: string, revision: number, report: Report) => void;
  markError: (id: string, message: string, conflict?: boolean) => void;
  replaceFromServer: (report: Report) => void;
  rebase: (id: string, version: number) => void;
};
const storage = {
  getItem: (key: string) => localStorage.getItem(key),
  removeItem: (key: string) => localStorage.removeItem(key),
  setItem: (key: string, value: string) => {
    try {
      localStorage.setItem(key, value);
    } catch {
      window.dispatchEvent(new CustomEvent("draft-storage-error"));
    }
  },
};
export const useReportDraftStore = create<State>()(
  devtools(
    persist(
      (set, get) => ({
        activeReportId: null,
        drafts: {},
        createDraft: (equipmentId, values = {}) => {
          const id = crypto.randomUUID();
          const now = new Date().toISOString();
          set((s) => ({
            activeReportId: id,
            drafts: {
              ...s.drafts,
              [id]: {
                id,
                equipmentId,
                values: { ...emptyFields, ...values },
                localRevision: 1,
                savedRevision: 0,
                serverVersion: 0,
                updatedAt: now,
                saveStatus: "idle",
              },
            },
          }));
          return id;
        },
        activate: (id) => set({ activeReportId: id }),
        initializeMaintenance: (id, maintenance) =>
          set((s) => {
            const d = s.drafts[id];
            if (!d || d.values.maintenance) return s;
            const values = { ...d.values, maintenance };
            return {
              drafts: {
                ...s.drafts,
                [id]: { ...d, values, savedValues: values },
              },
            };
          }),
        captureSensors: (id, sensors) =>
          set((s) => {
            const d = s.drafts[id];
            const m = d?.values.maintenance;
            if (!m || m.status === "confirmed" || m.original.kind === "example")
              return s;
            const captured = m.original.sensors.map((sensor) =>
              sensor.points
                ? sensor
                : (sensors.find(
                    (row) => row.id === sensor.id && row.points?.length,
                  ) ?? sensor),
            );
            if (captured.every((row, i) => row === m.original.sensors[i]))
              return s;
            const original = { ...m.original, sensors: captured };
            const values = { ...d.values, maintenance: { ...m, original } };
            const savedValues = d.savedValues?.maintenance
              ? {
                  ...d.savedValues,
                  maintenance: { ...d.savedValues.maintenance, original },
                }
              : d.savedValues;
            return {
              drafts: { ...s.drafts, [id]: { ...d, values, savedValues } },
            };
          }),
        restoreSaved: (id) =>
          set((s) => {
            const d = s.drafts[id];
            if (!d?.savedValues) return s;
            return {
              drafts: {
                ...s.drafts,
                [id]: {
                  ...d,
                  values: d.savedValues,
                  localRevision: d.savedRevision,
                  saveStatus: "idle",
                  error: undefined,
                },
              },
            };
          }),
        reopen: (id, reason) =>
          set((s) => {
            const d = s.drafts[id];
            const m = d?.values.maintenance;
            if (!m || m.status !== "confirmed" || !reason.trim()) return s;
            const { revisions, ...snapshot } = m;
            const maintenance = {
              ...m,
              status: "draft" as const,
              confirmedAt: null,
              diagnosis: {
                ...m.diagnosis,
                final: { ...m.diagnosis.final, confirmedAt: null },
              },
              revisions: [
                ...revisions,
                {
                  at: new Date().toISOString(),
                  reason: reason.trim(),
                  snapshot: JSON.stringify(snapshot),
                },
              ],
            };
            return {
              drafts: {
                ...s.drafts,
                [id]: {
                  ...d,
                  values: { ...d.values, maintenance },
                  localRevision: d.localRevision + 1,
                  updatedAt: new Date().toISOString(),
                },
              },
            };
          }),
        openReport: (report) =>
          set((s) => ({
            activeReportId: report.id,
            drafts: s.drafts[report.id]
              ? s.drafts
              : {
                  ...s.drafts,
                  [report.id]: {
                    ...report,
                    serverId: report.id,
                    savedValues: report.values,
                    localRevision: 0,
                    savedRevision: 0,
                    serverVersion: report.version,
                    saveStatus: "idle",
                  },
                },
          })),
        patch: (id, input, baseRevision) => {
          const validated = reportPatchSchema.safeParse(input);
          if (!validated.success) return false;
          const patch = validated.data;
          const draft = get().drafts[id];
          if (!draft) return false;
          if (draft.values.maintenance?.status === "confirmed") return false;
          if (
            patch.maintenance &&
            draft.values.maintenance &&
            JSON.stringify(patch.maintenance.original) !==
              JSON.stringify(draft.values.maintenance.original)
          )
            return false;
          if (
            !patch.maintenance &&
            patch.symptom !== undefined &&
            draft.values.maintenance
          )
            patch.maintenance = invalidateCause({
              ...draft.values.maintenance,
              observations: {
                ...draft.values.maintenance.observations,
                symptoms: patch.symptom,
              },
            });
          if (
            baseRevision !== undefined &&
            draft.localRevision !== baseRevision
          )
            return false;
          if (
            Object.entries(patch).every(
              ([key, value]) =>
                draft.values[key as keyof ReportFields] === value,
            )
          )
            return true;
          set((s) => ({
            drafts: {
              ...s.drafts,
              [id]: {
                ...draft,
                values: { ...draft.values, ...patch },
                localRevision: draft.localRevision + 1,
                updatedAt: new Date().toISOString(),
                saveStatus:
                  draft.saveStatus === "conflict"
                    ? "conflict"
                    : draft.saveStatus === "saving"
                      ? "saving"
                      : "idle",
                error:
                  draft.saveStatus === "conflict" ? draft.error : undefined,
              },
            },
          }));
          return true;
        },
        markSaving: (id) =>
          set((s) => ({
            drafts: {
              ...s.drafts,
              [id]: { ...s.drafts[id], saveStatus: "saving", error: undefined },
            },
          })),
        markSaved: (id, revision, report) =>
          set((s) => {
            const draft = s.drafts[id];
            if (!draft) return s;
            return {
              drafts: {
                ...s.drafts,
                [id]: {
                  ...draft,
                  serverId: report.id,
                  savedRevision: revision,
                  savedValues: report.values,
                  serverVersion: report.version,
                  saveStatus: "idle",
                  error: undefined,
                },
              },
            };
          }),
        markError: (id, error, conflict = false) =>
          set((s) => ({
            drafts: {
              ...s.drafts,
              [id]: {
                ...s.drafts[id],
                saveStatus: conflict ? "conflict" : "error",
                error,
              },
            },
          })),
        replaceFromServer: (report) =>
          set((s) => ({
            drafts: {
              ...s.drafts,
              [report.id]: {
                id: report.id,
                serverId: report.id,
                equipmentId: report.equipmentId,
                values: report.values,
                savedValues: report.values,
                localRevision: 0,
                savedRevision: 0,
                serverVersion: report.version,
                updatedAt: report.updatedAt,
                saveStatus: "idle",
              },
            },
          })),
        rebase: (id, version) =>
          set((s) => ({
            drafts: {
              ...s.drafts,
              [id]: {
                ...s.drafts[id],
                serverVersion: version,
                localRevision: s.drafts[id].localRevision + 1,
                saveStatus: "idle",
                error: undefined,
              },
            },
          })),
      }),
      {
        name: "skadi-report-drafts-v1",
        version: 1,
        storage: createJSONStorage(() => storage),
        partialize: (s) => ({
          activeReportId: s.activeReportId,
          drafts: Object.fromEntries(
            Object.entries(s.drafts).map(([id, d]) => [
              id,
              { ...d, saveStatus: "idle", error: undefined },
            ]),
          ),
        }),
        merge: (persisted, current) => {
          const raw = persisted as
            | { activeReportId?: unknown; drafts?: Record<string, unknown> }
            | undefined;
          const drafts: Record<string, ReportDraft> = {};
          for (const [key, value] of Object.entries(raw?.drafts ?? {})) {
            const parsed = persistedDraftSchema.safeParse(value);
            if (parsed.success && parsed.data.id === key)
              drafts[key] = { ...parsed.data, saveStatus: "idle" };
          }
          return {
            ...current,
            drafts,
            activeReportId:
              typeof raw?.activeReportId === "string" &&
              drafts[raw.activeReportId]
                ? raw.activeReportId
                : null,
          };
        },
      },
    ),
    {
      ...devtoolsOptions("Report Drafts"),
      anonymousActionType: "report-drafts/update",
    },
  ),
);
