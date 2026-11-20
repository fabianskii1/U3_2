import type { Equipment } from "../../../shared/api/contracts/hierarchy.ts";
import type {
  IncidentDetail,
  IncidentDraft,
} from "../../../shared/api/contracts/incident.ts";
import type { ReportFields } from "./report.schema.ts";
import {
  operatingConditionsText,
  operatingConditionsNote,
} from "../api/incident-operating.api.ts";
import type { OperatingReadings } from "../../../shared/api/contracts/maintenance-report.ts";
import type { MaintenanceReport } from "../../../shared/api/contracts/maintenance-report.ts";
import { createMaintenance } from "./maintenance-report.ts";
import {
  applyReportReferences,
  type ReportReferences,
} from "../api/report-references.api.ts";

/** Carry the selected incident into an editable report without asserting a final cause. */
export function incidentReportFields(
  incident: IncidentDetail,
  draft: IncidentDraft,
  equipment: Equipment,
  references?: ReportReferences,
  operating?: OperatingReadings,
): ReportFields & { maintenance: MaintenanceReport } {
  if (
    draft.incident_id !== incident.incident_id ||
    draft.equipment_id !== incident.equipment_id ||
    equipment.id !== incident.equipment_id
  )
    throw new Error(
      "사건과 보고서의 설비가 일치하지 않습니다. 사건을 다시 열어 주세요.",
    );
  const values = {
    title: draft.title.slice(0, 200),
    symptom: draft.symptom,
    cause: draft.cause,
    action: draft.action,
    risk: draft.risk,
    chartUrl: `/incidents/${encodeURIComponent(incident.incident_id)}?section=trend`,
  };
  const now = new Date().toISOString();
  const model = applyReportReferences(
    createMaintenance(
      {
        id: incident.incident_id,
        equipmentId: equipment.id,
        values,
        version: 0,
        updatedAt: now,
      },
      equipment,
    ),
    references,
  );
  const alarms = [...incident.alarms].sort(
    (a, b) => Date.parse(a.alarm_start_time) - Date.parse(b.alarm_start_time),
  );
  const firstAlarm = alarms[0];
  const ids = [
    ...new Set([
      ...(incident.lead_sensor_id ? [incident.lead_sensor_id] : []),
      ...incident.trend_window.signals.map((signal) => signal.sensor_id),
      ...alarms.map((alarm) => alarm.sensor_id),
    ]),
  ];
  const href = `/incidents/${encodeURIComponent(incident.incident_id)}`;
  return {
    ...values,
    maintenance: {
      ...model,
      original: {
        ...model.original,
        kind: "connected",
        incident: structuredClone(incident),
        operatingReadings: operating,
        fieldNotes: {
          ...model.original.fieldNotes,
          operatingConditions: operatingConditionsNote(operating),
        },
        alarm: firstAlarm
          ? {
              id: firstAlarm.alarm_id,
              equipmentId: incident.equipment_id,
              sensorId: firstAlarm.sensor_id,
              occurredAt: firstAlarm.alarm_start_time,
              value: null,
              threshold: null,
              unit:
                equipment.tags.find((tag) => tag.id === firstAlarm.sensor_id)
                  ?.unit ?? "",
              reason: `${firstAlarm.sensor_name} · ${firstAlarm.event_type ?? "알람"}`,
            }
          : null,
        aiCandidates: incident.candidates.map((candidate) => ({
          id: candidate.error_type_id,
          label: candidate.fault,
          rank: candidate.rank,
          probability: candidate.p * 100,
        })),
        sensors: ids.map((id) => {
          const signal = incident.trend_window.signals.find(
            (signal) => signal.sensor_id === id,
          );
          const tag = equipment.tags.find((tag) => tag.id === id);
          return {
            id,
            name: signal?.measurement_name ?? tag?.name ?? id,
            unit: signal?.unit ?? tag?.unit ?? "",
            baseline: null,
            observed: null,
          };
        }),
        referenceNotes: [
          ...(model.original.referenceNotes ?? []),
          ...incident.warnings,
        ],
      },
      incident: {
        ...model.incident,
        eventId: incident.incident_id,
        equipmentName: incident.equipment_name,
        alarmId: firstAlarm?.alarm_id ?? "",
        alarmAt:
          firstAlarm?.alarm_start_time ?? incident.first_alarm_time ?? "",
        sensorIds: ids,
        operatingConditions: operatingConditionsText(operating),
      },
      diagnosis: {
        ...model.diagnosis,
        candidateChecks: Object.fromEntries(
          incident.candidates.map((candidate) => [
            candidate.error_type_id,
            "unverified" as const,
          ]),
        ),
      },
      review: {
        ...model.review,
        csvRange: `${incident.trend_window.from} ~ ${incident.trend_window.to}`,
        evidence: [
          { id: incident.incident_id, title: "이상 사건 상세", href },
          {
            id: `${incident.incident_id}-causes`,
            title: "진단 후보와 분석 근거",
            href: `${href}?section=causes`,
          },
          {
            id: `${incident.incident_id}-alarms`,
            title: "사건 관련 알람",
            href: `${href}?section=alarms`,
          },
          {
            id: `${incident.incident_id}-trend`,
            title: "사건 구간 트렌드",
            href: `${href}?section=trend`,
          },
        ],
      },
    },
  };
}
