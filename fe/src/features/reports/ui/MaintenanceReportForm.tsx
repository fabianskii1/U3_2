import { useState, type ReactNode } from "react";
import {
  ArrowRight,
  BookOpen,
  Check,
  ClipboardCheck,
  ExternalLink,
  FileSearch,
  Plus,
  ShieldCheck,
  Trash2,
  Wrench,
} from "lucide-react";
import type { Equipment } from "../../../shared/api/contracts/hierarchy.ts";
import type {
  MaintenanceReport,
  Inspection,
} from "../../../shared/api/contracts/maintenance-report.ts";
import { Button } from "../../../shared/ui/button.tsx";
import { Input } from "../../../shared/ui/input.tsx";
import { Textarea } from "../../../shared/ui/textarea.tsx";
import { Badge } from "../../../shared/ui/badge.tsx";
import {
  checkLabels,
  causeConfirmationErrors,
  finalCause,
  fromKstInput,
  invalidateCause,
  kstInput,
  newInspection,
  safeSourceHref,
} from "../model/maintenance-report.ts";
import { ReportSensorAnalysis } from "./ReportSensorAnalysis.tsx";

export function ReportSection({
  number,
  title,
  children,
  description,
}: {
  number: number;
  title: string;
  children: ReactNode;
  description?: string;
}) {
  return (
    <section className="mr-section" aria-labelledby={`mr-section-${number}`}>
      <div className="mr-section-heading">
        <span>{number}</span>
        <h2 id={`mr-section-${number}`}>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      <div className="mr-section-content">{children}</div>
    </section>
  );
}
export function ReportField({
  label,
  value,
  onChange,
  editing,
  multiline,
  type = "text",
  required,
  placeholder,
  children,
}: {
  label: string;
  value: string;
  onChange?: (value: string) => void;
  editing: boolean;
  multiline?: boolean;
  type?: string;
  required?: boolean;
  placeholder?: string;
  children?: ReactNode;
}) {
  return (
    <label className={`mr-field ${multiline ? "mr-field-multiline" : ""}`}>
      <span>
        {label}
        {required && <b aria-hidden="true"> *</b>}
      </span>
      {multiline ? (
        <Textarea
          aria-label={label}
          readOnly={!editing}
          value={value}
          onChange={(e) => onChange?.(e.target.value)}
          rows={3}
          maxLength={10000}
          placeholder={placeholder ?? "미입력"}
        />
      ) : (
        <Input
          aria-label={label}
          type={type}
          readOnly={!editing}
          value={value}
          onChange={(e) => onChange?.(e.target.value)}
          maxLength={1000}
          placeholder={placeholder ?? "미입력"}
        />
      )}
      {children}
    </label>
  );
}
function SourceLink({ href, children }: { href: string; children: ReactNode }) {
  const safe = safeSourceHref(href);
  return safe ? (
    <a className="mr-source-link" href={safe} target="_blank" rel="noreferrer">
      {children}
      <ExternalLink size={13} />
    </a>
  ) : (
    <span className="small muted">{children} · 원문 미연결</span>
  );
}
export function MaintenanceReportForm({
  model: m,
  equipment,
  equipmentId,
  editing,
  onChange,
  causeNote,
  actionNote,
  reportId,
}: {
  model: MaintenanceReport;
  equipment?: Equipment;
  equipmentId: string;
  editing: boolean;
  onChange: (model: MaintenanceReport) => void;
  causeNote?: string;
  actionNote?: string;
  reportId: string;
}) {
  const [errors, setErrors] = useState<string[]>([]);
  const updateIncident = (
    key: keyof MaintenanceReport["incident"],
    value: string | string[],
  ) => {
    const updated = { ...m, incident: { ...m.incident, [key]: value } };
    onChange(
      ["alarmId", "alarmAt", "sensorIds"].includes(key)
        ? invalidateCause(updated)
        : updated,
    );
  };
  const updateWork = (key: keyof MaintenanceReport["work"], value: string) =>
    onChange({ ...m, work: { ...m.work, [key]: value } });
  const updateReview = (
    key: keyof MaintenanceReport["review"],
    value: unknown,
  ) => onChange({ ...m, review: { ...m.review, [key]: value } });
  const updateFinal = (
    key: "candidateId" | "otherCause" | "rationale",
    value: string,
  ) => {
    setErrors([]);
    onChange(
      invalidateCause({
        ...m,
        diagnosis: {
          ...m.diagnosis,
          final: { ...m.diagnosis.final, [key]: value },
        },
      }),
    );
  };
  const updateInspection = (id: string, patch: Partial<Inspection>) => {
    setErrors([]);
    onChange(
      invalidateCause({
        ...m,
        diagnosis: {
          ...m.diagnosis,
          inspections: m.diagnosis.inspections.map((row) =>
            row.id === id ? { ...row, ...patch } : row,
          ),
        },
      }),
    );
  };
  const candidateOptions = (
    <>
      <option value="">원인 후보 선택</option>
      {m.original.aiCandidates.map((c) => (
        <option key={c.id} value={c.id}>
          {c.rank}순위 · {c.label}
        </option>
      ))}
      <option value="other">기타 (직접 입력)</option>
    </>
  );
  return (
    <div className="mr-form">
      <ReportSection
        number={1}
        title="사건 및 설비 정보"
        description="알람 원본과 편집 내용을 구분하여 기록합니다."
      >
        <div className="mr-grid mr-grid-3">
          <ReportField
            label="사건 ID"
            value={m.incident.eventId}
            editing={editing}
            onChange={(v) => updateIncident("eventId", v)}
          />
          <ReportField label="설비 ID" value={equipmentId} editing={false} />
          <ReportField
            label="설비명"
            value={m.incident.equipmentName}
            editing={editing}
            onChange={(v) => updateIncident("equipmentName", v)}
          />
          <ReportField
            label="최초 알람 시각 (KST)"
            type="datetime-local"
            value={kstInput(m.incident.alarmAt)}
            editing={editing}
            onChange={(v) => updateIncident("alarmAt", fromKstInput(v))}
          />
          <ReportField
            label="알람 ID"
            value={m.incident.alarmId}
            editing={editing}
            onChange={(v) => updateIncident("alarmId", v)}
          />
          <ReportField
            label="이상 감지 센서 ID (쉼표로 구분)"
            value={m.incident.sensorIds.join(", ")}
            editing={editing}
            onChange={(v) =>
              updateIncident("sensorIds", [
                ...new Set(
                  v
                    .split(",")
                    .map((id) => id.trim())
                    .filter(Boolean),
                ),
              ])
            }
          />
        </div>
        {editing && equipment && (
          <div className="mr-related-picker">
            <span>사건 관련 센서</span>
            {equipment.tags.map((tag) => (
              <label key={tag.id}>
                <input
                  type="checkbox"
                  checked={m.incident.sensorIds.includes(tag.id)}
                  onChange={(e) =>
                    updateIncident(
                      "sensorIds",
                      e.target.checked
                        ? [...m.incident.sensorIds, tag.id]
                        : m.incident.sensorIds.filter((id) => id !== tag.id),
                    )
                  }
                />
                {tag.name} <small>{tag.id}</small>
              </label>
            ))}
          </div>
        )}
        <div className="mr-grid mr-grid-2 mr-spaced">
          <ReportField
            label="당시 운전 조건"
            value={m.incident.operatingConditions}
            editing={editing}
            onChange={(v) => updateIncident("operatingConditions", v)}
            placeholder="당시 온도 / RPM / 유량 등 · 현재값과 구분하여 입력"
          />
          <ReportField
            label="설비 위치"
            value={m.incident.location}
            editing={editing}
            onChange={(v) => updateIncident("location", v)}
          />
          <ReportField
            label="제조사"
            value={m.incident.manufacturer}
            editing={editing}
            onChange={(v) => updateIncident("manufacturer", v)}
          />
          <ReportField
            label="모델"
            value={m.incident.model}
            editing={editing}
            onChange={(v) => updateIncident("model", v)}
          />
        </div>
        <div className="mr-spaced">
          <ReportField
            label="최근 정비 이력"
            value={m.incident.recentMaintenance}
            editing={editing}
            onChange={(v) => updateIncident("recentMaintenance", v)}
          />
        </div>
        <details className="mr-original">
          <summary>
            <ShieldCheck size={14} /> 최초 수집 기록 보기 <span>원본 보존</span>
          </summary>
          {m.original.alarm ? (
            <dl className="mr-original-grid">
              <div>
                <dt>최초 알람</dt>
                <dd>
                  {m.original.alarm.id} ·{" "}
                  {kstInput(m.original.alarm.occurredAt).replace("T", " ")} KST
                </dd>
              </div>
              <div>
                <dt>설비 · 센서</dt>
                <dd>
                  {m.original.alarm.equipmentId} · {m.original.alarm.sensorId}
                </dd>
              </div>
              <div>
                <dt>측정값 / 기준값</dt>
                <dd>
                  {m.original.alarm.value} / {m.original.alarm.threshold}{" "}
                  {m.original.alarm.unit}
                </dd>
              </div>
              <div>
                <dt>수집 사유</dt>
                <dd>{m.original.alarm.reason || "미제공"}</dd>
              </div>
            </dl>
          ) : (
            <p>
              연결된 최초 알람이 없습니다. 위의 수기 입력을 원본 알람으로
              취급하지 않습니다.
            </p>
          )}
          <p className="small muted">
            AI 초기 분석:{" "}
            {m.original.aiCandidates.length
              ? m.original.aiCandidates
                  .map((c) => `${c.rank}순위 ${c.label}`)
                  .join(" · ")
              : "미연결"}
          </p>
          {m.original.legacyCause && (
            <p className="small">
              이전 보고서의 추정 원인: {m.original.legacyCause} (확정 여부
              미확인)
            </p>
          )}
          {m.original.legacyAction && (
            <p className="small">
              이전 보고서의 조치 기록: {m.original.legacyAction} (이번 실제 수행
              조치에 자동 입력하지 않음)
            </p>
          )}
        </details>
      </ReportSection>

      <ReportSection number={2} title="관측 증상 및 운전 영향">
        <div className="mr-grid mr-grid-2">
          <ReportField
            label="관측 증상"
            multiline
            value={m.observations.symptoms}
            editing={editing}
            onChange={(v) =>
              onChange(
                invalidateCause({
                  ...m,
                  observations: { ...m.observations, symptoms: v },
                }),
              )
            }
            placeholder="센서 변화, 측정값·단위, 이상 현상을 기록하세요."
          />
          <ReportField
            label="운전 영향"
            multiline
            value={m.observations.impact}
            editing={editing}
            onChange={(v) =>
              onChange({ ...m, observations: { ...m.observations, impact: v } })
            }
            placeholder="생산 영향, 설비 정지 여부, 관련 공정 영향을 확인 후 기록하세요."
          />
        </div>
        <ReportSensorAnalysis
          model={m}
          equipment={equipment}
          reportId={reportId}
        />
      </ReportSection>

      <ReportSection
        number={3}
        title="진단 및 원인 확인"
        description="AI 추정 → 현장 검증 → 작업자 확정"
      >
        <div className="mr-diagnosis-grid">
          <div className="mr-step-card">
            <h3>
              <span className="mr-step">1</span> AI 추정 원인 우선순위{" "}
              <ArrowRight size={15} />
            </h3>
            <div className="mr-step-body">
              <p className="mr-help">초기 분석 결과 · 최종 원인과 별도</p>
              {!!causeNote && !m.diagnosis.final.confirmedAt && (
                <ReportField
                  label="추정 원인 참고 메모"
                  value={causeNote}
                  editing={false}
                  multiline
                />
              )}
              {m.original.aiCandidates.length ? (
                <div className="mr-candidates">
                  {m.original.aiCandidates.map((candidate) => (
                    <div
                      className={`mr-candidate ${m.diagnosis.candidateChecks[candidate.id] === "verified" ? "is-verified" : ""}`}
                      key={candidate.id}
                    >
                      <div>
                        <span className="mr-rank">{candidate.rank}</span>
                        <strong>{candidate.label}</strong>
                        {candidate.probability !== null && (
                          <small>{candidate.probability}%</small>
                        )}
                      </div>
                      <label>
                        <span>{candidate.label} 확인 상태</span>
                        <select
                          aria-label={`${candidate.label} 확인 상태`}
                          disabled={!editing}
                          value={
                            m.diagnosis.candidateChecks[candidate.id] ??
                            "unverified"
                          }
                          onChange={(e) => {
                            onChange(
                              invalidateCause({
                                ...m,
                                diagnosis: {
                                  ...m.diagnosis,
                                  candidateChecks: {
                                    ...m.diagnosis.candidateChecks,
                                    [candidate.id]: e.target
                                      .value as keyof typeof checkLabels,
                                  },
                                },
                              }),
                            );
                          }}
                        >
                          {Object.entries(checkLabels).map(([value, label]) => (
                            <option key={value} value={value}>
                              {label}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="mr-empty">
                  <FileSearch size={23} />
                  <p>연결된 AI 원인 후보가 없습니다.</p>
                  <small>
                    진단 결과 API 연결 시 후보가 표시됩니다. 현장 원인은
                    ‘기타’로 직접 기록할 수 있습니다.
                  </small>
                </div>
              )}
              <div className="mr-ai-note">
                AI 1순위는 자동 확정되지 않습니다.
              </div>
            </div>
          </div>
          <div className="mr-step-card">
            <h3>
              <span className="mr-step">2</span> 현장 확인 및 검증 결과{" "}
              <ArrowRight size={15} />
            </h3>
            <div className="mr-step-body">
              {!m.diagnosis.inspections.length && (
                <p className="mr-empty">
                  현장에서 확인한 점검 결과를 기록하세요.
                </p>
              )}
              {m.diagnosis.inspections.map((row, i) => (
                <div className="mr-inspection" key={row.id}>
                  <div className="mr-inline-between">
                    <strong>점검 {i + 1}</strong>
                    {editing && (
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`점검 ${i + 1} 삭제`}
                        onClick={() =>
                          onChange(
                            invalidateCause({
                              ...m,
                              diagnosis: {
                                ...m.diagnosis,
                                inspections: m.diagnosis.inspections.filter(
                                  (r) => r.id !== row.id,
                                ),
                              },
                            }),
                          )
                        }
                      >
                        <Trash2 size={13} />
                      </Button>
                    )}
                  </div>
                  <label className="mr-field">
                    <span>확인 대상 원인</span>
                    <select
                      aria-label={`점검 ${i + 1} 대상 원인`}
                      disabled={!editing}
                      value={row.candidateId}
                      onChange={(e) =>
                        updateInspection(row.id, {
                          candidateId: e.target.value,
                        })
                      }
                    >
                      {candidateOptions}
                    </select>
                  </label>
                  <ReportField
                    label={`점검 ${i + 1} 방법`}
                    value={row.method}
                    editing={editing}
                    onChange={(v) => updateInspection(row.id, { method: v })}
                  />
                  <ReportField
                    label={`점검 ${i + 1} 일시 (KST)`}
                    type="datetime-local"
                    value={kstInput(row.checkedAt)}
                    editing={editing}
                    onChange={(v) =>
                      updateInspection(row.id, { checkedAt: fromKstInput(v) })
                    }
                  />
                  <ReportField
                    label={`점검 ${i + 1} 결과 및 확인·제외 근거`}
                    multiline
                    value={row.result}
                    editing={editing}
                    onChange={(v) => updateInspection(row.id, { result: v })}
                  />
                  <ReportField
                    label={`점검 ${i + 1} 증거 ID`}
                    value={row.evidenceId}
                    editing={editing}
                    onChange={(v) =>
                      updateInspection(row.id, { evidenceId: v })
                    }
                  />
                  <ReportField
                    label={`점검 ${i + 1} 사진·확인 자료 URL`}
                    value={row.evidenceUrl}
                    editing={editing}
                    onChange={(v) =>
                      updateInspection(row.id, { evidenceUrl: v })
                    }
                  >
                    {row.evidenceUrl && (
                      <SourceLink href={row.evidenceUrl}>
                        증거 자료 열기
                      </SourceLink>
                    )}
                  </ReportField>
                </div>
              ))}
              {editing && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    onChange({
                      ...m,
                      diagnosis: {
                        ...m.diagnosis,
                        inspections: [
                          ...m.diagnosis.inspections,
                          newInspection(m.diagnosis.final.candidateId ?? ""),
                        ],
                      },
                    })
                  }
                >
                  <Plus size={13} /> 현장 점검 추가
                </Button>
              )}
            </div>
          </div>
          <div
            className={`mr-step-card mr-final-card ${m.diagnosis.final.confirmedAt ? "is-confirmed" : ""}`}
          >
            <h3>
              <span className="mr-step">3</span> 최종 고장 원인 확정
            </h3>
            <div className="mr-step-body">
              <Badge
                tone={m.diagnosis.final.confirmedAt ? "success" : "neutral"}
              >
                {m.diagnosis.final.confirmedAt
                  ? "현장 원인 확정"
                  : "원인 미확정"}
              </Badge>
              <fieldset className="mr-final-options" disabled={!editing}>
                <legend className="sr-only">최종 고장 원인 선택</legend>
                {m.original.aiCandidates.map((candidate) => (
                  <label key={candidate.id}>
                    <input
                      type="radio"
                      name="final-cause"
                      value={candidate.id}
                      checked={m.diagnosis.final.candidateId === candidate.id}
                      onChange={() => updateFinal("candidateId", candidate.id)}
                    />
                    {candidate.label}
                  </label>
                ))}
                <label>
                  <input
                    type="radio"
                    name="final-cause"
                    value="other"
                    checked={m.diagnosis.final.candidateId === "other"}
                    onChange={() => updateFinal("candidateId", "other")}
                  />
                  기타 (직접 입력)
                </label>
              </fieldset>
              {m.diagnosis.final.candidateId === "other" && (
                <ReportField
                  label="기타 고장 원인"
                  required
                  value={m.diagnosis.final.otherCause}
                  editing={editing}
                  onChange={(v) => updateFinal("otherCause", v)}
                  placeholder="현장에서 확인한 실제 원인을 입력하세요."
                />
              )}
              <ReportField
                label="최종 원인 확정 근거"
                required
                multiline
                value={m.diagnosis.final.rationale}
                editing={editing}
                onChange={(v) => updateFinal("rationale", v)}
                placeholder="어떤 현장 결과로 이 원인을 확인했나요?"
              />
              {errors.length > 0 && (
                <ul className="mr-validation" role="alert">
                  {errors.map((error) => (
                    <li key={error}>{error}</li>
                  ))}
                </ul>
              )}
              {editing && (
                <Button
                  variant={
                    m.diagnosis.final.confirmedAt ? "outline" : "default"
                  }
                  disabled={!!m.diagnosis.final.confirmedAt}
                  onClick={() => {
                    const validation = causeConfirmationErrors(m);
                    setErrors(validation);
                    if (!validation.length)
                      onChange({
                        ...m,
                        status: "review",
                        diagnosis: {
                          ...m.diagnosis,
                          final: {
                            ...m.diagnosis.final,
                            confirmedAt: new Date().toISOString(),
                          },
                        },
                      });
                  }}
                >
                  <ShieldCheck size={14} />
                  {m.diagnosis.final.confirmedAt ? "원인 확정됨" : "원인 확정"}
                </Button>
              )}
              {m.diagnosis.final.confirmedAt && (
                <div className="mr-confirmed-cause">
                  <Check size={15} />
                  <div>
                    <strong>{finalCause(m)}</strong>
                    <small>
                      {kstInput(m.diagnosis.final.confirmedAt).replace(
                        "T",
                        " ",
                      )}{" "}
                      KST 확인
                    </small>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </ReportSection>

      <ReportSection number={4} title="실제 수행 조치">
        <div className="mr-grid mr-grid-2 mr-action-grid">
          <div className="mr-subcard">
            <h3>
              <BookOpen size={16} /> 매뉴얼 권장 조치 <span>참고</span>
            </h3>
            {m.manuals.length ? (
              m.manuals.map((manual) => (
                <div className="mr-manual" key={manual.id}>
                  <strong>{manual.title}</strong>
                  <p className="small muted">
                    {manual.id} · {manual.revision || "개정판 미제공"} ·{" "}
                    {manual.section || "절·페이지 미연결"}
                  </p>
                  <p>
                    {manual.recommendation ||
                      "등록 매뉴얼 원문을 확인하세요. 권장 조치 본문은 아직 연결되지 않았습니다."}
                  </p>
                  <SourceLink href={manual.href}>원문 매뉴얼 열기</SourceLink>
                </div>
              ))
            ) : (
              <p className="mr-empty">
                등록된 매뉴얼 또는 검색 결과가 없습니다.
              </p>
            )}
            {!!actionNote && actionNote !== m.work.description && (
              <div className="mr-help-padded">
                <ReportField
                  label="이전 기록·채팅의 조치 참고 메모"
                  value={actionNote}
                  editing={false}
                  multiline
                />
              </div>
            )}
            <div className="mr-help mr-help-padded">
              권장 조치는 참고 자료입니다. 실제 수행 조치는 오른쪽에 직접
              기록합니다.
            </div>
          </div>
          <div className="mr-subcard">
            <h3>
              <Wrench size={16} /> 현장 실제 수행 조치 <span>작업자 입력</span>
              <Badge tone={m.work.description.trim() ? "success" : "neutral"}>
                {m.work.description.trim() ? "입력됨" : "미입력"}
              </Badge>
            </h3>
            <div className="mr-subcard-body">
              <p className="mr-linked-cause">
                연결 원인 ·{" "}
                {m.diagnosis.final.confirmedAt ? finalCause(m) : "원인 미확정"}
              </p>
              <div className="mr-grid mr-grid-2">
                <ReportField
                  label="작업오더 ID"
                  value={m.work.orderId}
                  editing={editing}
                  onChange={(v) => updateWork("orderId", v)}
                />
                <ReportField
                  label="작업자"
                  required
                  value={m.work.worker}
                  editing={editing}
                  onChange={(v) => updateWork("worker", v)}
                />
                <ReportField
                  label="작업 시작 시각 (KST)"
                  type="datetime-local"
                  value={kstInput(m.work.startedAt)}
                  editing={editing}
                  onChange={(v) => updateWork("startedAt", fromKstInput(v))}
                />
                <ReportField
                  label="작업 완료 시각 (KST)"
                  type="datetime-local"
                  value={kstInput(m.work.completedAt)}
                  editing={editing}
                  onChange={(v) => updateWork("completedAt", fromKstInput(v))}
                />
              </div>
              <ReportField
                label="실제 수행한 정비 내용"
                required
                multiline
                value={m.work.description}
                editing={editing}
                onChange={(v) => updateWork("description", v)}
                placeholder="실제로 수행한 작업과 확인한 결과만 입력하세요."
              />
              <ReportField
                label="교체 부품 및 수량"
                value={m.work.parts}
                editing={editing}
                onChange={(v) => updateWork("parts", v)}
                placeholder="부품명 / 수량 · 교체하지 않았다면 ‘없음’"
              />
            </div>
          </div>
        </div>
      </ReportSection>

      <ReportSection number={5} title="출처 및 기록 검토">
        <div className="mr-grid mr-grid-2">
          <ReportField
            label="참고 센서 데이터 및 CSV 구간"
            value={m.review.csvRange}
            editing={editing}
            onChange={(v) => updateReview("csvRange", v)}
            placeholder="데이터 식별자 / 시작·종료 구간"
          />
          <ReportField
            label="참고한 과거 정비 사례 ID"
            value={m.review.pastCaseIds}
            editing={editing}
            onChange={(v) => updateReview("pastCaseIds", v)}
          />
        </div>
        <div className="mr-grid mr-grid-3 mr-spaced">
          <ReportField
            label="기록자"
            required
            value={m.review.recorder}
            editing={editing}
            onChange={(v) => updateReview("recorder", v)}
          />
          <ReportField
            label="검토자"
            value={m.review.reviewer}
            editing={editing}
            onChange={(v) => updateReview("reviewer", v)}
          />
          <ReportField
            label="등록 시각 (KST)"
            value={kstInput(m.review.registeredAt).replace("T", " ")}
            editing={false}
          />
        </div>
        <div className="mr-review-state">
          <ClipboardCheck size={16} />
          <label>
            검토 상태{" "}
            <select
              aria-label="검토 상태"
              disabled={!editing}
              value={m.review.state}
              onChange={(e) => updateReview("state", e.target.value)}
            >
              <option value="pending">검토 대기</option>
              <option value="reviewing">검토 중</option>
              <option value="reviewed">검토 완료</option>
            </select>
          </label>
        </div>
        <div className="mr-source-list">
          <strong>
            <FileSearch size={15} /> 증거 및 문서 출처
          </strong>
          {m.diagnosis.inspections
            .filter((i) => i.evidenceId || i.evidenceUrl)
            .map((i) => (
              <div key={i.id}>
                <span>{i.evidenceId || "증거 ID 미입력"}</span>
                <SourceLink href={i.evidenceUrl}>현장 확인 자료</SourceLink>
              </div>
            ))}
          {m.manuals.map((manual) => (
            <div key={manual.id}>
              <span>{manual.id}</span>
              <SourceLink href={manual.href}>{manual.title}</SourceLink>
            </div>
          ))}
          {m.review.evidence.map((source, i) => (
            <div key={i} className="mr-evidence-entry">
              {editing ? (
                <>
                  <ReportField
                    label={`출처 ${i + 1} 증거 ID`}
                    value={source.id}
                    editing
                    onChange={(id) =>
                      updateReview(
                        "evidence",
                        m.review.evidence.map((s, n) =>
                          n === i ? { ...s, id } : s,
                        ),
                      )
                    }
                  />
                  <ReportField
                    label={`출처 ${i + 1} 제목`}
                    value={source.title}
                    editing
                    onChange={(title) =>
                      updateReview(
                        "evidence",
                        m.review.evidence.map((s, n) =>
                          n === i ? { ...s, title } : s,
                        ),
                      )
                    }
                  />
                  <ReportField
                    label={`출처 ${i + 1} URL`}
                    value={source.href}
                    editing
                    onChange={(href) =>
                      updateReview(
                        "evidence",
                        m.review.evidence.map((s, n) =>
                          n === i ? { ...s, href } : s,
                        ),
                      )
                    }
                  />
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`출처 ${i + 1} 삭제`}
                    onClick={() =>
                      updateReview(
                        "evidence",
                        m.review.evidence.filter((_, n) => n !== i),
                      )
                    }
                  >
                    <Trash2 size={13} />
                  </Button>
                </>
              ) : (
                <>
                  <span>{source.id || "ID 미입력"}</span>
                  <SourceLink href={source.href}>
                    {source.title || "참고 자료"}
                  </SourceLink>
                </>
              )}
            </div>
          ))}
          {editing && (
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                updateReview("evidence", [
                  ...m.review.evidence,
                  { id: "", title: "", href: "" },
                ])
              }
            >
              <Plus size={13} />
              출처 추가
            </Button>
          )}
          {!m.manuals.length &&
            !m.review.evidence.length &&
            !m.diagnosis.inspections.some(
              (i) => i.evidenceId || i.evidenceUrl,
            ) && (
              <p className="small muted">
                연결된 증거 파일이나 문서가 없습니다. 사진·문서는 URL로 연결할
                수 있습니다.
              </p>
            )}
        </div>
      </ReportSection>
      {m.revisions.length > 0 && (
        <details className="mr-revision-history">
          <summary>확정 후 수정 이력 · {m.revisions.length}건</summary>
          {m.revisions.map((revision, i) => {
            const old = JSON.parse(revision.snapshot) as MaintenanceReport;
            return (
              <div key={i}>
                <strong>
                  {kstInput(revision.at).replace("T", " ")} KST ·{" "}
                  {revision.reason}
                </strong>
                <p>이전 확정 원인: {finalCause(old) || "미확정"}</p>
                <p>이전 실제 조치: {old.work.description || "미입력"}</p>
                <p>
                  이전 확정 근거: {old.diagnosis.final.rationale || "미입력"}
                </p>
              </div>
            );
          })}
        </details>
      )}
    </div>
  );
}
