import type { Alarm } from "../../../shared/api/contracts/alarm.ts";
import type { Equipment } from "../../../shared/api/contracts/hierarchy.ts";
import consoleLevels from "./console-levels.json";

const severityLevel = { High: 3, Medium: 2, Low: 1 } as const;
export const levelLabels = ["정상", "주의", "경고", "위험", "비상"] as const;
export const CONSOLE_EXAMPLE_HOUR = 441; // 2026-11-19 09:00 KST, matching the console example.
export const CONSOLE_MAX_HOUR = consoleLevels.NH;

export type ConsoleTrackSegment = {
  start: number;
  end: number;
  level: number;
};

export const consolePumpTracks = Object.entries(consoleLevels.pumps).map(
  ([id, pump]) => {
    const segments: ConsoleTrackSegment[] = [];
    for (let hour = 0; hour < CONSOLE_MAX_HOUR; hour++) {
      const index = hour - pump.off;
      const level =
        index < 0 || index >= pump.nh
          ? 0
          : pump.run[index] !== "1"
            ? -1
            : Number(pump.Mc[index] ?? 0);
      if (level === 0) continue;
      const last = segments.at(-1);
      if (last?.level === level && last.end === hour) last.end = hour + 1;
      else segments.push({ start: hour, end: hour + 1, level });
    }
    return { id, segments };
  },
);

const consoleStart = Date.parse(
  `${consoleLevels.t0.replace(" ", "T")}:00+09:00`,
);

export function consoleHourDate(hour: number): Date {
  return new Date(consoleStart + hour * 60 * 60 * 1000);
}

export function hasConsoleTimeline(equipment: Equipment): boolean {
  return equipment.unitId === "CDU-01" && equipment.id in consoleLevels.pumps;
}

function consoleSensorKey(tag: Equipment["tags"][number]): string | null {
  const name = tag.name.toLowerCase();
  if (/진동|\bvt\b/.test(name) || /-VT-/.test(tag.id)) return "VIB";
  if (/베어링.?온도/.test(name) || /-TT-\d?102$/.test(tag.id)) return "TB";
  if (/유체.?온도/.test(name) || /-TT-\d?101$/.test(tag.id)) return "TF";
  if (/흡입압/.test(name) || /-PT-\d?106$/.test(tag.id)) return "PS";
  if (/토출압/.test(name) || /-PT-\d?107$/.test(tag.id)) return "PD";
  if (/전류/.test(name) || /-IT-/.test(tag.id)) return "AMP";
  if (/회전수|rpm/.test(name) || /-ST-/.test(tag.id)) return "RPM";
  if (/전압/.test(name) || /-ET-/.test(tag.id)) return "VOLT";
  return null;
}

function replayState(equipment: Equipment, hour: number) {
  if (!hasConsoleTimeline(equipment)) return null;
  const pump =
    consoleLevels.pumps[equipment.id as keyof typeof consoleLevels.pumps];
  const index = hour - pump.off - 1;
  if (index < 0 || index >= pump.nh || pump.run[index] !== "1") {
    return {
      level: 0,
      predicted: false,
      sensorLevels: new Map<string, number>(),
      sensorPredictions: new Set<string>(),
    };
  }
  const level = Number(pump.Mc[index] ?? 0);
  const predicted = level > Number(pump.Mt[index] ?? 0);
  const sensorLevels = new Map<string, number>();
  const sensorPredictions = new Set<string>();
  for (const tag of equipment.tags) {
    const key = consoleSensorKey(tag) as keyof typeof pump.L | null;
    if (key && pump.L[key]) {
      const current = Number(pump.L[key].c[index] ?? 0);
      sensorLevels.set(tag.id, current);
      if (current > Number(pump.L[key].t[index] ?? 0))
        sensorPredictions.add(tag.id);
    }
  }
  return { level, predicted, sensorLevels, sensorPredictions };
}

export function alarmLevel(alarm: Alarm): number {
  return alarm.alarmLevel ?? severityLevel[alarm.severity];
}

export function isCurrentAlarm(alarm: Alarm, asOf?: Date): boolean {
  if (asOf) {
    const moment = asOf.getTime();
    return (
      Date.parse(alarm.occurredAt) <= moment &&
      (alarm.endedAt == null || moment <= Date.parse(alarm.endedAt))
    );
  }
  // Mock alarms have no activity metadata; remote history has an explicit state.
  return alarm.isActive === undefined
    ? !alarm.endedAt
    : alarm.isActive === true;
}

export function equipmentAlarmState(
  equipment: Equipment,
  alarms: Alarm[],
  replayHour?: number | null,
) {
  const asOf = replayHour == null ? undefined : consoleHourDate(replayHour);
  const active = alarms.filter(
    (alarm) =>
      alarm.equipmentId === equipment.id && isCurrentAlarm(alarm, asOf),
  );
  const replay = replayHour == null ? null : replayState(equipment, replayHour);
  if (replay) return { ...replay, active };
  const baseLevel = equipment.equipmentStatus ?? 0;
  const highestAlarm = Math.max(0, ...active.map(alarmLevel));
  const level = Math.max(baseLevel, highestAlarm);
  const predicted = active.some(
    (alarm) => alarm.eventType === "예측" && alarmLevel(alarm) === level,
  );
  const sensorLevels = new Map<string, number>();
  const sensorPredictions = new Set<string>();
  for (const alarm of active) {
    sensorLevels.set(
      alarm.tagId,
      Math.max(sensorLevels.get(alarm.tagId) ?? 0, alarmLevel(alarm)),
    );
    if (alarm.eventType === "예측") sensorPredictions.add(alarm.tagId);
  }
  return { level, predicted, active, sensorLevels, sensorPredictions };
}
