export type ComparisonSensorKind =
  "VIB" | "TB" | "TF" | "PS" | "PD" | "AMP" | "RPM" | "VOLT";

export const comparisonSensors: {
  id: ComparisonSensorKind;
  label: string;
  matches: (name: string) => boolean;
}[] = [
  { id: "VIB", label: "진동", matches: (name) => name.includes("진동") },
  {
    id: "TB",
    label: "베어링 온도",
    matches: (name) => name.includes("베어링 온도"),
  },
  {
    id: "TF",
    label: "유체 온도",
    matches: (name) => name.includes("유체 온도"),
  },
  { id: "PS", label: "흡입압", matches: (name) => name.includes("흡입압") },
  { id: "PD", label: "토출압", matches: (name) => name.includes("토출압") },
  { id: "AMP", label: "전류", matches: (name) => name.includes("전류") },
  { id: "RPM", label: "RPM", matches: (name) => name.includes("회전수") },
  { id: "VOLT", label: "전압", matches: (name) => name.includes("전압") },
];
