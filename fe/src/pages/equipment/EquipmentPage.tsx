import { lazy, Suspense } from "react";
import { useLocation, useSearchParams } from "react-router";
import { useSectionFocus } from "../../shared/lib/use-section-focus.ts";
import { replayHourFromParams } from "../../features/equipment/model/replay-navigation.ts";
import type { Hierarchy, Selection } from "../../features/hierarchy/index.ts";
import type { Alarm } from "../../features/alarms/index.ts";
import { CDUProcessLayout } from "../../features/equipment/ui/CDUProcessLayout.tsx";
import { EquipmentCards } from "../../features/equipment/ui/EquipmentCards.tsx";
import { EquipmentFeed } from "../../features/equipment/ui/EquipmentFeed.tsx";
import { EquipmentReplayControls } from "../../features/equipment/ui/EquipmentReplayControls.tsx";
import {
  consoleHourDate,
  hasConsoleTimeline,
} from "../../features/equipment/model/equipment-alarm-state.ts";
import { Card } from "../../shared/ui/card.tsx";
import {
  DiagnosisPanel,
  type FaultSelection,
} from "../../features/incidents/index.ts";

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
  const [params, setParams] = useSearchParams();
  useSectionFocus();
  const replayHour = replayHourFromParams(params);
  const setReplayHour = (hour: number | null) => {
    const next = new URLSearchParams(params);
    next.set("replay", hour === null ? "live" : String(hour));
    next.set("section", "replay");
    next.delete("fault");
    next.delete("incident_id");
    setParams(next);
  };
  const faultSelection: FaultSelection | null =
    params.get("fault") && params.get("incident_id")
      ? { incidentId: params.get("incident_id")!, fault: params.get("fault")! }
      : null;
  const setFaultSelection = (selected: FaultSelection) => {
    const next = new URLSearchParams(params);
    next.set("fault", selected.fault);
    next.set("incident_id", selected.incidentId);
    next.set("section", "diagnosis");
    setParams(next);
  };
  const location = useLocation();
  const unit = hierarchy.units.find((u) => u.id === selection.unitId);
  const equipment = unit
    ? hierarchy.equipment.filter((item) => item.unitId === unit.id)
    : hierarchy.equipment.filter(
        (item) => !selection.plantId || item.plantId === selection.plantId,
      );
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
          groupName={unit?.name ?? "전체 설비"}
          equipment={equipment}
          alarms={alarms}
          replayHour={activeReplayHour}
          selectedEquipmentId={selection.equipmentId}
          navigationKey={location.key}
          autoFocus={
            !params.get("section") || params.get("section") === "sensors"
          }
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
            faultSelection={faultSelection}
          />
        </Suspense>
      )}
      {selection.equipmentId && (
        <DiagnosisPanel
          equipmentId={selection.equipmentId}
          asOf={
            activeReplayHour == null
              ? undefined
              : consoleHourDate(activeReplayHour).toISOString()
          }
          selection={faultSelection}
          onSelect={setFaultSelection}
        />
      )}
    </div>
  );
}
