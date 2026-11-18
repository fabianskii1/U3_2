import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams, Link } from "react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Check,
  CloudUpload,
  LoaderCircle,
  Save,
  FileText,
} from "lucide-react";
import { toast } from "sonner";
import * as Dialog from "@radix-ui/react-dialog";
import type { Hierarchy, Selection } from "../../features/hierarchy/index.ts";
import {
  useReportDraftStore,
  reportQuery,
  flushReport,
  ReportForm,
  type Report,
} from "../../features/reports/index.ts";
import { Card, CardHeader } from "../../shared/ui/card.tsx";
import { Button } from "../../shared/ui/button.tsx";
import { Badge } from "../../shared/ui/badge.tsx";
import { LoadingState } from "../../shared/ui/LoadingState.tsx";
import { ErrorState } from "../../shared/ui/ErrorState.tsx";
import { errorMessage } from "../../shared/api/http-client.ts";
export function NewReportPage({
  hierarchy,
  selection,
}: {
  hierarchy: Hierarchy;
  selection: Selection;
}) {
  const navigate = useNavigate();
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const eq =
      hierarchy.equipment.find((e) => e.id === selection.equipmentId) ??
      hierarchy.equipment[0];
    const id = useReportDraftStore
      .getState()
      .createDraft(eq.id, { title: `${eq.name} 점검 보고서` });
    navigate(`/reports/${id}`, { replace: true });
  }, [hierarchy, selection, navigate]);
  return <LoadingState />;
}
export function ReportEditorPage({ hierarchy }: { hierarchy: Hierarchy }) {
  const { reportId = "" } = useParams();
  const local = useReportDraftStore((s) => s.drafts[reportId]);
  const activate = useReportDraftStore((s) => s.activate);
  const open = useReportDraftStore((s) => s.openReport);
  const query = useQuery({ ...reportQuery(reportId), enabled: !local });
  useEffect(() => {
    if (local) activate(reportId);
    else if (query.data) open(query.data);
  }, [reportId, local, activate, open, query.data]);
  if (local)
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
  const client = useQueryClient();
  const [server, setServer] = useState<Report | null>(null);
  const [compare, setCompare] = useState(false);
  const [fetching, setFetching] = useState(false);
  const eq = hierarchy.equipment.find((e) => e.id === d.equipmentId);
  const dirty = d.localRevision !== d.savedRevision;
  const state =
    d.saveStatus === "saving"
      ? "저장 중"
      : d.saveStatus === "error"
        ? "저장 실패"
        : d.saveStatus === "conflict"
          ? "버전 충돌"
          : dirty
            ? "저장 대기"
            : "모든 변경 저장됨";
  const save = async () => {
    try {
      await flushReport(id, client);
      toast.success("보고서가 저장되었습니다.");
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };
  const compareServer = async () => {
    setFetching(true);
    try {
      const report = await client.fetchQuery({
        ...reportQuery(d.serverId ?? id),
        staleTime: 0,
      });
      setServer(report);
      setCompare(true);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setFetching(false);
    }
  };
  return (
    <div className="page report-editor">
      <Link className="back-link" to="/reports">
        <ArrowLeft size={14} />
        보고서 목록
      </Link>
      <div className="page-heading">
        <div>
          <div className="eyebrow">REPORT EDITOR</div>
          <h1>보고서 작성</h1>
          <p>
            {eq?.name ?? d.equipmentId} · {d.equipmentId} · 초안
          </p>
        </div>
        <Button
          onClick={() => void save()}
          disabled={d.saveStatus === "saving" || d.saveStatus === "conflict"}
        >
          <Save size={15} />
          지금 저장
        </Button>
      </div>
      <div className="save-banner" role="status">
        {d.saveStatus === "saving" ? (
          <LoaderCircle size={16} className="spin" />
        ) : dirty ? (
          <CloudUpload size={16} />
        ) : (
          <Check size={16} />
        )}
        <strong data-testid="save-status">{state}</strong>
        <span>브라우저 복구본 · 자동 저장</span>
        <Badge>v{d.serverVersion}</Badge>
      </div>
      {d.error ? (
        <ErrorState
          message={d.error}
          retry={
            d.saveStatus === "conflict"
              ? () => void compareServer()
              : () => void save()
          }
        />
      ) : null}
      {fetching ? <p role="status">서버 보고서를 불러오는 중…</p> : null}
      <Card>
        <CardHeader
          title="점검 및 진단 내용"
          description="화면 입력과 채팅 수정은 같은 초안에 반영됩니다."
          action={<FileText size={18} className="muted" />}
        />
        <ReportForm id={id} />
      </Card>
      <p className="small muted">
        추정 원인과 권장 조치는 현장 확인 후 보완하세요. 보고서 저장은 설비
        운전이나 설정값을 변경하지 않습니다.
      </p>
      <Dialog.Root open={compare} onOpenChange={setCompare}>
        <Dialog.Portal>
          <Dialog.Overlay className="dialog-overlay" />
          <Dialog.Content className="dialog-content">
            <Dialog.Title>서버 보고서와 편집본 비교</Dialog.Title>
            <Dialog.Description>
              다른 편집본이 먼저 저장되었습니다. 아래 내용을 비교한 뒤 사용할
              버전을 선택하세요.
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
