import { validDateRange } from "../../../shared/lib/date-time.ts";

export const intervalSeconds = {
  "1s": 1,
  "5s": 5,
  "10s": 10,
  "30s": 30,
  "1m": 60,
  "5m": 300,
  "15m": 900,
  "30m": 1800,
  "1h": 3600,
  "3h": 10800,
  "6h": 21600,
  "12h": 43200,
  "1d": 86400,
} as const;
export type SensorInterval = keyof typeof intervalSeconds;
export type IntervalMode = "auto" | "1s" | "1m" | "1h" | "1d";
export const remoteTrendIntervals = ["1m", "1h", "1d"] as const;
export const MAX_TREND_POINTS = 10000;
export const intervalMode = (value: string | null): IntervalMode =>
  value === "1s" || value === "1m" || value === "1h" || value === "1d"
    ? value
    : "auto";
export function pointCount(from: string, to: string, interval: SensorInterval) {
  return (
    Math.floor(
      (Date.parse(to) - Date.parse(from)) / (intervalSeconds[interval] * 1000),
    ) + 1
  );
}
export function resolveInterval(
  mode: SensorInterval | "auto",
  from: string,
  to: string,
  available?: readonly SensorInterval[],
): SensorInterval {
  if (mode !== "auto" && (!available || available.includes(mode))) return mode;
  return (
    (available ?? (Object.keys(intervalSeconds) as SensorInterval[])).find(
      (interval) => pointCount(from, to, interval) <= 500,
    ) ?? "1d"
  );
}
export function intervalLabel(interval: SensorInterval) {
  const unit = interval.endsWith("s")
    ? "초"
    : interval.endsWith("m")
      ? "분"
      : interval.endsWith("h")
        ? "시간"
        : "일";
  return `${parseInt(interval)}${unit}`;
}

// Date-only links retain their original inclusive whole-day range.
export function trendRange(from: string, to: string) {
  const normalize = (value: string, end: boolean) =>
    value.length === 10
      ? `${value}T${end ? "23:59:59" : "00:00:00"}`
      : value.length === 16
        ? `${value}:00`
        : value;
  const start = normalize(from, false);
  const end = normalize(to, true);
  const validTime = (value: string) =>
    /^\d{4}-\d{2}-\d{2}T([01]\d|2[0-3]):[0-5]\d:[0-5]\d$/.test(value) &&
    validDateRange(value.slice(0, 10), value.slice(0, 10));
  const bounds = { from: `${start}+09:00`, to: `${end}+09:00` };
  return {
    ...bounds,
    inputFrom: start,
    inputTo: end,
    valid:
      validTime(start) &&
      validTime(end) &&
      Date.parse(bounds.from) < Date.parse(bounds.to),
  };
}
