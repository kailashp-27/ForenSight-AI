// frontend/src/components/ui/StatusToast.tsx
// Real-time Socket.io processing toast notifications — dark theme
import React from "react";
import { X, CheckCircle, AlertTriangle } from "lucide-react";
import { useSocketStore, type ProcessingToast } from "../../store/socketStore";

function ToastItem({ toast }: { toast: ProcessingToast }) {
  const dismiss = useSocketStore((s) => s.dismissToast);
  const isCompleted = toast.status === "COMPLETED" || toast.status === "CLEARED";
  const isFailed    = toast.status === "FAILED";

  return (
    <div
      className="animate-slide-in-right"
      role="alert"
      aria-live="polite"
      style={{
        background: "var(--color-bg-elevated)",
        border: "1px solid var(--color-border-bright)",
        borderRadius: 10,
        boxShadow: "var(--shadow-elevated)",
        padding: "0.875rem 1rem",
        width: 300,
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
        {/* Status Icon */}
        <div style={{ flexShrink: 0, marginTop: 2 }}>
          {isCompleted ? (
            <CheckCircle style={{ width: 16, height: 16, color: "#10b981" }} />
          ) : isFailed ? (
            <AlertTriangle style={{ width: 16, height: 16, color: "#ef4444" }} />
          ) : (
            <div className="live-dot" style={{ width: 10, height: 10 }}>
              <span className="live-dot-ping" style={{ background: "rgba(59,130,246,0.5)" }} />
              <span className="live-dot-core" style={{ width: 10, height: 10, background: "#3b82f6" }} />
            </div>
          )}
        </div>

        {/* Content */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <p
            style={{
              fontSize: "0.78rem", fontWeight: 600,
              color: "var(--color-text-primary)",
              overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
            }}
          >
            {toast.file_name}
          </p>
          <p style={{ fontSize: "0.7rem", color: "var(--color-text-muted)", marginTop: 2 }}>
            {toast.message}
          </p>

          {/* Progress bar */}
          {!isCompleted && !isFailed && (
            <div style={{ marginTop: 8 }}>
              <div
                style={{
                  display: "flex", justifyContent: "space-between",
                  fontSize: "0.65rem", color: "var(--color-text-subtle)", marginBottom: 4,
                }}
              >
                <span>{toast.status}</span>
                <span style={{ fontFamily: "monospace" }}>{toast.progress}%</span>
              </div>
              <div
                style={{
                  height: 2, background: "var(--color-border)",
                  borderRadius: 2, overflow: "hidden",
                }}
              >
                <div
                  style={{
                    height: "100%", background: "var(--color-accent)",
                    borderRadius: 2, width: `${toast.progress}%`,
                    transition: "width 0.3s ease",
                  }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Dismiss */}
        <button
          onClick={() => dismiss(toast.evidence_id)}
          style={{
            flexShrink: 0, background: "transparent", border: "none",
            color: "var(--color-text-subtle)", cursor: "pointer",
            transition: "color 0.15s",
          }}
          aria-label="Dismiss notification"
          onMouseEnter={e => (e.currentTarget.style.color = "var(--color-text-body)")}
          onMouseLeave={e => (e.currentTarget.style.color = "var(--color-text-subtle)")}
        >
          <X style={{ width: 14, height: 14 }} />
        </button>
      </div>
    </div>
  );
}

export function StatusToastContainer() {
  const toasts = useSocketStore((s) => s.toasts);
  if (toasts.length === 0) return null;

  return (
    <div
      style={{
        position: "fixed",
        bottom: "calc(var(--strip-h) + 16px)",
        right: "1rem",
        zIndex: 50,
        display: "flex",
        flexDirection: "column",
        gap: "0.5rem",
      }}
    >
      {toasts.map((toast) => (
        <ToastItem key={toast.evidence_id} toast={toast} />
      ))}
    </div>
  );
}
