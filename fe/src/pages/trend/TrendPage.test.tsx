import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import { hierarchy } from "../../../mock/fixtures.ts";
import { useTrendStore } from "../../features/trend/model/trend.store.ts";
import { defaultRange, dateBounds } from "../../shared/lib/date-time.ts";
import { TrendPage } from "./TrendPage.tsx";

vi.mock("../../features/trend/api/trend.queries.ts", () => ({
  trendQuery: () => ({
    queryKey: ["trend-test"],
    queryFn: () => new Promise(() => {}),
  }),
}));

afterEach(() => {
  cleanup();
  useTrendStore.getState().reset();
});

function renderTrend(search = "", equipmentId: string | null = "P-1101A") {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[`/trend${search}`]}>
        <TrendPage
          hierarchy={hierarchy}
          selection={{ plantId: "P-01", unitId: "P-01-P1", equipmentId }}
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
