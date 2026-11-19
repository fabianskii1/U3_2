import type { Alarm } from "../../../shared/api/contracts/alarm.ts";
import type {
  Equipment,
  Hierarchy,
  Selection,
} from "../../../shared/api/contracts/hierarchy.ts";
import { Card, CardHeader } from "../../../shared/ui/card.tsx";

type PumpId = "P1" | "P2" | "P3" | "P4" | "P5" | "P6";

const pumps: {
  id: PumpId;
  x: number;
  y: number;
  r: number;
  tagX: number;
  tagY: number;
  anchor?: "middle";
}[] = [
  { id: "P1", x: 151, y: 223, r: 20, tagX: 151, tagY: 196, anchor: "middle" },
  { id: "P2", x: 664, y: 124, r: 20, tagX: 700, tagY: 128 },
  { id: "P3", x: 576, y: 198, r: 14, tagX: 576, tagY: 178, anchor: "middle" },
  { id: "P4", x: 616, y: 232, r: 14, tagX: 616, tagY: 212, anchor: "middle" },
  { id: "P5", x: 656, y: 266, r: 14, tagX: 656, tagY: 246, anchor: "middle" },
  { id: "P6", x: 556, y: 316, r: 14, tagX: 582, tagY: 320 },
];

function findPump(
  id: PumpId,
  equipment: Equipment[],
  plantId: string | null,
): Equipment | undefined {
  const inPlant = equipment.filter(
    (item) => !plantId || item.plantId === plantId,
  );
  return (
    inPlant.find((item) => item.id === id) ??
    inPlant.find(
      (item) => item.unitId.endsWith(`-${id}`) && item.id.endsWith("A"),
    ) ??
    inPlant.find((item) => item.unitId.endsWith(`-${id}`))
  );
}

function pumpLevel(equipment: Equipment, alarms: Alarm[]): number {
  const alarmLevel = Math.max(
    0,
    ...alarms
      .filter((alarm) => alarm.equipmentId === equipment.id)
      .map(
        (alarm) =>
          alarm.alarmLevel ??
          ({ High: 3, Medium: 2, Low: 1 } as const)[alarm.severity],
      ),
  );
  return Math.max(equipment.equipmentStatus ?? 0, alarmLevel);
}

export function CUDProcessLayout({
  hierarchy,
  selection,
  alarms,
  onSelect,
}: {
  hierarchy: Hierarchy;
  selection: Selection;
  alarms: Alarm[];
  onSelect: (selection: Selection) => void;
}) {
  const plantId = selection.plantId ?? hierarchy.plants[0]?.id ?? null;

  return (
    <Card className="process-layout">
      <CardHeader
        title="공정 배치도"
        description="펌프 색은 현재 상태를 나타냅니다. 펌프를 선택하면 설비 상세로 이동합니다."
      />
      <div className="process-layout-scroll">
        <svg viewBox="0 0 760 340" role="group" aria-label="CDU 공정 배치도">
          <defs>
            <marker
              id="process-arrow"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path d="M0,0 L10,5 L0,10 z" className="process-arrow" />
            </marker>
          </defs>
          <rect
            className="process-box"
            x="10"
            y="200"
            width="88"
            height="46"
            rx="6"
          />
          <text x="54" y="227" textAnchor="middle">
            원유 탱크
          </text>
          <path
            className="process-pipe"
            d="M98,223 L130,223"
            markerEnd="url(#process-arrow)"
          />
          <path
            className="process-pipe"
            d="M172,223 L204,223"
            markerEnd="url(#process-arrow)"
          />
          <rect
            className="process-box"
            x="206"
            y="200"
            width="86"
            height="46"
            rx="6"
          />
          <text x="249" y="227" textAnchor="middle">
            열교환기
          </text>
          <path
            className="process-pipe"
            d="M292,223 L322,223"
            markerEnd="url(#process-arrow)"
          />
          <rect
            className="process-box"
            x="324"
            y="200"
            width="78"
            height="46"
            rx="6"
          />
          <text x="363" y="227" textAnchor="middle">
            가열로
          </text>
          <path
            className="process-pipe"
            d="M402,223 L436,223"
            markerEnd="url(#process-arrow)"
          />
          <rect
            className="process-box"
            x="438"
            y="40"
            width="66"
            height="260"
            rx="30"
          />
          <text x="471" y="174" textAnchor="middle">
            증류탑
          </text>
          <path
            className="process-pipe"
            d="M471,40 L471,22 L560,22 L560,40"
            markerEnd="url(#process-arrow)"
          />
          <rect
            className="process-box"
            x="530"
            y="42"
            width="62"
            height="34"
            rx="6"
          />
          <text x="561" y="63" textAnchor="middle">
            응축기
          </text>
          <path
            className="process-pipe"
            d="M592,59 L618,59"
            markerEnd="url(#process-arrow)"
          />
          <rect
            className="process-box"
            x="620"
            y="40"
            width="88"
            height="40"
            rx="18"
          />
          <text x="664" y="64" textAnchor="middle">
            리플럭스 드럼
          </text>
          <path
            className="process-pipe"
            d="M664,80 L664,102"
            markerEnd="url(#process-arrow)"
          />
          <path
            className="process-pipe"
            d="M643,124 L506,124"
            markerEnd="url(#process-arrow)"
          />
          <text className="process-label" x="560" y="117" textAnchor="middle">
            환류
          </text>
          <path
            className="process-pipe"
            d="M664,145 L664,170 L740,170"
            markerEnd="url(#process-arrow)"
          />
          <text className="process-label" x="712" y="164" textAnchor="middle">
            나프타
          </text>
          <path className="process-pipe" d="M504,198 L561,198" />
          <path className="process-pipe" d="M504,232 L601,232" />
          <path className="process-pipe" d="M504,266 L641,266" />
          <path className="process-pipe" d="M471,300 L471,316 L541,316" />
          <text className="process-label" x="712" y="236" textAnchor="middle">
            측류 인출
          </text>
          <text className="process-label" x="606" y="320">
            탑 바닥 잔사유
          </text>
          {pumps.map((pump) => {
            const equipment = findPump(pump.id, hierarchy.equipment, plantId);
            const level = equipment ? pumpLevel(equipment, alarms) : null;
            return (
              <g
                key={pump.id}
                className={`process-pump ${equipment ? "is-interactive" : ""} ${selection.equipmentId === equipment?.id ? "is-selected" : ""}`}
                data-pump={pump.id}
                data-level={level ?? "unknown"}
                role={equipment ? "button" : undefined}
                tabIndex={equipment ? 0 : undefined}
                aria-label={`${pump.id}${equipment ? ` ${equipment.name} 선택` : " 설비 없음"}`}
                aria-pressed={
                  equipment ? selection.equipmentId === equipment.id : undefined
                }
                onClick={
                  equipment
                    ? () =>
                        onSelect({
                          plantId: equipment.plantId,
                          unitId: equipment.unitId,
                          equipmentId: equipment.id,
                        })
                    : undefined
                }
                onKeyDown={
                  equipment
                    ? (event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          onSelect({
                            plantId: equipment.plantId,
                            unitId: equipment.unitId,
                            equipmentId: equipment.id,
                          });
                        }
                      }
                    : undefined
                }
              >
                <circle cx={pump.x} cy={pump.y} r={pump.r} />
                <text
                  className="process-tag"
                  x={pump.tagX}
                  y={pump.tagY}
                  textAnchor={pump.anchor}
                >
                  {pump.id}
                </text>
                {pump.id === "P1" && (
                  <text
                    className="process-label"
                    x="151"
                    y="260"
                    textAnchor="middle"
                  >
                    원유 공급
                  </text>
                )}
                {pump.id === "P2" && (
                  <text className="process-label" x="700" y="143">
                    환류·나프타
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
    </Card>
  );
}
