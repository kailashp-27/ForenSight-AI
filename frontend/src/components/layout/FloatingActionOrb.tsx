// frontend/src/components/layout/FloatingActionOrb.tsx
import React, { useState, useEffect, useRef } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  Plus, LayoutDashboard, FolderOpen, FileVideo,
  BarChart2, Settings, HelpCircle, X,
} from "lucide-react";

const NAV_ITEMS = [
  { to: "/",         icon: LayoutDashboard, label: "Dashboard",   angle: -90 },
  { to: "/cases",    icon: FolderOpen,      label: "Cases",       angle: -45 },
  { to: "/evidence", icon: FileVideo,       label: "Evidence",    angle: 0   },
  { to: "/reports",  icon: BarChart2,       label: "Reports",     angle: 45  },
  { to: "/settings", icon: Settings,        label: "Settings",    angle: 90  },
  { to: "/help",     icon: HelpCircle,      label: "Help",        angle: 135 },
];

const RADIUS = 68; // px from orb center to menu item center

export function FloatingActionOrb() {
  const [open, setOpen] = useState(false);
  const [tooltip, setTooltip] = useState<string | null>(null);
  const orbRef = useRef<HTMLDivElement>(null);
  const location = useLocation();

  // Close on route change
  useEffect(() => { setOpen(false); }, [location.pathname]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (orbRef.current && !orbRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);

  return (
    <div
      ref={orbRef}
      style={{
        position: "fixed",
        bottom: "calc(var(--strip-h) + 24px)",
        left: 24,
        zIndex: 30,
      }}
      aria-label="Navigation menu"
    >
      {/* Radial menu items */}
      {NAV_ITEMS.map(({ to, icon: Icon, label, angle }, i) => {
        const rad = (angle * Math.PI) / 180;
        const x = Math.cos(rad) * RADIUS;
        const y = Math.sin(rad) * RADIUS;
        const isCurrentActive =
          to === "/" ? location.pathname === "/" : location.pathname.startsWith(to);

        return (
          <div key={to} style={{ position: "absolute", bottom: 0, left: 0 }}>
            {/* Tooltip */}
            {tooltip === label && open && (
              <div
                style={{
                  position: "absolute",
                  bottom: y + 24 + 4,
                  left: x + 24,
                  transform: "translateX(-50%) translateY(-100%)",
                  background: "var(--color-bg-elevated)",
                  border: "1px solid var(--color-border-bright)",
                  borderRadius: 6,
                  padding: "3px 8px",
                  fontSize: "0.6875rem",
                  fontWeight: 500,
                  color: "var(--color-text-primary)",
                  whiteSpace: "nowrap",
                  pointerEvents: "none",
                  boxShadow: "var(--shadow-elevated)",
                }}
              >
                {label}
              </div>
            )}
            <NavLink
              to={to}
              end={to === "/"}
              className="fab-item"
              aria-label={label}
              style={{
                bottom: 0,
                left: 0,
                transform: open
                  ? `translate(${x}px, ${-y}px) scale(1)`
                  : `translate(0px, 0px) scale(0)`,
                opacity: open ? 1 : 0,
                transition: `transform 0.25s cubic-bezier(0.34,1.56,0.64,1) ${i * 35}ms, opacity 0.2s ease ${i * 30}ms`,
                pointerEvents: open ? "auto" : "none",
              }}
              onMouseEnter={() => setTooltip(label)}
              onMouseLeave={() => setTooltip(null)}
            >
              {({ isActive }) => (
                <span
                  className={isActive || isCurrentActive ? "active" : ""}
                  style={{ display: "contents" }}
                >
                  <Icon
                    style={{
                      width: 16, height: 16,
                      color: isActive || isCurrentActive ? "white" : undefined,
                    }}
                    aria-hidden="true"
                  />
                </span>
              )}
            </NavLink>
          </div>
        );
      })}

      {/* Main Orb button */}
      <button
        className={`fab-orb ${open ? "open" : ""}`}
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={open ? "Close navigation" : "Open navigation"}
        style={{ position: "relative", zIndex: 1 }}
      >
        {open
          ? <X style={{ width: 20, height: 20, color: "white" }} />
          : <Plus style={{ width: 20, height: 20, color: "white" }} />
        }
      </button>

      {/* Backdrop when open */}
      {open && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: -1,
          }}
          onClick={() => setOpen(false)}
          aria-hidden="true"
        />
      )}
    </div>
  );
}
