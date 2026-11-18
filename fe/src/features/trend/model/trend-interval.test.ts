import { expect, it } from "vitest";
import {
  intervalMode,
  pointCount,
  remoteTrendIntervals,
  resolveInterval,
  trendRange,
} from "./trend-interval.ts";

it("자동 간격은 500개 이하에서 가장 촘촘한 간격을 선택한다", () => {
  const from = "2026-11-01T00:00:00+09:00";
  expect(resolveInterval("auto", from, "2026-11-01T00:05:00+09:00")).toBe("1s");
  expect(resolveInterval("auto", from, "2026-11-01T00:08:19+09:00")).toBe("1s");
  expect(resolveInterval("auto", from, "2026-11-01T00:08:20+09:00")).toBe("5s");
  expect(resolveInterval("auto", from, "2026-11-08T00:00:00+09:00")).toBe(
    "30m",
  );
  expect(resolveInterval("auto", from, "2027-11-01T00:00:00+09:00")).toBe("1d");
  expect(resolveInterval("1m", from, "2027-11-01T00:00:00+09:00")).toBe("1m");
  expect(
    resolveInterval("auto", from, "2026-11-08T00:00:00+09:00", [
      "1m",
      "1h",
      "1d",
    ]),
  ).toBe("1h");
  expect(intervalMode("invalid")).toBe("auto");
  expect(
    resolveInterval(
      "3h",
      "2026-10-02T00:00:00+09:00",
      "2026-11-20T23:59:59+09:00",
      remoteTrendIntervals,
    ),
  ).toBe("1d");
  expect(
    resolveInterval(
      "1s",
      from,
      "2026-11-01T00:05:00+09:00",
      remoteTrendIntervals,
    ),
  ).toBe("1m");
});

it("날짜 링크와 초 단위 시각을 한국 시간 조회 범위로 변환한다", () => {
  expect(trendRange("2026-11-01", "2026-11-01")).toMatchObject({
    from: "2026-11-01T00:00:00+09:00",
    to: "2026-11-01T23:59:59+09:00",
    valid: true,
  });
  const range = trendRange("2026-11-01T09:00", "2026-11-01T09:05:00");
  expect(range.valid).toBe(true);
  expect(pointCount(range.from, range.to, "1s")).toBe(301);
  expect(trendRange("2026-02-30", "2026-03-01").valid).toBe(false);
  expect(trendRange("2026-11-01T25:00", "2026-11-02").valid).toBe(false);
  expect(trendRange("2026-11-02", "2026-11-01").valid).toBe(false);
});
