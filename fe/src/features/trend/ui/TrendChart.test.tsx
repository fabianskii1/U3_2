import { describe, expect, it } from "vitest";
import { linearTrend, trendYAxis, violationRanges } from "./TrendChart.tsx";

describe("trendYAxis", () => {
  it("frames voltage readings and visible limits with clean ticks near the data", () => {
    const axis = trendYAxis([379.89, 380.11, 323, 436.99999999999994]);
    expect(axis.domain[0]).toBeGreaterThan(280);
    expect(axis.domain[0]).toBeLessThan(323);
    expect(axis.domain[1]).toBeGreaterThan(437);
    expect(axis.domain[1]).toBeLessThan(490);
    expect(axis.ticks.map(axis.formatTick)).toEqual(
      axis.ticks.map((value) => String(Math.round(value))),
    );
  });

  it("keeps flat and negative traces visible and ignores missing values", () => {
    const flat = trendYAxis([null, Number.NaN, 0.005, 0.005]);
    expect(flat.domain[0]).toBeLessThan(0.005);
    expect(flat.domain[1]).toBeGreaterThan(0.005);
    expect(new Set(flat.ticks.map(flat.formatTick)).size).toBe(flat.ticks.length);
    expect(trendYAxis([-13.2, -12.8]).domain[1]).toBeLessThan(0);
  });
});

describe("linearTrend", () => {
  it("uses elapsed time and skips missing measurements", () => {
    const points = [
      { time: "2026-11-19T00:00:00Z", value: 2 },
      { time: "2026-11-19T01:00:00Z", value: null },
      { time: "2026-11-19T03:00:00Z", value: 8 },
    ];
    expect(linearTrend(points)).toEqual([2, 4, 8]);
  });

  it("omits a trend with fewer than two valid measurements", () => {
    expect(
      linearTrend([
        { time: "2026-11-19T00:00:00Z", value: null },
        { time: "2026-11-19T01:00:00Z", value: 3 },
      ]),
    ).toEqual([null, null]);
  });
});

describe("violationRanges", () => {
  it("shades only the crossed HIGH interval and stops at a missing sample", () => {
    const points = [2, 5, 6, null, 3].map((value, index) => ({
      time: String(index),
      value,
    }));
    expect(violationRanges(points, 5, "HIGH")).toEqual([{ x1: "0", x2: "3" }]);
  });

  it("uses the lower side for LOW rules", () => {
    const points = [4, 2, 4].map((value, index) => ({
      time: String(index),
      value,
    }));
    expect(violationRanges(points, 2, "LOW")).toEqual([{ x1: "0", x2: "2" }]);
  });
});
