import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SensorInterval } from "../model/trend-interval.ts";
export function TrendChart({
  interval = "1h",
  points,
  limit,
  unit,
}: {
  interval?: SensorInterval;
  points: { time: string; value: number | null }[];
  limit: number | null;
  unit: string;
}) {
  return (
    <div
      className="trend-chart"
      role="img"
      aria-label={
        limit === null
          ? `시계열 차트, 단위 ${unit}`
          : `시계열 차트, 기준 ${limit} ${unit}`
      }
    >
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={points.map((p) => ({
            ...p,
            excess:
              p.value !== null && limit !== null && p.value > limit
                ? p.value
                : null,
          }))}
          margin={{ top: 20, right: 30, bottom: 5, left: 0 }}
        >
          <defs>
            <linearGradient id="trend-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#168b81" stopOpacity={0.22} />
              <stop offset="100%" stopColor="#168b81" stopOpacity={0} />
            </linearGradient>
          </defs>
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
                      ...(interval.endsWith("s") ? { second: "2-digit" } : {}),
                    }),
              }).format(new Date(v))
            }
            minTickGap={65}
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 11, fill: "#7b8b92" }}
          />
          <YAxis
            domain={[
              0,
              (maximum: number) =>
                Math.ceil(Math.max(maximum, limit ?? 0) * 1.15),
            ]}
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 11, fill: "#7b8b92" }}
            width={45}
          />
          <Tooltip
            labelFormatter={(v) =>
              new Date(String(v)).toLocaleString("ko-KR", {
                timeZone: "Asia/Seoul",
              })
            }
            formatter={(value) => [`${value} ${unit}`, "실측값"]}
            contentStyle={{
              borderRadius: 8,
              border: "1px solid #e3e9eb",
              fontSize: 12,
            }}
          />
          {limit !== null ? (
            <ReferenceLine
              y={limit}
              stroke="#d66554"
              strokeDasharray="5 4"
              label={{
                value: `기준 ${limit}`,
                position: "insideTopRight",
                fill: "#c25847",
                fontSize: 11,
              }}
            />
          ) : null}
          <Area
            type="monotone"
            dataKey="value"
            stroke="#168b81"
            strokeWidth={2}
            fill="url(#trend-fill)"
            isAnimationActive={false}
          />
          {limit !== null ? (
            <Area
              type="monotone"
              dataKey="excess"
              name="기준 초과"
              stroke="#d66554"
              strokeWidth={2}
              fill="#d66554"
              fillOpacity={0.1}
              baseValue={limit}
              isAnimationActive={false}
            />
          ) : null}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
