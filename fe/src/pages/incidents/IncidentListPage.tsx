import { useInfiniteQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";
import type { Hierarchy, Selection } from "../../features/hierarchy/index.ts";
import {
  STATUS_LABELS,
  incidentListSchema,
  levelLabel,
  levelTone,
  type IncidentStatus,
  type IncidentSummary,
} from "../../features/incidents/index.ts";
import { http, errorMessage } from "../../shared/api/http-client.ts";
import { Card, CardHeader } from "../../shared/ui/card.tsx";
import { Select } from "../../shared/ui/select.tsx";
import { Badge } from "../../shared/ui/badge.tsx";
import { Button } from "../../shared/ui/button.tsx";
import { LoadingState } from "../../shared/ui/LoadingState.tsx";
import { ErrorState } from "../../shared/ui/ErrorState.tsx";
import { EmptyState } from "../../shared/ui/EmptyState.tsx";
import { dateTime } from "../../shared/lib/date-time.ts";

const FILTERS = ["status", "min_level", "actionable"] as const;

export function IncidentListPage({
  selection,
}: {
  hierarchy: Hierarchy;
  selection: Selection;
}) {
  const [params, setParams] = useSearchParams();
  const filters = {
    plant_id: selection.plantId ?? undefined,
    equipment_group_id: selection.unitId ?? undefined,
    equipment_id: selection.equipmentId ?? undefined,
    status: (params.get("status") || undefined) as IncidentStatus | undefined,
    min_level: params.get("min_level") || undefined,
    actionable: params.get("actionable") || undefined,
  };
  const query = useInfiniteQuery({
    queryKey: ["incidents", "pages", filters],
    initialPageParam: "",
    queryFn: async ({ pageParam, signal }) =>
      incidentListSchema.parse(
        (
          await http.get("/incidents", {
            params: Object.fromEntries(
              Object.entries({
                ...filters,
                cursor: pageParam,
                limit: 50,
              }).filter(([, value]) => value !== undefined && value !== ""),
            ),
            signal,
          })
        ).data,
      ),
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    refetchInterval: 60000,
  });
  const items = query.data?.pages.flatMap((page) => page.items) ?? [];
  const setFilter = (key: (typeof FILTERS)[number], value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next);
  };
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">INCIDENTS</div>
          <h1>이상 사건</h1>
          <p>
            분석기가 알람을 묶어 판정한 사건과 원인 후보(추정)를 확인하세요.
          </p>
        </div>
        <Badge tone="success">1분 주기 조회</Badge>
      </div>
      <Card>
        <div className="filter-bar">
          <Select
            aria-label="상태 필터"
            value={params.get("status") ?? ""}
            onChange={(e) => setFilter("status", e.target.value)}
          >
            <option value="">시작된 사건 전체</option>
            {(Object.keys(STATUS_LABELS) as IncidentStatus[]).map((key) => (
              <option key={key} value={key}>
                {STATUS_LABELS[key]}
              </option>
            ))}
          </Select>
          <Select
            aria-label="최소 등급 필터"
            value={params.get("min_level") ?? ""}
            onChange={(e) => setFilter("min_level", e.target.value)}
          >
            <option value="">전체 등급</option>
            {[4, 3, 2, 1].map((level) => (
              <option key={level} value={level}>
                {levelLabel(level)} 이상
              </option>
            ))}
          </Select>
          <Select
            aria-label="조치 필요 필터"
            value={params.get("actionable") ?? ""}
            onChange={(e) => setFilter("actionable", e.target.value)}
          >
            <option value="">조치 필요 여부 전체</option>
            <option value="true">조치 필요</option>
            <option value="false">조치 불필요</option>
          </Select>
        </div>
        <CardHeader
          title="사건 목록"
          description="선택한 플랜트·공정·설비 범위 · 시작 시각 최신순"
        />
        {query.isPending ? (
          <LoadingState />
        ) : query.isError ? (
          <ErrorState
            message={errorMessage(query.error)}
            retry={() => void query.refetch()}
          />
        ) : items.length ? (
          <IncidentTable items={items} />
        ) : (
          <EmptyState
            title="기간 내 사건이 없습니다"
            description="선택한 범위와 필터를 확인해 주세요."
          />
        )}
        {query.hasNextPage && (
          <Button
            variant="outline"
            disabled={query.isFetchingNextPage}
            onClick={() => void query.fetchNextPage()}
          >
            {query.isFetchingNextPage ? "불러오는 중" : "더 보기"}
          </Button>
        )}
      </Card>
    </div>
  );
}

function IncidentTable({ items }: { items: IncidentSummary[] }) {
  return (
    <div className="table-scroll">
      <table aria-label="이상 사건 목록">
        <thead>
          <tr>
            <th scope="col">상태</th>
            <th scope="col">시작</th>
            <th scope="col">설비</th>
            <th scope="col">최고 등급</th>
            <th scope="col">선행 센서</th>
            <th scope="col">진단(추정)</th>
            <th scope="col">사건 점수</th>
            <th scope="col">대응</th>
            <th scope="col">알람</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.incident_id}
              className={item.actionable ? undefined : "row-dimmed"}
              title={item.actionable ? undefined : item.grade_reason}
            >
              <td>{STATUS_LABELS[item.status]}</td>
              <td className="small mono">
                {dateTime(item.incident_start_time)}
              </td>
              <td>
                <Link
                  className="equipment-link"
                  to={`/incidents/${encodeURIComponent(item.incident_id)}`}
                >
                  {item.equipment_name}
                  <small>{item.incident_id}</small>
                </Link>
              </td>
              <td>
                <Badge tone={levelTone(item.peak_level)}>
                  {levelLabel(item.peak_level)}
                </Badge>
              </td>
              <td>{item.lead_sensor_name ?? "미기록"}</td>
              <td>{item.diagnosis}</td>
              <td className="mono">{item.incident_score}</td>
              <td>
                {item.alarm_grade}
                {!item.actionable && (
                  <small className="muted"> · 조치 불필요</small>
                )}
              </td>
              <td className="mono">{item.linked_alarm_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
