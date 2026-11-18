import { useState } from "react";
import {
  Factory,
  ChevronDown,
  ChevronRight,
  Layers,
  CircleDot,
  Search,
} from "lucide-react";
import type { Hierarchy, Selection } from "../model/hierarchy.schema.ts";
import { Input } from "../../../shared/ui/input.tsx";
export function HierarchyNavigation({
  data,
  selection,
  onSelect,
  hidden = false,
}: {
  hidden?: boolean;
  data: Hierarchy;
  selection: Selection;
  onSelect: (next: Selection) => void;
}) {
  const [search, setSearch] = useState("");
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const toggle = (id: string) => setCollapsed((s) => ({ ...s, [id]: !s[id] }));
  return (
    <aside
      className="hierarchy"
      id="hierarchy-panel"
      aria-label="설비 탐색 패널"
      hidden={hidden}
    >
      <div className="hierarchy-title">
        <span>설비 탐색</span>
        <span className="eyebrow">ASSET EXPLORER</span>
      </div>
      <div className="hierarchy-search">
        <Search size={14} />
        <Input
          aria-label="설비 검색"
          placeholder="설비명 또는 ID 검색"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      <nav aria-label="Plant Unit Equipment 계층">
        <button
          className={`tree-row all-row ${!selection.plantId ? "selected" : ""}`}
          onClick={() =>
            onSelect({ plantId: null, unitId: null, equipmentId: null })
          }
        >
          <Layers size={15} />
          전체 플랜트<span className="tree-count">{data.plants.length}</span>
        </button>
        {data.plants.map((plant) => (
          <div key={plant.id}>
            <div className="tree-group">
              <button
                className="tree-toggle"
                aria-label={`${plant.name} ${collapsed[plant.id] ? "펼치기" : "접기"}`}
                aria-expanded={!collapsed[plant.id]}
                onClick={() => toggle(plant.id)}
              >
                {collapsed[plant.id] ? (
                  <ChevronRight size={13} />
                ) : (
                  <ChevronDown size={13} />
                )}
              </button>
              <button
                className={`tree-row ${selection.plantId === plant.id && !selection.unitId ? "selected" : ""}`}
                onClick={() =>
                  onSelect({
                    plantId: plant.id,
                    unitId: null,
                    equipmentId: null,
                  })
                }
              >
                <Factory size={15} />
                {plant.name}
              </button>
            </div>
            {!collapsed[plant.id] || search
              ? data.units
                  .filter((u) => u.plantId === plant.id)
                  .map((unit) => (
                    <div key={unit.id} className="tree-unit">
                      <div className="tree-group">
                        <button
                          className="tree-toggle"
                          aria-label={`${unit.name} ${collapsed[unit.id] ? "펼치기" : "접기"}`}
                          aria-expanded={!collapsed[unit.id]}
                          onClick={() => toggle(unit.id)}
                        >
                          {collapsed[unit.id] ? (
                            <ChevronRight size={12} />
                          ) : (
                            <ChevronDown size={12} />
                          )}
                        </button>
                        <button
                          className={`tree-row ${selection.unitId === unit.id && !selection.equipmentId ? "selected" : ""}`}
                          onClick={() =>
                            onSelect({
                              plantId: plant.id,
                              unitId: unit.id,
                              equipmentId: null,
                            })
                          }
                        >
                          {unit.name}
                        </button>
                      </div>
                      {!collapsed[unit.id] || search
                        ? data.equipment
                            .filter(
                              (e) =>
                                e.unitId === unit.id &&
                                `${e.name} ${e.id}`
                                  .toLowerCase()
                                  .includes(search.toLowerCase()),
                            )
                            .map((e) => (
                              <button
                                key={e.id}
                                className={`tree-row tree-equipment ${selection.equipmentId === e.id ? "selected" : ""}`}
                                onClick={() =>
                                  onSelect({
                                    plantId: e.plantId,
                                    unitId: e.unitId,
                                    equipmentId: e.id,
                                  })
                                }
                              >
                                <CircleDot size={12} />
                                <span>
                                  {e.name}
                                  <small>{e.id}</small>
                                </span>
                              </button>
                            ))
                        : null}
                    </div>
                  ))
              : null}
          </div>
        ))}
      </nav>
      <div className="hierarchy-note">
        <span className="status-dot" />총 {data.equipment.length}대의 회전설비
        <br />
        <span className="muted">계층을 선택해 범위를 좁히세요.</span>
      </div>
    </aside>
  );
}
