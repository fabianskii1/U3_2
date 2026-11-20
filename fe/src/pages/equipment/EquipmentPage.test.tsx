import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { hierarchy as demoHierarchy } from "../../../mock/fixtures.ts";
import { getIncident, listIncidents } from "../../../mock/incidents.ts";
import {
  incidentQuery,
  incidentsQuery,
} from "../../features/incidents/api/incidents.queries.ts";
import type {
  Hierarchy,
  Selection,
} from "../../shared/api/contracts/hierarchy.ts";
import { EquipmentPage } from "./EquipmentPage.tsx";

vi.mock("../../features/equipment/ui/Pump3D.tsx", () => ({
  Pump3D: ({
    equipment,
    faultSelection,
  }: {
    equipment: { id: string };
    faultSelection?: { fault: string } | null;
  }) => (
    <div data-testid="pump-3d">
      {equipment.id} 3D 부품 {faultSelection?.fault}
    </div>
  ),
}));

afterEach(cleanup);

function renderPage(
  processType: string | null,
  unitId: string | null,
  equipmentId: string | null = null,
  queryClient = new QueryClient(),
) {
  const hierarchy: Hierarchy = {
    ...demoHierarchy,
    units: demoHierarchy.units.map((unit) => ({ ...unit, processType })),
  };
  const selection: Selection = {
    plantId: "P-01",
    unitId,
    equipmentId,
    sensorIds: [],
  };
  render(
    <QueryClientProvider client={queryClient}>
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
  it("shows the CDU layout only for a CDU equipment group", () => {
    renderPage("CDU", "P-01-P1");
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
    renderPage("CDU", null);
    expect(screen.queryByText("공정 배치도")).not.toBeInTheDocument();
  });

  it("shows the 3D component after equipment is selected", async () => {
    renderPage("CDU", "P-01-P1", "P-1101A");
    expect(await screen.findByTestId("pump-3d")).toHaveTextContent(
      "P-1101A 3D 부품",
    );
  });

  it("passes the selected diagnosis fault to the 3D model", async () => {
    const now = Date.now();
    const incident = getIncident(now, "INC-DEMO-1101A")!;
    const queryClient = new QueryClient({
      defaultOptions: { queries: { staleTime: Infinity } },
    });
    queryClient.setQueryData(
      incidentsQuery({ equipment_id: "P-1101A", limit: 20 }).queryKey,
      listIncidents(now, new URLSearchParams({ equipment_id: "P-1101A" })),
    );
    queryClient.setQueryData(
      incidentQuery(incident.incident_id).queryKey,
      incident,
    );
    renderPage("CDU", "P-01-P1", "P-1101A", queryClient);

    const fault = await screen.findByRole("button", {
      name: /위험 2위 · 임펠러 불균형/,
    });
    expect(document.querySelectorAll(".diagnosis-candidate")).toHaveLength(2);
    fireEvent.click(fault);
    expect(fault).toHaveAttribute("aria-pressed", "true");
    expect(document.querySelectorAll(".diagnosis-candidate")).toHaveLength(2);
    expect(screen.getByTestId("pump-3d")).toHaveTextContent("임펠러 불균형");
  });
});
