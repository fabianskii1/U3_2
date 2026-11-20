import { useEffect, useRef } from "react";
import { useQueries } from "@tanstack/react-query";
import type {
  Equipment,
  Selection,
} from "../../../shared/api/contracts/hierarchy.ts";
import type { Alarm } from "../../../shared/api/contracts/alarm.ts";
import { dateTime } from "../../../shared/lib/date-time.ts";
import { Card, CardHeader } from "../../../shared/ui/card.tsx";
import { equipmentQuery } from "../api/equipment.queries.ts";
import {
  equipmentAlarmState,
  levelLabels,
} from "../model/equipment-alarm-state.ts";

export function EquipmentCards({
  groupName,
  equipment,
  alarms,
  replayHour,
  selectedEquipmentId,
  navigationKey,
  autoFocus = true,
  onSelect,
}: {
  groupName: string;
  equipment: Equipment[];
  alarms: Alarm[];
  replayHour?: number | null;
  selectedEquipmentId: string | null;
  navigationKey?: string;
  autoFocus?: boolean;
  onSelect: (selection: Selection) => void;
}) {
  const details = useQueries({
    queries: equipment.map((item) => equipmentQuery(item.id)),
  });

  const selectedCard = useRef<HTMLButtonElement | null>(null);
  const centered = useRef<string | null>(null);
  const selectedIndex = equipment.findIndex(
    (item) => item.id === selectedEquipmentId,
  );
  const selectedPending =
    selectedIndex >= 0 && details[selectedIndex].isPending;

  useEffect(() => {
    const card = selectedCard.current;
    const container = card?.closest<HTMLElement>(".page-scroll");
    const key = `${navigationKey ?? ""}:${selectedEquipmentId ?? ""}`;
    if (
      !autoFocus ||
      !card ||
      !container ||
      selectedPending ||
      centered.current === key
    )
      return;
    const frame = window.requestAnimationFrame(() => {
      if (!card.isConnected) return;
      const bounds = card.getBoundingClientRect();
      const viewport = container.getBoundingClientRect();
      const top =
        container.scrollTop + bounds.top - viewport.top - container.clientTop;
      const inset = Math.max(0, (container.clientHeight - bounds.height) / 2);
      container.scrollTo({
        top: Math.max(0, top - inset),
        behavior: window.matchMedia?.("(prefers-reduced-motion: reduce)")
          .matches
          ? "instant"
          : "smooth",
      });
      centered.current = key;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [autoFocus, navigationKey, selectedEquipmentId, selectedPending]);

  return (
    <Card className="equipment-cards-panel" data-chat-section="sensors">
      <CardHeader
        title="설비 및 센서"
        description={`${groupName} · 설비 ${equipment.length}대 · ${replayHour == null ? "현재 상태" : "색은 기록 시각의 단계"} · 센서값은 최근 저장값`}
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
            const status = equipmentAlarmState(
              query.data ?? item,
              alarms,
              replayHour,
            );
            const selected = item.id === selectedEquipmentId;
            return (
              <button
                key={item.id}
                ref={selected ? selectedCard : undefined}
                type="button"
                className={`equipment-summary-card${selected ? " is-selected" : ""}`}
                data-status={status.level}
                data-predicted={status.predicted || undefined}
                aria-pressed={selected}
                aria-label={`${item.name} ${item.id} 선택`}
                onClick={() =>
                  onSelect({
                    plantId: item.plantId,
                    unitId: item.unitId,
                    equipmentId: item.id,
                    sensorIds: item.tags.map((tag) => tag.id),
                  })
                }
              >
                <span className="equipment-summary-head">
                  <span>
                    <strong className="equipment-summary-id">{item.id}</strong>
                    <span className="equipment-summary-name">{item.name}</span>
                  </span>
                  <span
                    className="equipment-status-badge"
                    data-level={status.level}
                  >
                    {levelLabels[status.level] ?? "정상"}
                    {status.predicted ? " (예측)" : ""}
                  </span>
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
                  {tags.map((tag) => {
                    const sensorLevel =
                      replayHour == null
                        ? Math.max(
                            tag.sensorLevel ?? 0,
                            status.sensorLevels.get(tag.id) ?? 0,
                          )
                        : (status.sensorLevels.get(tag.id) ?? 0);
                    const predicted = status.sensorPredictions.has(tag.id);
                    return (
                      <span
                        className="equipment-sensor-cell"
                        key={tag.id}
                        data-level={sensorLevel}
                        data-predicted={predicted || undefined}
                        title={
                          tag.measuredAt
                            ? `${tag.name} · ${dateTime(tag.measuredAt)} KST`
                            : tag.name
                        }
                      >
                        <span className="equipment-sensor-name">
                          {tag.name}
                        </span>
                        <span className="equipment-sensor-value">
                          {tag.currentValue == null
                            ? "—"
                            : tag.currentValue.toLocaleString("ko-KR", {
                                maximumFractionDigits: 3,
                              })}
                          {tag.currentValue != null && (
                            <small>{tag.unit}</small>
                          )}
                        </span>
                      </span>
                    );
                  })}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </Card>
  );
}
