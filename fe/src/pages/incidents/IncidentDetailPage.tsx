import { useQuery } from "@tanstack/react-query";
import { Link, useParams, useSearchParams, useNavigate } from "react-router";
import { TriangleAlert } from "lucide-react";
import {
  STATUS_LABELS,
  incidentDraftQuery,
  incidentQuery,
  levelLabel,
  levelTone,
  splitEvidence,
  timeline,
  type IncidentDetail,
} from "../../features/incidents/index.ts";
import { trendQuery } from "../../features/trend/api/trend.queries.ts";
import { TrendChart } from "../../features/trend/ui/TrendChart.tsx";
import { errorMessage } from "../../shared/api/http-client.ts";
import { Card, CardHeader } from "../../shared/ui/card.tsx";
import { Badge } from "../../shared/ui/badge.tsx";
import { Button } from "../../shared/ui/button.tsx";
import { LoadingState } from "../../shared/ui/LoadingState.tsx";
import { ErrorState } from "../../shared/ui/ErrorState.tsx";
import { EmptyState } from "../../shared/ui/EmptyState.tsx";
import { useSectionFocus } from "../../shared/lib/use-section-focus.ts";
import { dateTime } from "../../shared/lib/date-time.ts";

export function IncidentDetailPage() {
  const { incidentId = "" } = useParams();
  const [params] = useSearchParams();
  useSectionFocus();
  const query = useQuery(
    incidentQuery(incidentId, params.get("as_of") ?? undefined),
  );
  if (query.isPending) return <LoadingState />;
  if (query.isError)
    return (
      <div className="page">
        <ErrorState
          message={errorMessage(query.error)}
          retry={() => void query.refetch()}
        />
        <Button asChild variant="outline">
          <Link to="/incidents">사건 목록으로</Link>
        </Button>
      </div>
    );
  const incident = query.data;
  return (
    <div className="page incident-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">INCIDENT · {incident.incident_id}</div>
          <h1>
            {incident.equipment_name} · {incident.diagnosis}
            <span className="muted"> (추정)</span>
          </h1>
          <p>
            {STATUS_LABELS[incident.status]} · 대응 {incident.alarm_grade} (
            {incident.grade_reason}) · 조치 필요{" "}
            {incident.actionable ? "예" : "아니오"}
          </p>
        </div>
        <Badge tone={levelTone(incident.peak_level)}>
          최고 {levelLabel(incident.peak_level)}
        </Badge>
      </div>
      {incident.warnings.map((warning) => (
        <p key={warning} className="incident-warning" role="status">
          <TriangleAlert size={15} /> {warning}
        </p>
      ))}
      <Card data-chat-section="timeline">
        <CardHeader title="경과" description="시각은 KST" />
        <ol className="incident-timeline">
          {timeline(incident).map((step) => (
            <li key={step.key}>
              <span className="muted small">{step.label}</span>
              <strong className="mono">
                {step.time ? dateTime(step.time) : "없음"}
              </strong>
              {step.gap && <span className="small muted">+{step.gap}</span>}
            </li>
          ))}
        </ol>
        <dl className="incident-facts">
          <div>
            <dt>선행 센서</dt>
            <dd>
              {incident.lead_sensor_name ?? "미기록"}
              {incident.lead_sensor_id && (
                <small className="muted"> {incident.lead_sensor_id}</small>
              )}
            </dd>
          </div>
          <div>
            <dt>사건 점수</dt>
            <dd className="mono">{incident.incident_score}</dd>
          </div>
          <div>
            <dt>사건 CoF · PoF</dt>
            <dd className="mono">
              {incident.top_cof} · {(incident.top_pof * 100).toFixed(1)}%
            </dd>
          </div>
          <div>
            <dt>연결 알람</dt>
            <dd className="mono">{incident.linked_alarm_count}건</dd>
          </div>
        </dl>
      </Card>
      <CandidateCard incident={incident} />
      <AlarmCard incident={incident} />
      <TrendCard incident={incident} />
      <DraftCard incident={incident} />
      <Button asChild variant="outline">
        <Link to="/incidents">사건 목록으로</Link>
      </Button>
    </div>
  );
}

function CandidateCard({ incident }: { incident: IncidentDetail }) {
  return (
    <Card data-chat-section="causes">
      <CardHeader
        title="원인 후보"
        description="분석기 추정 결과이며 확정 원인이 아닙니다."
      />
      <ol className="incident-candidates">
        {incident.candidates.map((item) => (
          <li key={item.rank}>
            <div className="inline">
              <strong>
                {item.rank}. {item.fault}
              </strong>
              {item.is_diagnosis && <Badge tone="Medium">진단(추정)</Badge>}
              {item.is_top_risk && <Badge tone="High">최고 위험</Badge>}
              <span className="mono small muted">
                점수 {item.score} · p {item.p} · CoF {item.cof} · PoF{" "}
                {(item.pof * 100).toFixed(1)}%
              </span>
            </div>
            <ul>
              {splitEvidence(item.evidence).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </li>
        ))}
      </ol>
      {incident.candidates.length === 1 && (
        <p className="small muted">비교할 다른 원인 후보가 없습니다.</p>
      )}
    </Card>
  );
}

function AlarmCard({ incident }: { incident: IncidentDetail }) {
  return (
    <Card data-chat-section="alarms">
      <CardHeader
        title={`관련 알람 ${incident.alarms.length}건`}
        description="등급은 판정 setpoint 등급, 최고 도달은 구간 중 최고 등급"
      />
      {incident.alarms.length ? (
        <div className="table-scroll">
          <table aria-label="사건 관련 알람">
            <thead>
              <tr>
                <th scope="col">시작</th>
                <th scope="col">센서</th>
                <th scope="col">유형</th>
                <th scope="col">등급</th>
                <th scope="col">최고 도달</th>
                <th scope="col">센서 초과 구간</th>
                <th scope="col">조치 완료</th>
              </tr>
            </thead>
            <tbody>
              {incident.alarms.map((alarm) => (
                <tr key={alarm.alarm_id}>
                  <td className="small mono">
                    {dateTime(alarm.alarm_start_time)}
                  </td>
                  <td>
                    <Link
                      className="equipment-link"
                      to={`/equip?equip_id=${encodeURIComponent(alarm.equipment_id)}&sensor_id=${encodeURIComponent(alarm.sensor_id)}`}
                    >
                      {alarm.sensor_name}
                      <small>{alarm.sensor_id}</small>
                    </Link>
                  </td>
                  <td>{alarm.event_type ?? "미기록"}</td>
                  <td>{levelLabel(alarm.alarm_level)}</td>
                  <td>{levelLabel(alarm.peak_level)}</td>
                  <td className="small mono">
                    {alarm.sensor_start_time
                      ? `${dateTime(alarm.sensor_start_time)} ~ ${alarm.sensor_end_time ? dateTime(alarm.sensor_end_time) : ""}`
                      : "센서 초과 없음(예측)"}
                  </td>
                  <td className="small mono">
                    {alarm.alarm_end_time
                      ? dateTime(alarm.alarm_end_time)
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState title="알람 없음" />
      )}
    </Card>
  );
}

function TrendCard({ incident }: { incident: IncidentDetail }) {
  const range = incident.trend_window;
  return (
    <Card data-chat-section="trend">
      <CardHeader
        title="사건 구간 트렌드"
        description={`${dateTime(range.from)} ~ ${dateTime(range.to)} · 1시간 평균 · 보라색 영역은 사건 구간`}
      />
      {incident.data_coverage === "none" ? (
        <EmptyState title="이 기간 시계열 없음" />
      ) : (
        <>
          {incident.data_coverage === "partial" && (
            <p className="incident-warning" role="status">
              <TriangleAlert size={15} /> 사건 구간의 시계열이 일부만 있습니다.
            </p>
          )}
          {range.signals.map((signal) => (
            <SignalTrend
              key={signal.signal_id}
              incident={incident}
              sensorId={signal.sensor_id}
              name={signal.measurement_name}
            />
          ))}
        </>
      )}
    </Card>
  );
}

function SignalTrend({
  incident,
  sensorId,
  name,
}: {
  incident: IncidentDetail;
  sensorId: string;
  name: string;
}) {
  const { from, to } = incident.trend_window;
  const query = useQuery(trendQuery(sensorId, from, to, "1h"));
  const markers = incident.alarms
    .filter((alarm) => alarm.sensor_id === sensorId)
    .map((alarm) => ({
      time: alarm.alarm_start_time,
      label: alarm.event_type === "임계치 초과" ? "초과" : "예측",
    }));
  return (
    <section className="incident-trend">
      <h3>
        {name} <small className="muted">{sensorId}</small>
      </h3>
      {query.isPending ? (
        <LoadingState />
      ) : query.isError ? (
        <ErrorState
          message={errorMessage(query.error)}
          retry={() => void query.refetch()}
        />
      ) : (
        <TrendChart
          points={query.data.points}
          limit={query.data.limit}
          unit={query.data.unit}
          setpoints={query.data.setpoints}
          incidents={[
            {
              id: incident.incident_id,
              from: incident.incident_start_time,
              to: incident.incident_end_time,
              label: "사건",
            },
          ]}
          markers={[{ time: incident.detect_time, label: "감지" }, ...markers]}
        />
      )}
    </section>
  );
}

function DraftCard({ incident }: { incident: IncidentDetail }) {
  const incidentId = incident.incident_id;
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const open = params.get("draft") === "open";
  const setOpen = () => {
    const next = new URLSearchParams(params);
    next.set("draft", "open");
    next.set("section", "draft");
    setParams(next);
  };
  const draft = useQuery({ ...incidentDraftQuery(incidentId), enabled: open });
  const createReport = () => {
    const next = new URLSearchParams({
      incident_id: incidentId,
      equip_id: incident.equipment_id,
    });
    if (params.get("as_of")) next.set("as_of", params.get("as_of")!);
    void navigate(`/reports/new?${next}`);
  };
  return (
    <Card data-chat-section="draft">
      <CardHeader
        title="보고서 초안"
        description="사건 정보로 채운 검토용 초안입니다. 원인은 검토 항목입니다."
        action={
          !open && (
            <Button variant="outline" onClick={setOpen}>
              초안 만들기
            </Button>
          )
        }
      />
      {open &&
        (draft.isPending ? (
          <LoadingState />
        ) : draft.isError ? (
          <ErrorState
            message={errorMessage(draft.error)}
            retry={() => void draft.refetch()}
          />
        ) : (
          <>
            <dl className="incident-draft">
              {(
                [
                  ["제목", draft.data.title],
                  ["증상", draft.data.symptom],
                  ["원인 (검토 필요)", draft.data.cause],
                  ["조치", draft.data.action],
                  ["잔여 위험", draft.data.risk],
                ] as const
              ).map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
            <div className="incident-report-actions">
              <Button onClick={createReport}>최종 보고서 작성</Button>
              <span className="small muted">
                사건·진단 후보·알람·센서·초안을 작성 양식에 가져옵니다.
              </span>
            </div>
          </>
        ))}
    </Card>
  );
}
