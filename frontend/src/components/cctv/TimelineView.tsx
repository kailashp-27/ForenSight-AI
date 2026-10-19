// frontend/src/components/cctv/TimelineView.tsx
// Vis.js multi-track timeline: one track per evidence clip, with verified
// findings and transcript segments. Time is the offset from each clip's
// start (CCTV exports share no absolute clock), rendered as HH:MM:SS.

import React, { useEffect, useRef } from "react";
import * as vis from "vis-timeline/standalone";
import type { Timeline } from "vis-timeline/standalone";
import "vis-timeline/styles/vis-timeline-graph2d.min.css";
import { Clock } from "lucide-react";
import type { CaseTimeline } from "../../services/forensicApi";

interface TimelineViewProps {
  data: CaseTimeline | null;
  /** Clicking an item seeks to it (evidenceId, offset in ms). */
  onSelect?: (evidenceId: string, startMs: number) => void;
  /** Evidence currently loaded in the player (its track is highlighted). */
  activeEvidenceId?: string;
}

// The standalone bundle exports its own moment instance, but its typings omit it.
const visMoment = (vis as unknown as { moment: { utc: (d: unknown) => unknown } }).moment;

const KIND_STYLE: Record<string, string> = {
  verified: "background:#065f46;border-color:#10b981;color:#ecfdf5;",
  draft: "background:#78350f;border-color:#f59e0b;color:#fffbeb;",
  transcript: "background:#1e293b;border-color:#475569;color:#cbd5e1;",
};

export function TimelineView({ data, onSelect, activeEvidenceId }: TimelineViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const timelineRef = useRef<Timeline | null>(null);

  const empty = !data || data.items.length === 0;

  useEffect(() => {
    if (!containerRef.current || !data || empty) return;

    const groups = data.tracks.map((t) => ({
        id: t.id,
        content: `<span style="font-size:11px">${escapeHtml(t.name)}</span>`,
        className: t.id === activeEvidenceId ? "fs-track-active" : "",
      }));

    const items = data.items.map((it) => {
        const kind = it.kind === "transcript" ? "transcript" : it.verified ? "verified" : "draft";
        const conf = it.confidence != null ? ` · ${Math.round(it.confidence * 100)}%` : "";
        return {
          id: it.id,
          group: it.track,
          start: it.start_ms,
          end: it.end_ms ?? undefined,
          type: it.end_ms ? "range" : "box",
          content: escapeHtml(it.label || "(untitled)") + conf,
          title: escapeHtml(`${it.timestamp_str}${it.text ? " — " + it.text : ""}`),
          style: KIND_STYLE[kind],
        };
      });

    const maxMs = Math.max(...data.items.map((i) => i.end_ms ?? i.start_ms), 10_000);

    const timeline = new vis.Timeline(containerRef.current, items, groups, {
      // Treat the numeric axis as elapsed time: UTC so 90 s renders 00:01:30.
      moment: (date: unknown) => visMoment.utc(date) as never,
      format: {
        minorLabels: { millisecond: "SSS", second: "HH:mm:ss", minute: "HH:mm:ss", hour: "HH:mm:ss", day: "HH:mm", month: "HH:mm", year: "HH:mm" },
        majorLabels: { millisecond: "HH:mm:ss", second: "HH:mm", minute: "HH:mm", hour: "HH:mm", day: "", month: "", year: "" },
      },
      min: 0,
      max: maxMs + Math.max(2_000, maxMs * 0.1),
      start: 0,
      end: maxMs + Math.max(2_000, maxMs * 0.1),
      zoomMin: 500,
      stack: true,
      showCurrentTime: false,
      orientation: { axis: "top" },
      margin: { item: 6 },
    });

    timeline.on("select", (props: { items: string[] }) => {
      const id = props.items?.[0];
      const item = data.items.find((i) => i.id === id);
      if (item) onSelect?.(item.track, item.start_ms);
    });

    timelineRef.current = timeline;
    return () => {
      timeline.destroy();
      timelineRef.current = null;
    };
  }, [data, empty, activeEvidenceId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (empty) {
    return (
      <div
        style={{
          height: "100%", minHeight: 180, display: "flex", flexDirection: "column", alignItems: "center",
          justifyContent: "center", textAlign: "center", color: "var(--color-text-subtle)", padding: "1rem",
        }}
      >
        <Clock size={34} style={{ opacity: 0.6, marginBottom: 8 }} />
        <p style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--color-text-muted)" }}>Timeline is empty</p>
        <p style={{ fontSize: "0.72rem", marginTop: 4, maxWidth: 320 }}>
          Verified findings and transcript segments appear here, one track per clip.
        </p>
      </div>
    );
  }

  return (
    <div style={{ height: "100%" }}>
      <style>{`
        .fs-timeline .vis-timeline { border: 1px solid var(--color-border); border-radius: 8px; background: var(--color-bg-elevated); color: var(--color-text-body); font-family: inherit; }
        .fs-timeline .vis-item { border-radius: 6px; font-size: 11px; border-width: 1px; }
        .fs-timeline .vis-labelset .vis-label, .fs-timeline .vis-time-axis .vis-text { color: var(--color-text-muted); }
        .fs-timeline .vis-panel.vis-center, .fs-timeline .vis-panel.vis-left, .fs-timeline .vis-panel.vis-top, .fs-timeline .vis-panel.vis-bottom { border-color: var(--color-border); }
        .fs-timeline .vis-time-axis .vis-grid.vis-minor, .fs-timeline .vis-time-axis .vis-grid.vis-major { border-color: var(--color-border-subtle); }
        .fs-timeline .fs-track-active { background: var(--color-accent-light); }
      `}</style>
      <div className="fs-timeline" style={{ height: "100%" }}>
        <div ref={containerRef} data-testid="timeline" />
      </div>
      <div style={{ display: "flex", gap: 12, marginTop: 6, fontSize: "0.65rem", color: "var(--color-text-muted)" }}>
        <Legend color="#10b981" label="Verified finding" />
        <Legend color="#f59e0b" label="Unverified draft" />
        <Legend color="#475569" label="Machine transcript" />
      </div>
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
      <span style={{ width: 10, height: 10, borderRadius: 2, background: color, display: "inline-block" }} />
      {label}
    </span>
  );
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));
}
