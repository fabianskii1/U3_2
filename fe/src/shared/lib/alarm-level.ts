import type { Alarm } from "../api/contracts/alarm.ts";

const labels = ["정상", "주의", "경고", "위험", "비상"] as const;
export function alarmLabel(alarm: Alarm): string {
  return alarm.alarmLevel === undefined
    ? alarm.severity
    : labels[alarm.alarmLevel];
}
export function alarmFilterValue(alarm: Alarm): string {
  return alarm.alarmLevel === undefined
    ? alarm.severity
    : String(alarm.alarmLevel);
}
