import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { hierarchy as demoHierarchy } from "../../../../mock/fixtures.ts";
import type {
  Hierarchy,
  Selection,
} from "../../../shared/api/contracts/hierarchy.ts";
import { CUDProcessLayout } from "./CUDProcessLayout.tsx";

const emptySelection: Selection = {
  plantId: null,
  unitId: null,
  equipmentId: null,
};

afterEach(cleanup);

describe("CUDProcessLayout", () => {
  it("selects the matching demo pump in the active plant", () => {
    const onSelect = vi.fn();
    render(
      <CUDProcessLayout
        hierarchy={demoHierarchy}
        selection={{ ...emptySelection, plantId: "P-02" }}
        alarms={[]}
        onSelect={onSelect}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /P3.*선택/ }));
    expect(onSelect).toHaveBeenCalledWith({
      plantId: "P-02",
      unitId: "P-02-P3",
      equipmentId: "P-2301A",
    });
  });

  it("selects a real P1 equipment with the keyboard", () => {
    const onSelect = vi.fn();
    const equipment = {
      ...demoHierarchy.equipment[0],
      id: "P1",
      plantId: "CDU",
      unitId: "CUD-01",
    };
    const hierarchy: Hierarchy = {
      plants: [{ id: "CDU", name: "CDU", location: "" }],
      units: [
        { id: "CUD-01", name: "CUD-01", plantId: "CDU", processType: "CUD" },
      ],
      equipment: [equipment],
    };
    render(
      <CUDProcessLayout
        hierarchy={hierarchy}
        selection={emptySelection}
        alarms={[]}
        onSelect={onSelect}
      />,
    );

    fireEvent.keyDown(screen.getByRole("button", { name: /P1.*선택/ }), {
      key: "Enter",
    });
    expect(onSelect).toHaveBeenCalledWith({
      plantId: "CDU",
      unitId: "CUD-01",
      equipmentId: "P1",
    });
    expect(screen.queryByRole("button", { name: /P2.*선택/ })).toBeNull();
  });
});
