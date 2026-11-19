import type { ReportFields } from "../../../shared/api/contracts/report.ts";
export * from "../../../shared/api/contracts/report.ts";
export const emptyFields: ReportFields = {
  title: "",
  symptom: "",
  cause: "",
  action: "",
  chartUrl: "",
  risk: "",
};
export const fieldLabels: Record<
  Exclude<keyof ReportFields, "maintenance">,
  string
> = {
  title: "보고서 제목",
  symptom: "이상 현상",
  cause: "추정 원인",
  action: "조치 내역",
  chartUrl: "첨부 차트 링크",
  risk: "남은 리스크",
};
