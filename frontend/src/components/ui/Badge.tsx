// frontend/src/components/ui/Badge.tsx
import React from "react";

export type BadgeVariant =
  | "queued" | "pending" | "processing" | "analyzing"
  | "review" | "cleared" | "failed"
  | "open" | "under_review" | "closed" | "archived";

const CONFIG: Record<BadgeVariant, { label: string; dot: string; bg: string; text: string }> = {
  queued:      { label: "QUEUED",          dot: "#64748b", bg: "rgba(100,116,139,0.12)", text: "#94a3b8" },
  pending:     { label: "PENDING",         dot: "#8b5cf6", bg: "rgba(139,92,246,0.12)",  text: "#a78bfa" },
  processing:  { label: "PROCESSING",      dot: "#06b6d4", bg: "rgba(6,182,212,0.12)",   text: "#22d3ee" },
  analyzing:   { label: "ANALYZING",       dot: "#3b82f6", bg: "rgba(59,130,246,0.12)",  text: "#60a5fa" },
  review:      { label: "REVIEW REQUIRED", dot: "#f59e0b", bg: "rgba(245,158,11,0.12)",  text: "#fbbf24" },
  cleared:     { label: "CLEARED",         dot: "#10b981", bg: "rgba(16,185,129,0.12)",  text: "#34d399" },
  failed:      { label: "FAILED",          dot: "#ef4444", bg: "rgba(239,68,68,0.12)",   text: "#f87171" },
  open:        { label: "OPEN",            dot: "#3b82f6", bg: "rgba(59,130,246,0.12)",  text: "#60a5fa" },
  under_review:{ label: "UNDER REVIEW",    dot: "#f59e0b", bg: "rgba(245,158,11,0.12)",  text: "#fbbf24" },
  closed:      { label: "CLOSED",          dot: "#64748b", bg: "rgba(100,116,139,0.12)", text: "#94a3b8" },
  archived:    { label: "ARCHIVED",        dot: "#4b5563", bg: "rgba(75,85,99,0.12)",    text: "#6b7280" },
};

interface BadgeProps {
  variant: BadgeVariant;
  className?: string;
}

export function Badge({ variant }: BadgeProps) {
  const cfg = CONFIG[variant];
  const isPulsing = variant === "processing" || variant === "analyzing";

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        borderRadius: 9999,
        padding: "0.2rem 0.6rem",
        fontSize: "0.6875rem",
        fontWeight: 700,
        letterSpacing: "0.03em",
        background: cfg.bg,
        color: cfg.text,
        border: `1px solid ${cfg.dot}30`,
        whiteSpace: "nowrap",
      }}
    >
      <span style={{ position: "relative", display: "inline-flex", width: 6, height: 6, flexShrink: 0 }}>
        {isPulsing && (
          <span
            style={{
              position: "absolute", inset: 0, borderRadius: "50%",
              background: cfg.dot, opacity: 0.6,
              animation: "ping 1.5s cubic-bezier(0,0,0.2,1) infinite",
            }}
          />
        )}
        <span
          style={{
            position: "relative", width: 6, height: 6,
            borderRadius: "50%", background: cfg.dot, display: "inline-flex",
          }}
        />
      </span>
      {cfg.label}
    </span>
  );
}

export function statusToVariant(status: string): BadgeVariant {
  const map: Record<string, BadgeVariant> = {
    PENDING:      "pending",
    PROCESSING:   "processing",
    COMPLETED:    "cleared",
    FAILED:       "failed",
    OPEN:         "open",
    UNDER_REVIEW: "under_review",
    CLOSED:       "closed",
    ARCHIVED:     "archived",
  };
  return map[status] ?? "queued";
}
