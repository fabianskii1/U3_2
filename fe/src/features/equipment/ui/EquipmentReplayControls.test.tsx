import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { consolePumpTracks } from "../model/equipment-alarm-state.ts";
import { EquipmentReplayControls } from "./EquipmentReplayControls.tsx";

afterEach(cleanup);

describe("EquipmentReplayControls", () => {
  it("shows six pump timelines from console levels", () => {
    render(<EquipmentReplayControls hour={441} onChange={vi.fn()} />);
    expect(
      screen.getAllByRole("button", { name: /기록에서 시각 선택/ }),
    ).toHaveLength(6);
    expect(screen.getByText("P1")).toBeInTheDocument();
    expect(screen.getByText("P6")).toBeInTheDocument();
    expect(
      consolePumpTracks
        .find((pump) => pump.id === "P3")
        ?.segments.some(
          (segment) =>
            segment.level === 3 && segment.start <= 440 && segment.end > 440,
        ),
    ).toBe(true);
  });

  it("selects an hour when a pump lane is clicked", () => {
    const onChange = vi.fn();
    render(<EquipmentReplayControls hour={441} onChange={onChange} />);
    const lane = screen.getByRole("button", { name: "P1 기록에서 시각 선택" });
    vi.spyOn(lane, "getBoundingClientRect").mockReturnValue({
      left: 0,
      width: 1000,
    } as DOMRect);
    fireEvent.click(lane, { clientX: 500 });
    expect(onChange).toHaveBeenCalledWith(361);
  });
});
