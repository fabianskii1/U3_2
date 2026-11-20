import { describe, expect, it } from "vitest";
import { hierarchy } from "../../../../mock/fixtures.ts";
import type { Alarm } from "../../../shared/api/contracts/alarm.ts";
import {
  CONSOLE_EXAMPLE_HOUR,
  consoleHourDate,
  equipmentAlarmState,
} from "./equipment-alarm-state.ts";

const equipment = hierarchy.equipment[0];
const alarm: Alarm = {
  id: "alarm-1",
  equipmentId: equipment.id,
  tagId: equipment.tags[0].id,
  signal: equipment.tags[0].signal,
  severity: "Medium",
  alarmLevel: 2,
  eventType: "예측",
  unit: equipment.tags[0].unit,
  occurredAt: "2026-11-20T00:00:00Z",
  type: "Setpoint",
  reason: "예측 경고",
};

describe("equipmentAlarmState", () => {
  it("uses the highest active alarm and marks a predicted stage", () => {
    expect(equipmentAlarmState(equipment, [alarm])).toMatchObject({
      level: 2,
      predicted: true,
    });
    expect(
      equipmentAlarmState(equipment, [alarm]).sensorLevels.get(alarm.tagId),
    ).toBe(2);
  });

  it("ignores closed or unconfirmed alarm history", () => {
    const state = equipmentAlarmState(equipment, [
      { ...alarm, isActive: false },
      { ...alarm, id: "alarm-2", isActive: null },
      { ...alarm, id: "alarm-3", endedAt: "2026-11-20T01:00:00Z" },
    ]);
    expect(state.level).toBe(0);
    expect(state.active).toHaveLength(0);
  });

  it("replays the console pump levels at the example time", () => {
    const levels = (["P1", "P2", "P3", "P4", "P5", "P6"] as const).map((id) =>
      equipmentAlarmState(
        { ...equipment, id, unitId: "CDU-01" },
        [],
        CONSOLE_EXAMPLE_HOUR,
      ),
    );
    expect(levels.map((state) => state.level)).toEqual([1, 2, 3, 2, 0, 0]);
    expect(levels.map((state) => state.predicted)).toEqual([
      false,
      true,
      false,
      true,
      false,
      false,
    ]);
    expect(consoleHourDate(CONSOLE_EXAMPLE_HOUR).toISOString()).toBe(
      "2026-11-19T00:00:00.000Z",
    );
    expect(
      equipmentAlarmState(
        { ...equipment, id: "P1", unitId: "CDU-01" },
        [],
        CONSOLE_EXAMPLE_HOUR + 2,
      ).level,
    ).toBe(2);
    const p1 = {
      ...equipment,
      id: "P1",
      unitId: "CDU-01",
      tags: [{ ...equipment.tags[0], id: "10-PT-1106", name: "흡입압" }],
    };
    expect(
      equipmentAlarmState(p1, [], CONSOLE_EXAMPLE_HOUR).sensorLevels.get(
        "10-PT-1106",
      ),
    ).toBe(1);
  });

  it("uses alarm intervals when replaying history", () => {
    const historical = {
      ...alarm,
      equipmentId: "P1",
      isActive: null,
      occurredAt: "2026-11-19T00:00:00Z",
      endedAt: "2026-11-19T02:00:00Z",
    };
    const p1 = { ...equipment, id: "P1", unitId: "CDU-01" };
    expect(
      equipmentAlarmState(p1, [historical], CONSOLE_EXAMPLE_HOUR).active,
    ).toHaveLength(1);
    expect(
      equipmentAlarmState(p1, [historical], CONSOLE_EXAMPLE_HOUR + 3).active,
    ).toHaveLength(0);
  });
});
