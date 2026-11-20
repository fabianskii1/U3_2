import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams, Link } from "react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Check,
  FileCheck2,
  FileText,
  History,
  LoaderCircle,
  Pencil,
  Save,
  ShieldCheck,
  X,
} from "lucide-react";
import { toast } from "sonner";
import * as Dialog from "@radix-ui/react-dialog";
import type { Hierarchy, Selection } from "../../features/hierarchy/index.ts";
import {
  useReportDraftStore,
  reportQuery,
  flushReport,
  type Report,
} from "../../features/reports/index.ts";
import {
  incidentQuery,
  incidentDraftQuery,
} from "../../features/incidents/api/incidents.queries.ts";
import { incidentReportFields } from "../../features/reports/model/incident-report.ts";
import {
  incidentOperatingQuery,
  incidentReferenceTime,
} from "../../features/reports/api/incident-operating.api.ts";
import { alarmsQuery } from "../../features/alarms/index.ts";
import { Button } from "../../shared/ui/button.tsx";
import { Badge } from "../../shared/ui/badge.tsx";
import { LoadingState } from "../../shared/ui/LoadingState.tsx";
import { ErrorState } from "../../shared/ui/ErrorState.tsx";
import { errorMessage } from "../../shared/api/http-client.ts";
import { remoteApi } from "../../shared/api/be-adapter.ts";
import { MaintenanceReportForm } from "../../features/reports/ui/MaintenanceReportForm.tsx";
import {
  createExample,
  createMaintenance,
  finalCause,
  reportConfirmationErrors,
  reportStatusLabels,
} from "../../features/reports/model/maintenance-report.ts";
import {
  applyReportReferences,
  reportReferencesQuery,
} from "../../features/reports/api/report-references.api.ts";
import type { MaintenanceReport } from "../../shared/api/contracts/maintenance-report.ts";
import "../../features/reports/ui/maintenance-report.css";

export function NewReportPage(props: {
  hierarchy: Hierarchy;
  selection: Selection;
}) {
  const [params] = useSearchParams();
  const incidentId = params.get("incident_id");
  return incidentId ? (
    <NewIncidentReportPage
      hierarchy={props.hierarchy}
      incidentId={incidentId}
    />
  ) : (
    <NewEquipmentReportPage {...props} />
  );
}

function NewIncidentReportPage({
  hierarchy,
  incidentId,
}: {
  hierarchy: Hierarchy;
  incidentId: string;
}) {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const started = useRef(false);
  const [creationError, setCreationError] = useState("");
  const incident = useQuery(
    incidentQuery(incidentId, params.get("as_of") ?? undefined),
  );
  const draft = useQuery(incidentDraftQuery(incidentId));
  const equipment = hierarchy.equipment.find(
    (asset) => asset.id === incident.data?.equipment_id,
  );
  const references = useQuery(
    reportReferencesQuery(
      equipment?.id ?? "",
      incident.data ? incidentReferenceTime(incident.data) : undefined,
    ),
  );
  const operating = useQuery(incidentOperatingQuery(incident.data, equipment));
  useEffect(() => {
    if (
      started.current ||
      !incident.data ||
      !draft.data ||
      !equipment ||
      operating.isPending ||
      (remoteApi && references.isPending)
    )
      return;
    try {
      const { maintenance, ...values } = incidentReportFields(
        incident.data,
        draft.data,
        equipment,
        references.data,
        operating.data,
      );
      started.current = true;
      const store = useReportDraftStore.getState();
      const id = store.createDraft(equipment.id, values);
      store.initializeMaintenance(id, maintenance);
      void navigate(
        `/reports/${id}?edit=1&equip_id=${encodeURIComponent(equipment.id)}`,
        { replace: true },
      );
    } catch (error) {
      setCreationError(errorMessage(error));
    }
  }, [
    incident.data,
    draft.data,
    equipment,
    references.isPending,
    references.data,
    operating.isPending,
    operating.data,
    navigate,
  ]);
  const error = incident.error ?? draft.error;
  if (error || creationError)
    return (
      <div className="page">
        <ErrorState
          message={creationError || errorMessage(error)}
          retry={() => {
            void incident.refetch();
            void draft.refetch();
          }}
        />
        <Button asChild variant="outline">
          <Link to={`/incidents/${encodeURIComponent(incidentId)}`}>
            사건 상세로 돌아가기
          </Link>
        </Button>
      </div>
    );
  if (incident.data && !equipment)
    return <ErrorState message="사건에 연결된 설비를 찾지 못했습니다." />;
  return <LoadingState />;
}

function NewEquipmentReportPage({
  hierarchy,
  selection,
}: {
  hierarchy: Hierarchy;
  selection: Selection;
}) {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const started = useRef(false);
  const sample = params.get("sample") === "1";
  const equipment =
    hierarchy.equipment.find((e) => e.id === selection.equipmentId) ??
    hierarchy.equipment[0];
  const alarms = useQuery({ ...alarmsQuery, enabled: !sample });
  const references = useQuery(
    reportReferencesQuery(sample ? "" : (equipment?.id ?? "")),
  );
  useEffect(() => {
    if (
      started.current ||
      !equipment ||
      (!sample && alarms.isPending) ||
      (remoteApi && !sample && references.isPending)
    )
      return;
    started.current = true;
    const store = useReportDraftStore.getState();
    const id = store.createDraft(equipment.id, {
      title: sample
        ? "CDU 펌프 정비 보고서 (예시)"
        : `${equipment.name} 정비 보고서`,
    });
    const draft = useReportDraftStore.getState().drafts[id];
    const report: Report = {
      id,
      equipmentId: equipment.id,
      values: draft.values,
      version: 0,
      updatedAt: draft.updatedAt,
    };
    const alarm = alarms.data?.alarms
      .filter(
        (a) =>
          a.equipmentId === equipment.id &&
          (!params.get("alarm_id") || a.id === params.get("alarm_id")),
      )
      .sort((a, b) => b.occurredAt.localeCompare(a.occurredAt))[0];
    const model = sample
      ? createExample(report, equipment)
      : applyReportReferences(
          createMaintenance(report, equipment, alarm),
          references.data,
        );
    store.initializeMaintenance(id, model);
    navigate(
      `/reports/${id}?${sample ? "" : "edit=1&"}equip_id=${encodeURIComponent(equipment.id)}`,
      { replace: true },
    );
  }, [
    equipment,
    alarms.isPending,
    alarms.data,
    references.isPending,
    references.data,
    navigate,
    params,
    sample,
  ]);
  if (!equipment)
    return <ErrorState message="보고서를 작성할 설비가 없습니다." />;
  return <LoadingState />;
}
export function ReportEditorPage({ hierarchy }: { hierarchy: Hierarchy }) {
  const { reportId = "" } = useParams();
  const local = useReportDraftStore((s) => s.drafts[reportId]);
  const query = useQuery({ ...reportQuery(reportId), enabled: !local });
  const activate = useReportDraftStore((s) => s.activate);
  const open = useReportDraftStore((s) => s.openReport);
  const source = local ?? query.data;
  const references = useQuery({
    ...reportReferencesQuery(source?.equipmentId ?? ""),
    enabled: remoteApi && !!source && !source.values.maintenance,
  });
  useEffect(() => {
    if (local) activate(reportId);
    else if (query.data) open(query.data);
  }, [reportId, local, activate, open, query.data]);
  useEffect(() => {
    if (
      !local ||
      local.values.maintenance ||
      (remoteApi && references.isPending)
    )
      return;
    const equipment = hierarchy.equipment.find(
      (e) => e.id === local.equipmentId,
    );
    useReportDraftStore.getState().initializeMaintenance(
      reportId,
      applyReportReferences(
        createMaintenance(
          {
            id: local.id,
            equipmentId: local.equipmentId,
            values: local.values,
            version: local.serverVersion,
            updatedAt: local.updatedAt,
          },
          equipment,
        ),
        references.data,
      ),
    );
  }, [local, reportId, hierarchy, references.isPending, references.data]);
  if (local?.values.maintenance)
    return <EditorContent key={reportId} id={reportId} hierarchy={hierarchy} />;
  if (query.isError)
    return (
      <div className="page">
        <ErrorState
          message={errorMessage(query.error)}
          retry={() => void query.refetch()}
        />
        <Button asChild variant="outline">
          <Link to="/reports">보고서 목록으로</Link>
        </Button>
      </div>
    );
  return <LoadingState />;
}
function EditorContent({
  id,
  hierarchy,
}: {
  id: string;
  hierarchy: Hierarchy;
}) {
  const d = useReportDraftStore((s) => s.drafts[id]);
  const m = d.values.maintenance!;
  const client = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [editing, setEditing] = useState(
    params.get("edit") === "1" && m.status !== "confirmed",
  );
  const [errors, setErrors] = useState<string[]>([]);
  const [reopen, setReopen] = useState(false);
  const [reason, setReason] = useState("");
  const [server, setServer] = useState<Report | null>(null);
  const [compare, setCompare] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [storageError, setStorageError] = useState(false);
  const equipment = hierarchy.equipment.find((e) => e.id === d.equipmentId);
  const dirty = d.localRevision !== d.savedRevision;
  const saving = d.saveStatus === "saving";
  const label = saving
    ? "저장 중"
    : d.saveStatus === "conflict"
      ? "버전 충돌"
      : d.saveStatus === "error"
        ? "저장 실패"
        : dirty
          ? "미저장 변경 있음"
          : "모든 변경 저장됨";
  useEffect(() => {
    const failed = () => setStorageError(true);
    window.addEventListener("draft-storage-error", failed);
    return () => window.removeEventListener("draft-storage-error", failed);
  }, []);
  const leaveEdit = () => {
    setEditing(false);
    const p = new URLSearchParams(params);
    p.delete("edit");
    setParams(p, { replace: true });
  };
  const change = (model: MaintenanceReport) => {
    if (!editing || saving || m.status === "confirmed") return;
    setErrors([]);
    useReportDraftStore.getState().patch(id, {
      maintenance: model,
      symptom: model.observations.symptoms,
      cause: model.diagnosis.final.confirmedAt
        ? finalCause(model)
        : d.values.cause,
      action: model.work.description,
    });
  };
  const save = async (confirm = false) => {
    const current =
      useReportDraftStore.getState().drafts[id].values.maintenance!;
    if (confirm) {
      const validation = reportConfirmationErrors(current);
      setErrors(validation);
      if (validation.length) {
        setConfirming(false);
        return;
      }
    }
    try {
      if (confirm)
        useReportDraftStore.getState().patch(id, {
          maintenance: {
            ...current,
            status: "confirmed",
            confirmedAt: new Date().toISOString(),
          },
          cause: finalCause(current),
        });
      localStorage.setItem("skadi-storage-check", "ok");
      localStorage.removeItem("skadi-storage-check");
      await flushReport(id, client);
      setStorageError(false);
      setConfirming(false);
      leaveEdit();
      toast.success(
        remoteApi
          ? confirm
            ? "보고서를 이 브라우저에 확정 저장했습니다."
            : "보고서를 이 브라우저에 임시 저장했습니다."
          : "보고서를 Mock 저장소에 저장했습니다.",
      );
    } catch (error) {
      if (confirm) {
        const state = useReportDraftStore.getState();
        const draft = state.drafts[id];
        useReportDraftStore.setState({
          drafts: {
            ...state.drafts,
            [id]: {
              ...draft,
              values: { ...draft.values, maintenance: current },
            },
          },
        });
      }
      setConfirming(false);
      toast.error(errorMessage(error));
    }
  };
  const compareServer = async () => {
    try {
      setServer(
        await client.fetchQuery({
          ...reportQuery(d.serverId ?? id),
          staleTime: 0,
        }),
      );
      setCompare(true);
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };
  return (
    <div className="page maintenance-report">
      <Link
        className="back-link"
        to={`/reports${equipment ? `?equip_id=${encodeURIComponent(equipment.id)}` : ""}`}
      >
        <ArrowLeft size={14} /> 보고서 목록 <span>/</span> 정비 보고서 상세
      </Link>
      <header className="mr-page-heading">
        <div className="mr-heading-title">
          <div className="mr-document-icon">
            <FileCheck2 size={26} />
          </div>
          <div>
            <div className="eyebrow">MAINTENANCE REPORT</div>
            <h1>{d.values.title || "CDU 펌프 정비 보고서"}</h1>
            <p>
              설비 알람과 현장 확인, 최종 원인 및 실제 수행 조치를 기록합니다.
            </p>
          </div>
        </div>
        <div className="mr-toolbar">
          <Badge
            tone={
              m.status === "confirmed"
                ? "success"
                : m.status === "review"
                  ? "Medium"
                  : "neutral"
            }
          >
            <span className="mr-status-dot" />
            {reportStatusLabels[m.status]}
          </Badge>
          {editing ? (
            <>
              <Button
                variant="outline"
                disabled={saving}
                onClick={() => {
                  useReportDraftStore.getState().restoreSaved(id);
                  setErrors([]);
                  leaveEdit();
                }}
              >
                <X size={14} />
                취소
              </Button>
              <Button
                variant="outline"
                disabled={saving}
                onClick={() => void save()}
              >
                <Save size={14} />
                임시 저장
              </Button>
              <Button
                disabled={saving}
                onClick={() => {
                  const validation = reportConfirmationErrors(m);
                  setErrors(validation);
                  if (!validation.length) setConfirming(true);
                }}
              >
                <ShieldCheck size={14} />
                보고서 확정
              </Button>
            </>
          ) : (
            <Button
              variant="outline"
              onClick={() => {
                if (m.status === "confirmed") setReopen(true);
                else setEditing(true);
              }}
            >
              <Pencil size={14} />
              수정
            </Button>
          )}
        </div>
      </header>
      <div className="mr-storage-banner" role="status">
        {saving ? (
          <LoaderCircle size={14} className="spin" />
        ) : (
          <Check size={14} />
        )}
        <strong data-testid="save-status">{label}</strong>
        <span>
          {remoteApi
            ? "이 브라우저에 저장 · 서버 저장 API 미연결"
            : "프론트 예시 모드 · Mock 저장소"}
        </span>
        <span>v{d.serverVersion}</span>
      </div>
      {m.original.kind === "example" && (
        <div className="mr-example-banner">
          <strong>프론트 예시 보고서</strong>
          <span>
            알람·AI 순위·센서 그래프는 합성 데이터입니다. 현장 점검과 실제
            조치는 직접 입력합니다.
          </span>
        </div>
      )}
      {m.original.kind !== "example" && (
        <div className="mr-connection-note">
          <FileText size={14} />
          {m.original.incident ? (
            <div>
              <strong>
                사건 {m.original.incident.incident_id}에서 가져온 보고서
              </strong>
              <p>{d.values.risk}</p>
              <Link
                to={`/incidents/${encodeURIComponent(m.original.incident.incident_id)}`}
              >
                원본 사건 보기
              </Link>
            </div>
          ) : (
            <>
              등록 알람·설비·매뉴얼은 연결 가능한 데이터를 사용합니다. AI 원인
              후보와 매뉴얼 권장 조치 본문은 아직 연결되지 않았습니다.
            </>
          )}
        </div>
      )}
      {!!m.original.referenceNotes?.length && (
        <ErrorState message={m.original.referenceNotes.join(" · ")} />
      )}
      {storageError && (
        <ErrorState message="브라우저 저장 공간에 기록하지 못했습니다. 입력 내용을 복사하여 보관한 뒤 저장을 다시 시도해 주세요." />
      )}
      {d.error && (
        <ErrorState
          message={d.error}
          retry={
            d.saveStatus === "conflict"
              ? () => void compareServer()
              : () => void save()
          }
        />
      )}
      {errors.length > 0 && (
        <div className="mr-errors" role="alert">
          <strong>확정하려면 아래 내용을 확인하세요.</strong>
          <ul>
            {errors.map((error) => (
              <li key={error}>{error}</li>
            ))}
          </ul>
        </div>
      )}
      {editing && (
        <div className="mr-title-field">
          <label htmlFor="mr-title">보고서 제목</label>
          <input
            id="mr-title"
            value={d.values.title}
            maxLength={200}
            onChange={(e) =>
              useReportDraftStore
                .getState()
                .patch(id, { title: e.target.value })
            }
          />
        </div>
      )}
      <fieldset className="mr-edit-fieldset" disabled={saving}>
        <MaintenanceReportForm
          reportId={id}
          model={m}
          equipment={equipment}
          equipmentId={d.equipmentId}
          causeNote={d.values.cause}
          actionNote={d.values.action}
          editing={editing && !saving}
          onChange={change}
        />
      </fieldset>
      <footer className="mr-footer">
        <History size={14} />
        <span>
          AI 초기 분석과 최초 알람은 별도 보존됩니다. 확정 후 수정 시 사유와
          이전 확정 내용을 기록합니다.
        </span>
      </footer>
      <Dialog.Root open={reopen} onOpenChange={setReopen}>
        <Dialog.Portal>
          <Dialog.Overlay className="dialog-overlay" />
          <Dialog.Content className="dialog-content mr-dialog">
            <Dialog.Title>확정 보고서 수정</Dialog.Title>
            <Dialog.Description>
              수정 사유와 이전 확정 내용을 이력에 남깁니다. 수정 후 원인 확인과
              보고서 확정이 다시 필요합니다.
            </Dialog.Description>
            <label className="mr-field">
              <span>수정 사유</span>
              <textarea
                aria-label="수정 사유"
                className="textarea"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </label>
            <div className="mr-dialog-actions">
              <Dialog.Close asChild>
                <Button variant="outline">취소</Button>
              </Dialog.Close>
              <Button
                disabled={!reason.trim()}
                onClick={() => {
                  useReportDraftStore.getState().reopen(id, reason);
                  setReopen(false);
                  setReason("");
                  setEditing(true);
                }}
              >
                수정 시작
              </Button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
      <Dialog.Root open={confirming} onOpenChange={setConfirming}>
        <Dialog.Portal>
          <Dialog.Overlay className="dialog-overlay" />
          <Dialog.Content className="dialog-content mr-dialog">
            <Dialog.Title>정비 보고서를 확정할까요?</Dialog.Title>
            <Dialog.Description>
              현장 확인 근거와 실제 수행 조치를 검토했습니다. 확정 후 수정할
              때는 수정 사유를 기록해야 합니다.
            </Dialog.Description>
            <div className="mr-confirm-summary">
              <strong>최종 원인 · {finalCause(m)}</strong>
              <p>작업자 · {m.work.worker}</p>
              <p>{m.work.description}</p>
              <small>
                {remoteApi
                  ? "이 브라우저에 확정 상태를 저장합니다. 서버에는 저장되지 않습니다."
                  : "프론트 Mock 저장소에 확정 상태를 저장합니다."}
              </small>
            </div>
            <div className="mr-dialog-actions">
              <Dialog.Close asChild>
                <Button variant="outline">돌아가기</Button>
              </Dialog.Close>
              <Button disabled={saving} onClick={() => void save(true)}>
                확정 저장
              </Button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
      <Dialog.Root open={compare} onOpenChange={setCompare}>
        <Dialog.Portal>
          <Dialog.Overlay className="dialog-overlay" />
          <Dialog.Content className="dialog-content">
            <Dialog.Title>서버 보고서와 편집본 비교</Dialog.Title>
            <Dialog.Description>
              다른 편집본이 먼저 저장되었습니다. 사용할 버전을 선택하세요.
            </Dialog.Description>
            <div className="compare-grid">
              <div>
                <h3>현재 편집본</h3>
                <pre>{JSON.stringify(d.values, null, 2)}</pre>
              </div>
              <div>
                <h3>서버 저장본 v{server?.version}</h3>
                <pre>{JSON.stringify(server?.values, null, 2)}</pre>
              </div>
            </div>
            <div className="inline">
              <Button
                variant="outline"
                onClick={() => {
                  if (server)
                    useReportDraftStore.getState().replaceFromServer(server);
                  setCompare(false);
                }}
              >
                서버 내용 사용
              </Button>
              <Button
                onClick={() => {
                  if (server)
                    useReportDraftStore.getState().rebase(id, server.version);
                  setCompare(false);
                }}
              >
                내 편집본으로 다시 저장
              </Button>
              <Dialog.Close asChild>
                <Button variant="ghost">나중에</Button>
              </Dialog.Close>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
