import { useRef, useState } from "react";
import type { ReactNode } from "react";
import { Link, useLocation } from "react-router";
import {
  House,
  GripVertical,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightOpen,
  PanelRightClose,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import {
  HierarchyNavigation,
  HierarchyFilters,
  useHierarchyUiStore,
  type Hierarchy,
  type Selection,
} from "../../features/hierarchy/index.ts";
import { ChatPanel, useChatUiStore } from "../../features/chat/index.ts";
import { useReportDraftStore } from "../../features/reports/index.ts";
import { Button } from "../../shared/ui/button.tsx";
import { Header } from "./Header.tsx";
import { alarmsQuery } from "../../features/alarms/index.ts";
import { equipmentQuery } from "../../features/equipment/api/equipment.queries.ts";
import { remoteApi } from "../../shared/api/be-adapter.ts";
import { buildChatContext } from "../integrations/chat-context.ts";
import { handleChatAction } from "../integrations/chat-action-handler.ts";
import { useNavigate } from "react-router";
import { dateTime } from "../../shared/lib/date-time.ts";
export function AppLayout({
  hierarchy,
  selection,
  onSelect,
  children,
}: {
  hierarchy: Hierarchy;
  selection: Selection;
  onSelect: (s: Selection) => void;
  children: ReactNode;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const hierarchyOpen = useHierarchyUiStore((state) => state.open);
  const toggleHierarchy = useHierarchyUiStore((state) => state.toggle);
  const open = useChatUiStore((s) => s.open);
  const toggleChat = useChatUiStore((s) => s.toggle);
  const width = useChatUiStore((s) => s.width);
  const setWidth = useChatUiStore((s) => s.setWidth);
  const drag = useRef<{ x: number; width: number } | null>(null);
  const [dragging, setDragging] = useState(false);
  const active = useReportDraftStore((s) => s.activeReportId);
  const reportTitle = useReportDraftStore((s) =>
    active ? s.drafts[active]?.values.title : undefined,
  );
  const alarms = useQuery(alarmsQuery);
  const watchingEquipment =
    remoteApi && location.pathname === "/equip" && !!selection.equipmentId;
  const equipment = useQuery({
    ...equipmentQuery(selection.equipmentId ?? ""),
    enabled: watchingEquipment,
    refetchInterval: false,
  });
  const syncError = watchingEquipment ? equipment.isError : alarms.isError;
  const syncedAt = watchingEquipment
    ? equipment.dataUpdatedAt
    : alarms.dataUpdatedAt;
  return (
    <div className={`app-shell ${dragging ? "resizing" : ""}`}>
      <Header />
      <div className="workspace">
        <HierarchyNavigation
          hidden={!hierarchyOpen}
          data={hierarchy}
          selection={selection}
          onSelect={onSelect}
        />
        <main className="work-area">
          <div className="context-bar">
            <div className="context-controls">
              <Button
                variant="ghost"
                size="icon"
                aria-label={hierarchyOpen ? "설비 탐색 닫기" : "설비 탐색 열기"}
                title={hierarchyOpen ? "설비 탐색 닫기" : "설비 탐색 열기"}
                aria-expanded={hierarchyOpen}
                aria-controls="hierarchy-panel"
                onClick={toggleHierarchy}
              >
                {hierarchyOpen ? (
                  <PanelLeftClose size={17} />
                ) : (
                  <PanelLeftOpen size={17} />
                )}
              </Button>

              <Link
                className="context-home"
                to="/dashboard"
                aria-label="대시보드 홈"
              >
                <House size={14} />
              </Link>
              <HierarchyFilters
                data={hierarchy}
                selection={selection}
                onSelect={onSelect}
              />
            </div>
            <div
              className={`sync-status ${syncError ? "sync-error" : ""}`}
            >
              <span className="status-dot" />
              {syncError
                ? "연결 오류 · 마지막 데이터 표시"
                : syncedAt
                  ? `${dateTime(new Date(syncedAt).toISOString())} 갱신`
                  : "연결 중"}
            </div>
            <Button
              className="context-chat-toggle"
              variant="ghost"
              size="icon"
              aria-label={open ? "채팅 닫기" : "채팅 열기"}
              title={open ? "채팅 닫기" : "채팅 열기"}
              aria-expanded={open}
              aria-controls="chat-panel"
              onClick={toggleChat}
            >
              {open ? (
                <PanelRightClose size={17} />
              ) : (
                <PanelRightOpen size={17} />
              )}
            </Button>
          </div>
          <div className="page-scroll">{children}</div>
          <footer className="app-footer">
            <span>SKADI / 회전기계설비 모니터링</span>
            <span>
              표시 시간대 KST · {remoteApi ? "BE WORKSPACE" : "DEMO WORKSPACE"}
            </span>
          </footer>
        </main>
        <aside
          id="chat-panel"
          className={`chat-panel ${open ? "" : "chat-hidden"}`}
          style={{ width: open ? width : 0 }}
          aria-label="AI 대화 패널"
          aria-hidden={!open}
          inert={!open}
        >
          <div
            className="resize-handle"
            role="separator"
            aria-label="채팅 패널 너비"
            aria-orientation="vertical"
            aria-valuemin={200}
            aria-valuemax={520}
            aria-valuenow={width}
            tabIndex={open ? 0 : -1}
            onKeyDown={(e) => {
              if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
                e.preventDefault();
                setWidth(width + (e.key === "ArrowLeft" ? 20 : -20));
              }
            }}
            onPointerDown={(e) => {
              e.currentTarget.setPointerCapture(e.pointerId);
              drag.current = { x: e.clientX, width };
              setDragging(true);
            }}
            onPointerMove={(e) => {
              if (drag.current)
                setWidth(drag.current.width + drag.current.x - e.clientX);
            }}
            onPointerUp={() => {
              drag.current = null;
              setDragging(false);
            }}
            onPointerCancel={() => {
              drag.current = null;
              setDragging(false);
            }}
          >
            <GripVertical size={12} />
          </div>
          <ChatPanel
            buildContext={(message, sessionId) =>
              buildChatContext(
                message,
                sessionId,
                location.pathname,
                location.search,
                hierarchy,
              )
            }
            onAction={(response) => handleChatAction(response, navigate)}
            reportTitle={reportTitle}
          />
        </aside>
      </div>
    </div>
  );
}
