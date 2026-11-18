import { it, expect } from "vitest";
import { answerChat } from "./chat.ts";
import { emptyFields } from "../src/features/reports/model/report.schema.ts";
const context = {
  sessionId: "test",
  screenContext: { page: "/reports/R1", equipmentId: "P-1101A" },
  reportContext: {
    reportId: "R1",
    equipmentId: "P-1101A",
    localRevision: 12,
    values: { ...emptyFields, title: "유지할 제목" },
  },
};
it("명시한 필드만 수정하고 기준 편집본을 전달한다", () => {
  const response = answerChat({
    ...context,
    message: '추정 원인을 "축 정렬 불량 의심"으로 수정해줘',
  });
  expect(response.action).toEqual({
    type: "patch-draft",
    reportId: "R1",
    baseLocalRevision: 12,
    patch: { cause: "축 정렬 불량 의심" },
  });
});
it("대상 보고서가 없으면 수정을 실행하지 않는다", () => {
  expect(
    answerChat({
      sessionId: "t",
      screenContext: { page: "/dashboard", equipmentId: null },
      message: '추정 원인을 "원인"으로 수정해줘',
    }).action,
  ).toBeUndefined();
});
it("초안 생성에 현장 미확인 리스크를 남긴다", () => {
  const response = answerChat({ ...context, message: "보고서 초안 생성해줘" });
  expect(response.action?.type).toBe("create-draft");
  if (response.action?.type === "create-draft")
    expect(response.action.values.risk).toContain("미확정");
});
