import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import { hierarchy } from "../../../mock/fixtures.ts";
import { useTrendStore } from "../../features/trend/model/trend.store.ts";
import { defaultRange, dateBounds } from "../../shared/lib/date-time.ts";
import { TrendPage } from "./TrendPage.tsx";
import { trendQuery } from "../../features/trend/api/trend.queries.ts";

vi.mock("../../features/trend/api/trend.queries.ts", () => ({
  trendQuery: vi.fn(() => ({
    queryKey: ["trend-test"],
    queryFn: () => new Promise(() => {}),
  })),
}));

vi.mock("../../features/trend/api/trend-view.queries.ts", () => ({
  savedTrendQuery: () => ({
    queryKey: ["saved-trend-test"],
    queryFn: async () => ({
      viewId: "e6d7f434-5d9a-4e6d-b4c4-0f72fbb74092",
      plantId: "P-01",
      equipmentGroupId: "P-01-P1",
      equipmentId: "P-1101A",
      config: {
        version: 1,
        showAnomalies: false,
        series: [
          {
            sensorId: "P1101A-VIB",
            start: "2026-11-01T00:00:00+09:00",
            end: "2026-11-08T00:00:00+09:00",
          },
          {
            sensorId: "P1101A-TEMP",
            start: "2026-11-07T00:00:00+09:00",
            end: "2026-11-08T00:00:00+09:00",
          },
        ],
      },
      createdAt: "2026-11-08T00:00:00+09:00",
      expiresAt: null,
    }),
  }),
}));

afterEach(() => {
  cleanup();
  useTrendStore.getState().reset();
  vi.clearAllMocks();
});

function renderTrend(
  search = "",
  equipmentId: string | null = "P-1101A",
  plantId: string | null = "P-01",
  unitId: string | null = "P-01-P1",
) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[`/trend${search}`]}>
        <TrendPage
          hierarchy={hierarchy}
          selection={{ plantId, unitId, equipmentId }}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

it("URL 없이 진입해도 기본 센서와 실제 조회 시간 범위를 저장한다", () => {
  const range = defaultRange();
  const bounds = dateBounds(range.from, range.to);
  renderTrend();
  expect(useTrendStore.getState()).toMatchObject({
    sensor_id: "P1101A-VIB",
    sensor_start_time: bounds.from,
    sensor_end_time: bounds.to,
    sensor_interval: "30m",
  });
});

it("URL로 복원한 센서·기간과 화면에서 변경한 값을 동기화하고 이탈 시 초기화한다", () => {
  const equipment = hierarchy.equipment.find((item) => item.id === "P-1101A")!;
  const sensorId = equipment.tags[1].id;
  const { unmount } = renderTrend(
    `?sensor_id=${sensorId}&from=2026-11-01&to=2026-11-05`,
  );
  expect(useTrendStore.getState()).toMatchObject({
    sensor_id: sensorId,
    sensor_start_time: "2026-11-01T00:00:00+09:00",
    sensor_end_time: "2026-11-05T23:59:59+09:00",
    sensor_interval: "15m",
  });
  fireEvent.change(screen.getByLabelText("센서"), {
    target: { value: equipment.tags[0].id },
  });
  fireEvent.change(screen.getByLabelText("시작 일자"), {
    target: { value: "2026-11-02T00:00:00" },
  });
  fireEvent.change(screen.getByLabelText("종료 일자"), {
    target: { value: "2026-11-06T23:59:59" },
  });
  expect(useTrendStore.getState()).toMatchObject({
    sensor_id: equipment.tags[0].id,
    sensor_start_time: "2026-11-02T00:00:00+09:00",
    sensor_end_time: "2026-11-06T23:59:59+09:00",
  });
  unmount();
  expect(useTrendStore.getState()).toMatchObject({
    sensor_id: null,
    sensor_start_time: null,
    sensor_end_time: null,
    sensor_interval: null,
  });
});

it("조회 간격 선택을 전역 상태에 반영하고 과도한 수동 조회를 안내한다", () => {
  renderTrend("?from=2026-11-01&to=2026-11-05&interval=1d");
  expect(screen.getByLabelText("조회 간격")).toHaveValue("1d");
  expect(useTrendStore.getState().sensor_interval).toBe("1d");
  fireEvent.change(screen.getByLabelText("조회 간격"), {
    target: { value: "1s" },
  });
  expect(useTrendStore.getState().sensor_interval).toBe("1s");
  expect(screen.getByRole("alert")).toHaveTextContent("최대 10,000개");
  fireEvent.change(screen.getByLabelText("조회 간격"), {
    target: { value: "auto" },
  });
  expect(useTrendStore.getState().sensor_interval).toBe("15m");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("설비 미선택 시 조회 대상을 비우고 잘못된 기간은 조회 시간으로 저장하지 않는다", () => {
  const { unmount } = renderTrend("", null);
  expect(useTrendStore.getState()).toMatchObject({
    sensor_id: null,
    sensor_start_time: null,
    sensor_end_time: null,
  });
  unmount();
  renderTrend("?from=2026-11-05&to=2026-11-01");
  expect(useTrendStore.getState()).toMatchObject({
    sensor_id: "P1101A-VIB",
    sensor_start_time: null,
    sensor_end_time: null,
  });
});

it("Plant 또는 Equipment Group이 없으면 비교 차트를 표시하지 않는다", () => {
  const { unmount } = renderTrend("", null, null, null);
  expect(screen.queryByText(/진동 비교/)).not.toBeInTheDocument();
  expect(
    screen.getByText("Plant와 Equipment Group을 선택하세요"),
  ).toBeInTheDocument();
  unmount();

  renderTrend("", null, "P-01", null);
  expect(screen.queryByText(/진동 비교/)).not.toBeInTheDocument();
  expect(
    screen.getByText("Plant와 Equipment Group을 선택하세요"),
  ).toBeInTheDocument();
});

it("Plant와 Equipment Group을 선택하고 설비는 선택하지 않으면 비교 패널을 표시한다", () => {
  renderTrend("", null);
  expect(screen.getByText(/진동 비교/)).toBeInTheDocument();
});

it("viewId가 있으면 일반 선택 파라미터보다 저장된 센서별 기간을 우선한다", async () => {
  renderTrend(
    "?viewId=e6d7f434-5d9a-4e6d-b4c4-0f72fbb74092&equip_id=P2&sensor_id=ignored",
  );
  await waitFor(() =>
    expect(
      screen.getByText("저장 당시 확정된 센서별 조회 기간을 표시합니다."),
    ).toBeInTheDocument(),
  );
  expect(trendQuery).toHaveBeenCalledWith(
    "P1101A-VIB",
    "2026-11-01T00:00:00+09:00",
    "2026-11-08T00:00:00+09:00",
    expect.any(String),
  );
  expect(trendQuery).toHaveBeenCalledWith(
    "P1101A-TEMP",
    "2026-11-07T00:00:00+09:00",
    "2026-11-08T00:00:00+09:00",
    expect.any(String),
  );
});

it("일반 URL에서 설비만 지정하면 그 설비의 센서를 모두 조회한다", () => {
  const asset = hierarchy.equipment.find((item) => item.id === "P-1101A")!;
  renderTrend("?equip_id=P-1101A");
  expect(
    screen.getByText(`${asset.name} 전체 센서 트렌드`),
  ).toBeInTheDocument();
  expect(trendQuery).toHaveBeenCalledTimes(asset.tags.length);
});

it("잘못된 viewId는 조회하지 않고 오류를 표시한다", () => {
  renderTrend("?viewId=invalid");
  expect(screen.getByRole("alert")).toHaveTextContent(
    "올바르지 않은 트렌드 링크",
  );
});
