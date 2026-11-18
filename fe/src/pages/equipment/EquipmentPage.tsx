import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";
import {
  Factory,
  Layers,
  ArrowUpRight,
  Activity,
  Gauge,
  Thermometer,
} from "lucide-react";
import type { Hierarchy, Selection } from "../../features/hierarchy/index.ts";
import { AlarmTable, type Alarm } from "../../features/alarms/index.ts";
import { equipmentQuery } from "../../features/equipment/api/equipment.queries.ts";
import { remoteApi } from "../../shared/api/be-adapter.ts";
import { Card, CardHeader } from "../../shared/ui/card.tsx";
import { Badge } from "../../shared/ui/badge.tsx";
import { Button } from "../../shared/ui/button.tsx";
import { LoadingState } from "../../shared/ui/LoadingState.tsx";
import { ErrorState } from "../../shared/ui/ErrorState.tsx";
import { errorMessage } from "../../shared/api/http-client.ts";
import { dateTime } from "../../shared/lib/date-time.ts";
export function EquipmentPage({
  hierarchy,
  selection,
  alarms,
  onSelect,
}: {
  hierarchy: Hierarchy;
  selection: Selection;
  alarms: Alarm[];
  onSelect: (s: Selection) => void;
}) {
  const [params] = useSearchParams();
  const eq = hierarchy.equipment.find((e) => e.id === selection.equipmentId);
  const query = useQuery(equipmentQuery(eq?.id ?? ""));
  const plant = hierarchy.plants.find((p) => p.id === selection.plantId);
  const unit = hierarchy.units.find((u) => u.id === selection.unitId);
  const nodes = !plant
    ? hierarchy.plants.map((p) => ({
        id: p.id,
        name: p.name,
        sub: p.location,
        kind: "plant",
        equipment: hierarchy.equipment.filter((e) => e.plantId === p.id),
      }))
    : !unit
      ? hierarchy.units
          .filter((u) => u.plantId === plant.id)
          .map((u) => ({
            id: u.id,
            name: u.name,
            sub: "PROCESS UNIT",
            kind: "unit",
            equipment: hierarchy.equipment.filter((e) => e.unitId === u.id),
          }))
      : hierarchy.equipment
          .filter((e) => e.unitId === unit.id)
          .map((e) => ({
            id: e.id,
            name: e.name,
            sub: e.type,
            kind: "equipment",
            equipment: [e],
          }));
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">ASSET MONITORING</div>
          <h1>{eq ? eq.name : "설비 현황"}</h1>
          <p>
            {eq
              ? `${eq.id} · ${eq.type} · ${eq.equipmentLevel === undefined ? `설비 등급 ${eq.grade}` : `설비 중요도 ${eq.equipmentLevel}`}`
              : "플랜트부터 설비까지, 계층별 운영 상태를 확인하세요."}
          </p>
        </div>
        {eq ? (
          <Badge
            tone={
              alarms.find((a) => a.equipmentId === eq.id)?.severity ?? "success"
            }
          >
            {alarms.some((a) => a.equipmentId === eq.id) ||
            (eq.equipmentStatus !== undefined && eq.equipmentStatus > 0)
              ? "점검 필요"
              : "정상 운전"}
          </Badge>
        ) : (
          <Badge>2D 설비 배치</Badge>
        )}
      </div>
      {!eq ? (
        <Card className="facility-card">
          <CardHeader
            title={unit?.name ?? plant?.name ?? "전체 플랜트"}
            description="상태 색상: High → Medium → Low 순으로 하위 알람 집계"
          />
          <div className="facility-map">
            <div className="map-key">
              <span className="status-dot" /> 정상{" "}
              <span className="status-dot red-dot" /> 점검 필요
            </div>
            <div className="facility-nodes">
              {nodes.map((node) => {
                const nodeAlarms = alarms.filter((a) =>
                  node.equipment.some((e) => e.id === a.equipmentId),
                );
                return (
                  <button
                    className={`facility-node ${nodeAlarms.length ? "node-warning" : ""}`}
                    key={node.id}
                    onClick={() =>
                      onSelect(
                        node.kind === "plant"
                          ? {
                              plantId: node.id,
                              unitId: null,
                              equipmentId: null,
                            }
                          : node.kind === "unit"
                            ? {
                                plantId: plant!.id,
                                unitId: node.id,
                                equipmentId: null,
                              }
                            : {
                                plantId: plant!.id,
                                unitId: unit!.id,
                                equipmentId: node.id,
                              },
                      )
                    }
                  >
                    <div className="facility-icon">
                      {node.kind === "plant" ? (
                        <Factory size={38} />
                      ) : node.kind === "unit" ? (
                        <Layers size={38} />
                      ) : (
                        <Gauge size={38} />
                      )}
                    </div>
                    <Badge tone={nodeAlarms[0]?.severity ?? "success"}>
                      {nodeAlarms.length
                        ? `${nodeAlarms.length}건 알람`
                        : "정상"}
                    </Badge>
                    <strong>{node.name}</strong>
                    <span>
                      {node.id} · {node.sub}
                    </span>
                    <span className="node-action">
                      상세 보기 <ArrowUpRight size={13} />
                    </span>
                  </button>
                );
              })}
            </div>
            <span className="map-caption">
              SCHEMATIC VIEW · 실제 배치 자료 연결 전의 예시 구성
            </span>
          </div>
        </Card>
      ) : query.isPending ? (
        <LoadingState />
      ) : query.isError ? (
        <ErrorState
          message={errorMessage(query.error)}
          retry={() => void query.refetch()}
        />
      ) : (
        <>
          <div className="tag-grid">
            {query.data.tags.map((tag) => {
              const selected =
                tag.signal === params.get("sensor") ||
                tag.id === params.get("sensor_id");
              const Icon =
                tag.signal === "vibration"
                  ? Activity
                  : tag.signal === "temperature"
                    ? Thermometer
                    : Gauge;
              return (
                <Card
                  key={tag.id}
                  className={`tag-card ${selected ? "tag-selected" : ""}`}
                >
                  <div className="inline between">
                    <span className="muted">
                      <Icon size={15} /> {tag.name}
                    </span>
                    <Badge
                      tone={
                        tag.limit !== undefined &&
                        tag.current !== null &&
                        tag.current > tag.limit
                          ? "High"
                          : "success"
                      }
                    >
                      {tag.limit === undefined || tag.current === null
                        ? "기준 미설정"
                        : tag.current > tag.limit
                          ? "기준 초과"
                          : "정상"}
                    </Badge>
                  </div>
                  <div className="tag-value mono">
                    {tag.current?.toFixed(2) ?? "—"}
                    <small>{tag.unit}</small>
                  </div>
                  <p className="muted small">
                    {tag.id} ·{" "}
                    {tag.limit === undefined
                      ? "기준 미설정"
                      : `기준 ${tag.limit} ${tag.unit}`}
                  </p>
                  <Button asChild variant="outline" size="sm">
                    <Link to={`/trend?equip_id=${eq.id}&sensor_id=${tag.id}`}>
                      트렌드 보기
                      <ArrowUpRight size={13} />
                    </Link>
                  </Button>
                </Card>
              );
            })}
          </div>
          <p className="small muted">
            현재값 기준 시각 {dateTime(query.data.asOf)} ·{" "}
            {remoteApi ? "10초 주기 조회" : "1초 주기 갱신"}
          </p>
          <Card>
            <CardHeader
              title="최근 알람"
              description={
                remoteApi
                  ? "선택한 센서의 활성 알람"
                  : "선택한 센서의 활성 Setpoint 알람"
              }
            />
            <AlarmTable
              alarms={alarms.filter(
                (a) =>
                  a.equipmentId === eq.id &&
                  (!params.get("sensor") ||
                    a.signal === params.get("sensor")) &&
                  (!params.get("sensor_id") ||
                    a.tagId === params.get("sensor_id")),
              )}
              equipment={hierarchy.equipment}
            />
          </Card>
        </>
      )}
    </div>
  );
}
