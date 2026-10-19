// frontend/src/components/investigation/ClueList.tsx
// Every clue extracted from every evidence item in the case — grouped by
// evidence, filterable, and flagged when the same clue appears elsewhere.

import React, { useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Link2, Search } from "lucide-react";
import type { CaseClue } from "../../services/forensicApi";

const SOURCE_LABEL: Record<string, string> = {
  AUTO_YOLO: "Object detector",
  AUTO_OCR: "OCR (on-screen text)",
  TRANSCRIPT: "Speech transcript",
  DOCUMENT: "Document text",
  CHAT: "Chat message",
  VLM_ROI: "Regional scan",
  EXIF: "Metadata",
};

const KIND_COLOR: Record<string, string> = {
  PLATE: "#ec4899", PHONE: "#10b981", EMAIL: "#3b82f6", ID: "#a855f7", AMOUNT: "#f59e0b",
  NAME: "#06b6d4", OBJECT: "#8b5cf6", TEXT: "#94a3b8", TIME: "#f97316", LOCATION: "#22c55e",
  DATE: "#eab308", NUMBER: "#64748b", KEYWORD: "#475569",
};

function fmt(ms: number | null): string {
  if (ms == null) return "whole file";
  const t = Math.max(0, Math.round(ms));
  const p = (n: number, w = 2) => String(n).padStart(w, "0");
  return `${p(Math.floor(t / 3_600_000))}:${p(Math.floor((t % 3_600_000) / 60_000))}:${p(Math.floor((t % 60_000) / 1000))}.${p(t % 1000, 3)}`;
}

interface Props {
  clues: CaseClue[] | null;
  onOpen: (evidenceId: string, ts: number | null) => void;
  onShowMatches?: () => void;
}

export function ClueList({ clues, onOpen, onShowMatches }: Props) {
  const [kind, setKind] = useState<string>("ALL");
  const [source, setSource] = useState<string>("ALL");
  const [matchedOnly, setMatchedOnly] = useState(false);
  const [query, setQuery] = useState("");
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const kinds = useMemo(() => [...new Set((clues ?? []).map((c) => c.kind))].sort(), [clues]);
  const sources = useMemo(() => [...new Set((clues ?? []).map((c) => c.source))].sort(), [clues]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (clues ?? []).filter(
      (c) =>
        (kind === "ALL" || c.kind === kind) &&
        (source === "ALL" || c.source === source) &&
        (!matchedOnly || c.match_ids.length > 0) &&
        (!q || c.value.toLowerCase().includes(q) || (c.context ?? "").toLowerCase().includes(q))
    );
  }, [clues, kind, source, matchedOnly, query]);

  const groups = useMemo(() => {
    const m = new Map<string, { name: string; items: CaseClue[] }>();
    for (const c of filtered) {
      const g = m.get(c.evidence_id) ?? { name: c.file_name ?? c.evidence_id, items: [] };
      g.items.push(c);
      m.set(c.evidence_id, g);
    }
    for (const g of m.values()) {
      g.items.sort((a, b) => b.match_ids.length - a.match_ids.length || a.kind.localeCompare(b.kind));
    }
    return [...m.entries()];
  }, [filtered]);

  const chip = (active: boolean): React.CSSProperties => ({
    padding: "3px 10px", borderRadius: 999, fontSize: "0.7rem", fontWeight: 600, cursor: "pointer",
    border: `1px solid ${active ? "var(--color-accent)" : "var(--color-border)"}`,
    background: active ? "var(--color-accent-light)" : "transparent",
    color: active ? "var(--color-text-primary)" : "var(--color-text-muted)",
  });

  if (clues === null) return <p style={{ color: "var(--color-text-muted)", fontSize: "0.85rem" }}>Loading clues…</p>;
  if (clues.length === 0) {
    return (
      <div style={{ textAlign: "center", padding: "3rem 1rem", color: "var(--color-text-subtle)" }}>
        <p style={{ fontSize: "0.9rem", fontWeight: 600, color: "var(--color-text-muted)" }}>No clues yet</p>
        <p style={{ fontSize: "0.75rem", marginTop: 4 }}>
          Run automatic analysis, transcribe audio, or run a regional scan on a video frame.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 10 }}>
        <div style={{ position: "relative" }}>
          <Search size={13} style={{ position: "absolute", left: 9, top: 9, color: "var(--color-text-subtle)" }} />
          <input
            aria-label="Search clues"
            placeholder="Search clues…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ height: 31, width: 200, paddingLeft: 28, background: "var(--color-bg-input)",
                     color: "var(--color-text-primary)", border: "1px solid var(--color-border-bright)",
                     borderRadius: 6, fontSize: "0.78rem" }}
          />
        </div>
        <button style={chip(kind === "ALL")} onClick={() => setKind("ALL")}>All types</button>
        {kinds.map((k) => (
          <button key={k} style={chip(kind === k)} onClick={() => setKind(k)}>{k}</button>
        ))}
        <span style={{ width: 1, height: 18, background: "var(--color-border)" }} />
        <select
          aria-label="Filter by source"
          value={source}
          onChange={(e) => setSource(e.target.value)}
          style={{ height: 31, background: "var(--color-bg-input)", color: "var(--color-text-body)",
                   border: "1px solid var(--color-border-bright)", borderRadius: 6, fontSize: "0.75rem", padding: "0 6px" }}
        >
          <option value="ALL">All sources</option>
          {sources.map((s) => <option key={s} value={s}>{SOURCE_LABEL[s] ?? s}</option>)}
        </select>
        <label style={{ fontSize: "0.75rem", color: "var(--color-text-body)", display: "flex", gap: 5, alignItems: "center" }}>
          <input type="checkbox" checked={matchedOnly} onChange={(e) => setMatchedOnly(e.target.checked)} />
          Only clues found in other evidence
        </label>
        <span style={{ marginLeft: "auto", fontSize: "0.72rem", color: "var(--color-text-muted)", fontFamily: "monospace" }}>
          {filtered.length} of {clues.length}
        </span>
      </div>

      {groups.length === 0 && <p style={{ fontSize: "0.8rem", color: "var(--color-text-muted)" }}>No clues match the filters.</p>}

      {groups.map(([evId, g]) => {
        const isCollapsed = collapsed[evId];
        return (
          <section key={evId} className="card" style={{ marginBottom: 10, overflow: "hidden" }}>
            <button
              onClick={() => setCollapsed({ ...collapsed, [evId]: !isCollapsed })}
              style={{ width: "100%", display: "flex", alignItems: "center", gap: 8, padding: "0.55rem 0.8rem",
                       background: "var(--color-bg-elevated)", border: "none", cursor: "pointer", textAlign: "left" }}
            >
              {isCollapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
              <strong style={{ fontSize: "0.82rem", color: "var(--color-text-primary)" }}>{g.name}</strong>
              <span style={{ fontSize: "0.7rem", color: "var(--color-text-muted)" }}>
                {g.items.length} clue(s) · {g.items.filter((c) => c.match_ids.length).length} shared
              </span>
            </button>
            {!isCollapsed && (
              <div>
                {g.items.map((c) => {
                  const matched = c.match_ids.length > 0;
                  return (
                    <div
                      key={c.id}
                      data-testid="clue-row"
                      style={{ display: "grid", gridTemplateColumns: "76px 1fr auto", gap: 10, padding: "0.5rem 0.8rem",
                               borderTop: "1px solid var(--color-border-subtle)",
                               background: matched ? "rgba(245,158,11,0.06)" : "transparent" }}
                    >
                      <span style={{ fontSize: "0.65rem", fontWeight: 700, color: KIND_COLOR[c.kind] ?? "#94a3b8",
                                     border: `1px solid ${KIND_COLOR[c.kind] ?? "#94a3b8"}`, borderRadius: 4,
                                     padding: "1px 5px", alignSelf: "start", textAlign: "center" }}>
                        {c.kind}
                      </span>
                      <div style={{ minWidth: 0 }}>
                        <button
                          onClick={() => onOpen(c.evidence_id, c.timestamp_ms)}
                          style={{ background: "none", border: "none", padding: 0, cursor: "pointer", textAlign: "left",
                                   fontFamily: c.kind === "OBJECT" || c.kind === "NAME" ? "inherit" : "monospace",
                                   fontSize: "0.85rem", fontWeight: 600, color: "var(--color-text-primary)" }}
                        >
                          {c.value}
                        </button>
                        {c.context && (
                          <div style={{ fontSize: "0.7rem", color: "var(--color-text-muted)", marginTop: 2, lineHeight: 1.4,
                                        overflow: "hidden", textOverflow: "ellipsis", display: "-webkit-box",
                                        WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>
                            {c.context}
                          </div>
                        )}
                      </div>
                      <div style={{ textAlign: "right", fontSize: "0.68rem", color: "var(--color-text-subtle)", whiteSpace: "nowrap" }}>
                        <div>{SOURCE_LABEL[c.source] ?? c.source} · {Math.round(c.confidence * 100)}%</div>
                        <div style={{ fontFamily: "monospace" }}>{fmt(c.timestamp_ms)}</div>
                        {matched && (
                          <button
                            onClick={onShowMatches}
                            style={{ marginTop: 2, background: "none", border: "none", color: "#f59e0b", fontWeight: 700,
                                     fontSize: "0.68rem", cursor: "pointer", display: "inline-flex", gap: 3, alignItems: "center" }}
                          >
                            <Link2 size={11} /> in {c.match_ids.length} match{c.match_ids.length > 1 ? "es" : ""}
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}
