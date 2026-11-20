import {
  CONSOLE_EXAMPLE_HOUR,
  CONSOLE_MAX_HOUR,
} from "./equipment-alarm-state.ts";

export function replayHourFromParams(params: URLSearchParams): number | null {
  const value = params.get("replay");
  if (value === "live") return null;
  if (value === null || value === "example") return CONSOLE_EXAMPLE_HOUR;
  if (!/^\d+$/.test(value)) return CONSOLE_EXAMPLE_HOUR;
  return Math.max(1, Math.min(CONSOLE_MAX_HOUR, Number(value)));
}
