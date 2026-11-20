import { z } from "zod";

export const incidentStatusSchema = z.enum(["upcoming", "ongoing", "closed"]);
const level = z.number().int().min(0).max(4);

export const incidentSummarySchema = z.object({
  incident_id: z.string(),
  plant_id: z.string(),
  equipment_group_id: z.string(),
  equipment_id: z.string(),
  equipment_name: z.string(),
  status: incidentStatusSchema,
  incident_start_time: z.string(),
  detect_time: z.string(),
  first_alarm_time: z.string().nullable(),
  incident_end_time: z.string().nullable(),
  peak_level: level,
  lead_sensor_id: z.string().nullable(),
  lead_sensor_name: z.string().nullable(),
  diagnosis: z.string(),
  top_risk_fault: z.string(),
  top_cof: z.number(),
  top_pof: z.number(),
  incident_score: z.number(),
  alarm_grade: z.string(),
  grade_reason: z.string(),
  response_time_h: z.number(),
  actionable: z.boolean(),
  alarm_count: z.number().int(),
  linked_alarm_count: z.number().int(),
  trend_count: z.number().int(),
});

export const incidentListSchema = z.object({
  as_of: z.string(),
  items: z.array(incidentSummarySchema),
  next_cursor: z.string().nullable(),
});

export const incidentCandidateSchema = z.object({
  rank: z.number().int(),
  error_type_id: z.string(),
  fault: z.string(),
  score: z.number(),
  p: z.number(),
  cof: z.number(),
  pof: z.number(),
  rule_score_s: z.number(),
  speed: z.number(),
  impact: z.number(),
  pf_hours: z.number(),
  is_diagnosis: z.boolean(),
  is_top_risk: z.boolean(),
  evidence: z.string(),
});

export const incidentAlarmSchema = z.object({
  alarm_id: z.string(),
  source_alarm_id: z.string().nullable(),
  equipment_id: z.string(),
  sensor_id: z.string(),
  sensor_name: z.string(),
  setpoint_id: z.string().nullable(),
  event_type: z.enum(["예측", "임계치 초과"]).nullable(),
  alarm_level: level,
  peak_level: level.nullable(),
  alarm_start_time: z.string(),
  alarm_end_time: z.string().nullable(),
  sensor_start_time: z.string().nullable(),
  sensor_end_time: z.string().nullable(),
  cof_score: z.number().nullable(),
});

export const incidentDetailSchema = incidentSummarySchema.extend({
  as_of: z.string(),
  candidates: z.array(incidentCandidateSchema),
  alarms: z.array(incidentAlarmSchema),
  trend_window: z.object({
    from: z.string(),
    to: z.string(),
    signals: z.array(
      z.object({
        sensor_id: z.string(),
        measurement_name: z.string(),
        signal_id: z.string(),
        unit: z.string(),
      }),
    ),
  }),
  data_coverage: z.enum(["full", "partial", "none"]),
  warnings: z.array(z.string()),
});

export const incidentDraftSchema = z.object({
  incident_id: z.string(),
  equipment_id: z.string(),
  title: z.string(),
  symptom: z.string(),
  cause: z.string(),
  action: z.string(),
  risk: z.string(),
  suspected_error_type_ids: z.array(z.string()),
});

export const trendIncidentSchema = z.object({
  incident_id: z.string(),
  incident_start_time: z.string(),
  incident_end_time: z.string().nullable(),
  peak_level: level,
  diagnosis: z.string(),
  status: incidentStatusSchema,
});

export type IncidentStatus = z.infer<typeof incidentStatusSchema>;
export type IncidentSummary = z.infer<typeof incidentSummarySchema>;
export type IncidentList = z.infer<typeof incidentListSchema>;
export type IncidentDetail = z.infer<typeof incidentDetailSchema>;
export type IncidentCandidate = z.infer<typeof incidentCandidateSchema>;
export type IncidentAlarm = z.infer<typeof incidentAlarmSchema>;
export type IncidentDraft = z.infer<typeof incidentDraftSchema>;
export type TrendIncident = z.infer<typeof trendIncidentSchema>;
