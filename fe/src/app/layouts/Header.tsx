import { NavLink, Link, useLocation } from "react-router";
import * as NavigationMenu from "@radix-ui/react-navigation-menu";
import {
  Activity,
  LayoutDashboard,
  Factory,
  ChartNoAxesCombined,
  FileText,
  Bell,
} from "lucide-react";
import { Badge } from "../../shared/ui/badge.tsx";
import { remoteApi } from "../../shared/api/be-adapter.ts";
const menus = [
  { to: "/dashboard", label: "대시보드", icon: LayoutDashboard },
  { to: "/equip", label: "설비 현황", icon: Factory },
  { to: "/trend", label: "트렌드", icon: ChartNoAxesCombined },
  { to: "/reports", label: "보고서", icon: FileText },
  { to: "/alarms", label: "알람", icon: Bell },
];
export function Header() {
  const location = useLocation();
  const hierarchyParams = new URLSearchParams();
  for (const key of ["plant_id", "unit_id", "equip_id"]) {
    const value = new URLSearchParams(location.search).get(key);
    if (value) hierarchyParams.set(key, value);
  }
  const suffix = hierarchyParams.size ? "?" + hierarchyParams.toString() : "";
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
                  to={to + suffix}
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
