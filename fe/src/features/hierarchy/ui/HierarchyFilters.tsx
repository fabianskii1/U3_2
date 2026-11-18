import { ChevronRight } from "lucide-react";
import type { Hierarchy, Selection } from "../model/hierarchy.schema.ts";
import { Select } from "../../../shared/ui/select.tsx";

export function HierarchyFilters({
  data,
  selection,
  onSelect,
}: {
  data: Hierarchy;
  selection: Selection;
  onSelect: (next: Selection) => void;
}) {
  const units = data.units.filter((unit) => unit.plantId === selection.plantId);
  const equipment = data.equipment.filter(
    (item) => item.unitId === selection.unitId,
  );

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
    </div>
  );
}
