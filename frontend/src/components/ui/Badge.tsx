// frontend/src/components/ui/Badge.tsx
import React from "react";

export type BadgeVariant =
  | "queued"
  | "pending"
  | "processing"
  | "analyzing"
  | "review"
  | "cleared"
  | "failed"
  | "open"
  | "under_review"
  | "closed"
  | "archived";

const CONFIG: Record<BadgeVariant, { label: string; dot: string; bg: string; text: string }> = {
  queued:      { label: "QUEUED",           dot: "bg-slate-400",   bg: "bg-slate-100",   text: "text-slate-600" },
  pending:     { label: "PENDING",          dot: "bg-violet-500",  bg: "bg-violet-50",   text: "text-violet-700" },
  processing:  { label: "PROCESSING",       dot: "bg-sky-500",     bg: "bg-sky-50",      text: "text-sky-700" },
  analyzing:   { label: "ANALYZING",        dot: "bg-blue-500",    bg: "bg-blue-50",     text: "text-blue-700" },
  review:      { label: "REVIEW REQUIRED",  dot: "bg-amber-500",   bg: "bg-amber-50",    text: "text-amber-700" },
  cleared:     { label: "CLEARED",          dot: "bg-emerald-500", bg: "bg-emerald-50",  text: "text-emerald-700" },
  failed:      { label: "FAILED",           dot: "bg-red-500",     bg: "bg-red-50",      text: "text-red-700" },
  open:        { label: "OPEN",             dot: "bg-blue-500",    bg: "bg-blue-50",     text: "text-blue-700" },
  under_review:{ label: "UNDER REVIEW",     dot: "bg-amber-500",   bg: "bg-amber-50",    text: "text-amber-700" },
  closed:      { label: "CLOSED",           dot: "bg-slate-400",   bg: "bg-slate-100",   text: "text-slate-600" },
  archived:    { label: "ARCHIVED",         dot: "bg-slate-300",   bg: "bg-slate-50",    text: "text-slate-500" },
};

interface BadgeProps {
  variant: BadgeVariant;
  className?: string;
}

export function Badge({ variant, className = "" }: BadgeProps) {
  const cfg = CONFIG[variant];
  const isPulsing = variant === "processing" || variant === "analyzing";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${cfg.bg} ${cfg.text} ${className}`}
    >
      <span className="relative flex h-2 w-2 flex-shrink-0">
        {isPulsing && (
          <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${cfg.dot} opacity-75`} />
        )}
        <span className={`relative inline-flex h-2 w-2 rounded-full ${cfg.dot}`} />
      </span>
      {cfg.label}
    </span>
  );
}

export function statusToVariant(status: string): BadgeVariant {
  const map: Record<string, BadgeVariant> = {
    PENDING: "pending",
    PROCESSING: "processing",
    COMPLETED: "cleared",
    FAILED: "failed",
    OPEN: "open",
    UNDER_REVIEW: "under_review",
    CLOSED: "closed",
    ARCHIVED: "archived",
  };
  return map[status] ?? "queued";
}
