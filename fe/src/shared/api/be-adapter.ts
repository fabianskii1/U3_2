import { z } from "zod";
import type { Hierarchy } from "./contracts/hierarchy.ts";
import type { Alarm } from "./contracts/alarm.ts";
import type { Report } from "./contracts/report.ts";

export const remoteApi = import.meta.env.VITE_API_MODE === "remote";
function sensorSignal(name: string): string {
  if (name.includes("진동")) return "vibration";
  if (name.includes("온도")) return "temperature";
  if (name.includes("압")) return "pressure";
  if (name.includes("전류")) return "current";
  if (name.includes("전압")) return "voltage";
  if (name.includes("회전수")) return "speed";
  return name;
}
const id = z.string();
const sensor = z.object({
  sensor_id: id,
  equipment_id: id,
  measurement_name: z.string(),
  unit: z.string(),
  current_value: z.number().nullable().optional(),
  measured_at: z.string().nullable().optional(),
  threshold_value: z.number().nullable().optional(),
});
const equipment = z.object({
  equipment_id: id,
  plant_id: id,
  equipment_group_id: id,
  equipment_name: z.string(),
  equipment_type: z.string(),
  equipment_status: z.number().int().min(0).max(4),
  equipment_level: z.number().int(),
  location: z.string().nullable(),
  sensors: z.array(sensor),
});
const hierarchy = z.object({
  plants: z.array(
    z.object({ plant_id: id, plant_name: z.string(), location: z.string() }),
  ),
  units: z.array(
    z.object({
      equipment_group_id: id,
      plant_id: id,
      equipment_group_name: z.string(),
      process_type: z.string().nullable(),
    }),
  ),
  equipment: z.array(equipment),
});
const alarm = z.object({
  alarm_id: id,
  equipment_id: id,
  sensor_id: id,
  alarm_type: z.string(),
  alarm_start_time: z.string(),
  unit: z.string(),
  alarm_level: z.number().int().min(0).max(4),
  user_message: z.string(),
});
const report = z.object({
  report_id: id,
  equipment_id: id,
  title: z.string(),
  symptom: z.string(),
  cause: z.string(),
  action: z.string(),
  chart_url: z.string().nullable(),
  risk: z.string(),
  version: z.number().int(),
  updated_at: z.string(),
});
export const beReportList = z.object({
  items: z.array(report),
  next_cursor: z.string().nullable(),
});
export const beAlarmSnapshot = z.object({
  alarms: z.array(alarm),
  as_of: z.string(),
  cursor: z.string(),
});
export const beTrend = z.object({
  sensor_id: id,
  interval: z.string(),
  unit: z.string(),
  as_of: z.string(),
  threshold_value: z.number().nullable().optional(),
  points: z.array(
    z.object({
      time: z.string(),
      value: z.number().nullable(),
      quality: z.string().nullable(),
    }),
  ),
});
export function mapEquipment(data: unknown): Hierarchy["equipment"][number] {
  const raw = equipment.parse(data);
  return {
    id: raw.equipment_id,
    name: raw.equipment_name,
    type: raw.equipment_type,
    grade: String(raw.equipment_level),
    equipmentLevel: raw.equipment_level,
    equipmentStatus: raw.equipment_status,
    unitId: raw.equipment_group_id,
    plantId: raw.plant_id,
    tags: raw.sensors.map((s) => ({
      id: s.sensor_id,
      signal: sensorSignal(s.measurement_name),
      name: s.measurement_name,
      unit: s.unit,
      currentValue: s.current_value ?? null,
      measuredAt: s.measured_at ?? null,
      limit: s.threshold_value ?? undefined,
    })),
  };
}
export function mapHierarchy(data: unknown): Hierarchy {
  const raw = hierarchy.parse(data);
  return {
    plants: raw.plants.map((p) => ({
      id: p.plant_id,
      name: p.plant_name,
      location: p.location,
    })),
    units: raw.units.map((u) => ({
      id: u.equipment_group_id,
      name: u.equipment_group_name,
      plantId: u.plant_id,
      processType: u.process_type,
    })),
    equipment: raw.equipment.map(mapEquipment),
  };
}
export function mapAlarm(data: unknown, sensors: Hierarchy): Alarm {
  const raw = alarm.parse(data);
  const s = sensors.equipment
    .flatMap((e) => e.tags)
    .find((t) => t.id === raw.sensor_id);
  return {
    id: raw.alarm_id,
    equipmentId: raw.equipment_id,
    tagId: raw.sensor_id,
    signal: s?.signal ?? "",
    severity:
      raw.alarm_level >= 3 ? "High" : raw.alarm_level === 2 ? "Medium" : "Low",
    alarmLevel: raw.alarm_level,
    unit: raw.unit,
    occurredAt: raw.alarm_start_time,
    type: raw.alarm_type,
    reason: raw.user_message,
  };
}
export function mapReport(data: unknown): Report {
  const raw = report.parse(data);
  return {
    id: raw.report_id,
    equipmentId: raw.equipment_id,
    version: raw.version,
    updatedAt: raw.updated_at,
    values: {
      title: raw.title,
      symptom: raw.symptom,
      cause: raw.cause,
      action: raw.action,
      chartUrl: raw.chart_url ?? "",
      risk: raw.risk,
    },
  };
}
