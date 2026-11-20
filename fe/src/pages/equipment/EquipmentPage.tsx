import { lazy, Suspense, useState } from "react";
import type { Hierarchy, Selection } from "../../features/hierarchy/index.ts";
import type { Alarm } from "../../features/alarms/index.ts";
import { CDUProcessLayout } from "../../features/equipment/ui/CDUProcessLayout.tsx";
import { EquipmentCards } from "../../features/equipment/ui/EquipmentCards.tsx";
import { EquipmentFeed } from "../../features/equipment/ui/EquipmentFeed.tsx";
import { EquipmentReplayControls } from "../../features/equipment/ui/EquipmentReplayControls.tsx";
import {
  CONSOLE_EXAMPLE_HOUR,
  consoleHourDate,
  hasConsoleTimeline,
} from "../../features/equipment/model/equipment-alarm-state.ts";
import { Card } from "../../shared/ui/card.tsx";
import { IncidentPanel } from "../../features/incidents/index.ts";

const Pump3D = lazy(() =>
  import("../../features/equipment/ui/Pump3D.tsx").then((module) => ({
    default: module.Pump3D,
  })),
);

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
  const [replayHour, setReplayHour] = useState<number | null>(
    CONSOLE_EXAMPLE_HOUR,
  );
  const unit = hierarchy.units.find((u) => u.id === selection.unitId);
  const equipment = unit
    ? hierarchy.equipment.filter((item) => item.unitId === unit.id)
    : [];
  const selectedEquipment = hierarchy.equipment.find(
    (item) => item.id === selection.equipmentId,
  );
  const activeReplayHour =
    unit?.processType === "CDU" && equipment.some(hasConsoleTimeline)
      ? replayHour
      : null;
  return (
    <div className="page">
      {unit?.processType === "CDU" && equipment.some(hasConsoleTimeline) && (
        <EquipmentReplayControls hour={replayHour} onChange={setReplayHour} />
      )}
      {unit?.processType === "CDU" ? (
        <CDUProcessLayout
          hierarchy={hierarchy}
          selection={selection}
          alarms={alarms}
          replayHour={activeReplayHour}
          onSelect={onSelect}
        />
      ) : unit ? (
        <Card className="process-layout-placeholder">
          <p>이 공정 유형의 배치도는 준비 중입니다.</p>
        </Card>
      ) : null}
      {unit && (
        <EquipmentFeed
          equipment={equipment}
          alarms={alarms}
          onSelect={onSelect}
        />
      )}
      {unit && (
        <EquipmentCards
          groupName={unit.name}
          equipment={equipment}
          alarms={alarms}
          replayHour={activeReplayHour}
          selectedEquipmentId={selection.equipmentId}
          onSelect={onSelect}
        />
      )}
      {selectedEquipment && (
        <Suspense
          fallback={
            <Card className="pump-3d-panel">3D 모델을 불러오는 중입니다.</Card>
          }
        >
          <Pump3D
            key={selectedEquipment.id}
            equipment={selectedEquipment}
            alarms={alarms}
            replayHour={activeReplayHour}
          />
        </Suspense>
      )}
      {selection.equipmentId && (
        <IncidentPanel
          title="이상 사건"
          description="선택한 설비의 최근 사건 · 진단은 추정"
          filters={{
            equipment_id: selection.equipmentId,
            as_of:
              activeReplayHour == null
                ? undefined
                : consoleHourDate(activeReplayHour).toISOString(),
          }}
          emptyText="이 설비에 기록된 이상 사건이 없습니다."
          moreHref={`/incidents?equip_id=${encodeURIComponent(selection.equipmentId)}`}
        />
      )}
    </div>
  );
}
