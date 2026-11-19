import { describe, it, expect } from "vitest";
import {
  resolveSelection,
  selectionParams,
  internalHref,
  savedTrendSelection,
} from "./navigation.ts";
import { hierarchy } from "../../../mock/fixtures.ts";
describe("계층과 URL", () => {
  it("설비 딥링크의 상위 계층을 복원한다", () => {
    expect(
      resolveSelection(
        new URLSearchParams("equip_id=P-1101A&plant_id=P-02"),
        hierarchy,
      ),
    ).toEqual({
      plantId: "P-01",
      unitId: "P-01-P1",
      equipmentId: "P-1101A",
      sensorIds: hierarchy.equipment
        .find((item) => item.id === "P-1101A")!
        .tags.map((tag) => tag.id),
    });
  });
  it("저장된 View의 계층이 일반 URL 파라미터보다 우선한다", () => {
    expect(
      savedTrendSelection({
        plantId: "P-01",
        equipmentGroupId: "P-01-P1",
        equipmentId: "P-1101A",
        config: { series: [{ sensorId: "P1101A-VIB" }] },
      }),
    ).toEqual({
      plantId: "P-01",
      unitId: "P-01-P1",
      equipmentId: "P-1101A",
      sensorIds: ["P1101A-VIB"],
    });
  });
  it("상위 변경 시 센서와 하위 선택은 제거하고 기간은 유지한다", () => {
    const p = selectionParams(
      { plantId: "P-02", unitId: null, equipmentId: null, sensorIds: [] },
      new URLSearchParams(
        "viewId=e6d7f434-5d9a-4e6d-b4c4-0f72fbb74092&equip_id=P-1101A&sensor_id=P1101A-VIB&sensor=vibration&from=2026-11-01",
      ),
    );
    expect(p.get("plant_id")).toBe("P-02");
    expect(p.has("equip_id")).toBe(false);
    expect(p.has("sensor_id")).toBe(false);
    expect(p.has("viewId")).toBe(false);
    expect(p.get("from")).toBe("2026-11-01");
  });
  it("센서 복수 선택과 선택 해제를 URL에서 복원한다", () => {
    const base = { plantId: "P-01", unitId: "P-01-P1", equipmentId: "P-1101A" };
    const chosen = selectionParams({
      ...base,
      sensorIds: ["P1101A-VIB", "P1101A-TEMP"],
    });
    expect(resolveSelection(chosen, hierarchy).sensorIds).toEqual([
      "P1101A-VIB",
      "P1101A-TEMP",
    ]);
    const empty = selectionParams({ ...base, sensorIds: [] });
    expect(resolveSelection(empty, hierarchy).sensorIds).toEqual([]);
  });
  it("저장된 View에서 선택한 센서만 복원한다", () => {
    const view = {
      plantId: "P-01",
      equipmentGroupId: "P-01-P1",
      equipmentId: "P-1101A",
      config: {
        series: [{ sensorId: "P1101A-VIB" }, { sensorId: "P1101A-TEMP" }],
      },
    };
    expect(
      savedTrendSelection(
        view,
        new URLSearchParams("selected_sensor_id=P1101A-TEMP"),
      ).sensorIds,
    ).toEqual(["P1101A-TEMP"]);
    expect(
      savedTrendSelection(view, new URLSearchParams("sensor_id=ignored"))
        .sensorIds,
    ).toEqual(["P1101A-VIB", "P1101A-TEMP"]);
  });
  it("알 수 없는 ID는 전체 계층으로 복원한다", () => {
    expect(
      resolveSelection(new URLSearchParams("equip_id=missing"), hierarchy)
        .equipmentId,
    ).toBeNull();
  });
  it("외부 또는 지원하지 않는 Agent 이동을 거부한다", () => {
    expect(() => internalHref("https://example.com")).toThrow();
    expect(() => internalHref("/api/reports")).toThrow();
  });
});
