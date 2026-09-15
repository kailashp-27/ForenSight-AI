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
  high:   "0 0 10px rgba(239,68,68,0.7)",
  medium: "0 0 10px rgba(245,158,11,0.5)",
  low:    "0 0 10px rgba(16,185,129,0.4)",
};

interface TimelineViewProps {
  events: TimelineEvent[];
  onEventClick?: (event: TimelineEvent) => void;
}

// Each event gets its own dedicated column — wide enough that a label fits without clipping
const COL_W = 150;

export function TimelineView({ events, onEventClick }: TimelineViewProps) {
  const [hoveredId,  setHoveredId]  = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  if (events.length === 0) {
    return (
      <div style={{
        display: "flex", flexDirection: "column", alignItems: "center",
        justifyContent: "center", padding: "3rem 1rem", textAlign: "center", gap: 10,
      }}>
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

  // ── Layout constants ────────────────────────────────────────────────────────
  const STEM_H   = 32;  // vertical line from track node to bubble
  const BUBBLE_D = 30;  // entity bubble diameter
  const ELABEL_H = 14;  // entity text height
  const PILL_H   = 26;  // event label pill height
  const TIME_H   = 12;  // time label height
  const GAP      = 5;   // space between elements
  const NODE_R   = 6;   // track node radius

  // Height of one arm from the track centre out to the farthest label
  const ARM_H = NODE_R + STEM_H + BUBBLE_D + GAP + ELABEL_H + GAP + PILL_H + GAP + TIME_H;

  const totalW = Math.max(events.length * COL_W + 40, 500);
  const totalH = ARM_H * 2 + 8;
  const trackY = ARM_H;  // the horizontal centre of the SVG

  const handleClick = (ev: TimelineEvent, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedId(ev.id);
    onEventClick?.(ev);
  };

  return (
    <div
      ref={containerRef}
      style={{ overflowX: "auto", overflowY: "visible", padding: "0.5rem 1rem 0.75rem", userSelect: "none" }}
      onClick={() => setSelectedId(null)}
    >
      <svg width={totalW} height={totalH} style={{ display: "block", overflow: "visible" }}>

        {/* Track glow + line */}
        <line x1={16} y1={trackY} x2={totalW - 16} y2={trackY}
          stroke="rgba(99,102,241,0.12)" strokeWidth={8} />
        <line x1={16} y1={trackY} x2={totalW - 16} y2={trackY}
          stroke="var(--color-border)" strokeWidth={2} />

        {events.map((ev, i) => {
          const isAbove    = i % 2 === 0;
          const cx         = 20 + i * COL_W + COL_W / 2;
          const typeColor  = TYPE_COLOR[ev.type] ?? "var(--color-accent)";
          const entColor   = ENTITY_COLOR[ev.entityType ?? "device"];
          const IconComp   = ENTITY_ICON[ev.entityType ?? "device"] ?? ENTITY_ICON.device;
          const isHovered  = hoveredId  === ev.id;
          const isSelected = selectedId === ev.id;
          const nodeR      = isSelected ? NODE_R + 3 : isHovered ? NODE_R + 1 : NODE_R;

          const stemStart = isAbove ? trackY - nodeR  : trackY + nodeR;
          const stemEnd   = isAbove ? trackY - STEM_H : trackY + STEM_H;
          const bubbleCy  = isAbove ? stemEnd - BUBBLE_D / 2 : stemEnd + BUBBLE_D / 2;
          const elabelY   = isAbove ? bubbleCy - BUBBLE_D / 2 - GAP - 2 : bubbleCy + BUBBLE_D / 2 + GAP + ELABEL_H;
          const pillY     = isAbove ? elabelY - GAP - PILL_H : elabelY + GAP;
          const timeY     = isAbove ? pillY - GAP : pillY + PILL_H + GAP + TIME_H;

          return (
            <g
              key={ev.id}
              onClick={(e) => handleClick(ev, e)}
              onMouseEnter={() => setHoveredId(ev.id)}
              onMouseLeave={() => setHoveredId(null)}
              style={{ cursor: "pointer" }}
              role="button"
              aria-label={`Event: ${ev.label} at ${ev.time}`}
            >
              {/* Vertical stem */}
              <line x1={cx} y1={stemStart} x2={cx} y2={stemEnd}
                stroke={isHovered || isSelected ? entColor : "var(--color-border)"}
                strokeWidth={1.5}
                style={{ transition: "stroke 0.2s" }} />

              {/* Entity bubble */}
              <circle cx={cx} cy={bubbleCy} r={BUBBLE_D / 2}
                fill="var(--color-bg-elevated)"
                stroke={entColor}
                strokeWidth={isHovered || isSelected ? 2.5 : 1.5}
                style={{ filter: isHovered ? `drop-shadow(0 0 8px ${entColor}80)` : "none", transition: "all 0.2s" }} />
              <foreignObject x={cx - 7} y={bubbleCy - 7} width={14} height={14} style={{ pointerEvents: "none" }}>
                <div style={{ width: 14, height: 14, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <IconComp style={{ width: 11, height: 11, color: entColor }} />
                </div>
              </foreignObject>

              {/* Entity label */}
              <text x={cx} y={elabelY}
                textAnchor="middle"
                fill="var(--color-text-subtle)"
                fontSize={9} fontFamily="monospace"
                style={{ pointerEvents: "none" }}>
                {(ev.entity ?? "").slice(0, 16)}
              </text>

              {/* Event label pill */}
              <foreignObject x={cx - COL_W / 2 + 4} y={pillY} width={COL_W - 8} height={PILL_H + 2}>
                <div style={{
                  background: isSelected ? `${typeColor}1c` : "var(--color-bg-elevated)",
                  border: `1px solid ${isSelected ? typeColor : isHovered ? "var(--color-border-bright)" : "var(--color-border)"}`,
                  borderRadius: 6, padding: "4px 7px",
                  fontSize: "0.595rem", fontWeight: isSelected ? 600 : 400,
                  color: isSelected ? typeColor : "var(--color-text-body)",
                  whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                  textAlign: "center", lineHeight: "1.4",
                  height: PILL_H, boxSizing: "border-box",
                  transition: "all 0.15s",
                  boxShadow: isHovered ? "0 2px 10px rgba(0,0,0,0.4)" : "none",
                }}
                title={`${ev.label}\n${ev.description ?? ""}`}>
                  {ev.label}
                </div>
              </foreignObject>

              {/* Time label */}
              <text x={cx} y={timeY}
                textAnchor="middle"
                fill={isHovered ? typeColor : "var(--color-text-subtle)"}
                fontSize={8.5} fontFamily="monospace"
                fontWeight={isHovered ? 600 : 400}
                opacity={isHovered ? 1 : 0.6}
                style={{ pointerEvents: "none", transition: "all 0.2s" }}>
                {ev.time}
              </text>

              {/* Track node */}
              <circle cx={cx} cy={trackY} r={nodeR}
                fill={typeColor}
                stroke={isSelected ? "white" : "var(--color-bg-canvas)"}
                strokeWidth={isSelected ? 2.5 : 1.5}
                style={{ filter: ev.risk ? (RISK_GLOW[ev.risk] ?? "none") : "none", transition: "all 0.2s" }} />
            </g>
          );
        })}
      </svg>
    </div>
  );
}
