import { Card } from "../../../shared/ui/card.tsx";
import {
  CONSOLE_EXAMPLE_HOUR,
  CONSOLE_MAX_HOUR,
  consolePumpTracks,
  consoleHourDate,
} from "../model/equipment-alarm-state.ts";

const formatter = new Intl.DateTimeFormat("ko-KR", {
  timeZone: "Asia/Seoul",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

export function EquipmentReplayControls({
  hour,
  onChange,
}: {
  hour: number | null;
  onChange: (hour: number | null) => void;
}) {
  const liveHour = Math.min(
    CONSOLE_MAX_HOUR,
    Math.max(
      1,
      Math.floor((Date.now() - consoleHourDate(1).getTime()) / 3_600_000) + 1,
    ),
  );
  const selected = hour ?? liveHour;
  return (
    <Card className="equipment-replay">
      <div className="equipment-replay-header">
        <div>
          <strong>설비 상태 기록 재생</strong>
          <span className="muted small">
            선택 시각의 펌프·센서 단계를 표시합니다.
          </span>
        </div>
        <span className="equipment-replay-time">
          {hour === null
            ? "현재 상태"
            : `${formatter.format(consoleHourDate(hour))} KST`}
        </span>
        <button type="button" onClick={() => onChange(CONSOLE_EXAMPLE_HOUR)}>
          예시 시각
        </button>
        <button type="button" onClick={() => onChange(null)}>
          현재 상태
        </button>
      </div>
      <input
        type="range"
        min={1}
        max={CONSOLE_MAX_HOUR}
        value={selected}
        aria-label="설비 상태 기록 시각"
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <div className="equipment-replay-ends muted small">
        <span>{formatter.format(consoleHourDate(1))}</span>
        <span>{formatter.format(consoleHourDate(CONSOLE_MAX_HOUR))}</span>
      </div>
      <div className="muted small">펌프별 단계 기록 · 띠를 눌러 시각 선택</div>
      <div className="equipment-replay-strip" aria-label="펌프별 상태 기록">
        <div className="equipment-replay-labels" aria-hidden="true">
          {consolePumpTracks.map((pump) => (
            <span key={pump.id}>{pump.id}</span>
          ))}
        </div>
        <div className="equipment-replay-lanes">
          {consolePumpTracks.map((pump) => (
            <button
              key={pump.id}
              type="button"
              className="equipment-replay-lane"
              aria-label={`${pump.id} 기록에서 시각 선택`}
              onClick={(event) => {
                const rect = event.currentTarget.getBoundingClientRect();
                const ratio = Math.max(
                  0,
                  Math.min(1, (event.clientX - rect.left) / rect.width),
                );
                onChange(
                  Math.min(
                    CONSOLE_MAX_HOUR,
                    Math.max(1, Math.round(ratio * CONSOLE_MAX_HOUR) + 1),
                  ),
                );
              }}
            >
              {pump.segments.map((segment) => (
                <span
                  key={segment.start}
                  className="equipment-replay-segment"
                  data-level={segment.level}
                  style={{
                    left: `${(segment.start / CONSOLE_MAX_HOUR) * 100}%`,
                    width: `${((segment.end - segment.start) / CONSOLE_MAX_HOUR) * 100}%`,
                  }}
                />
              ))}
            </button>
          ))}
          <span
            className="equipment-replay-cursor"
            style={{ left: `${((selected - 1) / CONSOLE_MAX_HOUR) * 100}%` }}
            aria-hidden="true"
          />
        </div>
      </div>
    </Card>
  );
}
