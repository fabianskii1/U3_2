import { QueryClient } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import { http } from "../../../shared/api/http-client.ts";
import { trendQuery } from "./trend.queries.ts";

vi.mock("../../../shared/api/be-adapter.ts", () => ({
  remoteApi: true,
  beTrend: { parse: (value: unknown) => value },
}));
vi.mock("../../../shared/api/http-client.ts", () => ({
  http: { get: vi.fn() },
}));

it("원격 트렌드 요청은 자동 선택에서 나온 3h를 지원 간격으로 바꾼다", async () => {
  vi.mocked(http.get).mockResolvedValue({
    data: {
      sensor_id: "10-PT-1106",
      signal_id: "10-PT-1106",
      interval: "1d",
      unit: "kPa(g)",
      points: [],
      as_of: "2026-11-16T00:00:00+00:00",
      threshold_value: null,
    },
  });
  const from = "2026-10-02T00:00:00+09:00";
  const to = "2026-11-20T23:59:59+09:00";
  const client = new QueryClient();

  await client.fetchQuery(trendQuery("10-PT-1106", from, to, "3h"));

  expect(http.get).toHaveBeenCalledWith(
    "/trend",
    expect.objectContaining({
      params: { sensor_id: "10-PT-1106", from, to, interval: "1d" },
    }),
  );
});
