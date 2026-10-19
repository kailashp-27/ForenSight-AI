// frontend/src/components/investigation/EventTimeline.tsx
// One wall-clock timeline: chat messages, times mentioned in text, speech and
// video frames. Aligned groups (close in time + a shared place/name/item) are
// listed on the right; events with no time are shown beneath, linked by content.

import React, { useEffect, useRef } from "react";
import * as vis from "vis-timeline/standalone";
import type { Timeline } from "vis-timeline/standalone";
import "vis-timeline/styles/vis-timeline-graph2d.min.css";
import { Clock, Link2 } from "lucide-react";
import type { EventTimelineData, TimelineEvent } from "../../services/forensicApi";

const visMoment = (vis as unknown as { moment: { utc: (d: unknown) => unknown } }).moment;

const KIND_STYLE: Record<string, string> = {
  message: "background:#1e3a8a;border-color:#3b82f6;color:#eff6ff;",
  mention: "background:#4c1d95;border-color:#a855f7;color:#faf5ff;border-style:dashed;",
  speech: "background:#065f46;border-color:#10b981;color:#ecfdf5;",
  scan: "background:#78350f;border-color:#f59e0b;color:#fffbeb;",
  video: "background:#1e293b;border-color:#64748b;color:#cbd5e1;",
  document: "background:#1e293b;border-color:#475569;color:#cbd5e1;",
};
const KIND_LABEL: Record<string, string> = {
  message: "Chat message", mention: "Time referred to", speech: "Speech", scan: "Video frame / scan",
  video: "Recording start", document: "Document",
};

const esc = (s: string) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));

interface Props {
  data: EventTimelineData | null;
  onOpen: (evidenceId: string, fileType: string | null, offsetMs: number | null) => void;
}

export function EventTimeline({ data, onOpen }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const tlRef = useRef<Timeline | null>(null);

  const dated = (data?.events ?? []).filter((e) => e.time);
  const undated = (data?.events ?? []).filter((e) => !e.time);

  useEffect(() => {
    if (!ref.current || !data || dated.length === 0) return;
    const files = [...new Map(dated.map((e) => [e.evidence_id, e.file_name])).entries()];
    const groups = files.map(([id, name]) => ({ id, content: `<span style="font-size:11px">${esc(name)}</span>` }));
    const items = dated.map((e) => ({
      id: e.id,
      group: e.evidence_id,
      start: new Date(e.time + "Z"),
      type: "box",
      content: esc(e.label.length > 34 ? e.label.slice(0, 33) + "…" : e.label),
      title: esc(`${e.time!.replace("T", " ")}${e.assumed_date ? " (date assumed)" : ""}\n${KIND_LABEL[e.kind] ?? e.kind}\n${e.text}`),
      style: KIND_STYLE[e.kind] ?? KIND_STYLE.document,
    }));

    const times = dated.map((e) => new Date(e.time + "Z").getTime());
    const pad = 10 * 60 * 1000;
    const tl = new vis.Timeline(ref.current, items, groups, {
      moment: (d: unknown) => visMoment.utc(d) as never,
      start: new Date(Math.min(...times) - pad),
      end: new Date(Math.max(...times) + pad),
      stack: true,
      showCurrentTime: false,
      orientation: { axis: "top" },
      margin: { item: 6 },
      zoomMin: 30 * 1000,
    });
    tl.on("select", (p: { items: string[] }) => {
      const e = dated.find((x) => x.id === p.items?.[0]);
      if (e) onOpen(e.evidence_id, e.file_type, e.offset_ms);
    });
    tlRef.current = tl;
    return () => {
      tl.destroy();
      tlRef.current = null;
    };
  }, [data]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!data) return <p style={{ color: "var(--color-text-muted)", fontSize: "0.85rem" }}>Loading timeline…</p>;
  if (data.events.length === 0) {
    return (
      <div style={{ textAlign: "center", padding: "3rem 1rem", color: "var(--color-text-subtle)" }}>
        <Clock size={34} style={{ opacity: 0.6, margin: "0 auto 8px" }} />
        <p style={{ fontSize: "0.9rem", fontWeight: 600, color: "var(--color-text-muted)" }}>No events yet</p>
        <p style={{ fontSize: "0.75rem", marginTop: 4 }}>
          Upload a chat export, transcribe audio, or run a regional scan on a video that has a burned-in clock.
        </p>
      </div>
    );
  }

  const chip = (color: string, text: string) => (
    <span key={text} style={{ fontSize: "0.62rem", color, border: `1px solid ${color}`, borderRadius: 999, padding: "0 7px" }}>{text}</span>
  );
  const byId = new Map(data.events.map((e) => [e.id, e]));

  return (
    <div data-testid="event-timeline">
      {data.notes.map((n) => (
        <p key={n} style={{ fontSize: "0.68rem", color: "var(--color-text-subtle)", marginBottom: 2 }}>{n}</p>
      ))}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", margin: "6px 0 10px" }}>
        {Object.entries(KIND_LABEL).map(([k, label]) => (
          <span key={k} style={{ fontSize: "0.65rem", color: "var(--color-text-body)", display: "inline-flex", gap: 4, alignItems: "center" }}>
            <span style={{ width: 10, height: 10, borderRadius: 2, display: "inline-block",
                           background: KIND_STYLE[k].match(/background:(#\w+)/)?.[1] }} />
            {label}
          </span>
        ))}
      </div>

      <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          {dated.length > 0 ? (
            <div ref={ref} data-testid="event-vis" className="fs-timeline" />
          ) : (
            <p style={{ fontSize: "0.8rem", color: "var(--color-text-muted)" }}>
              No event has a recoverable clock time. Add a recording start time to a video, or upload a chat export.
            </p>
          )}
        </div>

        <aside style={{ width: 330, flexShrink: 0 }}>
          <h4 style={{ fontSize: "0.8rem", fontWeight: 700, color: "var(--color-text-primary)", marginBottom: 6 }}>
            Aligned across evidence ({data.groups.length})
          </h4>
          {data.groups.length === 0 && (
            <p style={{ fontSize: "0.72rem", color: "var(--color-text-subtle)" }}>
              No events from different files fall close together and share a place, person or item.
            </p>
          )}
          {data.groups.map((g) => (
            <div key={g.id} className="card" data-testid="aligned-group" style={{ padding: "0.55rem 0.7rem", marginBottom: 8 }}>
              <div style={{ fontFamily: "monospace", fontSize: "0.78rem", color: "#22d3ee" }}>
                {g.start.slice(11, 16)}{g.end !== g.start ? ` – ${g.end.slice(11, 16)}` : ""}
                {g.assumed_date && <span style={{ color: "#f59e0b", marginLeft: 6, fontSize: "0.62rem" }}>date assumed</span>}
              </div>
              <div style={{ fontSize: "0.72rem", color: "var(--color-text-body)", margin: "3px 0" }}>{g.summary}</div>
              <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                {g.shared_terms.map((t) => chip("#f59e0b", `${t.kind.toLowerCase()}: ${t.value}`))}
              </div>
              <div style={{ marginTop: 5, display: "flex", flexDirection: "column", gap: 2 }}>
                {[...g.event_ids, ...g.linked_undated_ids].map((id) => {
                  const e = byId.get(id);
                  if (!e) return null;
                  return (
                    <button key={id} onClick={() => onOpen(e.evidence_id, e.file_type, e.offset_ms)}
                            style={{ textAlign: "left", background: "none", border: "none", cursor: "pointer",
                                     fontSize: "0.68rem", color: "var(--color-text-muted)", padding: "1px 0" }}>
                      <span style={{ fontFamily: "monospace", color: e.time ? "#22d3ee" : "#94a3b8" }}>
                        {e.time ? e.time.slice(11, 16) : "no time"}
                      </span>{" "}
                      <strong style={{ color: "var(--color-text-primary)" }}>{e.file_name}</strong> — {e.text.slice(0, 60)}
                      {!e.time && <Link2 size={10} style={{ marginLeft: 4, color: "#f59e0b" }} aria-label="linked by content" />}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </aside>
      </div>

      {undated.length > 0 && (
        <section style={{ marginTop: 14 }}>
          <h4 style={{ fontSize: "0.8rem", fontWeight: 700, color: "var(--color-text-primary)", marginBottom: 6 }}>
            No clock time ({undated.length}) — linked to the timeline only by shared content
          </h4>
          <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
            {undated.slice(0, 40).map((e: TimelineEvent) => (
              <button key={e.id} onClick={() => onOpen(e.evidence_id, e.file_type, e.offset_ms)}
                      style={{ textAlign: "left", background: "var(--color-bg-card)", border: "1px solid var(--color-border)",
                               borderRadius: 6, padding: "4px 8px", cursor: "pointer", fontSize: "0.72rem",
                               color: "var(--color-text-body)" }}>
                <strong style={{ color: "var(--color-text-primary)" }}>{e.file_name}</strong>{" "}
                <span style={{ color: "var(--color-text-subtle)" }}>{KIND_LABEL[e.kind] ?? e.kind}</span> — {e.text}
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
