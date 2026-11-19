import { useQueries } from "@tanstack/react-query";
import type {
  Equipment,
  Selection,
} from "../../../shared/api/contracts/hierarchy.ts";
import { dateTime } from "../../../shared/lib/date-time.ts";
import { Badge } from "../../../shared/ui/badge.tsx";
import { Card, CardHeader } from "../../../shared/ui/card.tsx";
import { equipmentQuery } from "../api/equipment.queries.ts";

export function EquipmentCards({
  groupName,
  equipment,
  selectedEquipmentId,
  onSelect,
}: {
  groupName: string;
  equipment: Equipment[];
  selectedEquipmentId: string | null;
  onSelect: (selection: Selection) => void;
}) {
  const details = useQueries({
    queries: equipment.map((item) => equipmentQuery(item.id)),
  });

  return (
    <Card className="equipment-cards-panel">
      <CardHeader
        title="설비 및 센서"
        description={`${groupName} · 설비 ${equipment.length}대 · 최근 저장된 센서값`}
      />
      {equipment.length === 0 ? (
        <p className="equipment-cards-empty">
          이 그룹에 등록된 설비가 없습니다.
        </p>
      ) : (
        <div className="equipment-cards-grid">
          {equipment.map((item, index) => {
            const query = details[index];
            const tags = query.data?.tags ?? item.tags;
            const selected = item.id === selectedEquipmentId;
            return (
              <button
                key={item.id}
                type="button"
                className={`equipment-summary-card${selected ? " is-selected" : ""}`}
                data-status={item.equipmentStatus ?? 0}
                aria-pressed={selected}
                aria-label={`${item.name} ${item.id} 선택`}
                onClick={() =>
                  onSelect({
                    plantId: item.plantId,
                    unitId: item.unitId,
                    equipmentId: item.id,
                  })
                }
              >
                <span className="equipment-summary-head">
                  <span>
                    <strong className="equipment-summary-id">{item.id}</strong>
                    <span className="equipment-summary-name">{item.name}</span>
                  </span>
                  <Badge tone={item.equipmentStatus ? "High" : "success"}>
                    {item.equipmentStatus ? "점검 필요" : "정상"}
                  </Badge>
                </span>
                {query.isError ? (
                  <span className="equipment-summary-message">
                    센서값 조회 실패
                  </span>
                ) : query.isPending ? (
                  <span className="equipment-summary-message">
                    센서값 불러오는 중
                  </span>
                ) : null}
                <span className="equipment-sensor-grid">
                  {tags.map((tag) => (
                    <span
                      className="equipment-sensor-cell"
                      key={tag.id}
                      title={
                        tag.measuredAt
                          ? `${tag.name} · ${dateTime(tag.measuredAt)} KST`
                          : tag.name
                      }
                    >
                      <span className="equipment-sensor-name">{tag.name}</span>
                      <span className="equipment-sensor-value">
                        {tag.currentValue == null
                          ? "—"
                          : tag.currentValue.toLocaleString("ko-KR", {
                              maximumFractionDigits: 3,
                            })}
                        {tag.currentValue != null && <small>{tag.unit}</small>}
                      </span>
                    </span>
                  ))}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </Card>
  );
}
