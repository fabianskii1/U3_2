import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router";
import { Plus, FileText, ArrowUpRight } from "lucide-react";
import type { Hierarchy, Selection } from "../../features/hierarchy/index.ts";
import {
  reportsQuery,
  useReportDraftStore,
} from "../../features/reports/index.ts";
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
import { errorMessage } from "../../shared/api/http-client.ts";
import { remoteApi } from "../../shared/api/be-adapter.ts";
export function ReportListPage({
  hierarchy,
  selection,
}: {
  hierarchy: Hierarchy;
  selection: Selection;
}) {
  const query = useQuery(reportsQuery);
  const drafts = useReportDraftStore((s) => s.drafts);
  const create = useReportDraftStore((s) => s.createDraft);
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const range = defaultRange();
  const from = params.get("from") ?? range.from;
  const to = params.get("to") ?? range.to;
  const merged = new Map(
    (query.data ?? []).map((r) => [r.id, { ...r, status: "서버 저장됨" }]),
  );
  for (const d of remoteApi ? [] : Object.values(drafts)) {
    if (d.serverId) merged.delete(d.serverId);
    merged.set(d.id, {
      id: d.id,
      equipmentId: d.equipmentId,
      values: d.values,
      version: d.serverVersion,
      updatedAt: d.updatedAt,
      status:
        d.saveStatus === "conflict"
          ? "충돌"
          : d.saveStatus === "error"
            ? "저장 실패"
            : d.localRevision !== d.savedRevision
              ? "편집 중"
              : "저장됨",
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
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">MAINTENANCE JOURNAL</div>
          <h1>진단 보고서</h1>
          <p>현장의 기록과 분석을 하나의 보고서로 관리하세요.</p>
        </div>
        {!remoteApi && hierarchy.equipment.length > 0 && (
          <Button
            onClick={() => {
              const eq =
                hierarchy.equipment.find(
                  (e) => e.id === selection.equipmentId,
                ) ?? hierarchy.equipment[0];
              const id = create(eq.id, { title: `${eq.name} 점검 보고서` });
              navigate(`/reports/${id}`);
            }}
          >
            <Plus size={15} />새 보고서
          </Button>
        )}
      </div>
      {!remoteApi && (
        <div className="report-tip">
          <FileText size={18} />
          <div>
            <strong>이동해도, 닫아도 작성 내용은 유지됩니다.</strong>
            <p>초안은 브라우저에 즉시 보관되고 Mock 서버에 자동 저장됩니다.</p>
          </div>
        </div>
      )}
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
        {query.isError ? (
          <ErrorState
            message={errorMessage(query.error)}
            retry={() => void query.refetch()}
          />
        ) : null}
        {!validDateRange(from, to) ? (
          <ErrorState message="조회 기간을 확인하세요." />
        ) : (
          <DataTable
            label="보고서 목록"
            data={data}
            columns={[
              {
                accessorKey: "values.title",
                header: "보고서",
                cell: ({ row }) => (
                  <Link
                    className="equipment-link"
                    to={`/reports/${row.original.id}`}
                  >
                    {row.original.values.title || "제목 없는 보고서"}
                    <small>{row.original.id.slice(0, 8)}</small>
                  </Link>
                ),
              },
              {
                accessorKey: "equipmentId",
                header: "대상 설비",
                cell: ({ row }) => (
                  <span>
                    {hierarchy.equipment.find(
                      (e) => e.id === row.original.equipmentId,
                    )?.name ?? row.original.equipmentId}
                  </span>
                ),
              },
              {
                accessorKey: "status",
                header: "상태",
                cell: ({ row }) => (
                  <Badge
                    tone={
                      row.original.status === "충돌" ||
                      row.original.status === "저장 실패"
                        ? "High"
                        : "neutral"
                    }
                  >
                    {row.original.status}
                  </Badge>
                ),
              },
              {
                accessorKey: "updatedAt",
                header: "최근 수정",
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
                    aria-label="보고서 열기"
                    to={`/reports/${row.original.id}`}
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
