// frontend/src/components/visualization/TimelineView.tsx
import React, { useRef, useState } from "react";
import { User, Monitor, Globe, FileText } from "lucide-react";
import type { TimelineEvent } from "../../services/api";

export type { TimelineEvent };

const TYPE_COLOR: Record<string, string> = {
  login:       "#3b82f6",
  transaction: "#f59e0b",
  detection:   "#ef4444",
  document:    "#10b981",
  alert:       "#ec4899",
};

const ENTITY_ICON: Record<string, React.FC<{ style?: React.CSSProperties }>> = {
  person:  ({ style }) => <User    style={style} />,
  device:  ({ style }) => <Monitor style={style} />,
  account: ({ style }) => <Globe   style={style} />,
  network: ({ style }) => <Globe   style={style} />,
};

const ENTITY_COLOR: Record<string, string> = {
  person:  "#3b82f6",
  device:  "#10b981",
  account: "#f59e0b",
  network: "#ec4899",
};

const RISK_GLOW: Record<string, string> = {
  high:   "0 0 8px rgba(239,68,68,0.6)",
  medium: "0 0 8px rgba(245,158,11,0.4)",
  low:    "0 0 8px rgba(16,185,129,0.3)",
};

interface TooltipState {
  event: TimelineEvent;
  x: number;
}

interface TimelineViewProps {
  events: TimelineEvent[];
  onEventClick?: (event: TimelineEvent) => void;
}

export function TimelineView({ events, onEventClick }: TimelineViewProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleNodeClick = (ev: TimelineEvent, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedId(ev.id);
    onEventClick?.(ev);
  };

  // Empty state
  if (events.length === 0) {
    return (
      <div
        style={{
          display: "flex", flexDirection: "column", alignItems: "center",
          justifyContent: "center", padding: "3rem 1rem", textAlign: "center", gap: 10,
        }}
      >
        <FileText style={{ width: 36, height: 36, color: "var(--color-border-bright)" }} />
        <p style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--color-text-muted)" }}>
          No timeline events yet
        </p>
        <p style={{ fontSize: "0.75rem", color: "var(--color-text-subtle)", maxWidth: 300 }}>
          Upload evidence and run AI analysis to start building the case storyline.
        </p>
      </div>
    );
  }

  const topEvents    = events.filter((_, i) => i % 2 === 0);
  const bottomEvents = events.filter((_, i) => i % 2 !== 0);

  return (
    <div
      style={{
        position: "relative",
        padding: "1.5rem 2rem",
        userSelect: "none",
        minWidth: Math.max(900, events.length * 120),
      }}
      ref={containerRef}
      onClick={() => setSelectedId(null)}
    >
      {/* Time Labels row */}
      <div style={{ position: "relative", height: 20, marginBottom: 8 }}>
        {events.map((ev) => (
          <span
            key={`label-${ev.id}`}
            style={{
              position: "absolute",
              left: `${ev.timestamp}%`,
              transform: "translateX(-50%)",
              fontSize: "0.6rem",
              fontFamily: "monospace",
              color: "var(--color-text-subtle)",
              whiteSpace: "nowrap",
            }}
          >
            {ev.time}
          </span>
        ))}
      </div>

      {/* Top entities */}
      <div style={{ position: "relative", height: 48, marginBottom: 0 }}>
        {topEvents.map((ev) => {
          const IconComp = ENTITY_ICON[ev.entityType ?? "device"] ?? ENTITY_ICON.device;
          return (
            <div
              key={`top-${ev.id}`}
              style={{
                position: "absolute",
                left: `${ev.timestamp}%`,
                bottom: 0,
                transform: "translateX(-50%)",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 4,
              }}
            >
              <div
                style={{
                  width: 28, height: 28, borderRadius: "50%",
                  background: "var(--color-bg-elevated)",
                  border: `1.5px solid ${ENTITY_COLOR[ev.entityType ?? "device"]}`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  boxShadow: hoveredId === ev.id || selectedId === ev.id
                    ? `0 0 12px ${ENTITY_COLOR[ev.entityType ?? "device"]}60`
                    : "none",
                  transition: "box-shadow 0.2s",
                }}
              >
                <IconComp
                  style={{ width: 12, height: 12, color: ENTITY_COLOR[ev.entityType ?? "device"] }}
                />
              </div>
              <span
                style={{
                  fontSize: "0.6rem", color: "var(--color-text-subtle)",
                  whiteSpace: "nowrap", fontFamily: "monospace",
                  opacity: hoveredId === ev.id ? 1 : 0.7,
                }}
              >
                {ev.entity}
              </span>
              <div style={{ width: 1, height: 8, background: "var(--color-border)" }} />
            </div>
          );
        })}
      </div>

      {/* Timeline track */}
      <div className="timeline-track" style={{ position: "relative", margin: "0 0" }}>
        {events.map((ev) => (
          <div
            key={`node-${ev.id}`}
            className="timeline-node"
            style={{
              left: `${ev.timestamp}%`,
              background: TYPE_COLOR[ev.type] ?? "var(--color-accent)",
              borderColor: selectedId === ev.id ? "white" : "var(--color-bg-canvas)",
              width:  selectedId === ev.id ? 14 : hoveredId === ev.id ? 12 : 10,
              height: selectedId === ev.id ? 14 : hoveredId === ev.id ? 12 : 10,
              boxShadow: ev.risk ? (RISK_GLOW[ev.risk] ?? "none") : "none",
              zIndex: selectedId === ev.id ? 10 : 1,
            }}
            onClick={(e) => handleNodeClick(ev, e)}
            onMouseEnter={() => { setHoveredId(ev.id); setTooltip({ event: ev, x: ev.timestamp }); }}
            onMouseLeave={() => { setHoveredId(null); setTooltip(null); }}
            role="button"
            tabIndex={0}
            aria-label={`Timeline event: ${ev.label}`}
            onKeyDown={(e) => e.key === "Enter" && handleNodeClick(ev, e as any)}
          />
        ))}
      </div>

      {/* Bottom entities */}
      <div style={{ position: "relative", marginTop: 0 }}>
        {bottomEvents.map((ev) => {
          const IconComp = ENTITY_ICON[ev.entityType ?? "device"] ?? ENTITY_ICON.device;
          return (
            <div
              key={`bot-${ev.id}`}
              style={{
                position: "absolute",
                left: `${ev.timestamp}%`,
                top: 0,
                transform: "translateX(-50%)",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 4,
              }}
            >
              <div style={{ width: 1, height: 8, background: "var(--color-border)" }} />
              <div
                style={{
                  width: 28, height: 28, borderRadius: "50%",
                  background: "var(--color-bg-elevated)",
                  border: `1.5px solid ${ENTITY_COLOR[ev.entityType ?? "device"]}`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}
              >
                <IconComp
                  style={{ width: 12, height: 12, color: ENTITY_COLOR[ev.entityType ?? "device"] }}
                />
              </div>
              <span
                style={{
                  fontSize: "0.6rem", color: "var(--color-text-subtle)",
                  whiteSpace: "nowrap", fontFamily: "monospace",
                }}
              >
                {ev.entity}
              </span>
            </div>
          );
        })}
      </div>

      {/* Event label pills */}
      <div style={{ position: "relative", marginTop: 52, height: 80 }}>
        {events.map((ev, i) => (
          <button
            key={`pill-${ev.id}`}
            className="timeline-event-pill"
            style={{
              position: "absolute",
              left: `${ev.timestamp}%`,
              top: i % 2 === 0 ? 0 : 28,
              transform: "translateX(-50%)",
              borderColor: selectedId === ev.id
                ? TYPE_COLOR[ev.type]
                : hoveredId === ev.id
                  ? "var(--color-border-bright)"
                  : "var(--color-border)",
              color: selectedId === ev.id
                ? TYPE_COLOR[ev.type]
                : "var(--color-text-body)",
              background: selectedId === ev.id
                ? `${TYPE_COLOR[ev.type]}18`
                : "var(--color-bg-elevated)",
            }}
            onClick={(e) => handleNodeClick(ev, e)}
            onMouseEnter={() => setHoveredId(ev.id)}
            onMouseLeave={() => setHoveredId(null)}
          >
            {ev.label}
          </button>
        ))}
      </div>

      {/* Floating Tooltip */}
      {tooltip && (
        <div
          style={{
            position: "absolute",
            left: `${tooltip.event.timestamp}%`,
            top: "50%",
            transform: "translate(-50%, -130%)",
            background: "var(--color-bg-elevated)",
            border: `1px solid ${TYPE_COLOR[tooltip.event.type]}50`,
            borderRadius: 8,
            padding: "0.5rem 0.75rem",
            minWidth: 160,
            boxShadow: "var(--shadow-elevated)",
            pointerEvents: "none",
            zIndex: 20,
          }}
        >
          <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--color-text-primary)" }}>
            {tooltip.event.label}
          </div>
          <div style={{ fontSize: "0.65rem", color: "var(--color-text-muted)", marginTop: 3 }}>
            {tooltip.event.description}
          </div>
          <div
            style={{
              fontSize: "0.6rem", fontFamily: "monospace",
              color: TYPE_COLOR[tooltip.event.type], marginTop: 4,
              textTransform: "uppercase", letterSpacing: "0.06em",
            }}
          >
            {tooltip.event.type}
            {tooltip.event.risk && ` · ${tooltip.event.risk} risk`}
          </div>
        </div>
      )}
    </div>
  );
}
