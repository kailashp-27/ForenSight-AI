// frontend/src/components/layout/ContextPanel.tsx
import React from "react";
import {
  X, ExternalLink, Tag, Flag, Download, Brain,
  AlertTriangle, Link2, Clock, User, FileText,
} from "lucide-react";

export interface ContextPanelItem {
  id: string;
  title: string;
  subtitle?: string;
  type: "lead" | "event" | "entity" | "evidence";
  confidence?: number;
  risk?: "high" | "medium" | "low";
  aiReasoning?: string;
  details?: Record<string, string>;
  relatedItems?: Array<{ label: string; value: string }>;
  timestamp?: string;
}

interface ContextPanelProps {
  item: ContextPanelItem | null;
  onClose: () => void;
}

const RISK_COLOR: Record<string, string> = {
  high:   "#ef4444",
  medium: "#f59e0b",
  low:    "#10b981",
};

const RISK_BG: Record<string, string> = {
  high:   "rgba(239,68,68,0.1)",
  medium: "rgba(245,158,11,0.1)",
  low:    "rgba(16,185,129,0.1)",
};

function ConfidenceBar({ value }: { value: number }) {
  const color = value >= 80 ? "#ef4444" : value >= 60 ? "#f59e0b" : "#10b981";
  return (
    <div style={{ marginTop: 4 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ fontSize: "0.6875rem", color: "var(--color-text-muted)" }}>AI Confidence</span>
        <span style={{ fontSize: "0.6875rem", fontWeight: 700, fontFamily: "var(--font-mono, monospace)", color }}>
          {value}%
        </span>
      </div>
      <div className="confidence-bar">
        <div className="confidence-fill" style={{ width: `${value}%`, background: color }} />
      </div>
    </div>
  );
}

export function ContextPanel({ item, onClose }: ContextPanelProps) {
  if (!item) return null;

  return (
    <aside
      className="hub-panel animate-slide-in-right"
      aria-label="Context panel"
      role="complementary"
    >
      {/* Header */}
      <div
        style={{
          display: "flex", alignItems: "flex-start", justifyContent: "space-between",
          padding: "1rem 1.25rem", borderBottom: "1px solid var(--color-border)",
          flexShrink: 0, gap: "0.75rem",
        }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          {item.risk && (
            <span
              style={{
                display: "inline-flex", alignItems: "center", gap: 4,
                padding: "0.15rem 0.5rem", borderRadius: 4,
                background: RISK_BG[item.risk],
                color: RISK_COLOR[item.risk],
                fontSize: "0.65rem", fontWeight: 700, letterSpacing: "0.06em",
                marginBottom: "0.5rem",
              }}
            >
              <AlertTriangle style={{ width: 10, height: 10 }} />
              {item.risk.toUpperCase()} RISK
            </span>
          )}
          <h2
            style={{
              fontSize: "0.875rem", fontWeight: 700,
              color: "var(--color-text-primary)",
              lineHeight: 1.3,
            }}
          >
            {item.title}
          </h2>
          {item.subtitle && (
            <p style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginTop: 2 }}>
              {item.subtitle}
            </p>
          )}
          {item.timestamp && (
            <div style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 6 }}>
              <Clock style={{ width: 10, height: 10, color: "var(--color-text-subtle)" }} />
              <span
                style={{
                  fontSize: "0.6875rem", fontFamily: "monospace",
                  color: "var(--color-text-subtle)",
                }}
              >
                {item.timestamp}
              </span>
            </div>
          )}
        </div>
        <button
          onClick={onClose}
          style={{
            width: 28, height: 28, borderRadius: 6, flexShrink: 0,
            background: "transparent", border: "1px solid var(--color-border)",
            color: "var(--color-text-muted)", cursor: "pointer",
            display: "flex", alignItems: "center", justifyContent: "center",
            transition: "background 0.15s, color 0.15s",
          }}
          aria-label="Close context panel"
          onMouseEnter={e => { e.currentTarget.style.background = "var(--color-bg-elevated)"; e.currentTarget.style.color = "var(--color-text-primary)"; }}
          onMouseLeave={e => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--color-text-muted)"; }}
        >
          <X style={{ width: 14, height: 14 }} />
        </button>
      </div>

      {/* Confidence */}
      {item.confidence !== undefined && (
        <div className="panel-section">
          <ConfidenceBar value={item.confidence} />
        </div>
      )}

      {/* AI Reasoning */}
      {item.aiReasoning && (
        <div className="panel-section">
          <div
            style={{
              display: "flex", alignItems: "center", gap: "0.4rem",
              marginBottom: "0.625rem",
            }}
          >
            <Brain style={{ width: 13, height: 13, color: "var(--color-accent)" }} />
            <span
              style={{
                fontSize: "0.7rem", fontWeight: 700, textTransform: "uppercase",
                letterSpacing: "0.08em", color: "var(--color-accent)",
              }}
            >
              AI Reasoning
            </span>
          </div>
          {/* AI disclaimer */}
          <div className="ai-disclaimer" style={{ marginBottom: "0.625rem", borderRadius: 6 }}>
            <AlertTriangle style={{ width: 10, height: 10, flexShrink: 0 }} />
            <span>Assistive only — not for legal conclusions</span>
          </div>
          <p
            style={{
              fontSize: "0.8rem", color: "var(--color-text-body)",
              lineHeight: 1.6,
            }}
          >
            {item.aiReasoning}
          </p>
        </div>
      )}

      {/* Details */}
      {item.details && Object.keys(item.details).length > 0 && (
        <div className="panel-section">
          <div
            style={{
              display: "flex", alignItems: "center", gap: "0.4rem",
              marginBottom: "0.75rem",
            }}
          >
            <FileText style={{ width: 13, height: 13, color: "var(--color-text-muted)" }} />
            <span
              style={{
                fontSize: "0.7rem", fontWeight: 700, textTransform: "uppercase",
                letterSpacing: "0.08em", color: "var(--color-text-muted)",
              }}
            >
              Details
            </span>
          </div>
          <dl style={{ display: "grid", gap: "0.5rem" }}>
            {Object.entries(item.details).map(([k, v]) => (
              <div key={k} style={{ display: "grid", gridTemplateColumns: "1fr 1.5fr", gap: "0.5rem", alignItems: "start" }}>
                <dt style={{ fontSize: "0.7rem", color: "var(--color-text-subtle)" }}>{k}</dt>
                <dd
                  style={{
                    fontSize: "0.75rem", fontFamily: "monospace",
                    color: "var(--color-text-body)", wordBreak: "break-all",
                  }}
                >
                  {v}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {/* Related Items */}
      {item.relatedItems && item.relatedItems.length > 0 && (
        <div className="panel-section">
          <div
            style={{
              display: "flex", alignItems: "center", gap: "0.4rem",
              marginBottom: "0.75rem",
            }}
          >
            <Link2 style={{ width: 13, height: 13, color: "var(--color-text-muted)" }} />
            <span
              style={{
                fontSize: "0.7rem", fontWeight: 700, textTransform: "uppercase",
                letterSpacing: "0.08em", color: "var(--color-text-muted)",
              }}
            >
              Related
            </span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.375rem" }}>
            {item.relatedItems.map((r, i) => (
              <div
                key={i}
                style={{
                  display: "flex", justifyContent: "space-between",
                  padding: "0.4rem 0.625rem",
                  background: "var(--color-bg-canvas)",
                  borderRadius: 6, border: "1px solid var(--color-border-subtle)",
                }}
              >
                <span style={{ fontSize: "0.7rem", color: "var(--color-text-muted)" }}>{r.label}</span>
                <span style={{ fontSize: "0.7rem", color: "var(--color-text-body)", fontFamily: "monospace" }}>{r.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="panel-section">
        <div
          style={{
            display: "flex", alignItems: "center", gap: "0.4rem",
            marginBottom: "0.75rem",
          }}
        >
          <span
            style={{
              fontSize: "0.7rem", fontWeight: 700, textTransform: "uppercase",
              letterSpacing: "0.08em", color: "var(--color-text-muted)",
            }}
          >
            Actions
          </span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
          {[
            { icon: Tag,          label: "Tag" },
            { icon: Flag,         label: "Escalate" },
            { icon: Download,     label: "Export" },
            { icon: ExternalLink, label: "Open Full" },
          ].map(({ icon: Icon, label }) => (
            <button
              key={label}
              style={{
                display: "flex", alignItems: "center", justifyContent: "center", gap: "0.375rem",
                padding: "0.5rem", borderRadius: 6,
                background: "var(--color-bg-canvas)", border: "1px solid var(--color-border)",
                color: "var(--color-text-muted)", fontSize: "0.75rem",
                cursor: "pointer", transition: "background 0.15s, color 0.15s, border-color 0.15s",
              }}
              aria-label={label}
              onMouseEnter={e => {
                e.currentTarget.style.background = "var(--color-accent-light)";
                e.currentTarget.style.color = "var(--color-accent)";
                e.currentTarget.style.borderColor = "var(--color-accent)";
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = "var(--color-bg-canvas)";
                e.currentTarget.style.color = "var(--color-text-muted)";
                e.currentTarget.style.borderColor = "var(--color-border)";
              }}
            >
              <Icon style={{ width: 12, height: 12 }} aria-hidden="true" />
              {label}
            </button>
          ))}
        </div>
      </div>
    </aside>
  );
}
