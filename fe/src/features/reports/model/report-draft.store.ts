import { devtoolsOptions } from "../../../shared/lib/devtools.ts";
import { create } from "zustand";
import { devtools, persist, createJSONStorage } from "zustand/middleware";
import { z } from "zod";
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
});
type State = {
  activeReportId: string | null;
  drafts: Record<string, ReportDraft>;
  createDraft: (equipmentId: string, values?: Partial<ReportFields>) => string;
  openReport: (report: Report) => void;
  activate: (id: string) => void;
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
