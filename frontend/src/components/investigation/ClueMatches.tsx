// frontend/src/components/investigation/ClueMatches.tsx
// Cross-evidence matches, strongest first. Each card lists every source
// observation so the investigator can jump straight to it.

import React, { useState } from "react";
import { AlertTriangle, BadgeCheck, ChevronDown, ChevronRight, ExternalLink, Link2 } from "lucide-react";
import type { ClueMatch, MatchStrength } from "../../services/forensicApi";

const COLORS: Record<MatchStrength, { fg: string; bg: string }> = {
  STRONG: { fg: "#10b981", bg: "rgba(16,185,129,0.12)" },
  MEDIUM: { fg: "#f59e0b", bg: "rgba(245,158,11,0.12)" },
  WEAK: { fg: "#94a3b8", bg: "rgba(148,163,184,0.12)" },
};

interface Props {
  matches: ClueMatch[];
  highlightedId?: string | null;
  onHighlight?: (m: ClueMatch | null) => void;
  onOpenMember: (evidenceId: string, fileType: string | null, timestampMs: number | null) => void;
}

export function ClueMatches({ matches, highlightedId, onHighlight, onOpenMember }: Props) {
  const [showWeak, setShowWeak] = useState(false);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const keywords = matches.filter((m) => m.kind === "KEYWORD");
  const strong = matches.filter((m) => m.kind !== "KEYWORD" && m.strength !== "WEAK");
  const weak = matches.filter((m) => m.kind !== "KEYWORD" && m.strength === "WEAK");
  const [kwOpen, setKwOpen] = useState(true);
  const [kwQuery, setKwQuery] = useState("");
  const kwShown = keywords.filter((m) => !kwQuery.trim() || m.value.toLowerCase().includes(kwQuery.trim().toLowerCase()));
  const list = showWeak ? [...strong, ...weak] : strong;

  if (matches.length === 0) {
    return (
      <div style={{ textAlign: "center", padding: "3rem 1rem", color: "var(--color-text-subtle)" }}>
        <Link2 size={36} style={{ opacity: 0.6, margin: "0 auto 10px" }} />
        <p style={{ fontSize: "0.9rem", fontWeight: 600, color: "var(--color-text-muted)" }}>No shared clues found yet</p>
        <p style={{ fontSize: "0.75rem", marginTop: 4 }}>
          Run automatic analysis. A clue is reported when the same plate, phone, e-mail, ID or object appears in two or
          more evidence items.
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {list.length === 0 && weak.length > 0 && (
        <p style={{ fontSize: "0.8rem", color: "var(--color-text-muted)" }}>
          Only weak appearance-only similarities were found. They are hidden by default.
        </p>
      )}
      {list.map((m) => {
        const c = COLORS[m.strength];
        const expanded = open[m.id] ?? m.strength === "STRONG";
        return (
          <article
            key={m.id}
            data-testid="match-card"
            onMouseEnter={() => onHighlight?.(m)}
            onMouseLeave={() => onHighlight?.(null)}
            style={{
              background: "var(--color-bg-elevated)",
              border: `1px solid ${highlightedId === m.id ? c.fg : "var(--color-border)"}`,
              borderLeft: `4px solid ${c.fg}`,
              borderRadius: 8,
              padding: "0.7rem 0.85rem",
            }}
          >
            <header style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <button
                onClick={() => setOpen({ ...open, [m.id]: !expanded })}
                aria-label={expanded ? "Collapse match" : "Expand match"}
                style={{ background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer", padding: 0 }}
              >
                {expanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
              </button>
              <span style={{ fontSize: "0.65rem", fontWeight: 700, color: c.fg, background: c.bg, borderRadius: 999, padding: "2px 8px" }}>
                {m.strength}
              </span>
              <span style={{ fontSize: "0.65rem", color: "var(--color-text-muted)", border: "1px solid var(--color-border)", borderRadius: 4, padding: "0 5px" }}>
                {m.kind}
              </span>
              <strong style={{ fontFamily: m.kind === "OBJECT" ? "inherit" : "monospace", fontSize: "0.92rem", color: "var(--color-text-primary)" }}>
                {m.value}
              </strong>
              <span style={{ marginLeft: "auto", fontFamily: "monospace", fontSize: "0.72rem", color: "var(--color-text-muted)" }}>
                {Math.round(m.score * 100)}% · {m.match_type.replace("_", " ")} · {m.evidence_ids.length} files
              </span>
              {m.verified ? (
                <span style={{ display: "inline-flex", gap: 4, alignItems: "center", fontSize: "0.65rem", color: "#10b981", fontWeight: 700 }}>
                  <BadgeCheck size={13} /> includes verified
                </span>
              ) : (
                <span style={{ display: "inline-flex", gap: 4, alignItems: "center", fontSize: "0.65rem", color: "#f59e0b", fontWeight: 700 }}>
                  <AlertTriangle size={12} /> needs review
                </span>
              )}
            </header>
            <p style={{ fontSize: "0.76rem", color: "var(--color-text-body)", margin: "6px 0 0 21px", lineHeight: 1.5 }}>
              {m.explanation}
            </p>
            {expanded && (
              <div style={{ margin: "8px 0 0 21px", display: "flex", flexDirection: "column", gap: 4 }}>
                {m.members.map((mem) => (
                  <button
                    key={mem.clue_id}
                    onClick={() => onOpenMember(mem.evidence_id, mem.file_type, mem.timestamp_ms)}
                    style={{
                      display: "flex", alignItems: "center", gap: 8, textAlign: "left", cursor: "pointer",
                      background: "var(--color-bg-card)", border: "1px solid var(--color-border)", borderRadius: 6,
                      padding: "5px 8px", color: "var(--color-text-body)", fontSize: "0.74rem",
                    }}
                  >
                    <ExternalLink size={12} style={{ color: "var(--color-accent)", flexShrink: 0 }} />
                    <span style={{ fontWeight: 600, color: "var(--color-text-primary)" }}>{mem.file_name}</span>
                    <span style={{ fontFamily: "monospace", color: "#22d3ee" }}>{mem.timestamp_str ?? "whole file"}</span>
                    <span style={{ color: "var(--color-text-muted)" }}>
                      read “{mem.value}” · {Math.round(mem.confidence * 100)}% · {mem.source}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </article>
        );
      })}
      {keywords.length > 0 && (
        <section className="card" style={{ overflow: "hidden" }} data-testid="keyword-section">
          <button
            onClick={() => setKwOpen(!kwOpen)}
            style={{ width: "100%", display: "flex", alignItems: "center", gap: 8, padding: "0.6rem 0.85rem",
                     background: "var(--color-bg-elevated)", border: "none", cursor: "pointer", textAlign: "left" }}
          >
            {kwOpen ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
            <strong style={{ fontSize: "0.85rem", color: "var(--color-text-primary)" }}>
              Shared keywords ({keywords.length})
            </strong>
            <span style={{ fontSize: "0.7rem", color: "var(--color-text-muted)" }}>
              words, dates and numbers that appear in more than one evidence item
            </span>
          </button>
          {kwOpen && (
            <div style={{ padding: "0.6rem 0.85rem" }}>
              <input
                aria-label="Search shared keywords"
                placeholder="Search keywords…"
                value={kwQuery}
                onChange={(e) => setKwQuery(e.target.value)}
                style={{ height: 30, width: 220, marginBottom: 8, padding: "0 8px", background: "var(--color-bg-input)",
                         color: "var(--color-text-primary)", border: "1px solid var(--color-border-bright)",
                         borderRadius: 6, fontSize: "0.76rem" }}
              />
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {kwShown.map((m) => (
                  <div
                    key={m.id}
                    data-testid="keyword-row"
                    style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", padding: "4px 0",
                             borderBottom: "1px solid var(--color-border-subtle)" }}
                  >
                    <strong style={{ fontSize: "0.82rem", color: "var(--color-text-primary)", minWidth: 120 }}>{m.value}</strong>
                    <span style={{ fontSize: "0.65rem", fontFamily: "monospace", color: "var(--color-text-subtle)" }}>
                      {Math.round(m.score * 100)}%
                    </span>
                    {[...new Map(m.members.map((x) => [x.evidence_id, x])).values()].map((mem) => (
                      <button
                        key={mem.evidence_id}
                        title={mem.context ?? ""}
                        onClick={() => onOpenMember(mem.evidence_id, mem.file_type, mem.timestamp_ms)}
                        style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: "0.7rem", cursor: "pointer",
                                 color: "var(--color-text-body)", background: "var(--color-bg-card)",
                                 border: "1px solid var(--color-border)", borderRadius: 999, padding: "1px 8px" }}
                      >
                        <ExternalLink size={10} style={{ color: "var(--color-accent)" }} />
                        {mem.file_name}
                        {mem.timestamp_str ? <span style={{ fontFamily: "monospace", color: "#22d3ee" }}>@{mem.timestamp_str}</span> : null}
                      </button>
                    ))}
                  </div>
                ))}
                {kwShown.length === 0 && <p style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>No keywords match.</p>}
              </div>
            </div>
          )}
        </section>
      )}
      {weak.length > 0 && (
        <button
          onClick={() => setShowWeak(!showWeak)}
          style={{ alignSelf: "flex-start", background: "none", border: "none", color: "var(--color-accent)", fontSize: "0.75rem", cursor: "pointer" }}
        >
          {showWeak ? "Hide" : "Show"} {weak.length} weak appearance-only similarit{weak.length === 1 ? "y" : "ies"}
        </button>
      )}
    </div>
  );
}
