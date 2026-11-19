import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { hierarchy as demoHierarchy } from "../../../../mock/fixtures.ts";
import type { Hierarchy } from "../../../shared/api/contracts/hierarchy.ts";
import { trendQuery } from "../api/trend.queries.ts";
import {
  buildComparisonData,
  PumpComparisonChart,
} from "./PumpComparisonChart.tsx";

vi.mock("../api/trend.queries.ts", () => ({
  trendQuery: vi.fn(
    (sensorId: string, _from: string, _to: string, interval: string) => ({
      queryKey: ["comparison-test", sensorId, interval],
      queryFn: async () => ({
        points: [
          { time: "2026-11-16T00:00:00Z", value: 10 },
          { time: "2026-11-16T01:00:00Z", value: 12 },
        ],
      }),
      enabled: !!sensorId,
    }),
  ),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

it("merges hourly pump readings and compares each pump with its own mean", () => {
  const series = [
    {
      id: "P1",
      points: [
        { time: "2026-11-16T00:00:00Z", value: 10 },
        { time: "2026-11-16T01:00:00Z", value: 12 },
      ],
    },
    {
      id: "P2",
      points: [
        { time: "2026-11-16T00:00:00Z", value: 20 },
        { time: "2026-11-16T01:00:00Z", value: 22 },
      ],
    },
  ];
  expect(buildComparisonData(series, "deviation")).toEqual([
    { time: "2026-11-16T00:00:00Z", P1: -1, P2: -1 },
    { time: "2026-11-16T01:00:00Z", P1: 1, P2: 1 },
  ]);
  expect(buildComparisonData(series, "raw")[0]).toMatchObject({
    P1: 10,
    P2: 20,
  });
});

it("requests 1-hour series for P1-P6 and switches sensor kind and value mode", async () => {
  const equipment = demoHierarchy.equipment
    .filter((item) => item.plantId === "P-01" && item.id.endsWith("A"))
    .map((item, index) => ({
      ...item,
      id: `P${index + 1}`,
      unitId: "CUD-01",
      plantId: "PLANT-01",
      tags: [
        { ...item.tags[0], id: `VT-${index + 1}`, name: "진동 속도 RMS" },
        { ...item.tags[1], id: `ET-${index + 1}`, name: "모터 선간전압" },
      ],
    }));
  const hierarchy: Hierarchy = {
    plants: [{ id: "PLANT-01", name: "울산CLX", location: "울산" }],
    units: [
      {
        id: "CUD-01",
        name: "상압증류",
        plantId: "PLANT-01",
        processType: "CUD",
      },
    ],
    equipment,
  };
  render(
    <QueryClientProvider client={new QueryClient()}>
      <PumpComparisonChart
        hierarchy={hierarchy}
        plantId="PLANT-01"
        unitId="CUD-01"
      />
    </QueryClientProvider>,
  );

  await screen.findByRole("img", { name: /진동 P1부터 P6까지 1시간 평균/ });
  expect(
    vi
      .mocked(trendQuery)
      .mock.calls.filter(([sensorId]) => sensorId.startsWith("VT-"))
      .every(([, , , interval]) => interval === "1h"),
  ).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "P1 선 숨기기" }));
  expect(screen.getByRole("button", { name: "P1 선 표시" })).toHaveAttribute(
    "aria-pressed",
    "false",
  );
  fireEvent.click(screen.getByRole("button", { name: "전압" }));
  await waitFor(() =>
    expect(trendQuery).toHaveBeenCalledWith(
      "ET-1",
      expect.any(String),
      expect.any(String),
      "1h",
    ),
  );
  fireEvent.click(screen.getByRole("button", { name: "실제 값" }));
  expect(screen.getByText(/전압 비교 \(실제 값/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "P1 선 표시" })).toHaveAttribute(
    "aria-pressed",
    "false",
  );
  fireEvent.click(screen.getByRole("button", { name: "P1 선 표시" }));
  expect(screen.getByRole("button", { name: "P1 선 숨기기" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});
