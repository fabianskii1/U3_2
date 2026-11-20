import type { CellContext } from "@tanstack/react-table";
import { Link } from "react-router";
import type { Alarm } from "../api/alarms.schema.ts";
import type { Equipment } from "../../../shared/api/contracts/hierarchy.ts";
import { DataTable } from "../../../shared/ui/DataTable.tsx";
import { Badge } from "../../../shared/ui/badge.tsx";
import { dateTime } from "../../../shared/lib/date-time.ts";
import { alarmLabel } from "../../../shared/lib/alarm-level.ts";

const LEVEL_LABELS = ["정상", "주의", "경고", "위험", "비상"] as const;
export function AlarmTable({
  alarms,
  equipment,
}: {
  alarms: Alarm[];
  equipment: Equipment[];
}) {
  return (
    <DataTable
      label="알람 목록"
      data={alarms}
      columns={[
        {
          accessorKey: "severity",
          header: "심각도",
          cell: ({ row }) => (
            <Badge tone={row.original.severity}>
              {alarmLabel(row.original)}
            </Badge>
          ),
        },
        {
          accessorKey: "equipmentId",
          header: "설비",
          cell: ({ row }) => (
            <Link
              className="equipment-link"
              to={`/equip?equip_id=${encodeURIComponent(row.original.equipmentId)}&sensor_id=${encodeURIComponent(row.original.tagId)}`}
            >
              {equipment.find((e) => e.id === row.original.equipmentId)?.name ??
                row.original.equipmentId}
              <small>{row.original.equipmentId}</small>
            </Link>
          ),
        },
        { accessorKey: "tagId", header: "태그" },
        ...(alarms.some(
          (alarm) => alarm.value !== undefined && alarm.limit !== undefined,
        )
          ? [
              {
                accessorKey: "value",
                header: "실측 / 기준",
                cell: ({ row }: CellContext<Alarm, unknown>) => (
                  <span className="mono">
                    {row.original.value?.toFixed(2)}{" "}
                    <span className="muted">
                      / {row.original.limit} {row.original.unit}
                    </span>
                  </span>
                ),
              },
            ]
          : []),
        ...(alarms.some((alarm) => alarm.peakLevel !== undefined)
          ? [
              {
                accessorKey: "peakLevel",
                header: "최고 도달",
                cell: ({ row }: CellContext<Alarm, unknown>) =>
                  row.original.peakLevel === undefined ? (
                    <span className="muted">—</span>
                  ) : (
                    LEVEL_LABELS[row.original.peakLevel]
                  ),
              },
            ]
          : []),
        ...(alarms.some((alarm) => alarm.incidentId)
          ? [
              {
                accessorKey: "incidentId",
                header: "이상 사건",
                cell: ({ row }: CellContext<Alarm, unknown>) =>
                  row.original.incidentId ? (
                    <Link
                      className="small"
                      to={`/incidents/${encodeURIComponent(row.original.incidentId)}`}
                    >
                      사건 보기
                    </Link>
                  ) : (
                    <span className="muted">—</span>
                  ),
              },
            ]
          : []),
        {
          accessorKey: "occurredAt",
          header: "발생 시각",
          cell: ({ getValue }) => (
            <span className="small mono">{dateTime(String(getValue()))}</span>
          ),
        },
      ]}
    />
  );
}
