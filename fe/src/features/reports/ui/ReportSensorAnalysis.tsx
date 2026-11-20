import { useEffect, useState } from "react";
import { useQueries } from "@tanstack/react-query";
import { Activity, ChartNoAxesCombined } from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useReportDraftStore } from "../model/report-draft.store.ts";
import { trendQuery } from "../../trend/api/trend.queries.ts";
import type { Equipment } from "../../../shared/api/contracts/hierarchy.ts";
import type {
  MaintenanceReport,
  ReportSensor,
} from "../../../shared/api/contracts/maintenance-report.ts";
import { fromKstInput, kstInput } from "../model/maintenance-report.ts";

const colors = ["#e76561", "#3299c6", "#139c80", "#9c7cc3"];
const timeLabel = (time: number) =>
  new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(time);
export function ReportSensorAnalysis({
  model,
  equipment,
  reportId,
}: {
  model: MaintenanceReport;
  equipment?: Equipment;
  reportId: string;
}) {
  const alarmAt = Date.parse(
    model.original.alarm?.occurredAt ?? model.incident.alarmAt,
  );
  const reference = Number.isFinite(alarmAt) ? alarmAt : Date.now();
  const [from, setFrom] = useState(() =>
    kstInput(new Date(reference - 3600_000).toISOString()),
  );
  const [to, setTo] = useState(() =>
    kstInput(new Date(reference + 90 * 60_000).toISOString()),
  );
  const [hidden, setHidden] = useState<string[]>([]);
  const sensors = model.incident.sensorIds
    .map((id): ReportSensor | undefined => {
      const captured = model.original.sensors.find((s) => s.id === id);
      const tag = equipment?.tags.find((s) => s.id === id);
      return (
        captured ??
        (tag
          ? {
              id,
              name: tag.name,
              unit: tag.unit,
              baseline: null,
              observed: null,
            }
          : undefined)
      );
    })
    .filter((s): s is ReportSensor => !!s);
  const start = Date.parse(fromKstInput(from));
  const stop = Date.parse(fromKstInput(to));
  const valid =
    Number.isFinite(start) &&
    Number.isFinite(stop) &&
    start < stop &&
    stop - start <= 7 * 86400000;
  const queries = useQueries({
    queries: sensors.map((sensor) => ({
      ...trendQuery(
        sensor.id,
        fromKstInput(from),
        fromKstInput(to),
        stop - start > 10000 * 60000 ? "1h" : "1m",
      ),
      enabled: valid && model.original.kind !== "example",
      retry: false,
    })),
  });
  useEffect(() => {
    if (model.original.kind === "example") return;
    const captured = sensors.flatMap((sensor, i) =>
      queries[i].data?.points.length && !sensor.points
        ? [{ ...sensor, points: queries[i].data!.points }]
        : [],
    );
    if (captured.length)
      useReportDraftStore.getState().captureSensors(reportId, captured);
  }, [model.original.kind, sensors, queries, reportId]);
  return (
    <div className="mr-analysis">
      <div className="mr-analysis-heading">
        <h3>
          <ChartNoAxesCombined size={17} /> 센서 종합 분석{" "}
          <span>사건 관련 센서 · 개별 측정 단위</span>
        </h3>
        <div className="mr-time-range">
          <label>
            조회 시작
            <input
              aria-label="그래프 조회 시작"
              type="datetime-local"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
            />
          </label>
          <span>~</span>
          <label>
            조회 종료
            <input
              aria-label="그래프 조회 종료"
              type="datetime-local"
              value={to}
              onChange={(e) => setTo(e.target.value)}
            />
          </label>
        </div>
      </div>
      {!valid && (
        <p role="alert" className="mr-validation">
          조회 기간을 확인해 주세요. 최대 7일의 알람 전후 구간을 조회할 수
          있습니다.
        </p>
      )}
      {model.original.kind === "example" && (
        <div className="mr-example-label">
          예시 센서 데이터 · 실제 설비 측정값이 아닙니다.
        </div>
      )}
      {sensors.length ? (
        <>
          <div className="mr-sensor-toggles" aria-label="센서별 표시 여부">
            {sensors.map((sensor, i) => (
              <label
                key={sensor.id}
                style={
                  {
                    "--sensor-color": colors[i % colors.length],
                  } as React.CSSProperties
                }
              >
                <input
                  type="checkbox"
                  checked={!hidden.includes(sensor.id)}
                  onChange={(e) =>
                    setHidden((ids) =>
                      e.target.checked
                        ? ids.filter((id) => id !== sensor.id)
                        : [...ids, sensor.id],
                    )
                  }
                />
                <span className="mr-dot" />
                {sensor.name} <small>{sensor.id}</small>
              </label>
            ))}
          </div>
          <div className="mr-analysis-body">
            <div className="mr-sensor-charts">
              {sensors.map((sensor, i) => {
                if (hidden.includes(sensor.id)) return null;
                const query = queries[i];
                const points = (
                  model.original.kind === "example"
                    ? (sensor.points ?? [])
                    : (query.data?.points ?? [])
                )
                  .map((p) => ({ ...p, time: Date.parse(p.time) }))
                  .filter((p) => p.time >= start && p.time < stop);
                const before = points
                  .filter((p) => p.time < alarmAt && p.value !== null)
                  .map((p) => p.value!);
                const baseline =
                  sensor.baseline ??
                  (before.length
                    ? before.reduce((a, b) => a + b, 0) / before.length
                    : null);
                return (
                  <div className="mr-sensor-chart" key={sensor.id}>
                    <div className="mr-chart-caption">
                      <strong>
                        {sensor.name} <small>({sensor.unit})</small>
                      </strong>
                      <span>{sensor.id}</span>
                    </div>
                    {!valid ? (
                      <p className="mr-empty">유효한 조회 기간을 선택하세요.</p>
                    ) : query.isPending && model.original.kind !== "example" ? (
                      <p className="mr-empty" role="status">
                        시계열 데이터를 조회하고 있습니다…
                      </p>
                    ) : query.isError && model.original.kind !== "example" ? (
                      <div className="mr-empty">
                        <p>시계열을 불러오지 못했습니다.</p>
                        <button
                          type="button"
                          onClick={() => void query.refetch()}
                        >
                          다시 조회
                        </button>
                      </div>
                    ) : !points.length ? (
                      <p className="mr-empty">
                        이 구간에 저장된 측정값이 없습니다.
                      </p>
                    ) : (
                      <div
                        role="img"
                        aria-label={`${sensor.name} 센서 그래프, 단위 ${sensor.unit}, 알람 시점과 알람 이후 구간 표시`}
                        className="mr-chart-canvas"
                      >
                        <ResponsiveContainer width="100%" height={125}>
                          <AreaChart
                            data={points}
                            margin={{ top: 12, right: 12, left: 0, bottom: 0 }}
                          >
                            <CartesianGrid
                              stroke="#e9eff1"
                              vertical={false}
                              strokeDasharray="3 4"
                            />
                            <XAxis
                              dataKey="time"
                              type="number"
                              scale="time"
                              domain={[start, stop]}
                              tickFormatter={timeLabel}
                              tick={{ fontSize: 10, fill: "#83959c" }}
                              minTickGap={45}
                              axisLine={false}
                              tickLine={false}
                            />
                            <YAxis
                              domain={["auto", "auto"]}
                              width={48}
                              tick={{ fontSize: 10, fill: "#83959c" }}
                              tickFormatter={(v: number) =>
                                Number(v.toPrecision(4)).toLocaleString()
                              }
                              axisLine={false}
                              tickLine={false}
                            />
                            <Tooltip
                              labelFormatter={(v) => timeLabel(Number(v))}
                              formatter={(value) => [
                                `${value} ${sensor.unit}`,
                                sensor.name,
                              ]}
                              contentStyle={{
                                fontSize: 11,
                                borderRadius: 6,
                                border: "1px solid #e4eaed",
                              }}
                            />
                            {Number.isFinite(alarmAt) &&
                              alarmAt < stop &&
                              alarmAt >= start && (
                                <ReferenceArea
                                  x1={alarmAt}
                                  x2={stop}
                                  fill="#f7d9d6"
                                  fillOpacity={0.35}
                                />
                              )}
                            {Number.isFinite(alarmAt) &&
                              alarmAt <= stop &&
                              alarmAt >= start && (
                                <ReferenceLine
                                  x={alarmAt}
                                  stroke="#e76561"
                                  strokeDasharray="4 3"
                                  label={{
                                    value: "알람",
                                    fill: "#c64c48",
                                    fontSize: 10,
                                    position: "insideTopRight",
                                  }}
                                />
                              )}
                            {baseline !== null && (
                              <ReferenceLine
                                y={baseline}
                                stroke="#9bafb7"
                                strokeDasharray="3 4"
                              />
                            )}
                            <Area
                              type="linear"
                              dataKey="value"
                              stroke={colors[i % colors.length]}
                              fill={colors[i % colors.length]}
                              fillOpacity={0.07}
                              strokeWidth={2}
                              isAnimationActive={false}
                              connectNulls={false}
                            />
                          </AreaChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                  </div>
                );
              })}
              {hidden.length === sensors.length && (
                <p className="mr-empty">표시할 센서를 선택하세요.</p>
              )}
              <p className="mr-chart-note">
                점선: 알람 전 구간 평균(확보 시) · 음영: 알람 발생 이후 확인
                구간. 음영 전체가 이상으로 판정된 것은 아닙니다.
              </p>
            </div>
            <aside className="mr-sensor-summary">
              <h4>
                <Activity size={15} /> 센서 이상 요약
              </h4>
              {sensors.map((sensor, i) => {
                const points =
                  model.original.kind === "example"
                    ? (sensor.points ?? [])
                    : (queries[i].data?.points ?? []);
                const before = points
                  .filter(
                    (p) =>
                      Date.parse(p.time) < alarmAt &&
                      Date.parse(p.time) >= start &&
                      p.value !== null,
                  )
                  .map((p) => p.value!);
                const after = points
                  .filter(
                    (p) =>
                      Date.parse(p.time) >= alarmAt &&
                      Date.parse(p.time) < stop &&
                      p.value !== null,
                  )
                  .map((p) => p.value!);
                const baseline =
                  sensor.baseline ??
                  (before.length
                    ? before.reduce((a, b) => a + b, 0) / before.length
                    : null);
                const observed = after.at(-1) ?? sensor.observed;
                const format = (value: number | null) =>
                  value === null
                    ? "미확보"
                    : Number(value.toFixed(2)).toLocaleString();
                return (
                  <div key={sensor.id}>
                    <span
                      className="mr-summary-id"
                      style={{ color: colors[i % colors.length] }}
                    >
                      {sensor.id}
                    </span>
                    <strong>{sensor.name}</strong>
                    <p>
                      {format(baseline)} → {format(observed)}{" "}
                      <small>{sensor.unit}</small>
                    </p>
                  </div>
                );
              })}
              <p className="mr-summary-note">
                알람 전 평균과 구간 내 마지막 값을 비교합니다. 원인 판단은 현장
                검증 결과와 함께 확인하세요.
              </p>
            </aside>
          </div>
        </>
      ) : (
        <p className="mr-empty">
          연결된 관련 센서가 없습니다. 수정 모드에서 사건 관련 센서를
          선택하세요.
        </p>
      )}
    </div>
  );
}
