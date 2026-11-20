import { beforeEach, describe, expect, it } from "vitest";
import {
  createExample,
  createMaintenance,
  causeConfirmationErrors,
  finalCause,
  invalidateCause,
  newInspection,
  reportConfirmationErrors,
  safeSourceHref,
} from "./maintenance-report.ts";
import { useReportDraftStore as store } from "./report-draft.store.ts";
import { emptyFields, type Report } from "./report.schema.ts";
import type { Equipment } from "../../../shared/api/contracts/hierarchy.ts";
import type { Alarm } from "../../../shared/api/contracts/alarm.ts";
import { maintenanceReportSchema } from "../../../shared/api/contracts/maintenance-report.ts";
const equipment: Equipment = {
  id: "P1",
  name: "원유 공급 펌프",
  type: "펌프",
  grade: "1",
  unitId: "CUD-01",
  plantId: "PLANT-01",
  tags: [],
};
const report: Report = {
  id: "r1",
  equipmentId: "P1",
  values: { ...emptyFields },
  version: 1,
  updatedAt: "2026-11-19T00:00:00Z",
};
beforeEach(() => store.setState({ drafts: {}, activeReportId: null }));
describe("현장 원인 확인과 전체 보고서", () => {
  it("측정값이 없는 연결 알람도 원본 정보와 센서를 보존한다", () => {
    const alarm: Alarm = {
      id: "a1",
      equipmentId: "P1",
      tagId: "T1",
      signal: "vibration",
      severity: "High",
      unit: "mm/s",
      occurredAt: "2026-11-19T00:00:00Z",
      type: "threshold",
      reason: "진동 확인 필요",
    };
    const model = createMaintenance(
      report,
      {
        ...equipment,
        tags: [{ id: "T1", name: "진동", signal: "vibration", unit: "mm/s" }],
      },
      alarm,
    );
    expect(model.original.alarm).toMatchObject({
      id: "a1",
      value: null,
      threshold: null,
    });
    expect(model.original.sensors[0].observed).toBeNull();
    expect(model.observations.symptoms).not.toContain("undefined");
    expect(maintenanceReportSchema.safeParse(model).success).toBe(true);
  });
  it("AI 1순위를 확정하지 않고 실제 수행 조치를 비워 둔다", () => {
    const m = createExample(report, equipment);
    expect(m.original.aiCandidates[0].id).toBe("seal");
    expect(m.diagnosis.final.candidateId).toBeNull();
    expect(m.diagnosis.final.confirmedAt).toBeNull();
    expect(m.work.description).toBe("");
    expect(reportConfirmationErrors(m).length).toBeGreaterThan(0);
  });
  it("AI 2순위를 점검 근거와 함께 실제 원인으로 확정할 수 있다", () => {
    const m = createExample(report, equipment);
    m.diagnosis.final = {
      candidateId: "oring",
      otherCause: "",
      rationale: "분해 점검으로 O-ring 균열 확인",
      confirmedAt: null,
    };
    m.diagnosis.candidateChecks = { seal: "excluded", oring: "verified" };
    expect(causeConfirmationErrors(m)).not.toHaveLength(0);
    m.diagnosis.inspections = [
      {
        ...newInspection("oring"),
        method: "분해 점검",
        checkedAt: "2026-11-19T09:00:00+09:00",
        result: "O-ring 균열 확인",
      },
    ];
    expect(causeConfirmationErrors(m)).toEqual([]);
    expect(finalCause(m)).toBe("O-ring 손상");
    expect(m.original.aiCandidates[0].id).toBe("seal");
    expect(reportConfirmationErrors(m)).toContain(
      "현장 실제 수행 조치를 입력해 주세요.",
    );
  });
  it("기타 원인에는 직접 입력과 해당 원인의 현장 검증이 필요하다", () => {
    const m = createMaintenance(report, equipment);
    m.diagnosis.final.candidateId = "other";
    m.diagnosis.final.rationale = "점검 기록 E-1";
    expect(causeConfirmationErrors(m).length).toBe(2);
    m.diagnosis.final.otherCause = "배관 플랜지 가스켓 파손";
    m.diagnosis.inspections = [
      {
        ...newInspection("other"),
        method: "누설 검사",
        checkedAt: "2026-11-19T09:00:00+09:00",
        result: "가스켓 파손 확인",
      },
    ];
    expect(causeConfirmationErrors(m)).toEqual([]);
  });
  it("근거를 수정하면 원인 확정을 해제한다", () => {
    const m = createExample(report, equipment);
    m.status = "review";
    m.diagnosis.final.confirmedAt = "2026-11-19T09:00:00+09:00";
    const changed = invalidateCause(m);
    expect(changed.diagnosis.final.confirmedAt).toBeNull();
    expect(changed.status).toBe("draft");
  });
  it("다섯 영역과 확정 상태를 브라우저에서 복구하고 수집 원본 덮어쓰기를 거절한다", async () => {
    const id = store.getState().createDraft("P1");
    const m = createExample(report, equipment);
    store.getState().initializeMaintenance(id, m);
    const changed = { ...m, work: { ...m.work, description: "가스켓 교체" } };
    expect(store.getState().patch(id, { maintenance: changed })).toBe(true);
    const forged = {
      ...changed,
      original: { ...changed.original, aiCandidates: [] },
    };
    expect(store.getState().patch(id, { maintenance: forged })).toBe(false);
    const persisted = localStorage.getItem("skadi-report-drafts-v1")!;
    store.setState({ drafts: {}, activeReportId: null });
    localStorage.setItem("skadi-report-drafts-v1", persisted);
    await store.persist.rehydrate();
    const restored = store.getState().drafts[id].values.maintenance!;
    expect(restored.work.description).toBe("가스켓 교체");
    expect(restored.original.aiCandidates).toEqual(m.original.aiCandidates);
    expect(restored.original.sensors).toEqual(m.original.sensors);
  });
  it("확정 후에는 채팅·직접 수정을 잠그고 사유가 있어야 이전 내용을 보존하며 다시 연다", () => {
    const id = store.getState().createDraft("P1");
    const m = createExample(report, equipment);
    m.status = "confirmed";
    m.confirmedAt = "2026-11-19T09:00:00Z";
    store.getState().initializeMaintenance(id, m);
    expect(store.getState().patch(id, { action: "임의 변경" })).toBe(false);
    store.getState().reopen(id, "");
    expect(store.getState().drafts[id].values.maintenance?.status).toBe(
      "confirmed",
    );
    store.getState().reopen(id, "교체 부품 정보 보완");
    const current = store.getState().drafts[id].values.maintenance!;
    expect(current.status).toBe("draft");
    expect(current.revisions[0].reason).toBe("교체 부품 정보 보완");
    expect(JSON.parse(current.revisions[0].snapshot).status).toBe("confirmed");
  });
  it("취소 시 마지막 저장된 다섯 영역 전체로 복원한다", () => {
    const id = store.getState().createDraft("P1");
    const m = createExample(report, equipment);
    store.getState().initializeMaintenance(id, m);
    store
      .getState()
      .patch(id, {
        maintenance: { ...m, work: { ...m.work, description: "취소할 입력" } },
      });
    store.getState().restoreSaved(id);
    expect(
      store.getState().drafts[id].values.maintenance?.work.description,
    ).toBe("");
  });
  it("증거 링크는 지원하는 문서 주소만 연다", () => {
    expect(safeSourceHref("javascript:alert(1)")).toBeUndefined();
    expect(safeSourceHref("//external.test")).toBeUndefined();
    expect(safeSourceHref("/reports/123")).toBe("/reports/123");
    expect(safeSourceHref("https://example.com/manual.pdf")).toBe(
      "https://example.com/manual.pdf",
    );
  });
});
