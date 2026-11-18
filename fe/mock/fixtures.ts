import type {
  Hierarchy,
  Equipment,
} from "../src/shared/api/contracts/hierarchy.ts";
import type { Alarm } from "../src/shared/api/contracts/alarm.ts";

// 공정 설명을 위한 합성 데이터다. 실제 운전 조건·알람 설정값을 뜻하지 않는다.
const processes = [
  {
    number: 1,
    name: "원유 공급",
    pump: "원유 공급 펌프",
    grade: "A",
    temperature: 130,
    temperatureLimit: 170,
    pressure: 12.5,
    pressureLimit: 16,
  },
  {
    number: 2,
    name: "탑 상부 납사·환류",
    pump: "납사·환류 펌프",
    grade: "A",
    temperature: 110,
    temperatureLimit: 150,
    pressure: 7.2,
    pressureLimit: 10,
  },
  {
    number: 3,
    name: "등유 측류",
    pump: "등유 측류 펌프",
    grade: "C",
    temperature: 190,
    temperatureLimit: 230,
    pressure: 6,
    pressureLimit: 9,
  },
  {
    number: 4,
    name: "경유 측류",
    pump: "경유 측류 펌프",
    grade: "B",
    temperature: 260,
    temperatureLimit: 300,
    pressure: 7,
    pressureLimit: 10,
  },
  {
    number: 5,
    name: "펌프어라운드 · 열 회수",
    pump: "펌프어라운드 펌프",
    grade: "B",
    temperature: 220,
    temperatureLimit: 270,
    pressure: 8,
    pressureLimit: 12,
  },
  {
    number: 6,
    name: "탑 하부 잔사유",
    pump: "고온 잔사유 펌프",
    grade: "A",
    temperature: 360,
    temperatureLimit: 390,
    pressure: 9.5,
    pressureLimit: 14,
  },
] as const;

const plants = [
  { id: "P-01", name: "CDU1", location: "X1Y1" },
  { id: "P-02", name: "CDU2", location: "X2Y1" },
];

export const hierarchy: Hierarchy = {
  plants,
  units: plants.flatMap((plant) =>
    processes.map((process) => ({
      id: `${plant.id}-P${process.number}`,
      name: `P${process.number} · ${process.name}`,
      plantId: plant.id,
    })),
  ),
  equipment: plants.flatMap((plant, plantIndex) =>
    processes.flatMap((process) =>
      ["A", "B"].map((suffix): Equipment => {
        const stem = `${plantIndex + 1}${process.number}01${suffix}`;
        const vibration =
          suffix === "A"
            ? process.number === 1
              ? 5.8
              : process.number === 3
                ? 4.7
                : process.number === 5
                  ? 5.2
                  : 2.8
            : 2.1;
        return {
          id: `P-${stem}`,
          name: `${process.pump} ${suffix}`,
          type: process.number === 5 ? "인버터 구동 원심 펌프" : "원심 펌프",
          grade: process.grade,
          plantId: plant.id,
          unitId: `${plant.id}-P${process.number}`,
          tags: [
            {
              id: `P${stem}-VIB`,
              signal: "vibration",
              name: "펌프 베어링 진동",
              unit: "mm/s",
              limit: 4.5,
              base: vibration,
            },
            {
              id: `P${stem}-TEMP`,
              signal: "temperature",
              name: "유체 온도",
              unit: "°C",
              limit: process.temperatureLimit,
              base: process.temperature,
            },
            {
              id: `P${stem}-PRES`,
              signal: "pressure",
              name: "토출 압력",
              unit: "bar",
              limit: process.pressureLimit,
              base: process.pressure,
            },
          ],
        };
      }),
    ),
  ),
};
export const valueAt = (base: number, now: number) =>
  Number(
    (base + Math.sin(Math.floor(now / 1000) / 5) * base * 0.025).toFixed(2),
  );
const demoReferenceTime = Date.now();
export function getAlarms(now = Date.now()): Alarm[] {
  return hierarchy.equipment
    .flatMap((eq) =>
      eq.tags
        .filter((t) => t.base! > t.limit!)
        .map((t) => ({
          id: `AL-${t.id}`,
          equipmentId: eq.id,
          tagId: t.id,
          signal: t.signal,
          severity:
            eq.grade === "A"
              ? ("High" as const)
              : eq.grade === "B"
                ? ("Medium" as const)
                : ("Low" as const),
          value: valueAt(t.base!, now),
          limit: t.limit!,
          unit: t.unit,
          occurredAt: new Date(
            demoReferenceTime -
              3600000 -
              (eq.grade.charCodeAt(0) - 65) * 600000,
          ).toISOString(),
          type: "Setpoint" as const,
          reason: `설비 등급 ${eq.grade} · 기준값 대비 ${Math.round((t.base! / t.limit! - 1) * 100)}% 초과`,
        })),
    )
    .sort(
      (a, b) =>
        ["High", "Medium", "Low"].indexOf(a.severity) -
        ["High", "Medium", "Low"].indexOf(b.severity),
    );
}
