import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";
import { Plus, FileText, ArrowUpRight, FlaskConical } from "lucide-react";
import type { Hierarchy, Selection } from "../../features/hierarchy/index.ts";
import {
  reportsQuery,
  useReportDraftStore,
  type Report,
} from "../../features/reports/index.ts";
import { readBrowserReports } from "../../features/reports/api/reports.api.ts";
import {
  finalCause,
  reportStatusLabels,
} from "../../features/reports/model/maintenance-report.ts";
import { Card } from "../../shared/ui/card.tsx";
import { Button } from "../../shared/ui/button.tsx";
import { Badge } from "../../shared/ui/badge.tsx";
import { DateRangePicker } from "../../shared/ui/DateRangePicker.tsx";
import { DataTable } from "../../shared/ui/DataTable.tsx";
import {
  dateTime,
  dateOnly,
  defaultRange,
  validDateRange,
} from "../../shared/lib/date-time.ts";
import { ErrorState } from "../../shared/ui/ErrorState.tsx";
import { LoadingState } from "../../shared/ui/LoadingState.tsx";
import { errorMessage } from "../../shared/api/http-client.ts";
import { remoteApi } from "../../shared/api/be-adapter.ts";
import "../../features/reports/ui/maintenance-report.css";

export function ReportListPage({
  hierarchy,
  selection,
}: {
  hierarchy: Hierarchy;
  selection: Selection;
}) {
  const query = useQuery(reportsQuery);
  const drafts = useReportDraftStore((s) => s.drafts);
  const [params, setParams] = useSearchParams();
  const range = defaultRange();
  const from = params.get("from") ?? range.from;
  const to = params.get("to") ?? range.to;
  const merged = new Map<string, Report>(
    (query.data ?? []).map((r) => [r.id, r]),
  );
  if (remoteApi)
    for (const report of readBrowserReports()) merged.set(report.id, report);
  for (const d of Object.values(drafts)) {
    if (d.serverId) merged.delete(d.serverId);
    merged.set(d.id, {
      id: d.id,
      equipmentId: d.equipmentId,
      values: d.values,
      version: d.serverVersion,
      updatedAt: d.updatedAt,
    });
  }
  const data = [...merged.values()]
    .filter((r) => {
      const eq = hierarchy.equipment.find((e) => e.id === r.equipmentId);
      const date = dateOnly(r.updatedAt);
      return (
        (!selection.plantId || eq?.plantId === selection.plantId) &&
        (!selection.unitId || eq?.unitId === selection.unitId) &&
        (!selection.equipmentId || r.equipmentId === selection.equipmentId) &&
        date >= from &&
        date <= to
      );
    })
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  const selectionQuery = selection.equipmentId
    ? `equip_id=${encodeURIComponent(selection.equipmentId)}`
    : selection.unitId
      ? `unit_id=${encodeURIComponent(selection.unitId)}`
      : selection.plantId
        ? `plant_id=${encodeURIComponent(selection.plantId)}`
        : "";
  const href = (id: string) =>
    `/reports/${encodeURIComponent(id)}${selectionQuery ? `?${selectionQuery}` : ""}`;
  return (
    <div className="page maintenance-report-list">
      <div className="page-heading">
        <div>
          <div className="eyebrow">MAINTENANCE JOURNAL</div>
          <h1>정비 보고서</h1>
          <p>
            알람과 진단부터 현장 확인, 실제 정비까지 하나의 기록으로 관리하세요.
          </p>
        </div>
        {hierarchy.equipment.length > 0 && (
          <div className="inline mr-list-actions">
            <Button variant="outline" asChild>
              <Link to={`/reports/new?sample=1&${selectionQuery}`}>
                <FlaskConical size={14} />
                예시 보고서 열기
              </Link>
            </Button>
            <Button asChild>
              <Link to={`/reports/new?${selectionQuery}`}>
                <Plus size={15} />새 보고서
              </Link>
            </Button>
          </div>
        )}
      </div>
      <div className="report-tip">
        <FileText size={20} />
        <div>
          <strong>AI의 추정과 현장의 확정 결과를 구분해 기록합니다.</strong>
          <p>
            {remoteApi
              ? "확장 보고서는 이 브라우저에 저장됩니다. 서버 저장·공유 API는 아직 연결되지 않았습니다."
              : "프론트 예시 모드입니다. 작성 내용은 브라우저에 복구되고 임시 저장 시 Mock 저장소에 보관됩니다."}
          </p>
        </div>
      </div>
      <Card>
        <div className="filter-bar">
          <span className="small muted">최근 수정 일자</span>
          <DateRangePicker
            from={from}
            to={to}
            onChange={(f, t) => {
              const p = new URLSearchParams(params);
              p.set("from", f);
              p.set("to", t);
              setParams(p);
            }}
          />
        </div>
        {query.isError && (
          <ErrorState
            message={`${errorMessage(query.error)} · 브라우저에 남은 보고서는 계속 확인할 수 있습니다.`}
            retry={() => void query.refetch()}
          />
        )}
        {!validDateRange(from, to) ? (
          <ErrorState message="조회 기간을 확인하세요." />
        ) : query.isPending && !data.length ? (
          <LoadingState />
        ) : (
          <DataTable
            label="보고서 목록"
            data={data}
            columns={[
              {
                accessorKey: "values.title",
                header: "보고서 ID · 제목",
                cell: ({ row }) => (
                  <Link
                    className="equipment-link"
                    to={href(row.original.id)}
                    title={row.original.id}
                  >
                    {row.original.values.title || "제목 없는 보고서"}
                    <small>
                      {row.original.id.length > 12
                        ? `RPT-${row.original.id.slice(0, 8)}`
                        : row.original.id}
                      {row.original.values.maintenance?.original.kind ===
                      "example"
                        ? " · 예시"
                        : ""}
                    </small>
                  </Link>
                ),
              },
              {
                accessorKey: "equipmentId",
                header: "대상 설비",
                cell: ({ row }) => (
                  <span className="equipment-link">
                    {row.original.values.maintenance?.incident.equipmentName ||
                      hierarchy.equipment.find(
                        (e) => e.id === row.original.equipmentId,
                      )?.name ||
                      row.original.equipmentId}
                    <small>{row.original.equipmentId}</small>
                  </span>
                ),
              },
              {
                id: "alarm",
                header: "발생 알람",
                accessorFn: (r) =>
                  r.values.maintenance?.incident.alarmId || "미연결",
              },
              {
                id: "cause",
                header: "진단 · 최종 원인",
                cell: ({ row }) => {
                  const m = row.original.values.maintenance;
                  const confirmed = !!m?.diagnosis.final.confirmedAt;
                  return (
                    <span className="equipment-link">
                      {confirmed
                        ? finalCause(m!)
                        : m?.original.aiCandidates[0]?.label ||
                          row.original.values.cause ||
                          "원인 미확정"}
                      <small>
                        {confirmed
                          ? "현장 확정"
                          : m?.original.aiCandidates.length
                            ? "AI 1순위 · 현장 미확정"
                            : row.original.values.cause
                              ? "이전 보고서 기록 · 확정 여부 미확인"
                              : "현장 확인 필요"}
                      </small>
                    </span>
                  );
                },
              },
              {
                id: "status",
                header: "작성 상태",
                accessorFn: (r) => r.values.maintenance?.status ?? "draft",
                cell: ({ row }) => {
                  const status =
                    row.original.values.maintenance?.status ?? "draft";
                  return (
                    <Badge
                      tone={
                        status === "confirmed"
                          ? "success"
                          : status === "review"
                            ? "Medium"
                            : "neutral"
                      }
                    >
                      {reportStatusLabels[status]}
                    </Badge>
                  );
                },
              },
              {
                id: "createdAt",
                header: "작성일",
                accessorFn: (r) =>
                  r.values.maintenance?.createdAt ?? r.updatedAt,
                cell: ({ getValue }) => (
                  <span className="small mono">
                    {dateTime(String(getValue()))}
                  </span>
                ),
              },
              {
                id: "open",
                header: "",
                cell: ({ row }) => (
                  <Link
                    aria-label={`${row.original.values.title || "보고서"} 열기`}
                    to={href(row.original.id)}
                  >
                    <ArrowUpRight size={16} />
                  </Link>
                ),
              },
            ]}
          />
        )}
      </Card>
    </div>
  );
}
