import type { Alarm } from "../../alarms/index.ts";
import type {
  Equipment,
  Selection,
} from "../../../shared/api/contracts/hierarchy.ts";
import { alarmLabel } from "../../../shared/lib/alarm-level.ts";
import { dateTime } from "../../../shared/lib/date-time.ts";
import { Card } from "../../../shared/ui/card.tsx";

function level(alarm: Alarm) {
  return alarm.alarmLevel ?? { High: 3, Medium: 2, Low: 1 }[alarm.severity];
}

export function EquipmentFeed({
  equipment,
  alarms,
  onSelect,
}: {
  equipment: Equipment[];
  alarms: Alarm[];
  onSelect: (selection: Selection) => void;
}) {
  const equipmentById = new Map(equipment.map((item) => [item.id, item]));
  const items = alarms
    .filter((alarm) => equipmentById.has(alarm.equipmentId))
    .sort(
      (a, b) =>
        level(b) - level(a) ||
        Date.parse(b.occurredAt) - Date.parse(a.occurredAt),
    );
  const normal = items.filter((alarm) => alarm.eventType !== "예측");
  const predicted = items.filter((alarm) => alarm.eventType === "예측");

  function selectAlarm(alarm: Alarm) {
    const item = equipmentById.get(alarm.equipmentId);
    if (!item) return;
    onSelect({
      plantId: item.plantId,
      unitId: item.unitId,
      equipmentId: item.id,
      sensorIds: item.tags.map((tag) => tag.id),
    });
  }

  function column(title: string, list: Alarm[], predictive: boolean) {
    return (
      <div className="equipment-feed-column">
        <h3 className={predictive ? "is-prediction" : ""}>
          {title} <span className="muted">{list.length}건</span>
        </h3>
        <div className="equipment-feed-list">
          {list.length === 0 ? (
            <p className="equipment-feed-empty">{title}이 없습니다.</p>
          ) : (
            list.slice(0, 60).map((alarm) => {
              const item = equipmentById.get(alarm.equipmentId)!;
              const tag = item.tags.find(
                (candidate) => candidate.id === alarm.tagId,
              );
              return (
                <div key={alarm.id}>
                  <button
                    type="button"
                    className="equipment-feed-item"
                    onClick={() => selectAlarm(alarm)}
                    aria-label={`${item.id} ${tag?.name ?? alarm.tagId} ${alarmLabel(alarm)} 알림 선택`}
                  >
                    <span className="equipment-feed-item-top">
                      <strong>{item.id}</strong>
                      <span
                        className="equipment-feed-level"
                        data-level={level(alarm)}
                      >
                        {alarmLabel(alarm)}
                      </span>
                      <time className="muted" dateTime={alarm.occurredAt}>
                        {dateTime(alarm.occurredAt)}
                      </time>
                    </span>
                    <strong className="equipment-feed-title">
                      {tag?.name ?? alarm.tagId} {alarm.type} 알림
                    </strong>
                    <span className="equipment-feed-reason muted">
                      {alarm.reason}
                    </span>
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>
    );
  }

  return (
    <Card className="equipment-feed-panel" data-chat-section="feed">
      <div className="equipment-feed-header">
        <div>
          <h2>지금 봐야 할 알림</h2>
          <p className="muted small">
            {equipment.length}대 설비 · 최근 알람 이력 · 높은 단계부터
          </p>
        </div>
      </div>
      <div className="equipment-feed-split">
        {column("알림", normal, false)}
        {column("예측 알림", predicted, true)}
      </div>
    </Card>
  );
}
