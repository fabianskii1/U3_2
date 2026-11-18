import { z } from "zod";
export function dateTime(value: string) {
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(value));
}
export const dateOnly = (value: string) =>
  new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Seoul" }).format(
    new Date(value),
  );
export const defaultRange = () => ({
  from: dateOnly(new Date(Date.now() - 7 * 86400000).toISOString()),
  to: dateOnly(new Date().toISOString()),
});
export function dateBounds(from: string, to: string) {
  return { from: from + "T00:00:00+09:00", to: to + "T23:59:59+09:00" };
}

export function validDateRange(from: string, to: string) {
  return (
    z.iso.date().safeParse(from).success &&
    z.iso.date().safeParse(to).success &&
    from <= to
  );
}
