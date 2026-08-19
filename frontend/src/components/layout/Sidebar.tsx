// frontend/src/components/layout/Sidebar.tsx
import React from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  FolderOpen,
  FileVideo,
  Shield,
  Settings,
  Activity,
} from "lucide-react";
import { useSocketStore } from "../../store/socketStore";

const navItems = [
  { to: "/",        icon: LayoutDashboard, label: "Dashboard" },
  { to: "/cases",   icon: FolderOpen,      label: "Cases" },
  { to: "/evidence",icon: FileVideo,       label: "Evidence" },
];

export function Sidebar() {
  const connected = useSocketStore((s) => s.connected);

  return (
    <aside className="flex flex-col w-60 flex-shrink-0 bg-slate-900 h-full">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 py-5 border-b border-slate-800">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-blue-600">
          <Shield className="w-4 h-4 text-white" aria-hidden="true" />
        </div>
        <div>
          <p className="text-white font-bold text-sm leading-none">ForenSight</p>
          <p className="text-slate-400 text-xs mt-0.5 leading-none">AI Investigation</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1" aria-label="Main navigation">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            aria-label={label}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 h-10 rounded-lg text-sm font-medium transition-colors duration-150 ${
                isActive
                  ? "bg-blue-600 text-white"
                  : "text-slate-400 hover:text-white hover:bg-slate-800"
              }`
            }
          >
            <Icon className="w-5 h-5 flex-shrink-0" aria-hidden="true" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-3 py-4 border-t border-slate-800 space-y-1">
        {/* Live connection indicator */}
        <div className="flex items-center gap-2 px-3 py-2">
          <div className="relative flex h-2 w-2 flex-shrink-0">
            {connected && (
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            )}
            <span className={`relative inline-flex h-2 w-2 rounded-full ${connected ? "bg-emerald-500" : "bg-slate-600"}`} />
          </div>
          <span className="text-xs text-slate-500">
            {connected ? "Live connection" : "Offline"}
          </span>
          <Activity className="w-3 h-3 text-slate-600 ml-auto" aria-hidden="true" />
        </div>

        <NavLink
          to="/settings"
          aria-label="Settings"
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 h-10 rounded-lg text-sm font-medium transition-colors duration-150 ${
              isActive
                ? "bg-blue-600 text-white"
                : "text-slate-400 hover:text-white hover:bg-slate-800"
            }`
          }
        >
          <Settings className="w-5 h-5 flex-shrink-0" aria-hidden="true" />
          Settings
        </NavLink>
      </div>
    </aside>
  );
}
