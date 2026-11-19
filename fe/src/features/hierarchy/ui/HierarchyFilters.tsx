import { ChevronRight } from "lucide-react";
import type { Hierarchy, Selection } from "../model/hierarchy.schema.ts";
import { Select } from "../../../shared/ui/select.tsx";

export function HierarchyFilters({
  data,
  selection,
  onSelect,
  availableSensorIds,
}: {
  data: Hierarchy;
  selection: Selection;
  onSelect: (next: Selection) => void;
  availableSensorIds?: string[];
}) {
  const units = data.units.filter((unit) => unit.plantId === selection.plantId);
  const equipment = data.equipment.filter(
    (item) => item.unitId === selection.unitId,
  );
  const sensors =
    data.equipment
      .find((item) => item.id === selection.equipmentId)
      ?.tags.filter(
        (tag) => !availableSensorIds || availableSensorIds.includes(tag.id),
      ) ?? [];

  return (
    <div className="hierarchy-filters" role="group" aria-label="설비 계층 선택">
      <label className="context-select">
        <span>Plant</span>
        <Select
          aria-label="Plant 선택"
          value={selection.plantId ?? ""}
          onChange={(event) =>
            onSelect({
              plantId: event.target.value || null,
              unitId: null,
              equipmentId: null,
              sensorIds: [],
            })
          }
        >
          <option value="">전체 플랜트</option>
          {data.plants.map((plant) => (
            <option key={plant.id} value={plant.id}>
              {plant.name}
            </option>
          ))}
        </Select>
      </label>
      <ChevronRight size={12} aria-hidden="true" />
      <label className="context-select">
        <span>Unit</span>
        <Select
          aria-label="Unit 선택"
          value={selection.unitId ?? ""}
          disabled={!selection.plantId}
          onChange={(event) =>
            onSelect({
              plantId: selection.plantId,
              unitId: event.target.value || null,
              equipmentId: null,
              sensorIds: [],
            })
          }
        >
          <option value="">
            {selection.plantId ? "전체 유닛" : "플랜트 선택 후"}
          </option>
          {units.map((unit) => (
            <option key={unit.id} value={unit.id}>
              {unit.name}
            </option>
          ))}
        </Select>
      </label>
      <ChevronRight size={12} aria-hidden="true" />
      <label className="context-select context-equipment-select">
        <span>Equipment</span>
        <Select
          aria-label="Equipment 선택"
          value={selection.equipmentId ?? ""}
          disabled={!selection.unitId}
          onChange={(event) =>
            onSelect({ ...selection, equipmentId: event.target.value || null })
          }
        >
          <option value="">
            {selection.unitId ? "전체 설비" : "유닛 선택 후"}
          </option>
          {equipment.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name} · {item.id}
            </option>
          ))}
        </Select>
      </label>
      <ChevronRight size={12} aria-hidden="true" />
      <details className="context-sensors">
        <summary aria-label="Sensor 선택">
          <span>Sensor</span>
          <strong>
            {!selection.equipmentId
              ? "설비 선택 후"
              : `${selection.sensorIds.length} / ${sensors.length}개 선택`}
          </strong>
        </summary>
        {selection.equipmentId && (
          <div
            className="context-sensors-menu"
            role="group"
            aria-label="센서 복수 선택"
          >
            <div className="context-sensors-actions">
              <button
                type="button"
                disabled={selection.sensorIds.length === sensors.length}
                onClick={() =>
                  onSelect({
                    ...selection,
                    sensorIds: sensors.map((sensor) => sensor.id),
                  })
                }
              >
                전체 선택
              </button>
              <button
                type="button"
                disabled={selection.sensorIds.length === 0}
                onClick={() => onSelect({ ...selection, sensorIds: [] })}
              >
                전체 해제
              </button>
            </div>
            {sensors.map((sensor) => (
              <label key={sensor.id}>
                <input
                  type="checkbox"
                  checked={selection.sensorIds.includes(sensor.id)}
                  onChange={(event) =>
                    onSelect({
                      ...selection,
                      sensorIds: event.target.checked
                        ? [...selection.sensorIds, sensor.id]
                        : selection.sensorIds.filter((id) => id !== sensor.id),
                    })
                  }
                />
                <span>
                  {sensor.name} · {sensor.id}
                </span>
              </label>
            ))}
          </div>
        )}
      </details>
    </div>
  );
}
