import { Input } from "../../shared/ui/input.tsx";
import { useSearchParams } from "react-router";
import type { Hierarchy, Selection } from "../../features/hierarchy/index.ts";
import { AlarmTable, type Alarm } from "../../features/alarms/index.ts";
import { Card, CardHeader } from "../../shared/ui/card.tsx";
import { DateRangePicker } from "../../shared/ui/DateRangePicker.tsx";
import { Select } from "../../shared/ui/select.tsx";
import {
  defaultRange,
  dateBounds,
  validDateRange,
} from "../../shared/lib/date-time.ts";
import { Badge } from "../../shared/ui/badge.tsx";
import { ErrorState } from "../../shared/ui/ErrorState.tsx";
import { alarmFilterValue } from "../../shared/lib/alarm-level.ts";
import { remoteApi } from "../../shared/api/be-adapter.ts";
export function AlarmListPage({
  hierarchy,
  selection,
  alarms,
}: {
  hierarchy: Hierarchy;
  selection: Selection;
  alarms: Alarm[];
}) {
  const [params, setParams] = useSearchParams();
  const range = defaultRange();
  const from = params.get("from") ?? range.from;
  const to = params.get("to") ?? range.to;
  const severity = params.get("severity") ?? "";
  const eventType = params.get("event_type");
  const search = (params.get("q") ?? "").replace(/\s+/g, "").toLowerCase();
  const sensorIds = params.getAll("sensor_id");
  const bounds = dateBounds(from, to);
  const valid = validDateRange(from, to);
  const filtered = !valid
    ? []
    : alarms.filter((a) => {
        const eq = hierarchy.equipment.find((e) => e.id === a.equipmentId);
        const tag = eq?.tags.find((tag) => tag.id === a.tagId);
        const searchable =
          `${a.equipmentId} ${eq?.name ?? ""} ${a.tagId} ${tag?.name ?? ""} ${a.reason} ${a.type}`
            .replace(/\s+/g, "")
            .toLowerCase();
        return (
          (!selection.plantId || eq?.plantId === selection.plantId) &&
          (!selection.unitId || eq?.unitId === selection.unitId) &&
          (!selection.equipmentId || eq?.id === selection.equipmentId) &&
          (!params.get("equipment_type") ||
            eq?.type === params.get("equipment_type")) &&
          (!severity || alarmFilterValue(a) === severity) &&
          (!eventType || a.eventType === eventType) &&
          (!search || searchable.includes(search)) &&
          (!sensorIds.length || sensorIds.includes(a.tagId)) &&
          a.occurredAt >= new Date(bounds.from).toISOString() &&
          a.occurredAt <= new Date(bounds.to).toISOString()
        );
      });
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">ALARM CENTER</div>
          <h1>{remoteApi ? "알람 이력" : "알람 모니터링"}</h1>
          <p>
            {remoteApi
              ? "저장된 알람을 발생 일자와 설비별로 확인하세요."
              : "현재 활성 알람을 발생 일자와 설비별로 확인하세요."}
          </p>
        </div>
        <Badge tone="success">
          {remoteApi ? "1분 주기 조회" : "1초 주기 갱신"}
        </Badge>
      </div>
      <Card>
        <div className="filter-bar">
          <Input
            aria-label="알람 검색"
            placeholder="설비 · 태그 · 센서 · 진단 검색"
            value={params.get("q") ?? ""}
            onChange={(event) => {
              const next = new URLSearchParams(params);
              if (event.target.value) next.set("q", event.target.value);
              else next.delete("q");
              setParams(next);
            }}
          />
          <Select
            aria-label="심각도 필터"
            value={severity}
            onChange={(e) => {
              const p = new URLSearchParams(params);
              e.target.value
                ? p.set("severity", e.target.value)
                : p.delete("severity");
              setParams(p);
            }}
          >
            <option value="">전체 심각도</option>
            {(remoteApi
              ? [
                  ["4", "비상"],
                  ["3", "위험"],
                  ["2", "경고"],
                  ["1", "주의"],
                  ["0", "정상"],
                ]
              : [
                  ["High", "High"],
                  ["Medium", "Medium"],
                  ["Low", "Low"],
                ]
            ).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
          <DateRangePicker
            from={from}
            to={to}
            onChange={(f, t) => {
              const p = new URLSearchParams(params);
              p.set("from", f);
              p.set("to", t);
              setParams(p);
            }}
          />
        </div>
        <CardHeader
          title={remoteApi ? "저장된 알람" : "활성 알람"}
          description={
            remoteApi
              ? "알람 이력 조회"
              : "알람 종류: Setpoint · 현재 상태 스냅샷"
          }
        />
        {valid ? (
          <AlarmTable alarms={filtered} equipment={hierarchy.equipment} />
        ) : (
          <ErrorState message="조회 기간을 확인하세요." />
        )}
      </Card>
      {!remoteApi && (
        <p className="small muted">
          데모에서는 현재 활성 알람을 제공합니다. 해제된 알람을 포함한 과거
          이력은 이력 API 연결이 필요합니다.
        </p>
      )}
    </div>
  );
}
