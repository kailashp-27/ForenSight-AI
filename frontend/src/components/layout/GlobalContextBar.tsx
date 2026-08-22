// frontend/src/components/layout/GlobalContextBar.tsx
import React, { useState } from "react";
import { Search, Shield, Briefcase, Bell, User, Wifi, WifiOff } from "lucide-react";
import { useSocketStore } from "../../store/socketStore";

interface GlobalContextBarProps {
  onSearchChange?: (v: string) => void;
}

export function GlobalContextBar({ onSearchChange }: GlobalContextBarProps) {
  const connected = useSocketStore((s) => s.connected);
  const [search, setSearch] = useState("");

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(e.target.value);
    onSearchChange?.(e.target.value);
  };

  return (
    <header className="hub-header" role="banner">
      {/* Logo */}
      <div className="flex items-center gap-2.5 flex-shrink-0">
        <div
          style={{
            width: 32, height: 32, borderRadius: 8,
            background: "linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)",
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: "0 0 12px rgba(59,130,246,0.4)",
          }}
        >
          <Shield style={{ width: 16, height: 16, color: "white" }} aria-hidden="true" />
        </div>
        <div>
          <p style={{ fontSize: "0.875rem", fontWeight: 700, color: "var(--color-text-primary)", lineHeight: 1 }}>
            ForenSight
          </p>
          <p style={{ fontSize: "0.65rem", color: "var(--color-text-subtle)", marginTop: 2, lineHeight: 1, letterSpacing: "0.05em" }}>
            AI INVESTIGATION
          </p>
        </div>
      </div>

      {/* Divider */}
      <div style={{ width: 1, height: 28, background: "var(--color-border)", flexShrink: 0 }} />

      {/* Global Search */}
      <div style={{ position: "relative", flex: 1, maxWidth: 420 }}>
        <Search
          style={{
            position: "absolute", left: "0.75rem", top: "50%", transform: "translateY(-50%)",
            width: 14, height: 14, color: "var(--color-text-subtle)", pointerEvents: "none",
          }}
          aria-hidden="true"
        />
        <input
          type="search"
          className="global-search"
          style={{ width: "100%" }}
          placeholder="Search cases, entities, evidence…"
          value={search}
          onChange={handleSearch}
          aria-label="Global search"
          id="global-search"
        />
      </div>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Right controls */}
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexShrink: 0 }}>
        {/* Workspace */}
        <button
          style={{
            display: "flex", alignItems: "center", gap: "0.4rem",
            padding: "0.35rem 0.75rem", borderRadius: 6,
            background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)",
            color: "var(--color-text-body)", fontSize: "0.75rem", fontWeight: 500,
            cursor: "pointer", transition: "border-color 0.15s",
          }}
          aria-label="Switch workspace"
          onMouseEnter={e => (e.currentTarget.style.borderColor = "var(--color-border-bright)")}
          onMouseLeave={e => (e.currentTarget.style.borderColor = "var(--color-border)")}
        >
          <Briefcase style={{ width: 12, height: 12, color: "var(--color-text-muted)" }} />
          Fraud Investigations
        </button>

        {/* Live connection */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
          <div className="live-dot">
            {connected && (
              <span
                className="live-dot-ping"
                style={{ background: "rgba(16,185,129,0.5)" }}
              />
            )}
            <span
              className="live-dot-core"
              style={{ background: connected ? "#10b981" : "#374151" }}
            />
          </div>
          {connected
            ? <Wifi style={{ width: 12, height: 12, color: "#10b981" }} aria-label="Connected" />
            : <WifiOff style={{ width: 12, height: 12, color: "var(--color-text-subtle)" }} aria-label="Disconnected" />
          }
        </div>

        {/* Notifications */}
        <button
          style={{
            width: 32, height: 32, borderRadius: 8, cursor: "pointer",
            background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)",
            display: "flex", alignItems: "center", justifyContent: "center",
            color: "var(--color-text-muted)", position: "relative",
            transition: "border-color 0.15s, color 0.15s",
          }}
          aria-label="Notifications"
          onMouseEnter={e => { e.currentTarget.style.color = "var(--color-text-primary)"; e.currentTarget.style.borderColor = "var(--color-border-bright)"; }}
          onMouseLeave={e => { e.currentTarget.style.color = "var(--color-text-muted)"; e.currentTarget.style.borderColor = "var(--color-border)"; }}
        >
          <Bell style={{ width: 14, height: 14 }} aria-hidden="true" />
          {/* Notification dot */}
          <span
            style={{
              position: "absolute", top: 6, right: 6,
              width: 6, height: 6, borderRadius: "50%",
              background: "#ef4444", border: "1.5px solid var(--color-bg-header)",
            }}
          />
        </button>

        {/* User Avatar */}
        <button
          style={{
            width: 32, height: 32, borderRadius: "50%", cursor: "pointer",
            background: "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)",
            border: "2px solid var(--color-border-bright)",
            display: "flex", alignItems: "center", justifyContent: "center",
            color: "white", fontSize: "0.75rem", fontWeight: 700,
            transition: "border-color 0.15s",
          }}
          aria-label="User profile"
          onMouseEnter={e => (e.currentTarget.style.borderColor = "var(--color-accent)")}
          onMouseLeave={e => (e.currentTarget.style.borderColor = "var(--color-border-bright)")}
        >
          KP
        </button>
      </div>
    </header>
  );
}
