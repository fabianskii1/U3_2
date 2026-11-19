import { useState } from "react";
import { useQueries } from "@tanstack/react-query";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Hierarchy } from "../../../shared/api/contracts/hierarchy.ts";
import { Card, CardHeader } from "../../../shared/ui/card.tsx";
import { trendQuery } from "../api/trend.queries.ts";

type SensorKind = "VIB" | "TB" | "TF" | "PS" | "PD" | "AMP" | "RPM" | "VOLT";
type Mode = "deviation" | "raw";

const sensorKinds: {
  id: SensorKind;
  label: string;
  matches: (name: string) => boolean;
}[] = [
  { id: "VIB", label: "진동", matches: (name) => name.includes("진동") },
  {
    id: "TB",
    label: "베어링 온도",
    matches: (name) => name.includes("베어링 온도"),
  },
  {
    id: "TF",
    label: "유체 온도",
    matches: (name) => name.includes("유체 온도"),
  },
  { id: "PS", label: "흡입압", matches: (name) => name.includes("흡입압") },
  { id: "PD", label: "토출압", matches: (name) => name.includes("토출압") },
  { id: "AMP", label: "전류", matches: (name) => name.includes("전류") },
  { id: "RPM", label: "RPM", matches: (name) => name.includes("회전수") },
  { id: "VOLT", label: "전압", matches: (name) => name.includes("전압") },
];

const pumpColors = [
  "#168b81",
  "#d97145",
  "#5c77c8",
  "#a579b9",
  "#c6a23d",
  "#4f98b0",
];

function comparisonRange() {
  const end = Math.floor(Date.now() / 3_600_000) * 3_600_000;
  return {
    from: new Date(end - 7 * 86_400_000).toISOString(),
    to: new Date(end).toISOString(),
  };
}

function kstHour(value: string) {
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

export function buildComparisonData(
  series: { id: string; points: { time: string; value: number | null }[] }[],
  mode: Mode,
) {
  const rows = new Map<string, Record<string, string | number>>();
  for (const { id, points } of series) {
    const values = points.flatMap((point) =>
      point.value === null ? [] : [point.value],
    );
    const average = values.length
      ? values.reduce((sum, value) => sum + value, 0) / values.length
      : 0;
    for (const point of points) {
      if (point.value === null) continue;
      const row = rows.get(point.time) ?? { time: point.time };
      row[id] =
        mode === "deviation"
          ? Number((point.value - average).toFixed(3))
          : point.value;
      rows.set(point.time, row);
    }
  }
  return [...rows.values()].sort((a, b) =>
    String(a.time).localeCompare(String(b.time)),
  );
}

export function PumpComparisonChart({
  hierarchy,
  plantId,
  unitId,
}: {
  hierarchy: Hierarchy;
  plantId: string;
  unitId: string;
}) {
  const [kind, setKind] = useState<SensorKind>("VIB");
  const [mode, setMode] = useState<Mode>("deviation");
  const [hiddenPumpIds, setHiddenPumpIds] = useState<string[]>([]);
  const [range] = useState(comparisonRange);
  const group = hierarchy.units.find(
    (unit) => unit.id === unitId && unit.plantId === plantId,
  );
  const pumps = hierarchy.equipment
    .filter(
      (equipment) =>
        equipment.unitId === group?.id && /^P[1-6]$/.test(equipment.id),
    )
    .sort((a, b) => a.id.localeCompare(b.id, "en", { numeric: true }));
  const sensorKind = sensorKinds.find((item) => item.id === kind)!;
  const series = pumps.map((equipment) => ({
    equipment,
    sensor: equipment.tags.find((tag) => sensorKind.matches(tag.name)),
  }));
  const queries = useQueries({
    queries: series.map(({ sensor }) =>
      trendQuery(sensor?.id ?? "", range.from, range.to, "1h"),
    ),
  });
  const unit = series.find(({ sensor }) => sensor)?.sensor?.unit ?? "";
  const data = buildComparisonData(
    series.map(({ equipment }, index) => ({
      id: equipment.id,
      points: queries[index].data?.points ?? [],
    })),
    mode,
  );
  const loading = queries.some((query) => query.isPending && query.isFetching);
  const hasError = queries.some((query) => query.isError);
  const visibleSeries = series.filter(
    ({ equipment, sensor }) => sensor && !hiddenPumpIds.includes(equipment.id),
  );
  const togglePump = (id: string) => {
    setHiddenPumpIds((previous) =>
      previous.includes(id)
        ? previous.filter((pumpId) => pumpId !== id)
        : [...previous, id],
    );
  };

  return (
    <Card className="pump-comparison">
      <CardHeader
        title={`${sensorKind.label} 비교 (${mode === "deviation" ? "7일 평균 대비" : "실제 값"}${unit ? ` · ${unit}` : ""})`}
        description={`${group?.name ?? "CDU 그룹"} · 최근 완료된 7일 · 1시간 평균 · 펌프마다 한 선`}
      />
      <div className="pump-comparison-controls">
        <div
          className="pump-comparison-tabs"
          role="group"
          aria-label="센서 종류"
        >
          {sensorKinds.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-pressed={kind === item.id}
              onClick={() => setKind(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div
          className="pump-comparison-tabs"
          role="group"
          aria-label="값 표시 방식"
        >
          <button
            type="button"
            aria-pressed={mode === "deviation"}
            onClick={() => setMode("deviation")}
          >
            7일 평균 대비 차이
          </button>
          <button
            type="button"
            aria-pressed={mode === "raw"}
            onClick={() => setMode("raw")}
          >
            실제 값
          </button>
        </div>
      </div>
      {pumps.length > 0 && (
        <div
          className="pump-comparison-equipment"
          role="group"
          aria-label="설비 표시"
        >
          {series.map(({ equipment, sensor }) => {
            const visible = !hiddenPumpIds.includes(equipment.id);
            return (
              <button
                key={equipment.id}
                type="button"
                aria-label={`${equipment.id} 선 ${visible ? "숨기기" : "표시"}`}
                aria-pressed={visible}
                disabled={!sensor}
                onClick={() => togglePump(equipment.id)}
              >
                <span
                  className="pump-comparison-swatch"
                  style={{
                    backgroundColor:
                      pumpColors[Number(equipment.id.slice(1)) - 1],
                  }}
                  aria-hidden="true"
                />
                {equipment.id}
              </button>
            );
          })}
        </div>
      )}
      {pumps.length === 0 ? (
        <p className="pump-comparison-message">
          선택한 그룹에 P1~P6 설비가 없습니다.
        </p>
      ) : loading && data.length === 0 ? (
        <p className="pump-comparison-message">시계열을 불러오는 중입니다.</p>
      ) : data.length === 0 ? (
        <p className="pump-comparison-message">
          {hasError
            ? "시계열을 불러오지 못했습니다."
            : "선택한 센서의 7일 측정값이 없습니다."}
        </p>
      ) : visibleSeries.length === 0 ? (
        <p className="pump-comparison-message">표시할 펌프를 선택하세요.</p>
      ) : (
        <>
          {hasError && (
            <p className="pump-comparison-message">
              일부 펌프의 시계열을 불러오지 못했습니다.
            </p>
          )}
          <div
            className="pump-comparison-chart"
            role="img"
            aria-label={`${sensorKind.label} P1부터 P6까지 1시간 평균 비교 차트`}
          >
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={data}
                margin={{ top: 12, right: 24, bottom: 8, left: 8 }}
              >
                <CartesianGrid
                  vertical={false}
                  strokeDasharray="3 5"
                  stroke="#e8edef"
                />
                <XAxis
                  dataKey="time"
                  tickFormatter={(value) => kstHour(String(value))}
                  minTickGap={55}
                  tick={{ fontSize: 11 }}
                />
                <YAxis
                  width={58}
                  tick={{ fontSize: 11 }}
                  domain={["auto", "auto"]}
                />
                <Tooltip
                  labelFormatter={(value) => `${kstHour(String(value))} KST`}
                  formatter={(value, name) => [
                    `${Number(value).toLocaleString("ko-KR", { maximumFractionDigits: 3 })} ${unit}`,
                    String(name),
                  ]}
                />
                {visibleSeries.map(({ equipment }) => (
                  <Line
                    key={equipment.id}
                    type="monotone"
                    dataKey={equipment.id}
                    name={equipment.id}
                    stroke={pumpColors[Number(equipment.id.slice(1)) - 1]}
                    strokeWidth={2}
                    dot={false}
                    connectNulls={false}
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
      {mode === "deviation" && data.length > 0 && (
        <p className="pump-comparison-note">
          각 펌프의 조회 기간 평균을 0으로 놓고 차이를 표시합니다.
        </p>
      )}
    </Card>
  );
}
