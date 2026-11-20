import { hierarchy } from "./fixtures.ts";
import type {
  IncidentDetail,
  IncidentStatus,
} from "../src/shared/api/contracts/incident.ts";

const HOUR = 3600000;

/** Demo incidents anchored to the current time on mock equipment. */
function demoIncidents(now: number): IncidentDetail[] {
  const iso = (offsetHours: number) =>
    new Date(now + offsetHours * HOUR).toISOString();
  const base = (
    equipmentId: string,
    id: string,
    start: number,
    end: number,
    diagnosis: string,
    score: number,
  ) => {
    const equipment = hierarchy.equipment.find((e) => e.id === equipmentId)!;
    const tag = equipment.tags[0];
    return {
      incident_id: id,
      plant_id: equipment.plantId,
      equipment_group_id: equipment.unitId,
      equipment_id: equipment.id,
      equipment_name: equipment.name,
      status: "ongoing" as IncidentStatus,
      incident_start_time: iso(start),
      detect_time: iso(start + 3),
      first_alarm_time: iso(start + 4),
      incident_end_time: iso(end),
      peak_level: 3,
      lead_sensor_id: tag.id,
      lead_sensor_name: tag.name,
      diagnosis,
      top_risk_fault: diagnosis,
      top_cof: 1.0,
      top_pof: 0.069,
      incident_score: score,
      alarm_grade: "낮음",
      grade_reason: "작음 × 24시간 이상",
      response_time_h: 48,
      actionable: true,
      alarm_count: 1,
      linked_alarm_count: 1,
      trend_count: 1,
      as_of: iso(0),
      candidates: [
        {
          rank: 1,
          error_type_id: "1",
          fault: diagnosis,
          score,
          p: 0.5,
          cof: 1.0,
          pof: 0.069,
          rule_score_s: 6,
          speed: 1,
          impact: 2,
          pf_hours: 336,
          is_diagnosis: true,
          is_top_risk: true,
          evidence: "데모 근거 · 진동 +3.1 mm/s / 며칠에 걸쳐 진행",
        },
        {
          rank: 2,
          error_type_id: "2",
          fault: "임펠러 불균형",
          score: 0.3,
          p: 0.21,
          cof: 0.42,
          pof: 0.069,
          rule_score_s: 2.5,
          speed: 1,
          impact: 2,
          pf_hours: 336,
          is_diagnosis: false,
          is_top_risk: false,
          evidence: "데모 근거 · 진동 +3.1 / 흔들림 증가 없음",
        },
      ],
      alarms: [
        {
          alarm_id: `${id}-A1`,
          source_alarm_id: null,
          equipment_id: equipment.id,
          sensor_id: tag.id,
          sensor_name: tag.name,
          setpoint_id: null,
          event_type: "예측" as const,
          alarm_level: 2,
          peak_level: 3,
          alarm_start_time: iso(start + 4),
          alarm_end_time: iso(end - 0.1),
          sensor_start_time: null,
          sensor_end_time: null,
          cof_score: 1.0,
        },
      ],
      trend_window: {
        from: iso(start - 24),
        to: iso(Math.min(end + 6, 0)),
        signals: [
          {
            sensor_id: tag.id,
            measurement_name: tag.name,
            signal_id: tag.id,
            unit: tag.unit,
          },
        ],
      },
      data_coverage: "full" as const,
      warnings: [],
    };
  };
  return [
    base("P-1101A", "INC-DEMO-1101A", -30, 12, "베어링 마모", 0.8),
    {
      ...base("P-1301A", "INC-DEMO-1301A", -96, -60, "캐비테이션", 7.3),
      status: "closed" as IncidentStatus,
    },
  ];
}

function summary(item: IncidentDetail) {
  const {
    as_of: _asOf,
    candidates: _candidates,
    alarms: _alarms,
    trend_window: _window,
    data_coverage: _coverage,
    warnings: _warnings,
    ...rest
  } = item;
  return rest;
}

export function listIncidents(now: number, params: URLSearchParams) {
  const items = demoIncidents(now).filter(
    (item) =>
      (!params.get("equipment_id") ||
        item.equipment_id === params.get("equipment_id")) &&
      (!params.get("equipment_group_id") ||
        item.equipment_group_id === params.get("equipment_group_id")) &&
      (!params.get("plant_id") || item.plant_id === params.get("plant_id")) &&
      (!params.get("status") || item.status === params.get("status")) &&
      (!params.get("min_level") ||
        item.peak_level >= Number(params.get("min_level"))) &&
      (!params.get("actionable") ||
        String(item.actionable) === params.get("actionable")),
  );
  return {
    as_of: new Date(now).toISOString(),
    items: items.map(summary),
    next_cursor: null,
  };
}

export function getIncident(now: number, incidentId: string) {
  return demoIncidents(now).find((item) => item.incident_id === incidentId);
}

export function incidentDraft(now: number, incidentId: string) {
  const item = getIncident(now, incidentId);
  if (!item) return undefined;
  return {
    incident_id: item.incident_id,
    equipment_id: item.equipment_id,
    title: `${item.equipment_name} ${item.diagnosis} 의심 점검 보고서`,
    symptom: item.alarms
      .map((alarm) => `- ${alarm.sensor_name} ${alarm.event_type} 알람`)
      .join("\n"),
    cause:
      "검토 필요 · 분석기 원인 후보(추정)\n" +
      item.candidates
        .map((c) => `${c.rank}. ${c.fault} (점수 ${c.score}) — ${c.evidence}`)
        .join("\n"),
    action: "현장 점검 후 입력",
    risk: `대응 등급 ${item.alarm_grade} (${item.grade_reason})`,
    suspected_error_type_ids: item.candidates.map((c) => c.error_type_id),
  };
}
