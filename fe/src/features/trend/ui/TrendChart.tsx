import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SensorInterval } from "../model/trend-interval.ts";

export type ChartSetpoint = {
  setpoint_id: string;
  alarm_level: number;
  direction: "HIGH" | "LOW";
  operator: ">=" | "<=";
  value: number | null;
  effective_from: string;
  effective_to: string | null;
};

const levels = [
  { label: "주의", color: "#eab308" },
  { label: "경고", color: "#f97316" },
  { label: "위험", color: "#dc2626" },
  { label: "비상", color: "#7f1d1d" },
];

const formatBoundary = new Intl.NumberFormat("ko-KR", {
  maximumFractionDigits: 3,
}).format;

export function trendYAxis(values: Iterable<number | null>) {
  let minimum = Infinity;
  let maximum = -Infinity;
  for (const value of values) {
    if (value === null || !Number.isFinite(value)) continue;
    minimum = Math.min(minimum, value);
    maximum = Math.max(maximum, value);
  }
  if (minimum === Infinity) {
    minimum = 0;
    maximum = 1;
  }

  const spread = maximum - minimum;
  const padding =
    spread > 0 ? spread * 0.08 : Math.max(Math.abs(minimum) * 0.01, 0.001);
  const lower = minimum - padding;
  const upper = maximum + padding;
  const roughStep = (upper - lower) / 5;
  const magnitude = 10 ** Math.floor(Math.log10(roughStep));
  const step =
    ([1, 2, 2.5, 5, 10].find((factor) => factor * magnitude >= roughStep) ??
      10) * magnitude;
  const firstTick = Math.floor(lower / step);
  const lastTick = Math.ceil(upper / step);
  const fractionDigits = Math.min(
    15,
    Math.max(0, -Math.floor(Math.log10(step)) + 1),
  );
  const ticks = Array.from({ length: lastTick - firstTick + 1 }, (_, index) =>
    Number(((firstTick + index) * step).toFixed(fractionDigits)),
  );
  return {
    domain: [ticks[0], ticks[ticks.length - 1]] as [number, number],
    ticks,
    formatTick: new Intl.NumberFormat("ko-KR", {
      maximumFractionDigits: fractionDigits,
    }).format,
  };
}

export function linearTrend(points: { time: string; value: number | null }[]) {
  const valid = points
    .flatMap((point) =>
      point.value === null || !Number.isFinite(point.value)
        ? []
        : [{ x: Date.parse(point.time), y: point.value }],
    )
    .filter((point) => Number.isFinite(point.x));
  if (valid.length < 2) return points.map(() => null);
  const origin = valid[0].x;
  const xs = valid.map((point) => (point.x - origin) / 60_000);
  const meanX = xs.reduce((sum, x) => sum + x, 0) / xs.length;
  const meanY = valid.reduce((sum, point) => sum + point.y, 0) / valid.length;
  const denominator = xs.reduce((sum, x) => sum + (x - meanX) ** 2, 0);
  if (denominator === 0) return points.map(() => null);
  const slope =
    valid.reduce(
      (sum, point, index) => sum + (xs[index] - meanX) * (point.y - meanY),
      0,
    ) / denominator;
  return points.map((point) => {
    const time = Date.parse(point.time);
    return Number.isFinite(time)
      ? meanY + slope * ((time - origin) / 60_000 - meanX)
      : null;
  });
}

export function violationRanges(
  points: { time: string; value: number | null }[],
  boundary: number,
  direction: "HIGH" | "LOW",
) {
  const ranges: { x1: string | undefined; x2: string | undefined }[] = [];
  for (let index = 0; index < points.length; index++) {
    const value = points[index].value;
    if (
      value === null ||
      !(direction === "HIGH" ? value >= boundary : value <= boundary)
    )
      continue;
    const start = index;
    while (index + 1 < points.length) {
      const next = points[index + 1].value;
      if (
        next === null ||
        !(direction === "HIGH" ? next >= boundary : next <= boundary)
      )
        break;
      index++;
    }
    ranges.push({
      x1: points.length === 1 ? undefined : points[Math.max(0, start - 1)].time,
      x2:
        points.length === 1
          ? undefined
          : points[Math.min(points.length - 1, index + 1)].time,
    });
  }
  return ranges;
}

export type ChartIncident = {
  id: string;
  from: string;
  to: string | null;
  label: string;
};
export type ChartMarker = { time: string; label: string };

/** Snap an instant onto the categorical x-axis; null when outside the plotted range. */
export function snapTime(
  points: { time: string }[],
  instant: string,
  side: "start" | "end",
): string | null {
  const target = Date.parse(instant);
  if (!points.length || !Number.isFinite(target)) return null;
  const times = points.map((point) => Date.parse(point.time));
  if (side === "start") {
    if (target > times.at(-1)!) return null;
    const index = times.findIndex((time) => time >= target);
    return points[index].time;
  }
  if (target < times[0]) return null;
  let index = times.length - 1;
  while (index > 0 && times[index] > target) index -= 1;
  return points[index].time;
}

export function TrendChart({
  interval = "1h",
  points,
  limit,
  unit,
  setpoints = [],
  incidents = [],
  markers = [],
  onIncidentClick,
}: {
  interval?: SensorInterval;
  points: { time: string; value: number | null }[];
  limit: number | null;
  unit: string;
  setpoints?: ChartSetpoint[];
  incidents?: ChartIncident[];
  markers?: ChartMarker[];
  onIncidentClick?: (id: string) => void;
}) {
  const first = Date.parse(points[0]?.time ?? "");
  const last = Date.parse(points.at(-1)?.time ?? "");
  // A horizontal line is valid only when the rule covers every plotted sample.
  const boundaries = setpoints.filter(
    (rule) =>
      rule.value !== null &&
      Number.isFinite(rule.value) &&
      Date.parse(rule.effective_from) <= first &&
      (rule.effective_to === null || Date.parse(rule.effective_to) > last),
  );
  const trend = linearTrend(points);
  const fallbackLimit =
    boundaries.length === 0 && limit !== null && Number.isFinite(limit)
      ? limit
      : null;
  const yAxis = trendYAxis([
    ...points.map((point) => point.value),
    ...trend,
    ...boundaries.map((rule) => rule.value!),
    fallbackLimit,
  ]);
  const [yMin, yMax] = yAxis.domain;
  const data = points.map((point, index) => ({
    ...point,
    trend: trend[index],
  }));
  const bands = (["HIGH", "LOW"] as const).flatMap((direction) => {
    const sorted = boundaries
      .filter((rule) => rule.direction === direction)
      .sort((a, b) =>
        direction === "HIGH" ? a.value! - b.value! : b.value! - a.value!,
      );
    return sorted.flatMap((rule, index) =>
      violationRanges(points, rule.value!, direction).map((range) => ({
        rule,
        from: rule.value!,
        to: sorted[index + 1]?.value ?? (direction === "HIGH" ? yMax : yMin),
        ...range,
      })),
    );
  });
  const incidentAreas = incidents.flatMap((item) => {
    const x1 = snapTime(points, item.from, "start");
    const x2 = snapTime(
      points,
      item.to ?? points.at(-1)?.time ?? item.from,
      "end",
    );
    return x1 && x2 && Date.parse(x1) <= Date.parse(x2)
      ? [{ ...item, x1, x2 }]
      : [];
  });
  const markerLines = markers.flatMap((item) => {
    const x = snapTime(points, item.time, "start");
    return x ? [{ ...item, x }] : [];
  });
  const hasUnknown = setpoints.some((rule) => rule.value === null);
  const hasPartial = setpoints.some(
    (rule) => rule.value !== null && !boundaries.includes(rule),
  );

  return (
    <>
      <div
        className="trend-chart"
        role="img"
        aria-label={`시계열 차트, 단위 ${unit}, 추세선, setpoint 경계 ${boundaries.length}개${incidentAreas.length ? `, 이상 사건 구간 ${incidentAreas.length}개` : ""}`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={data}
            margin={{ top: 20, right: 30, bottom: 5, left: 0 }}
          >
            <CartesianGrid
              strokeDasharray="3 5"
              vertical={false}
              stroke="#e8edef"
            />
            <XAxis
              dataKey="time"
              tickFormatter={(v) =>
                new Intl.DateTimeFormat("ko-KR", {
                  timeZone: "Asia/Seoul",
                  month: "2-digit",
                  day: "2-digit",
                  ...(interval.endsWith("d")
                    ? {}
                    : {
                        hour: "2-digit",
                        minute: "2-digit",
                        ...(interval.endsWith("s")
                          ? { second: "2-digit" }
                          : {}),
                      }),
                }).format(new Date(v))
              }
              minTickGap={65}
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 11, fill: "#7b8b92" }}
            />
            <YAxis
              domain={yAxis.domain}
              ticks={yAxis.ticks}
              tickFormatter={yAxis.formatTick}
              allowDataOverflow
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 11, fill: "#7b8b92" }}
              width={60}
            />
            <Tooltip
              labelFormatter={(v) =>
                new Date(String(v)).toLocaleString("ko-KR", {
                  timeZone: "Asia/Seoul",
                })
              }
              formatter={(value, name) => [
                `${Number(value).toLocaleString("ko-KR", { maximumFractionDigits: 3 })} ${unit}`,
                String(name),
              ]}
              contentStyle={{
                borderRadius: 8,
                border: "1px solid #e3e9eb",
                fontSize: 12,
              }}
            />
            {incidentAreas.map((item) => (
              <ReferenceArea
                key={`incident-${item.id}`}
                x1={item.x1}
                x2={item.x2}
                fill="#7c3aed"
                fillOpacity={0.08}
                stroke="#7c3aed"
                strokeOpacity={0.35}
                strokeDasharray="4 4"
                ifOverflow="hidden"
                label={{
                  value: item.label,
                  position: "insideTopLeft",
                  fontSize: 10,
                }}
                onClick={
                  onIncidentClick ? () => onIncidentClick(item.id) : undefined
                }
                style={onIncidentClick ? { cursor: "pointer" } : undefined}
              />
            ))}
            {markerLines.map((item, index) => (
              <ReferenceLine
                key={`marker-${index}`}
                x={item.x}
                stroke="#7c3aed"
                strokeDasharray="2 3"
                label={{
                  value: item.label,
                  position: "insideBottomLeft",
                  fontSize: 10,
                }}
              />
            ))}
            {bands.map(({ rule, from, to, x1, x2 }, index) => (
              <ReferenceArea
                key={`${rule.setpoint_id}-${index}`}
                x1={x1}
                x2={x2}
                y1={from}
                y2={to}
                fill={levels[rule.alarm_level - 1]?.color ?? "#7f1d1d"}
                fillOpacity={0.12}
                strokeOpacity={0}
                ifOverflow="hidden"
              />
            ))}
            {boundaries.map((rule) => (
              <ReferenceLine
                key={rule.setpoint_id}
                y={rule.value!}
                stroke={levels[rule.alarm_level - 1]?.color ?? "#7f1d1d"}
                strokeDasharray="5 4"
                label={{
                  value: `${levels[rule.alarm_level - 1]?.label} ${formatBoundary(rule.value!)}`,
                  position: "insideTopRight",
                  fontSize: 10,
                }}
              />
            ))}
            {fallbackLimit !== null && (
              <ReferenceLine
                y={fallbackLimit}
                stroke="#d66554"
                strokeDasharray="5 4"
                label={{
                  value: `기준 ${formatBoundary(fallbackLimit)}`,
                  position: "insideTopRight",
                  fontSize: 11,
                }}
              />
            )}
            <Line
              type="monotone"
              dataKey="value"
              name="실측값"
              stroke="#168b81"
              strokeWidth={2}
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
            <Line
              type="linear"
              dataKey="trend"
              name="추세선"
              stroke="#2563eb"
              strokeWidth={1.5}
              strokeDasharray="7 4"
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      {(hasUnknown || hasPartial) && (
        <p className="small muted">
          {hasUnknown &&
            "계산 기준값이 없는 동적 setpoint는 표시하지 않았습니다. "}
          {hasPartial &&
            "조회 기간 중 변경된 setpoint는 단일 경계선으로 표시하지 않았습니다."}
        </p>
      )}
    </>
  );
}
