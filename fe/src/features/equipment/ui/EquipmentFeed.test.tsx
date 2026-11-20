import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { hierarchy } from "../../../../mock/fixtures.ts";
import type { Alarm } from "../../alarms/index.ts";
import { EquipmentFeed } from "./EquipmentFeed.tsx";

afterEach(() => {
  cleanup();
  localStorage.clear();
});

describe("EquipmentFeed", () => {
  it("shows historical predictions and selects equipment without changing alarm state", () => {
    const equipment = hierarchy.equipment.find(
      (item) => item.id === "P-1101A",
    )!;
    const base: Alarm = {
      id: "normal",
      equipmentId: equipment.id,
      tagId: equipment.tags[0].id,
      signal: equipment.tags[0].signal,
      severity: "High",
      unit: equipment.tags[0].unit,
      occurredAt: "2026-11-01T10:00:00+09:00",
      type: "Setpoint",
      reason: "기준 초과",
    };
    const onSelect = vi.fn();
    render(
      <EquipmentFeed
        equipment={[equipment]}
        alarms={[
          base,
          {
            ...base,
            id: "predicted",
            eventType: "예측",
            reason: "경고선 예측",
          },
        ]}
        onSelect={onSelect}
      />,
    );

    const columns = document.querySelectorAll(".equipment-feed-column");
    expect(
      within(columns[0] as HTMLElement).getByText("기준 초과"),
    ).toBeInTheDocument();
    expect(
      within(columns[1] as HTMLElement).getByText("경고선 예측"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByText("기준 초과").closest("button")!);
    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ equipmentId: equipment.id }),
    );
    expect(screen.getByText("기준 초과")).toBeInTheDocument();
    expect(localStorage.getItem("equipment-feed-seen")).toBeNull();
    expect(screen.queryByText(/새 알림|확인한 알림/)).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "모두 읽음" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "확인 기록 지우기" }),
    ).not.toBeInTheDocument();
  });
});
