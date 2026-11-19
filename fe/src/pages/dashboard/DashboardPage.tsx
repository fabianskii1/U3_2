import { Link } from "react-router";
import {
  Activity,
  ArrowUpRight,
  ShieldCheck,
  TriangleAlert,
  Radio,
  ArrowRight,
  FilePlus2,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import type { Hierarchy } from "../../features/hierarchy/index.ts";
import { type Alarm } from "../../features/alarms/index.ts";
import { TrendChart, trendQuery } from "../../features/trend/index.ts";
import { DataTable } from "../../shared/ui/DataTable.tsx";
import { Card, CardHeader } from "../../shared/ui/card.tsx";
import { Badge } from "../../shared/ui/badge.tsx";
import { Button } from "../../shared/ui/button.tsx";
import { defaultRange, dateBounds } from "../../shared/lib/date-time.ts";
import { LoadingState } from "../../shared/ui/LoadingState.tsx";
import { alarmLabel, alarmFilterValue } from "../../shared/lib/alarm-level.ts";
import { remoteApi } from "../../shared/api/be-adapter.ts";
export function DashboardPage({
  hierarchy,
  alarms,
}: {
  hierarchy: Hierarchy;
  alarms: Alarm[];
}) {
  const summary = Array.from(
    alarms
      .reduce((map, a) => {
        const key = a.equipmentId + "-" + alarmFilterValue(a);
        const current = map.get(key);
        map.set(key, {
          equipmentId: a.equipmentId,
          severity: a.severity,
          label: alarmLabel(a),
          count: (current?.count ?? 0) + 1,
        });
        return map;
      }, new Map<string, { equipmentId: string; severity: Alarm["severity"]; label: string; count: number }>())
      .values(),
  );
  const high = alarms.filter((a) =>
    a.alarmLevel === undefined ? a.severity === "High" : a.alarmLevel >= 3,
  ).length;
  const affected = new Set(alarms.map((a) => a.equipmentId)).size;
  const primaryEquipment =
    hierarchy.equipment.find((e) => e.id === alarms[0]?.equipmentId) ??
    hierarchy.equipment[0];
  const primaryTag = primaryEquipment?.tags.find(
    (tag) => tag.signal === "vibration",
  );
  const range = defaultRange();
  const { data: trend } = useQuery(
    trendQuery(
      primaryTag?.id ?? "",
      ...(Object.values(dateBounds(range.from, range.to)) as [string, string]),
    ),
  );
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">OPERATIONS OVERVIEW</div>
          <h1>운영 대시보드</h1>
          <p>회전설비의 상태를 한눈에 확인하고, 필요한 조치를 시작하세요.</p>
        </div>
        <Badge tone="success">
          <Radio size={12} />
          {remoteApi ? "DB 조회" : "1초 주기 갱신"}
        </Badge>
      </div>
      <div className="stat-grid">
        <Card className="stat-card">
          <span className="stat-label">
            모니터링 설비
            <Radio size={17} />
          </span>
          <div className="stat-value">
            {hierarchy.equipment.length}
            <small>대</small>
          </div>
          <span className="stat-note">
            {hierarchy.plants.length}개 플랜트 · {hierarchy.units.length}개 공정
          </span>
        </Card>
        <Card className="stat-card">
          <span className="stat-label">
            정상 설비
            <ShieldCheck size={17} />
          </span>
          <div className="stat-value green">
            {remoteApi
              ? hierarchy.equipment.filter((e) => e.equipmentStatus === 0)
                  .length
              : hierarchy.equipment.length - affected}
            <small>대</small>
          </div>
          <span className="stat-note">
            전체 설비의{" "}
            {Math.round(
              ((remoteApi
                ? hierarchy.equipment.filter((e) => e.equipmentStatus === 0)
                    .length
                : hierarchy.equipment.length - affected) /
                (hierarchy.equipment.length || 1)) *
                100,
            )}
            %
          </span>
        </Card>
        <Card className="stat-card">
          <span className="stat-label">
            활성 알람
            <TriangleAlert size={17} />
          </span>
          <div className="stat-value">
            {remoteApi ? "—" : alarms.length}
            <small>건</small>
          </div>
          <span className="stat-note">
            {remoteApi ? "실시간 판정 준비 중" : "Setpoint 기준 초과 알람"}
          </span>
        </Card>
        <Card className="stat-card high-stat">
          <span className="stat-label">
            우선 확인
            <Activity size={17} />
          </span>
          <div className="stat-value red">
            {remoteApi ? "—" : high}
            <small>건</small>
          </div>
          <span className="stat-note">
            {remoteApi ? "실시간 판정 준비 중" : "High 심각도 · 빠른 점검 권장"}
          </span>
        </Card>
      </div>
      <div className="dashboard-middle">
        <Card className="priority-card">
          <CardHeader
            title="대응 우선순위"
            description={
              remoteApi
                ? "실시간 알람 판정 준비 중"
                : "심각도 · 설비 등급 · 기준 초과율 기준"
            }
            action={<span className="tiny-label">PRIORITY</span>}
          />
          {alarms.length ? (
            alarms.map((alarm, i) => {
              const equipment = hierarchy.equipment.find(
                (e) => e.id === alarm.equipmentId,
              )!;
              return (
                <Link
                  key={alarm.id}
                  to={`/equip?equip_id=${encodeURIComponent(equipment.id)}&sensor_id=${encodeURIComponent(alarm.tagId)}`}
                  className="priority-row"
                >
                  <span className={`rank rank-${i}`}>
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <div className="priority-text">
                    <strong>{equipment.name}</strong>
                    <span>{alarm.reason}</span>
                  </div>
                  <Badge tone={alarm.severity}>{alarmLabel(alarm)}</Badge>
                  <ArrowUpRight size={15} />
                </Link>
              );
            })
          ) : (
            <p className="empty-state">
              {remoteApi ? "활성 알람 조회 준비 중" : "이상 없음"}
            </p>
          )}
          <div className="priority-foot">
            <ShieldCheck size={14} />
            {remoteApi
              ? "저장된 알람은 알람 이력 화면에서 확인할 수 있습니다."
              : "표와 AI 대화는 동일한 데모 우선순위를 사용합니다."}
          </div>
        </Card>
        <Card>
          <CardHeader
            title="주요 설비 진동 추이"
            description={`${primaryEquipment?.name ?? "설비 미선택"} · 최근 7일 · 1시간 집계`}
            action={
              <Link
                aria-label="트렌드 상세"
                to={`/trend?equip_id=${primaryEquipment?.id ?? ""}&sensor_id=${primaryTag?.id ?? ""}`}
              >
                <ArrowUpRight size={17} />
              </Link>
            }
          />
          <div className="chart-number">
            {trend?.points.at(-1)?.value?.toFixed(2) ?? "—"}
            <small>mm/s</small>
            {trend &&
            trend.limit !== null &&
            trend.max !== null &&
            trend.max > trend.limit ? (
              <Badge tone="High">기준 초과</Badge>
            ) : null}
          </div>
          {trend ? (
            <TrendChart
              points={trend.points}
              limit={trend.limit}
              unit={trend.unit}
              setpoints={trend.setpoints}
            />
          ) : (
            <LoadingState />
          )}
        </Card>
      </div>
      <Card>
        <CardHeader
          title="알람 요약"
          description={
            remoteApi
              ? "실시간 집계 준비 중"
              : "현재 활성 Setpoint 알람 · 태그별 집계"
          }
          action={
            <Button asChild variant="ghost" size="sm">
              <Link to="/alarms">
                전체 알람
                <ArrowRight size={14} />
              </Link>
            </Button>
          }
        />
        <DataTable
          label="설비별 알람 집계"
          data={summary}
          columns={[
            {
              accessorKey: "equipmentId",
              header: "설비",
              cell: ({ row }) => (
                <Link
                  className="equipment-link"
                  to={`/equip?equip_id=${row.original.equipmentId}`}
                >
                  {
                    hierarchy.equipment.find(
                      (e) => e.id === row.original.equipmentId,
                    )?.name
                  }
                  <small>{row.original.equipmentId}</small>
                </Link>
              ),
            },
            {
              accessorKey: "severity",
              header: "심각도",
              cell: ({ row }) => (
                <Badge tone={row.original.severity}>{row.original.label}</Badge>
              ),
            },
            {
              accessorKey: "count",
              header: "태그 알람 건수",
              cell: ({ getValue }) => (
                <strong className="mono">{String(getValue())}건</strong>
              ),
            },
          ]}
        />
      </Card>
      <div className="bottom-callout">
        <div>
          <FilePlus2 size={18} />
          <span>점검 결과를 기록해 보세요.</span>
          <span className="muted">
            {remoteApi
              ? "보고서 작성 기능은 준비 중입니다."
              : "대화에서 보고서 초안을 생성할 수 있습니다."}
          </span>
        </div>
        <Link to="/reports">
          보고서 관리 <ArrowRight size={14} />
        </Link>
      </div>
    </div>
  );
}
