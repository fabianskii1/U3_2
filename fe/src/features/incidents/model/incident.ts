import type {
  IncidentStatus,
  IncidentSummary,
} from "../../../shared/api/contracts/incident.ts";

export const LEVEL_LABELS = ["정상", "주의", "경고", "위험", "비상"] as const;

export const STATUS_LABELS: Record<IncidentStatus, string> = {
  upcoming: "시작 전",
  ongoing: "진행 중",
  closed: "종료",
};

export function levelLabel(level: number | null | undefined): string {
  return level === null || level === undefined
    ? "미기록"
    : (LEVEL_LABELS[level] ?? "미기록");
}

/** Badge tone used by the existing alarm severity colors. */
export function levelTone(level: number): "High" | "Medium" | "Low" {
  return level >= 3 ? "High" : level === 2 ? "Medium" : "Low";
}

/** Analyzer evidence joins observations with " / ". */
export function splitEvidence(evidence: string): string[] {
  return evidence
    .split(" / ")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function formatGap(from: string, to: string | null): string | null {
  if (!to) return null;
  const minutes = Math.round((Date.parse(to) - Date.parse(from)) / 60000);
  if (!Number.isFinite(minutes) || minutes < 0) return null;
  const days = Math.floor(minutes / 1440);
  const hours = Math.floor((minutes % 1440) / 60);
  const rest = minutes % 60;
  if (days) return hours ? `${days}일 ${hours}시간` : `${days}일`;
  if (hours) return rest ? `${hours}시간 ${rest}분` : `${hours}시간`;
  return `${rest}분`;
}

export type TimelineStep = {
  key: string;
  label: string;
  time: string | null;
  gap: string | null;
};

export function timeline(incident: IncidentSummary): TimelineStep[] {
  const steps: [string, string, string | null][] = [
    ["start", "사건 시작", incident.incident_start_time],
    ["detect", "감지", incident.detect_time],
    ["alarm", "첫 알람", incident.first_alarm_time],
    [
      "end",
      incident.status === "closed" ? "종료" : "예상 종료",
      incident.incident_end_time,
    ],
  ];
  let previous: string | null = null;
  return steps.map(([key, label, time]) => {
    const gap = previous && time ? formatGap(previous, time) : null;
    if (time) previous = time;
    return { key, label, time, gap };
  });
}
