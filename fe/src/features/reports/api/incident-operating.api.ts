import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";
import { http } from "../../../shared/api/http-client.ts";
import type { IncidentDetail } from "../../../shared/api/contracts/incident.ts";
import type { Equipment } from "../../../shared/api/contracts/hierarchy.ts";
import type { OperatingReadings } from "../../../shared/api/contracts/maintenance-report.ts";

const samplesSchema = z.object({
  unit: z.string(),
  points: z.array(z.object({ time: z.string(), value: z.number().nullable() })),
});
export const incidentReferenceTime = (incident: IncidentDetail) =>
  [...incident.alarms].sort(
    (a, b) => Date.parse(a.alarm_start_time) - Date.parse(b.alarm_start_time),
  )[0]?.alarm_start_time ??
  incident.first_alarm_time ??
  incident.detect_time;

export const incidentOperatingQuery = (
  incident?: IncidentDetail,
  equipment?: Equipment,
) => {
  const at = incident ? incidentReferenceTime(incident) : "";
  return queryOptions({
    queryKey: ["incident-operating", incident?.incident_id, equipment?.id, at],
    enabled: !!incident && !!equipment,
    staleTime: Infinity,
    queryFn: async ({ signal }): Promise<OperatingReadings> => {
      if (!incident || !equipment || equipment.id !== incident.equipment_id)
        throw new Error("사건 설비를 확인해 주세요.");
      const reference = Date.parse(at);
      const result: OperatingReadings = {
        referenceTime: at,
        lookbackMinutes: 5,
        readings: [],
        missing: [],
        failed: [],
      };
      if (!Number.isFinite(reference) || reference > Date.now()) {
        result.missing = equipment.tags.map((tag) => tag.name);
        return result;
      }
      const start = reference - 5 * 60000;
      const rows = await Promise.allSettled(
        equipment.tags.map(async (tag) => {
          const data = samplesSchema.parse(
            (
              await http.get("/trend", {
                params: {
                  sensor_id: tag.id,
                  from: new Date(start).toISOString(),
                  to: new Date(reference + 1).toISOString(),
                  interval: "1m",
                },
                signal,
              })
            ).data,
          );
          const latest = data.points
            .filter(
              (point) =>
                point.value !== null &&
                Number.isFinite(point.value) &&
                Date.parse(point.time) >= start &&
                Date.parse(point.time) <= reference,
            )
            .sort((a, b) => Date.parse(b.time) - Date.parse(a.time))[0];
          return latest
            ? {
                sensorId: tag.id,
                name: tag.name,
                unit: data.unit,
                value: latest.value!,
                measuredAt: latest.time,
              }
            : null;
        }),
      );
      rows.forEach((row, index) => {
        if (row.status === "rejected")
          result.failed.push(equipment.tags[index].name);
        else if (row.value) result.readings.push(row.value);
        else result.missing.push(equipment.tags[index].name);
      });
      return result;
    },
  });
};

const kst = (at: string) =>
  new Date(at).toLocaleString("ko-KR", {
    timeZone: "Asia/Seoul",
    hour12: false,
  });
export function operatingConditionsText(snapshot?: OperatingReadings): string {
  if (!snapshot?.readings.length) return "";
  return [
    `사건 기준 ${kst(snapshot.referenceTime)} KST · 직전 ${snapshot.lookbackMinutes}분 이내 저장값`,
    ...snapshot.readings.map(
      (row) =>
        `${row.name}: ${row.value.toLocaleString("ko-KR", { maximumFractionDigits: 6 })} ${row.unit} (측정 ${kst(row.measuredAt)} KST)`,
    ),
  ].join("\n");
}
export function operatingConditionsNote(snapshot?: OperatingReadings): string {
  if (!snapshot) return "사건 시점의 저장 데이터를 확인하지 못했습니다.";
  return [
    !snapshot.readings.length
      ? "기준 시점 직전 5분에 유효한 저장값이 없습니다."
      : "",
    snapshot.missing.length ? `미수집: ${snapshot.missing.join(" · ")}` : "",
    snapshot.failed.length ? `조회 실패: ${snapshot.failed.join(" · ")}` : "",
  ]
    .filter(Boolean)
    .join(" · ");
}
