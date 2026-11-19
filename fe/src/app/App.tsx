import { lazy, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Navigate,
  Route,
  Routes,
  useSearchParams,
  useNavigate,
  useLocation,
} from "react-router";
import {
  hierarchyQuery,
  useSelectionStore,
  type Selection,
} from "../features/hierarchy/index.ts";
import { alarmsQuery } from "../features/alarms/index.ts";
import { remoteApi } from "../shared/api/be-adapter.ts";
import { AppLayout } from "./layouts/AppLayout.tsx";
import { SelectionUrlSync } from "./integrations/SelectionUrlSync.tsx";
import { ReportAutosaveBridge } from "./integrations/ReportAutosaveBridge.tsx";
import { resolveSelection, selectionParams } from "./router/navigation.ts";
import { LoadingState } from "../shared/ui/LoadingState.tsx";
import { ErrorState } from "../shared/ui/ErrorState.tsx";
import { errorMessage } from "../shared/api/http-client.ts";
import { Button } from "../shared/ui/button.tsx";
import { Link } from "react-router";
const Dashboard = lazy(() =>
  import("../pages/dashboard/DashboardPage.tsx").then((m) => ({
    default: m.DashboardPage,
  })),
);
const Equipment = lazy(() =>
  import("../pages/equipment/EquipmentPage.tsx").then((m) => ({
    default: m.EquipmentPage,
  })),
);
const Trend = lazy(() =>
  import("../pages/trend/TrendPage.tsx").then((m) => ({
    default: m.TrendPage,
  })),
);
const Reports = lazy(() =>
  import("../pages/reports/ReportListPage.tsx").then((m) => ({
    default: m.ReportListPage,
  })),
);
const Editor = lazy(() =>
  import("../pages/reports/ReportEditorPage.tsx").then((m) => ({
    default: m.ReportEditorPage,
  })),
);
const NewReport = lazy(() =>
  import("../pages/reports/ReportEditorPage.tsx").then((m) => ({
    default: m.NewReportPage,
  })),
);
const Alarms = lazy(() =>
  import("../pages/alarms/AlarmListPage.tsx").then((m) => ({
    default: m.AlarmListPage,
  })),
);
export function App() {
  const hierarchy = useQuery(hierarchyQuery);
  const alarms = useQuery(alarmsQuery);
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  if (hierarchy.isPending)
    return (
      <div className="boot-screen">
        <h1>SKADI</h1>
        <LoadingState />
      </div>
    );
  if (hierarchy.isError)
    return (
      <div className="boot-screen">
        <ErrorState
          message={errorMessage(hierarchy.error)}
          retry={() => void hierarchy.refetch()}
        />
      </div>
    );
  const data = hierarchy.data;
  const selection = resolveSelection(params, data);
  const onSelect = (next: Selection) => {
    useSelectionStore.getState().setSelection(next);
    const p = selectionParams(next, params);
    navigate(`${pathname === "/" ? "/equip" : pathname}?${p.toString()}`);
  };
  return (
    <>
      <SelectionUrlSync />
      {!remoteApi && <ReportAutosaveBridge />}
      <AppLayout hierarchy={data} selection={selection} onSelect={onSelect}>
        <Suspense fallback={<LoadingState />}>
          {alarms.isError ? (
            <ErrorState
              message="실시간 상태를 갱신하지 못했습니다. 마지막 수신 데이터를 표시합니다."
              retry={() => void alarms.refetch()}
            />
          ) : null}
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route
              path="/dashboard"
              element={
                alarms.data ? (
                  <Dashboard
                    hierarchy={data}
                    alarms={remoteApi ? [] : alarms.data.alarms}
                  />
                ) : (
                  <LoadingState />
                )
              }
            />
            <Route
              path="/equip"
              element={
                <Equipment
                  hierarchy={data}
                  selection={selection}
                  alarms={remoteApi ? [] : (alarms.data?.alarms ?? [])}
                  onSelect={onSelect}
                />
              }
            />
            <Route
              path="/trend"
              element={<Trend hierarchy={data} selection={selection} />}
            />
            <Route
              path="/alarms"
              element={
                <Alarms
                  hierarchy={data}
                  selection={selection}
                  alarms={alarms.data?.alarms ?? []}
                />
              }
            />
            <Route
              path="/reports"
              element={<Reports hierarchy={data} selection={selection} />}
            />
            <Route
              path="/reports/new"
              element={<NewReport hierarchy={data} selection={selection} />}
            />
            <Route
              path="/reports/:reportId"
              element={<Editor hierarchy={data} />}
            />
            <Route
              path="*"
              element={
                <div className="page">
                  <h1>화면을 찾을 수 없습니다</h1>
                  <Button asChild>
                    <Link to="/dashboard">대시보드로 이동</Link>
                  </Button>
                </div>
              }
            />
          </Routes>
        </Suspense>
      </AppLayout>
    </>
  );
}
