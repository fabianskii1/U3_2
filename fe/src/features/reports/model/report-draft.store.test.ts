import { beforeEach, describe, it, expect } from "vitest";
import { useReportDraftStore as store } from "./report-draft.store.ts";
beforeEach(() => store.setState({ drafts: {}, activeReportId: null }));
describe("보고서 공통 초안", () => {
  it("채팅과 폼 변경을 같은 편집본에 반영한다", () => {
    const id = store.getState().createDraft("P-1101A", { title: "초안" });
    expect(store.getState().patch(id, { cause: "베어링 점검" }, 1)).toBe(true);
    expect(store.getState().drafts[id].values.cause).toBe("베어링 점검");
    expect(store.getState().drafts[id].localRevision).toBe(2);
  });
  it("늦게 도착한 Agent 수정이 추가 입력을 덮어쓰지 않는다", () => {
    const id = store.getState().createDraft("P-1101A");
    store.getState().patch(id, { cause: "사용자 입력" });
    expect(store.getState().patch(id, { cause: "Agent 수정" }, 1)).toBe(false);
    expect(store.getState().drafts[id].values.cause).toBe("사용자 입력");
  });
  it("저장 중 추가 입력이 있으면 저장 완료 후에도 dirty다", () => {
    const id = store.getState().createDraft("P-1101A");
    const snapshot = store.getState().drafts[id];
    store.getState().markSaving(id);
    store.getState().patch(id, { cause: "추가 입력" });
    store.getState().markSaved(id, snapshot.localRevision, {
      id,
      equipmentId: "P-1101A",
      values: snapshot.values,
      version: 1,
      updatedAt: new Date().toISOString(),
    });
    const d = store.getState().drafts[id];
    expect(d.localRevision).toBe(2);
    expect(d.savedRevision).toBe(1);
    expect(d.values.cause).toBe("추가 입력");
  });
  it("브라우저 복구 데이터에 입력을 즉시 저장한다", async () => {
    const id = store.getState().createDraft("P-1101A");
    store.getState().patch(id, { symptom: "종료 후에도 복원할 내용" });
    const persisted = localStorage.getItem("skadi-report-drafts-v1");
    expect(persisted).toContain("종료 후에도 복원할 내용");
    store.setState({ drafts: {}, activeReportId: null });
    localStorage.setItem("skadi-report-drafts-v1", persisted!);
    await store.persist.rehydrate();
    expect(store.getState().drafts[id].values.symptom).toBe(
      "종료 후에도 복원할 내용",
    );
  });
  it("별도 보고서를 생성해도 이전 보고서를 보존한다", () => {
    const a = store.getState().createDraft("P-1101A");
    const b = store.getState().createDraft("P-1501A");
    expect(Object.keys(store.getState().drafts)).toHaveLength(2);
    expect(store.getState().drafts[a].equipmentId).toBe("P-1101A");
    expect(store.getState().activeReportId).toBe(b);
  });
});
