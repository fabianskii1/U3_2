import { Link } from "react-router";
import type { Alarm } from "../api/alarms.schema.ts";
import type { Equipment } from "../../../shared/api/contracts/hierarchy.ts";
import { DataTable } from "../../../shared/ui/DataTable.tsx";
import { Badge } from "../../../shared/ui/badge.tsx";
import { dateTime } from "../../../shared/lib/date-time.ts";
import { alarmLabel } from "../../../shared/lib/alarm-level.ts";
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
        {
          accessorKey: "value",
          header: "실측 / 기준",
          cell: ({ row }) => (
            <span className="mono">
              {row.original.value.toFixed(2)}{" "}
              <span className="muted">
                / {row.original.limit} {row.original.unit}
              </span>
            </span>
          ),
        },
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
