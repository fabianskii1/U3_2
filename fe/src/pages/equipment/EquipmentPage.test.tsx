import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { hierarchy as demoHierarchy } from "../../../mock/fixtures.ts";
import type {
  Hierarchy,
  Selection,
} from "../../shared/api/contracts/hierarchy.ts";
import { EquipmentPage } from "./EquipmentPage.tsx";

afterEach(cleanup);

function renderPage(processType: string | null, unitId: string | null) {
  const hierarchy: Hierarchy = {
    ...demoHierarchy,
    units: demoHierarchy.units.map((unit) => ({ ...unit, processType })),
  };
  const selection: Selection = {
    plantId: "P-01",
    unitId,
    equipmentId: null,
  };
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <EquipmentPage
          hierarchy={hierarchy}
          selection={selection}
          alarms={[]}
          onSelect={vi.fn()}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("EquipmentPage process layout", () => {
  it("shows the CDU layout only for a CUD equipment group", () => {
    renderPage("CUD", "P-01-P1");
    expect(screen.getByText("공정 배치도")).toBeInTheDocument();
    expect(screen.getByText("P-1101A")).toBeInTheDocument();
    expect(screen.queryByText("P-1201A")).not.toBeInTheDocument();
  });

  it("shows a placeholder for another process type", () => {
    renderPage("HCU", "P-01-P1");
    expect(screen.queryByText("공정 배치도")).not.toBeInTheDocument();
    expect(
      screen.getByText("이 공정 유형의 배치도는 준비 중입니다."),
    ).toBeInTheDocument();
  });

  it("does not show a process layout before a group is selected", () => {
    renderPage("CUD", null);
    expect(screen.queryByText("공정 배치도")).not.toBeInTheDocument();
  });
});
