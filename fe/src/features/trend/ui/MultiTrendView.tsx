import { useQueries } from "@tanstack/react-query";
import type { Hierarchy } from "../../hierarchy/index.ts";
import { trendQuery } from "../api/trend.queries.ts";
import type { TrendSeries } from "../api/trend-view.queries.ts";
import { TrendChart } from "./TrendChart.tsx";
import { Card, CardHeader } from "../../../shared/ui/card.tsx";
import { ErrorState } from "../../../shared/ui/ErrorState.tsx";
import { LoadingState } from "../../../shared/ui/LoadingState.tsx";
import { errorMessage } from "../../../shared/api/http-client.ts";
import { remoteApi } from "../../../shared/api/be-adapter.ts";
import {
  intervalLabel,
  pointCount,
  remoteTrendIntervals,
  resolveInterval,
  MAX_TREND_POINTS,
} from "../model/trend-interval.ts";

export function MultiTrendView({
  hierarchy,
  series,
  showAnomalies,
}: {
  hierarchy: Hierarchy;
  series: TrendSeries[];
  showAnomalies: boolean;
}) {
  const limited = series.slice(0, 24);
  const tags = new Map(
    hierarchy.equipment
      .flatMap((asset) => asset.tags)
      .map((tag) => [tag.id, tag]),
  );
  const intervals = limited.map((item) =>
    resolveInterval(
      "auto",
      item.start,
      item.end,
      remoteApi ? remoteTrendIntervals : undefined,
    ),
  );
  const queries = useQueries({
    queries: limited.map((item, index) =>
      trendQuery(
        pointCount(item.start, item.end, intervals[index]) <= MAX_TREND_POINTS
          ? item.sensorId
          : "",
        item.start,
        item.end,
        intervals[index],
      ),
    ),
  });
  if (series.length > 24)
    return (
      <ErrorState message="한 번에 표시할 수 있는 센서는 최대 24개입니다." />
    );
  return (
    <>
      {showAnomalies && (
        <p className="small muted">
          이상 구간 표시가 요청되었습니다. 현재 조회 API에는 이상 구간 데이터가
          없어 실측 추이만 표시합니다.
        </p>
      )}
      {limited.map((item, index) => {
        const tag = tags.get(item.sensorId);
        const query = queries[index];
        const invalid =
          Date.parse(item.start) >= Date.parse(item.end) ||
          pointCount(item.start, item.end, intervals[index]) > MAX_TREND_POINTS;
        return (
          <Card key={`${item.sensorId}-${item.start}-${item.end}-${index}`}>
            <CardHeader
              title={`${tag?.name ?? item.sensorId} · ${item.sensorId}`}
              description={`${item.start} ~ ${item.end} · ${intervalLabel(intervals[index])} 간격 · ${tag?.unit ?? ""}`}
            />
            {invalid ? (
              <ErrorState message="이 센서의 조회 기간이 잘못됐거나 조회량이 너무 많습니다." />
            ) : query.isPending ? (
              <LoadingState />
            ) : query.isError ? (
              <ErrorState
                message={errorMessage(query.error)}
                retry={() => void query.refetch()}
              />
            ) : query.data.points.length === 0 ? (
              <p className="muted">이 기간의 측정 데이터가 없습니다.</p>
            ) : (
              <TrendChart
                interval={intervals[index]}
                points={query.data.points}
                limit={query.data.limit}
                unit={query.data.unit}
              />
            )}
          </Card>
        );
      })}
    </>
  );
}
