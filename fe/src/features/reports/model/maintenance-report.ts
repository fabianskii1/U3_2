import type { Equipment } from "../../../shared/api/contracts/hierarchy.ts";
import type { Alarm } from "../../../shared/api/contracts/alarm.ts";
import type { Report } from "./report.schema.ts";
import type {
  MaintenanceReport,
  Inspection,
  ReportSensor,
} from "../../../shared/api/contracts/maintenance-report.ts";

export const reportStatusLabels = {
  draft: "작성 중",
  review: "검토 필요",
  confirmed: "확정",
} as const;
export const checkLabels = {
  unverified: "미확인",
  checking: "확인 중",
  excluded: "제외",
  verified: "확인됨",
} as const;
export function kstInput(value: string) {
  const time = Date.parse(value);
  return Number.isFinite(time)
    ? new Date(time + 9 * 3600_000).toISOString().slice(0, 16)
    : "";
}
export function fromKstInput(value: string) {
  return value ? `${value}:00+09:00` : "";
}
export function safeSourceHref(value: string): string | undefined {
  if (!value || /[\s\\<>]/.test(value)) return;
  if (/^\/(reports|trend|equip|alarms)(\/|\?|$)/.test(value)) return value;
  try {
    const url = new URL(value);
    if (
      ["https:", "http:"].includes(url.protocol) &&
      !url.username &&
      !url.password
    )
      return url.href;
  } catch {
    /* An unlinked source remains plain text. */
  }
}
export function finalCause(report: MaintenanceReport): string {
  const selected = report.diagnosis.final;
  return selected.candidateId === "other"
    ? selected.otherCause
    : (report.original.aiCandidates.find((c) => c.id === selected.candidateId)
        ?.label ?? "");
}
export function newInspection(candidateId = ""): Inspection {
  return {
    id: crypto.randomUUID(),
    candidateId,
    method: "",
    checkedAt: "",
    result: "",
    evidenceId: "",
    evidenceUrl: "",
  };
}
export function relatedSensors(
  equipment: Equipment,
  alarm?: Alarm,
  context = "",
) {
  const signals = /씰|누출|누유/.test(context)
    ? ["gas", "flow", "pressure", "speed"]
    : /캐비테이션/.test(context)
      ? ["vibration", "pressure", "speed"]
      : /모터|전기|전류/.test(context)
        ? ["current", "voltage", "temperature", "speed"]
        : /베어링|진동|정렬/.test(context)
          ? ["vibration", "temperature", "speed"]
          : [];
  return equipment.tags.filter(
    (tag) => tag.id === alarm?.tagId || signals.includes(tag.signal),
  );
}
export function createMaintenance(
  report: Report,
  equipment?: Equipment,
  alarm?: Alarm,
): MaintenanceReport {
  const now = new Date().toISOString();
  const tags = equipment
    ? relatedSensors(
        equipment,
        alarm,
        `${report.values.symptom} ${report.values.cause} ${alarm?.reason ?? ""}`,
      )
    : [];
  const sensors: ReportSensor[] = tags.map((tag) => ({
    id: tag.id,
    name: tag.name,
    unit: tag.unit,
    baseline: null,
    observed: tag.id === alarm?.tagId ? alarm.value : null,
  }));
  return {
    schemaVersion: 1,
    status: "draft",
    createdAt: report.updatedAt || now,
    original: {
      kind: alarm ? "connected" : "manual",
      capturedAt: now,
      alarm: alarm
        ? {
            id: alarm.id,
            equipmentId: alarm.equipmentId,
            sensorId: alarm.tagId,
            occurredAt: alarm.occurredAt,
            value: alarm.value,
            threshold: alarm.limit,
            unit: alarm.unit,
            reason: alarm.reason,
          }
        : null,
      aiCandidates: [],
      sensors,
      legacyCause: report.values.cause,
      legacyAction: report.values.action,
    },
    incident: {
      eventId: "",
      equipmentName: equipment?.name ?? report.equipmentId,
      alarmId: alarm?.id ?? "",
      alarmAt: alarm?.occurredAt ?? "",
      sensorIds: tags.map((tag) => tag.id),
      operatingConditions: "",
      location: "",
      manufacturer: "",
      model: "",
      recentMaintenance: "",
    },
    observations: {
      symptoms:
        report.values.symptom ||
        (alarm
          ? `${alarm.tagId}: ${alarm.value} ${alarm.unit} (기준 ${alarm.limit} ${alarm.unit})\n${alarm.reason}`
          : ""),
      impact: "",
    },
    diagnosis: {
      candidateChecks: {},
      inspections: [],
      final: {
        candidateId: null,
        otherCause: "",
        rationale: "",
        confirmedAt: null,
      },
    },
    manuals: [],
    work: {
      orderId: "",
      worker: "",
      startedAt: "",
      completedAt: "",
      description: "",
      parts: "",
    },
    review: {
      csvRange: "",
      evidence: [],
      pastCaseIds: "",
      recorder: "",
      reviewer: "",
      registeredAt: now,
      state: "pending",
    },
    confirmedAt: null,
    revisions: [],
  };
}
// Explicitly requested sample reports are kept separate from equipment observations.
export function createExample(
  report: Report,
  equipment: Equipment,
): MaintenanceReport {
  const model = createMaintenance(report, equipment);
  const at = new Date();
  at.setSeconds(0, 0);
  at.setMinutes(0);
  const alarmAt = at.toISOString();
  const candidates = [
    { id: "seal", label: "메커니컬 씰 손상", rank: 1, probability: 72 },
    { id: "oring", label: "O-ring 손상", rank: 2, probability: 18 },
    { id: "alignment", label: "정렬 불량", rank: 3, probability: 6 },
  ];
  const sensors = [
    {
      id: `DEMO-GD-${equipment.id}`,
      name: "가스 농도",
      unit: "%LEL",
      baseline: 0,
      observed: 15,
    },
    {
      id: `DEMO-FT-${equipment.id}`,
      name: "유량",
      unit: "m³/h",
      baseline: 45,
      observed: 45,
    },
    {
      id: `DEMO-RPM-${equipment.id}`,
      name: "회전수",
      unit: "rpm",
      baseline: 1780,
      observed: 1780,
    },
  ].map((s, index) => ({
    ...s,
    points: Array.from({ length: 31 }, (_, n) => ({
      time: new Date(at.getTime() + (n - 12) * 5 * 60_000).toISOString(),
      value:
        index === 0
          ? n < 12
            ? 0
            : Math.min(15, (n - 11) * 5)
          : Number(
              (
                s.baseline +
                Math.sin(n * 0.7) * (index === 1 ? 0.08 : 2)
              ).toFixed(2),
            ),
    })),
  }));
  model.original = {
    ...model.original,
    kind: "example",
    aiCandidates: candidates,
    sensors,
    alarm: {
      id: "DEMO-AL-013",
      equipmentId: equipment.id,
      sensorId: sensors[0].id,
      occurredAt: alarmAt,
      value: 15,
      threshold: 10,
      unit: "%LEL",
      reason: "예시: 가스 농도 상승",
    },
  };
  model.incident = {
    ...model.incident,
    eventId: "DEMO-SIM-013",
    alarmId: "DEMO-AL-013",
    alarmAt,
    sensorIds: sensors.map((s) => s.id),
    operatingConditions: "예시 운전 조건: 유체 45 °C / 1,780 rpm / 45 m³/h",
  };
  model.observations = {
    symptoms: "예시 관측: 가스 농도 0 → 15 %LEL 상승. 유량과 회전수 변화 미미.",
    impact: "미확인 · 실제 운전 영향은 현장 확인 후 입력하세요.",
  };
  model.manuals = [
    {
      id: "DEMO-MANUAL",
      title: "펌프 정비 매뉴얼 (연결 형식 예시)",
      revision: "",
      section: "씰 및 O-ring 점검",
      recommendation:
        "현장 점검 시 씰과 O-ring의 상태를 확인하고 관련 작업 표준을 참고합니다. 실제 정비 지침을 대신하지 않는 화면 예시입니다.",
      href: "",
    },
  ];
  return model;
}
export function causeConfirmationErrors(report: MaintenanceReport): string[] {
  const f = report.diagnosis.final;
  const errors: string[] = [];
  if (!f.candidateId || !finalCause(report).trim())
    errors.push("최종 고장 원인을 선택하거나 직접 입력해 주세요.");
  if (!f.rationale.trim()) errors.push("최종 원인 확정 근거를 입력해 주세요.");
  if (
    f.candidateId &&
    f.candidateId !== "other" &&
    report.diagnosis.candidateChecks[f.candidateId] !== "verified"
  )
    errors.push("선택한 후보의 확인 상태를 ‘확인됨’으로 변경해 주세요.");
  const verified = report.diagnosis.inspections.some(
    (i) =>
      i.candidateId === f.candidateId &&
      i.method.trim() &&
      i.checkedAt &&
      Number.isFinite(Date.parse(i.checkedAt)) &&
      i.result.trim(),
  );
  if (!verified)
    errors.push("선택한 원인에 대한 점검 방법·일시·결과를 기록해 주세요.");
  return errors;
}
export function reportConfirmationErrors(report: MaintenanceReport): string[] {
  const errors = causeConfirmationErrors(report);
  if (!report.diagnosis.final.confirmedAt)
    errors.push("현장 확인 후 ‘원인 확정’을 먼저 눌러 주세요.");
  if (!report.work.description.trim())
    errors.push("현장 실제 수행 조치를 입력해 주세요.");
  if (!report.work.worker.trim()) errors.push("작업자를 입력해 주세요.");
  if (!report.work.startedAt || !report.work.completedAt)
    errors.push("작업 시작·완료 시각을 입력해 주세요.");
  else if (
    Date.parse(report.work.completedAt) < Date.parse(report.work.startedAt)
  )
    errors.push("작업 완료 시각은 시작 시각 이후여야 합니다.");
  if (!report.review.recorder.trim()) errors.push("기록자를 입력해 주세요.");
  return errors;
}
export function invalidateCause(report: MaintenanceReport): MaintenanceReport {
  return {
    ...report,
    status: "draft",
    confirmedAt: null,
    diagnosis: {
      ...report.diagnosis,
      final: { ...report.diagnosis.final, confirmedAt: null },
    },
  };
}
