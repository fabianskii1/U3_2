import { describe, expect, it } from "vitest";
import { mapAlarm, mapHierarchy, mapReport } from "./be-adapter.ts";

describe("BE 응답 변환", () => {
  const hierarchy = mapHierarchy({
    plants: [
      {
        plant_id: "PLANT-01",
        plant_name: "울산",
        location: "울산광역시 남구 신정동",
      },
    ],
    units: [
      {
        equipment_group_id: "20",
        plant_id: "9007199254740993",
        equipment_group_name: "CDU",
      },
    ],
    equipment: [
      {
        equipment_id: "30",
        plant_id: "9007199254740993",
        equipment_group_id: "20",
        equipment_name: "펌프",
        equipment_type: "펌프",
        equipment_status: 3,
        equipment_level: 5,
        location: null,
        sensors: [
          {
            sensor_id: "40",
            equipment_id: "30",
            measurement_name: "진동 속도 RMS",
            unit: "mm/s RMS",
            current_value: null,
            threshold_value: null,
          },
        ],
      },
    ],
  });

  it("코드형 ID와 위치를 유지하고 없는 측정값·기준값을 만들지 않는다", () => {
    expect(hierarchy.plants[0].id).toBe("PLANT-01");
    expect(hierarchy.plants[0].location).toBe("울산광역시 남구 신정동");
    expect(hierarchy.equipment[0].equipmentStatus).toBe(3);
    expect(hierarchy.equipment[0].tags[0]).toMatchObject({
      id: "40",
      signal: "vibration",
      currentValue: null,
    });
    expect(hierarchy.equipment[0].tags[0].limit).toBeUndefined();
  });

  it("알람의 5단계와 발생 당시 측정값·임계값을 보존한다", () => {
    const alarm = mapAlarm(
      {
        alarm_id: "50",
        equipment_id: "30",
        sensor_id: "40",
        alarm_type: "Setpoint",
        occurred_at: "2026-11-11T00:00:00Z",
        measured_value: 5.1,
        threshold_value: 4.5,
        unit: "mm/s RMS",
        alarm_level: 4,
        user_message: "비상",
      },
      hierarchy,
    );
    expect(alarm).toMatchObject({
      id: "50",
      alarmLevel: 4,
      value: 5.1,
      limit: 4.5,
      signal: "vibration",
    });
  });

  it("보고서 snake_case 필드를 편집 모델로 옮긴다", () => {
    const report = mapReport({
      report_id: "70",
      equipment_id: "30",
      title: "점검",
      symptom: "진동",
      cause: "미상",
      action: "확인",
      chart_url: null,
      risk: "남음",
      version: 2,
      updated_at: "2026-11-11T00:00:00Z",
    });
    expect(report).toMatchObject({
      id: "70",
      version: 2,
      values: { chartUrl: "", symptom: "진동" },
    });
  });
});
