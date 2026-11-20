import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { ArrowRight } from "lucide-react";
import { incidentQuery, incidentsQuery } from "../api/incidents.queries.ts";
import { levelLabel, levelTone, splitEvidence } from "../model/incident.ts";
import { Card, CardHeader } from "../../../shared/ui/card.tsx";
import { Badge } from "../../../shared/ui/badge.tsx";
import { Button } from "../../../shared/ui/button.tsx";
import { LoadingState } from "../../../shared/ui/LoadingState.tsx";
import { ErrorState } from "../../../shared/ui/ErrorState.tsx";
import { errorMessage } from "../../../shared/api/http-client.ts";
import { dateTime } from "../../../shared/lib/date-time.ts";

export type FaultSelection = { incidentId: string; fault: string };

export function DiagnosisPanel({
  equipmentId,
  asOf,
  selection,
  onSelect,
}: {
  equipmentId: string;
  asOf?: string;
  selection: FaultSelection | null;
  onSelect: (selection: FaultSelection) => void;
}) {
  const list = useQuery(
    incidentsQuery({ equipment_id: equipmentId, as_of: asOf, limit: 20 }),
  );
  const incident =
    list.data?.items.find((item) => item.status === "ongoing") ?? null;
  const detail = useQuery(incidentQuery(incident?.incident_id ?? "", asOf));
  const selectedFault =
    selection && incident && selection.incidentId === incident.incident_id
      ? selection.fault
      : incident?.diagnosis;
  const candidates = detail.data?.candidates ?? [];

  return (
    <Card className="diagnosis-panel" data-chat-section="diagnosis">
      <CardHeader
        title={`${equipmentId} 진단`}
        description="분석기 추정 결과 · 고장 유형을 선택하면 3D 부품 표시가 바뀝니다."
        action={
          incident && (
            <Button asChild variant="ghost" size="sm">
              <Link
                to={`/incidents/${encodeURIComponent(incident.incident_id)}`}
              >
                사건 상세 <ArrowRight size={14} />
              </Link>
            </Button>
          )
        }
      />
      {list.isPending ? (
        <LoadingState />
      ) : list.isError ? (
        <ErrorState
          message={`진단을 조회하지 못했습니다. ${errorMessage(list.error)}`}
          retry={() => void list.refetch()}
        />
      ) : !incident ? (
        <p className="empty-state">이 시각 진행 중인 이상 사건이 없습니다.</p>
      ) : (
        <>
          <div className="diagnosis-summary">
            <Badge tone={levelTone(incident.peak_level)}>
              최고 {levelLabel(incident.peak_level)}
            </Badge>
            <strong>판별 (확률 1위): {incident.diagnosis}</strong>
            {incident.top_risk_fault !== incident.diagnosis && (
              <span>위험 1위: {incident.top_risk_fault}</span>
            )}
            <p className="muted small">
              이상 시작 {dateTime(incident.incident_start_time)} · 추세 감지{" "}
              {dateTime(incident.detect_time)} · 첫 알림{" "}
              {incident.first_alarm_time
                ? dateTime(incident.first_alarm_time)
                : "없음"}
              {incident.incident_end_time &&
                ` · 예상 종료 ${dateTime(incident.incident_end_time)}`}
            </p>
            <p className="muted small">
              등급 {incident.alarm_grade} ({incident.grade_reason}) · 최고 단계{" "}
              {levelLabel(incident.peak_level)} · 먼저 변한 센서{" "}
              {incident.lead_sensor_name ?? "미기록"}
            </p>
          </div>
          {detail.isPending ? (
            <LoadingState />
          ) : detail.isError ? (
            <ErrorState
              message={`고장 후보를 조회하지 못했습니다. ${errorMessage(detail.error)}`}
              retry={() => void detail.refetch()}
            />
          ) : candidates.length ? (
            <div
              className="diagnosis-candidates"
              role="group"
              aria-label="고장 유형 선택"
            >
              {candidates.map((candidate) => {
                const selected = candidate.fault === selectedFault;
                return (
                  <button
                    key={candidate.error_type_id}
                    type="button"
                    className={`diagnosis-candidate${selected ? " is-selected" : ""}`}
                    aria-pressed={selected}
                    onClick={() =>
                      onSelect({
                        incidentId: incident.incident_id,
                        fault: candidate.fault,
                      })
                    }
                  >
                    <span className="diagnosis-candidate-heading">
                      <span>
                        위험 {candidate.rank}위 · {candidate.fault}
                        {candidate.is_diagnosis && " · 확률 1위"}
                      </span>
                      <span className="mono">{candidate.score}</span>
                    </span>
                    <span
                      className="diagnosis-candidate-bar"
                      aria-hidden="true"
                    >
                      <span
                        style={{
                          width: `${Math.min(100, Math.max(0, candidate.p * 100))}%`,
                        }}
                      />
                    </span>
                    <span className="muted small mono">
                      p {candidate.p} · CoF {candidate.cof} · PoF{" "}
                      {candidate.pof}
                    </span>
                    {selected &&
                      splitEvidence(candidate.evidence).length > 0 && (
                        <span className="diagnosis-candidate-evidence">
                          {splitEvidence(candidate.evidence)
                            .slice(0, 4)
                            .map((line) => (
                              <span key={line}>• {line}</span>
                            ))}
                        </span>
                      )}
                  </button>
                );
              })}
            </div>
          ) : (
            <p className="empty-state">표시할 고장 후보가 없습니다.</p>
          )}
        </>
      )}
    </Card>
  );
}
