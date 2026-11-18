import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router";
import { TrendingUp, Info } from "lucide-react";
import type { Hierarchy, Selection } from "../../features/hierarchy/index.ts";
import {
  TrendChart,
  trendQuery,
  useTrendStore,
} from "../../features/trend/index.ts";
import { Card, CardHeader } from "../../shared/ui/card.tsx";
import { Select } from "../../shared/ui/select.tsx";
import { DateRangePicker } from "../../shared/ui/DateRangePicker.tsx";
import { EmptyState } from "../../shared/ui/EmptyState.tsx";
import { ErrorState } from "../../shared/ui/ErrorState.tsx";
import { LoadingState } from "../../shared/ui/LoadingState.tsx";
import { defaultRange } from "../../shared/lib/date-time.ts";
import { errorMessage } from "../../shared/api/http-client.ts";
import { remoteApi } from "../../shared/api/be-adapter.ts";
import {
  intervalMode,
  resolveInterval,
  intervalLabel,
  trendRange,
  pointCount,
  remoteTrendIntervals,
  MAX_TREND_POINTS,
} from "../../features/trend/model/trend-interval.ts";
export function TrendPage({
  hierarchy,
  selection,
}: {
  hierarchy: Hierarchy;
  selection: Selection;
}) {
  const [params, setParams] = useSearchParams();
  const eq = hierarchy.equipment.find((e) => e.id === selection.equipmentId);
  const sensor =
    eq?.tags.find((t) => t.id === params.get("sensor_id")) ?? eq?.tags[0];
  const range = defaultRange();
  const from = params.get("from") ?? range.from;
  const to = params.get("to") ?? range.to;
  const bounds = trendRange(from, to);
  const valid = bounds.valid;
  const requestedMode = intervalMode(params.get("interval"));
  const mode = remoteApi && requestedMode === "1s" ? "auto" : requestedMode;
  const interval = resolveInterval(
    mode,
    bounds.from,
    bounds.to,
    remoteApi ? remoteTrendIntervals : undefined,
  );
  const tooManyPoints =
    valid && pointCount(bounds.from, bounds.to, interval) > MAX_TREND_POINTS;
  const setContext = useTrendStore((state) => state.setContext);
  const reset = useTrendStore((state) => state.reset);
  const sensorId = sensor?.id ?? null;
  const startTime = sensorId && valid ? bounds.from : null;
  const endTime = sensorId && valid ? bounds.to : null;
  useEffect(() => {
    setContext({
      sensor_id: sensorId,
      sensor_start_time: startTime,
      sensor_end_time: endTime,
      sensor_interval: sensorId && valid ? interval : null,
    });
  }, [sensorId, startTime, endTime, valid, interval, setContext]);
  useEffect(() => () => reset(), [reset]);
  const query = useQuery(
    trendQuery(
      valid && !tooManyPoints ? (sensor?.id ?? "") : "",
      bounds.from,
      bounds.to,
      interval,
    ),
  );
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">SIGNAL ANALYTICS</div>
          <h1>트렌드 분석</h1>
          <p>센서 신호의 변화와 기준 초과 구간을 확인하세요.</p>
        </div>
      </div>
      <Card>
        <div className="filter-bar">
          <div className="inline">
            <label htmlFor="trend-sensor" className="small muted">
              센서
            </label>
            <Select
              id="trend-sensor"
              value={sensor?.id ?? ""}
              disabled={!eq}
              onChange={(e) => {
                const p = new URLSearchParams(params);
                p.set("sensor_id", e.target.value);
                setParams(p);
              }}
            >
              {!eq ? (
                <option value="">설비를 먼저 선택하세요</option>
              ) : (
                eq.tags.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} · {t.id}
                  </option>
                ))
              )}
            </Select>
          </div>
          <div className="inline">
            <label htmlFor="trend-interval" className="small muted">
              조회 간격
            </label>
            <Select
              id="trend-interval"
              value={mode}
              onChange={(e) => {
                const p = new URLSearchParams(params);
                p.set("interval", e.target.value);
                setParams(p);
              }}
            >
              <option value="auto">자동</option>
              {!remoteApi && <option value="1s">1초</option>}
              <option value="1m">1분</option>
              <option value="1h">1시간</option>
              <option value="1d">1일</option>
            </Select>
            {mode === "auto" && valid && (
              <span className="small muted">
                현재 {intervalLabel(interval)} 간격
              </span>
            )}
          </div>
          <DateRangePicker
            withTime
            from={bounds.inputFrom}
            to={bounds.inputTo}
            onChange={(f, t) => {
              const p = new URLSearchParams(params);
              p.set("from", f);
              p.set("to", t);
              setParams(p);
            }}
          />
        </div>
      </Card>
      {!eq ? (
        <Card>
          <EmptyState
            title="분석할 설비를 선택하세요"
            description="왼쪽 설비 탐색에서 설비를 선택하거나 대화에서 요청해 주세요."
          />
        </Card>
      ) : !valid ? (
        <ErrorState message="시작 일자와 종료 일자를 확인하세요." />
      ) : tooManyPoints ? (
        <ErrorState message="조회 지점은 최대 10,000개입니다. 기간을 줄이거나 조회 간격을 자동 또는 더 큰 간격으로 변경하세요." />
      ) : query.isPending ? (
        <LoadingState />
      ) : query.isError ? (
        <ErrorState
          message={errorMessage(query.error)}
          retry={() => void query.refetch()}
        />
      ) : (
        <>
          <Card>
            <CardHeader
              title={`${eq.name} · ${sensor!.name}`}
              description={`${from} ~ ${to} · ${intervalLabel(interval)} 간격 · ${query.data.unit}`}
            />
            <div className="chart-number">
              {query.data.points.at(-1)?.value?.toFixed(2) ?? "—"}
              <small>{query.data.unit}</small>
              <span className="muted small">
                최대 {query.data.max ?? "—"}
                {query.data.limit !== null ? ` / 기준 ${query.data.limit}` : ""}
              </span>
            </div>
            <TrendChart
              interval={interval}
              points={query.data.points}
              limit={query.data.limit}
              unit={query.data.unit}
            />
            <div className="chart-legend">
              <span className="legend-line" /> 실측값{" "}
              {query.data.limit !== null ? (
                <>
                  <span className="legend-line red-line" /> 기준값{" "}
                  <span className="muted">
                    기준선 위의 값은 초과 구간입니다.
                  </span>
                </>
              ) : null}
            </div>
          </Card>
          <Card className="interpretation">
            <TrendingUp size={22} />
            <div>
              <h2>상승 추세</h2>
              <p>
                {from}부터 {to}까지 최대값은 {query.data.max ?? "—"}{" "}
                {query.data.unit}입니다.{" "}
                {query.data.limit !== null && query.data.max !== null
                  ? `기준값은 ${query.data.limit} ${query.data.unit}입니다. `
                  : "기준값이 설정되지 않았습니다. "}
                {query.data.limit !== null && query.data.max !== null
                  ? query.data.max > query.data.limit
                    ? "기준을 넘은 구간을 확인하고 현장 점검을 권장합니다."
                    : "조회 기간 내 기준 초과가 없습니다."
                  : ""}
              </p>
            </div>
          </Card>
          <p className="small muted inline">
            <Info size={14} />
            데모 시계열을 사용합니다. 한계값과 분석 결과는 실제 API 연결 시 서버
            결과로 대체됩니다.
          </p>
        </>
      )}
    </div>
  );
}
