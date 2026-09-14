// frontend/src/components/layout/GlobalContextBar.tsx
import React, { useState } from "react";
import { Search, Shield, Briefcase, Bell, User, Wifi, WifiOff } from "lucide-react";
import { Link } from "react-router-dom";
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
        <Link to="/" style={{ textDecoration: "none", outline: "none" }}>
          <p style={{ fontSize: "0.875rem", fontWeight: 700, color: "var(--color-text-primary)", lineHeight: 1 }}>
            ForenSight AI
          </p>
          <p style={{ fontSize: "0.65rem", color: "var(--color-text-subtle)", marginTop: 2, lineHeight: 1, letterSpacing: "0.05em" }}>
            AI INVESTIGATION
          </p>
        </Link>
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


      </div>
    </header>
  );
}
