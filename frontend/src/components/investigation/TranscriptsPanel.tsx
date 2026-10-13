// frontend/src/components/investigation/TranscriptsPanel.tsx
// All speech transcripts and document text in the case, with the clues inside
// each passage highlighted — amber where the same clue appears in other evidence.

import React, { useMemo, useState } from "react";
import { FileAudio, FileText, FileVideo, Link2, Search } from "lucide-react";
import type { CaseTranscripts, TranscriptChunk, TranscriptTerm } from "../../services/forensicApi";

function fmt(ms: number | null): string {
  if (ms == null) return "";
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** Split text into plain and highlighted runs for the given terms. */
function highlight(text: string, terms: TranscriptTerm[]): React.ReactNode[] {
  const usable = terms.filter((t) => t.value.trim().length >= 3).sort((a, b) => b.value.length - a.value.length);
  if (!usable.length) return [text];
  const re = new RegExp(`(${usable.map((t) => esc(t.value).replace(/\s+/g, "\\s+")).join("|")})`, "gi");
  const byLower = new Map(usable.map((t) => [t.value.toLowerCase().replace(/\s+/g, " "), t]));
  return text.split(re).map((part, i) => {
    const t = byLower.get(part.toLowerCase().replace(/\s+/g, " "));
    if (!t) return <React.Fragment key={i}>{part}</React.Fragment>;
    const matched = t.matches.length > 0;
    return (
      <mark
        key={i}
        title={matched ? `${t.kind}: also in ${t.matches.flatMap((m) => m.also_in).join(", ")}` : `${t.kind} (not found elsewhere)`}
        style={{
          background: matched ? "rgba(245,158,11,0.28)" : "rgba(34,211,238,0.12)",
          color: "inherit", borderBottom: `2px solid ${matched ? "#f59e0b" : "#22d3ee"}`, padding: "0 1px",
        }}
      >
        {part}
      </mark>
    );
  });
}

interface Props {
  data: CaseTranscripts | null;
  onOpen: (evidenceId: string, fileType: string, ts: number | null) => void;
  onAnalyze: (evidenceId: string) => void;
}

export function TranscriptsPanel({ data, onOpen, onAnalyze }: Props) {
  const [query, setQuery] = useState("");
  const [matchedOnly, setMatchedOnly] = useState(false);

  const view = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (data?.evidence ?? []).map((ev) => ({
      ...ev,
      chunks: ev.chunks.filter(
        (c) => (!matchedOnly || c.terms.some((t) => t.matches.length)) && (!q || c.text.toLowerCase().includes(q))
      ),
    }));
  }, [data, query, matchedOnly]);

  if (!data) return <p style={{ color: "var(--color-text-muted)", fontSize: "0.85rem" }}>Loading transcripts…</p>;

  const icon = (t: string) =>
    t === "AUDIO" ? <FileAudio size={14} /> : t === "VIDEO" ? <FileVideo size={14} /> : <FileText size={14} />;

  const chipRow = (c: TranscriptChunk) => {
    const matched = c.terms.filter((t) => t.matches.length);
    if (!matched.length) return null;
    return (
      <div style={{ display: "flex", gap: 5, flexWrap: "wrap", marginTop: 6 }}>
        {matched.map((t, i) => (
          <span
            key={i}
            title={t.matches.map((m) => `${m.strength} ${Math.round(m.score * 100)}% — also in ${m.also_in.join(", ")}`).join("\n")}
            style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: "0.68rem", fontWeight: 600,
                     color: "#fbbf24", background: "rgba(245,158,11,0.12)", border: "1px solid rgba(245,158,11,0.4)",
                     borderRadius: 999, padding: "1px 8px" }}
          >
            <Link2 size={10} /> {t.kind}: {t.value} → {[...new Set(t.matches.flatMap((m) => m.also_in))].join(", ") || "other evidence"}
          </span>
        ))}
      </div>
    );
  };

  return (
    <div>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
        <div style={{ position: "relative" }}>
          <Search size={13} style={{ position: "absolute", left: 9, top: 9, color: "var(--color-text-subtle)" }} />
          <input
            aria-label="Search transcripts"
            placeholder="Search all transcripts…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ height: 31, width: 240, paddingLeft: 28, background: "var(--color-bg-input)",
                     color: "var(--color-text-primary)", border: "1px solid var(--color-border-bright)",
                     borderRadius: 6, fontSize: "0.78rem" }}
          />
        </div>
        <label style={{ fontSize: "0.75rem", color: "var(--color-text-body)", display: "flex", gap: 5, alignItems: "center" }}>
          <input type="checkbox" checked={matchedOnly} onChange={(e) => setMatchedOnly(e.target.checked)} />
          Only passages with clues found in other evidence
        </label>
        <span style={{ marginLeft: "auto", fontSize: "0.72rem", color: "var(--color-text-muted)", fontFamily: "monospace" }}>
          {data.totals.passages} passages · {data.totals.matched_terms} shared clue mention(s)
        </span>
      </div>

      {view.map((ev) => (
        <section key={ev.evidence_id} className="card" style={{ marginBottom: 12, overflow: "hidden" }}>
          <header style={{ display: "flex", alignItems: "center", gap: 8, padding: "0.55rem 0.8rem",
                           background: "var(--color-bg-elevated)" }}>
            <span style={{ color: "var(--color-accent)" }}>{icon(ev.file_type)}</span>
            <strong style={{ fontSize: "0.82rem", color: "var(--color-text-primary)" }}>{ev.file_name}</strong>
            <span style={{ fontSize: "0.68rem", color: "var(--color-text-muted)" }}>
              {ev.file_type} · {ev.chunks.length} passage(s)
            </span>
            <button
              onClick={() => onOpen(ev.evidence_id, ev.file_type, null)}
              style={{ marginLeft: "auto", background: "none", border: "none", color: "var(--color-accent)",
                       fontSize: "0.72rem", cursor: "pointer" }}
            >
              Open evidence →
            </button>
          </header>

          {ev.chunks.length === 0 ? (
            <div style={{ padding: "0.8rem", fontSize: "0.76rem", color: "var(--color-text-muted)", display: "flex",
                          gap: 10, alignItems: "center", flexWrap: "wrap" }}>
              {data.evidence.find((e) => e.evidence_id === ev.evidence_id)!.chunks.length === 0
                ? ev.file_type === "AUDIO" || ev.file_type === "VIDEO"
                  ? "No speech transcript for this file yet."
                  : "No text has been extracted from this file yet."
                : "No passages match the filters."}
              {data.evidence.find((e) => e.evidence_id === ev.evidence_id)!.chunks.length === 0 &&
                (ev.file_type === "DOCUMENT" || ev.file_type === "IMAGE") && (
                  <button
                    onClick={() => onAnalyze(ev.evidence_id)}
                    style={{ height: 28, padding: "0 10px", borderRadius: 6, border: "1px solid var(--color-accent)",
                             background: "var(--color-accent)", color: "#fff", fontSize: "0.72rem", fontWeight: 700, cursor: "pointer" }}
                  >
                    Extract text now
                  </button>
                )}
            </div>
          ) : (
            ev.chunks.map((c) => (
              <div
                key={c.id}
                data-testid="transcript-chunk"
                onClick={() => onOpen(ev.evidence_id, ev.file_type, c.start_ms)}
                style={{ padding: "0.6rem 0.8rem", borderTop: "1px solid var(--color-border-subtle)", cursor: "pointer" }}
              >
                <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
                  <span style={{ fontFamily: "monospace", fontSize: "0.68rem", color: "#22d3ee", minWidth: 44 }}>
                    {c.page ? `p.${c.page}` : fmt(c.start_ms)}
                  </span>
                  {c.ocr && (
                    <span style={{ fontSize: "0.6rem", color: "#f59e0b", border: "1px solid rgba(245,158,11,0.4)",
                                   borderRadius: 4, padding: "0 4px" }} title="Read by OCR from a scanned page">
                      OCR
                    </span>
                  )}
                  <p style={{ fontSize: "0.82rem", color: "var(--color-text-body)", lineHeight: 1.6, flex: 1, whiteSpace: "pre-wrap" }}>
                    {highlight(c.text, c.terms)}
                  </p>
                </div>
                {chipRow(c)}
              </div>
            ))
          )}
        </section>
      ))}
    </div>
  );
}
