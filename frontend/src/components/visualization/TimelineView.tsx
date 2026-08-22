// frontend/src/components/visualization/TimelineView.tsx
import React, { useRef, useState } from "react";
import { User, Monitor, Globe, AlertTriangle, FileText } from "lucide-react";

export interface TimelineEvent {
  id: string;
  label: string;
  type: "login" | "transaction" | "detection" | "document" | "alert";
  time: string;
  timestamp: number; // 0–100 position %
  entity?: string;
  entityType?: "person" | "device" | "account" | "network";
  risk?: "high" | "medium" | "low";
  description?: string;
}

const MOCK_EVENTS: TimelineEvent[] = [
  { id: "E01", label: "Login surge", type: "login",       time: "00:12", timestamp: 5,  entity: "KP-2234",     entityType: "person",  risk: "high",   description: "23 logins in 4h from 7 IPs" },
  { id: "E02", label: "VPN detected", type: "alert",      time: "01:08", timestamp: 18, entity: "IP-45.32.x",  entityType: "network", risk: "high",   description: "Known VPN exit node" },
  { id: "E03", label: "CCTV object", type: "detection",   time: "02:14", timestamp: 30, entity: "CAM-LOBBY",   entityType: "device",  risk: "high",   description: "YOLOv8: possible firearm — 78%" },
  { id: "E04", label: "Tx cluster", type: "transaction",  time: "03:41", timestamp: 46, entity: "ACC-887",     entityType: "account", risk: "high",   description: "14 split transactions ₹4.7L" },
  { id: "E05", label: "Doc upload", type: "document",     time: "06:22", timestamp: 60, entity: "Analyst KP",  entityType: "person",  risk: "low",    description: "Bank statement uploaded" },
  { id: "E06", label: "Behavioral match", type: "alert",  time: "08:15", timestamp: 72, entity: "DEV-4420",    entityType: "device",  risk: "medium", description: "5 accounts — 94% fingerprint similarity" },
  { id: "E07", label: "RAG summary", type: "document",    time: "10:00", timestamp: 87, entity: "AI Engine",   entityType: "device",  risk: "low",    description: "Chronological timeline generated" },
];

const TYPE_COLOR: Record<string, string> = {
  login:       "#3b82f6",
  transaction: "#f59e0b",
  detection:   "#ef4444",
  document:    "#10b981",
  alert:       "#ec4899",
};

const ENTITY_ICON: Record<string, React.FC<{ style?: React.CSSProperties }>> = {
  person:  ({ style }) => <User   style={style} />,
  device:  ({ style }) => <Monitor style={style} />,
  account: ({ style }) => <Globe  style={style} />,
  network: ({ style }) => <Globe  style={style} />,
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
  y: number;
}

interface TimelineViewProps {
  onEventClick?: (event: TimelineEvent) => void;
}

export function TimelineView({ onEventClick }: TimelineViewProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleNodeClick = (ev: TimelineEvent, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedId(ev.id);
    onEventClick?.(ev);
  };

  return (
    <div
      style={{
        position: "relative",
        padding: "1.5rem 2rem",
        userSelect: "none",
      }}
      ref={containerRef}
      onClick={() => setSelectedId(null)}
    >
      {/* Time Labels row */}
      <div style={{ position: "relative", height: 20, marginBottom: 8 }}>
        {MOCK_EVENTS.map((ev) => (
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
        {MOCK_EVENTS.filter((_, i) => i % 2 === 0).map((ev) => {
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
              {/* Connector line to timeline */}
              <div style={{ width: 1, height: 8, background: "var(--color-border)" }} />
            </div>
          );
        })}
      </div>

      {/* Timeline track */}
      <div className="timeline-track" style={{ position: "relative", margin: "0 0" }}>
        {/* Event nodes on the track */}
        {MOCK_EVENTS.map((ev) => (
          <div
            key={`node-${ev.id}`}
            className="timeline-node"
            style={{
              left: `${ev.timestamp}%`,
              background: TYPE_COLOR[ev.type] ?? "var(--color-accent)",
              borderColor: selectedId === ev.id ? "white" : "var(--color-bg-canvas)",
              width: selectedId === ev.id ? 14 : hoveredId === ev.id ? 12 : 10,
              height: selectedId === ev.id ? 14 : hoveredId === ev.id ? 12 : 10,
              boxShadow: ev.risk ? RISK_GLOW[ev.risk] : "none",
              zIndex: selectedId === ev.id ? 10 : 1,
            }}
            onClick={(e) => handleNodeClick(ev, e)}
            onMouseEnter={() => { setHoveredId(ev.id); setTooltip({ event: ev, x: ev.timestamp, y: 0 }); }}
            onMouseLeave={() => { setHoveredId(null); setTooltip(null); }}
            role="button"
            tabIndex={0}
            aria-label={`Timeline event: ${ev.label}`}
            onKeyDown={(e) => e.key === "Enter" && handleNodeClick(ev, e as any)}
          />
        ))}
      </div>

      {/* Bottom entities + event pills */}
      <div style={{ position: "relative", marginTop: 0 }}>
        {MOCK_EVENTS.filter((_, i) => i % 2 !== 0).map((ev) => {
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

      {/* Event label pills below the bottom entities */}
      <div style={{ position: "relative", marginTop: 52 }}>
        {MOCK_EVENTS.map((ev, i) => (
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
          </div>
        </div>
      )}
    </div>
  );
}
