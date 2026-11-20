import type { Hierarchy, Selection } from "../../features/hierarchy/index.ts";
import type { Alarm } from "../../features/alarms/index.ts";
import { CDUProcessLayout } from "../../features/equipment/ui/CDUProcessLayout.tsx";
import { EquipmentCards } from "../../features/equipment/ui/EquipmentCards.tsx";
import { Card } from "../../shared/ui/card.tsx";
import { IncidentPanel } from "../../features/incidents/index.ts";

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
  const unit = hierarchy.units.find((u) => u.id === selection.unitId);
  const equipment = unit
    ? hierarchy.equipment.filter((item) => item.unitId === unit.id)
    : [];
  return (
    <div className="page">
      {unit?.processType === "CDU" ? (
        <CDUProcessLayout
          hierarchy={hierarchy}
          selection={selection}
          alarms={alarms}
          onSelect={onSelect}
        />
      ) : unit ? (
        <Card className="process-layout-placeholder">
          <p>이 공정 유형의 배치도는 준비 중입니다.</p>
        </Card>
      ) : null}
      {unit && (
        <EquipmentCards
          groupName={unit.name}
          equipment={equipment}
          selectedEquipmentId={selection.equipmentId}
          onSelect={onSelect}
        />
      )}
      {selection.equipmentId && (
        <IncidentPanel
          title="이상 사건"
          description="선택한 설비의 최근 사건 · 진단은 추정"
          filters={{ equipment_id: selection.equipmentId }}
          emptyText="이 설비에 기록된 이상 사건이 없습니다."
          moreHref={`/incidents?equip_id=${encodeURIComponent(selection.equipmentId)}`}
        />
      )}
    </div>
  );
}
