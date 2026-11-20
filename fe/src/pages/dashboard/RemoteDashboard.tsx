import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";
import { z } from "zod";
import { http, errorMessage } from "../../shared/api/http-client.ts";
import { Card, CardHeader } from "../../shared/ui/card.tsx";
import { LoadingState } from "../../shared/ui/LoadingState.tsx";
import { ErrorState } from "../../shared/ui/ErrorState.tsx";
import type { Hierarchy } from "../../features/hierarchy/index.ts";
import { IncidentPanel } from "../../features/incidents/index.ts";
import { MultiTrendView } from "../../features/trend/ui/MultiTrendView.tsx";

const schema = z.object({
  equipment_count: z.number(),
  normal_count: z.number(),
  plant_count: z.number(),
  unit_count: z.number(),
  high_count: z.number(),
  priority: z.object({
    status: z.string(),
    active_count: z.number(),
    affected_equipment_count: z.number(),
    unknown_count: z.number(),
    unscored_count: z.number(),
    as_of: z.string(),
    items: z.array(
      z.object({
        equipment_id: z.string(),
        equipment_name: z.string(),
        sensor_id: z.string(),
        cof_score: z.number(),
        alarm_level: z.number().nullable(),
        rank: z.number(),
        reason: z.string().nullable(),
      }),
    ),
  }),
  alarm_summary: z.array(
    z.object({
      equipment_id: z.string(),
      alarm_level: z.number().nullable(),
      count: z.number(),
    }),
  ),
});

export function RemoteDashboard({ hierarchy }: { hierarchy: Hierarchy }) {
  const [params] = useSearchParams();
  const scope = {
    plant_id: params.get("plant_id") ?? undefined,
    equipment_group_id: params.get("unit_id") ?? undefined,
    equipment_id: params.get("equip_id") ?? undefined,
  };
  const query = useQuery({
    queryKey: ["dashboard", scope],
    queryFn: async ({ signal }) =>
      schema.parse(
        (await http.get("/dashboard", { params: scope, signal })).data,
      ),
    refetchInterval: 10_000,
  });
  if (query.isPending) return <LoadingState />;
  if (query.isError)
    return (
      <ErrorState
        message={errorMessage(query.error)}
        retry={() => void query.refetch()}
      />
    );
  const data = query.data;
  const p = data.priority;
  const known = !["no_data", "unavailable"].includes(p.status);
  const assets = hierarchy.equipment.filter(
    (e) =>
      (!scope.plant_id || e.plantId === scope.plant_id) &&
      (!scope.equipment_group_id || e.unitId === scope.equipment_group_id) &&
      (!scope.equipment_id || e.id === scope.equipment_id),
  );
  const primary =
    assets.find((e) => e.id === p.items[0]?.equipment_id) ?? assets[0];
  const vibration = primary?.tags.find((t) => t.signal === "vibration");
  const end = p.as_of;
  const start = new Date(Date.parse(end) - 7 * 86400000).toISOString();
  const scopeName =
    hierarchy.equipment.find((e) => e.id === scope.equipment_id)?.name ??
    hierarchy.units.find((u) => u.id === scope.equipment_group_id)?.name ??
    hierarchy.plants.find((plant) => plant.id === scope.plant_id)?.name ??
    "전체 설비";
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">OPERATIONS OVERVIEW</div>
          <h1>운영 대시보드</h1>
          <p>
            {scopeName} · DB 조회 ·{" "}
            {new Date(p.as_of).toLocaleString("ko-KR", {
              timeZone: "Asia/Seoul",
            })}{" "}
            KST
          </p>
        </div>
      </div>
      <div className="stat-grid">
        {[
          [
            "모니터링 설비",
            `${data.equipment_count}대`,
            `${data.plant_count}개 플랜트 · ${data.unit_count}개 공정`,
          ],
          ["정상 설비", `${data.normal_count}대`, "등록된 설비 상태 기준"],
          [
            "활성 알람",
            known ? `${p.active_count}건` : "—",
            known
              ? `영향 설비 ${p.affected_equipment_count}대`
              : "활성 상태 확인 데이터 없음",
          ],
          [
            "우선 확인",
            known ? `${data.high_count}건` : "—",
            "알람 레벨 3 이상 · 대응 순위는 CoF 기준",
          ],
        ].map(([label, value, note]) => (
          <Card key={label} className="stat-card">
            <span className="stat-label">{label}</span>
            <div className="stat-value">{value}</div>
            <span className="stat-note">{note}</span>
          </Card>
        ))}
      </div>
      <div className="dashboard-middle">
        <Card className="priority-card">
          <CardHeader
            title="대응 우선순위"
            description="CoF · 알람 레벨 · 발생 시각 기준"
          />
          {p.items.length ? (
            p.items.map((item) => (
              <Link
                className="priority-row"
                key={item.equipment_id}
                to={`/equip?equip_id=${encodeURIComponent(item.equipment_id)}&sensor_id=${encodeURIComponent(item.sensor_id)}`}
              >
                <span className="rank">{item.rank}</span>
                <div className="priority-text">
                  <strong>{item.equipment_name}</strong>
                  <span>
                    CoF {item.cof_score} · {item.reason ?? "등록 알람"}
                  </span>
                </div>
              </Link>
            ))
          ) : (
            <p className="empty-state">
              {known
                ? "순위를 정할 평가 완료 활성 알람이 없습니다."
                : "활성 상태 확인 데이터가 없습니다."}
            </p>
          )}
          <div className="priority-foot">
            챗봇과 동일한 조회 기준 · 미확인 이력 {p.unknown_count}건 · CoF
            미평가 {p.unscored_count}건
          </div>
        </Card>
        <Card>
          <CardHeader
            title="주요 설비 진동 추이"
            description={`${primary?.name ?? "선택 설비 없음"} · 최근 7일`}
          />
          {vibration ? (
            <MultiTrendView
              hierarchy={hierarchy}
              series={[{ sensorId: vibration.id, start, end }]}
              showAnomalies={false}
              mode="1h"
            />
          ) : (
            <p className="empty-state">조회할 진동 센서가 없습니다.</p>
          )}
        </Card>
      </div>
      <Card>
        <CardHeader
          title="활성 알람 요약"
          description="설비·알람 레벨별 건수"
        />
        {data.alarm_summary.length ? (
          <table>
            <thead>
              <tr>
                <th>설비</th>
                <th>알람 레벨</th>
                <th>건수</th>
              </tr>
            </thead>
            <tbody>
              {data.alarm_summary.map((row) => (
                <tr key={`${row.equipment_id}-${row.alarm_level}`}>
                  <td>
                    <Link
                      to={`/equip?equip_id=${encodeURIComponent(row.equipment_id)}`}
                    >
                      {hierarchy.equipment.find(
                        (e) => e.id === row.equipment_id,
                      )?.name ?? row.equipment_id}
                    </Link>
                  </td>
                  <td>{row.alarm_level ?? "미기록"}</td>
                  <td>{row.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="empty-state">
            {known
              ? "활성 알람이 없습니다."
              : "활성 상태 확인 데이터가 없습니다."}
          </p>
        )}
      </Card>
      <IncidentPanel
        title="진행 중 이상 사건"
        description="분석기 사건 · 진단은 추정"
        filters={{ status: "ongoing", ...scope }}
        emptyText="진행 중인 이상 사건이 없습니다."
        moreHref="/incidents?status=ongoing"
      />
    </div>
  );
}
