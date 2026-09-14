// frontend/src/components/layout/FloatingActionOrb.tsx
import React, { useState, useEffect, useRef } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  Plus, LayoutDashboard, FolderOpen, FileVideo,
  BarChart2, Settings, X,
} from "lucide-react";

const NAV_ITEMS = [
  { to: "/",         icon: LayoutDashboard, label: "Dashboard" },
  { to: "/cases",    icon: FolderOpen,      label: "Cases" },
  { to: "/evidence", icon: FileVideo,       label: "Evidence" },
  { to: "/reports",  icon: BarChart2,       label: "Reports" },
  { to: "/settings", icon: Settings,        label: "Settings" },
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
        bottom: 32,
        right: 32,
        zIndex: 50,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        width: 48,
        height: 48,
      }}
      aria-label="Navigation menu"
    >
      {/* Menu items (Vertical List) */}
      {NAV_ITEMS.map(({ to, icon: Icon, label }, i) => {
        // Calculate vertical offset
        const yOffset = (i + 1) * 56;
        const isCurrentActive =
          to === "/" ? location.pathname === "/" : location.pathname.startsWith(to);

        return (
          <div key={to} style={{ position: "absolute", bottom: 0, left: 0, width: "100%", height: "100%" }}>
            <NavLink
              to={to}
              end={to === "/"}
              className="fab-item"
              aria-label={label}
              style={{
                position: "absolute",
                bottom: 4,
                left: 4, // 48/2 - 40/2 = 4 to center a 40px item inside a 48px orb container
                transform: open
                  ? `translateY(-${yOffset}px) scale(1)`
                  : `translateY(0px) scale(0)`,
                opacity: open ? 1 : 0,
                transition: `transform 0.25s cubic-bezier(0.34,1.56,0.64,1) ${i * 35}ms, opacity 0.2s ease ${i * 30}ms`,
                pointerEvents: open ? "auto" : "none",
              }}
              onMouseEnter={() => setTooltip(label)}
              onMouseLeave={() => setTooltip(null)}
            >
              {/* Tooltip */}
              {tooltip === label && open && (
                <div
                  style={{
                    position: "absolute",
                    right: "100%",
                    top: "50%",
                    marginRight: 12,
                    transform: "translateY(-50%)",
                    background: "var(--color-bg-elevated)",
                    border: "1px solid var(--color-border-bright)",
                    borderRadius: 6,
                    padding: "4px 10px",
                    fontSize: "0.75rem",
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
              
              {/* Icon */}
              <Icon
                style={{
                  width: 16, height: 16,
                  color: isCurrentActive ? "white" : undefined,
                }}
                aria-hidden="true"
              />
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
