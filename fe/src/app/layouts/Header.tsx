import { NavLink, Link, useLocation } from "react-router";
import type { Selection } from "../../features/hierarchy/index.ts";
import * as NavigationMenu from "@radix-ui/react-navigation-menu";
import {
  Activity,
  LayoutDashboard,
  Factory,
  ChartNoAxesCombined,
  FileText,
  Bell,
  Siren,
} from "lucide-react";
import { Badge } from "../../shared/ui/badge.tsx";
import { remoteApi } from "../../shared/api/be-adapter.ts";
const menus = [
  { to: "/dashboard", label: "대시보드", icon: LayoutDashboard },
  { to: "/equip", label: "설비 현황", icon: Factory },
  { to: "/trend", label: "트렌드", icon: ChartNoAxesCombined },
  { to: "/reports", label: "보고서", icon: FileText },
  { to: "/alarms", label: "알람", icon: Bell },
  { to: "/incidents", label: "이상 사건", icon: Siren },
];
export function Header({ selection }: { selection: Selection }) {
  const location = useLocation();
  const hierarchyParams = new URLSearchParams();
  if (selection.plantId) hierarchyParams.set("plant_id", selection.plantId);
  if (selection.unitId) hierarchyParams.set("unit_id", selection.unitId);
  if (selection.equipmentId) {
    hierarchyParams.set("equip_id", selection.equipmentId);
    if (selection.sensorIds.length === 0)
      hierarchyParams.append("sensor_id", "");
    else
      selection.sensorIds.forEach((id) =>
        hierarchyParams.append("sensor_id", id),
      );
  }
  const suffix = hierarchyParams.size ? "?" + hierarchyParams.toString() : "";
  const currentParams = new URLSearchParams(location.search);
  const viewId = currentParams.get("viewId");
  const savedTrendParams = new URLSearchParams();
  if (viewId) {
    savedTrendParams.set("viewId", viewId);
    for (const key of ["view_from", "view_to", "interval"]) {
      const value = currentParams.get(key);
      if (value) savedTrendParams.set(key, value);
    }
    if (selection.sensorIds.length === 0)
      savedTrendParams.append("selected_sensor_id", "");
    else
      selection.sensorIds.forEach((id) =>
        savedTrendParams.append("selected_sensor_id", id),
      );
  }
  return (
    <header className="app-header">
      <Link to="/dashboard" className="brand">
        <span className="brand-mark">
          <Activity size={23} />
        </span>
        <strong>
          SKADI<span>ROTATING INTELLIGENCE</span>
        </strong>
      </Link>
      <NavigationMenu.Root aria-label="업무 메뉴">
        <NavigationMenu.List className="top-nav">
          {menus.map(({ to, label, icon: Icon }) => (
            <NavigationMenu.Item key={to}>
              <NavigationMenu.Link asChild>
                <NavLink
                  to={
                    to === "/trend" && viewId
                      ? `/trend?${savedTrendParams}`
                      : to + suffix
                  }
                  className={({ isActive }) => (isActive ? "active" : "")}
                >
                  <Icon size={16} />
                  {label}
                </NavLink>
              </NavigationMenu.Link>
            </NavigationMenu.Item>
          ))}
        </NavigationMenu.List>
      </NavigationMenu.Root>
      <div className="header-actions">
        <Badge>{remoteApi ? "BE 연결" : "MOCK · 데모"}</Badge>
        <div className="header-separator" />
        <span className="environment-label">운영 모니터링</span>
        <span className="avatar" title="로그인 기능 미적용">
          OP
        </span>
      </div>
    </header>
  );
}
