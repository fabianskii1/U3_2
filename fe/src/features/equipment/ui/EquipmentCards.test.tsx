import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { hierarchy } from "../../../../mock/fixtures.ts";
import { EquipmentCards } from "./EquipmentCards.tsx";

afterEach(cleanup);

describe("EquipmentCards", () => {
  it("shows sensor values and selects the equipment", () => {
    const equipment = hierarchy.equipment.find(
      (item) => item.id === "P-1101A",
    )!;
    const queryClient = new QueryClient({
      defaultOptions: { queries: { staleTime: Infinity } },
    });
    queryClient.setQueryData(["equipment", equipment.id], {
      ...equipment,
      asOf: "2026-11-17T01:00:00+00:00",
      tags: [
        {
          ...equipment.tags[0],
          currentValue: 5.123,
          measuredAt: "2026-11-17T00:59:00+00:00",
        },
        { ...equipment.tags[1], currentValue: null },
      ],
    });
    const onSelect = vi.fn();
    render(
      <QueryClientProvider client={queryClient}>
        <EquipmentCards
          groupName="원유 공급"
          equipment={[equipment]}
          selectedEquipmentId={null}
          onSelect={onSelect}
        />
      </QueryClientProvider>,
    );

    expect(screen.getByText("5.123")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /P-1101A 선택/ }));
    expect(onSelect).toHaveBeenCalledWith({
      plantId: "P-01",
      unitId: "P-01-P1",
      equipmentId: "P-1101A",
      sensorIds: hierarchy.equipment
        .find((item) => item.id === "P-1101A")!
        .tags.map((tag) => tag.id),
    });
  });
});
