// frontend/src/components/cctv/EvidenceDrawer.tsx
// Lists ROI observations as "Unverified Drafts" until a human investigator
// approves them. Verification is the gate that lets a finding reach the
// entity graph and timeline.

import React, { useState } from "react";
import {
  AlertTriangle, BadgeCheck, CheckCircle2, Clock, FileSearch, Info, Loader2, Pencil, Undo2, X,
} from "lucide-react";
import type { Finding, FindingRole } from "../../services/forensicApi";

const ROLE_OPTIONS: { value: FindingRole; label: string }[] = [
  { value: "SUSPECT", label: "Suspect" }, { value: "VICTIM", label: "Victim" },
  { value: "WITNESS", label: "Witness" }, { value: "STOLEN", label: "Stolen item" },
  { value: "WEAPON", label: "Weapon" }, { value: "TOOL", label: "Tool" },
  { value: "ITEM", label: "Other item" }, { value: "VEHICLE", label: "Vehicle" },
  { value: "PLATE", label: "Number plate" }, { value: "ID", label: "ID / badge" },
  { value: "LOCATION", label: "Location" },
];

interface EvidenceDrawerProps {
  findings: Finding[];
  /** The 448x448 patch from the most recent scan, shown above the list. */
  latestPreviewB64?: string | null;
  latestFindingId?: string | null;
  busyId?: string | null;
  error?: string | null;
  onVerify: (id: string, role?: FindingRole | null, subjectName?: string | null) => void;
  onUnverify: (id: string) => void;
  onEdit: (id: string, changes: { label?: string; readout_text?: string; role?: FindingRole; subject_name?: string }) => void;
  onSeek: (timestampMs: number) => void;
  onDismissError?: () => void;
}

const CATEGORY_COLOR: Record<string, string> = {
  PERSON: "var(--color-entity-person)",
  VEHICLE: "var(--color-entity-network)",
  TEXT_OR_CODE: "var(--color-entity-account)",
  OBJECT: "var(--color-entity-device)",
  ANOMALY: "var(--color-entity-location)",
};

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 75 ? "#10b981" : pct >= 50 ? "#f59e0b" : "#ef4444";
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.68rem", marginBottom: 3 }}>
        <span style={{ color: "var(--color-text-muted)" }}>Model confidence</span>
        <span style={{ fontFamily: "monospace", fontWeight: 700, color: "var(--color-text-primary)" }}>{pct}%</span>
      </div>
      <div
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Confidence"
        style={{ height: 6, borderRadius: 3, background: "var(--color-border)", overflow: "hidden" }}
      >
        <div style={{ width: `${pct}%`, height: "100%", background: color, transition: "width 0.3s" }} />
      </div>
    </div>
  );
}

function FindingCard({
  f, isLatest, busy, onVerify, onUnverify, onEdit, onSeek,
}: {
  f: Finding;
  isLatest: boolean;
  busy: boolean;
  onVerify: (role?: FindingRole | null, subjectName?: string | null) => void;
  onUnverify: () => void;
  onEdit: (changes: { label?: string; readout_text?: string; role?: FindingRole; subject_name?: string }) => void;
  onSeek: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [label, setLabel] = useState(f.label);
  const [readout, setReadout] = useState(f.readout_text);
  const [role, setRole] = useState<FindingRole | "">((f.role as FindingRole) ?? "");
  const [subject, setSubject] = useState(f.subject_name ?? "");
  const verified = f.verification_status === "Verified";
  const accent = verified ? "#10b981" : "#f59e0b";

  const save = () => {
    const changes: { label?: string; readout_text?: string; role?: FindingRole; subject_name?: string } = {};
    if (label.trim() && label !== f.label) changes.label = label.trim();
    if (readout !== f.readout_text) changes.readout_text = readout;
    if (role && role !== (f.role ?? "")) changes.role = role;
    if (subject.trim() && subject.trim() !== (f.subject_name ?? "")) changes.subject_name = subject.trim();
    if (Object.keys(changes).length) onEdit(changes);
    setEditing(false);
  };

  const input: React.CSSProperties = {
    width: "100%", background: "var(--color-bg-input)", color: "var(--color-text-primary)",
    border: "1px solid var(--color-border-bright)", borderRadius: 6, padding: "6px 8px", fontSize: "0.8rem",
  };

  return (
    <article
      data-testid="finding-card"
      aria-label={`${verified ? "Verified" : "Unverified draft"} finding: ${f.label}`}
      style={{
        background: "var(--color-bg-elevated)",
        border: `1px solid ${isLatest ? accent : "var(--color-border)"}`,
        borderLeft: `4px solid ${accent}`,
        borderRadius: 8,
        padding: "0.75rem",
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      {/* status row */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        {verified ? (
          <span
            style={{
              display: "inline-flex", alignItems: "center", gap: 5, fontSize: "0.68rem", fontWeight: 700,
              color: "#10b981", background: "rgba(16,185,129,0.12)", border: "1px solid rgba(16,185,129,0.35)",
              borderRadius: 999, padding: "2px 8px",
            }}
          >
            <BadgeCheck size={12} /> VERIFIED{f.verified_by ? ` · ${f.verified_by}` : ""}
          </span>
        ) : (
          <span
            style={{
              display: "inline-flex", alignItems: "center", gap: 5, fontSize: "0.68rem", fontWeight: 700,
              color: "#f59e0b", background: "rgba(245,158,11,0.12)", border: "1px solid rgba(245,158,11,0.35)",
              borderRadius: 999, padding: "2px 8px",
            }}
          >
            <AlertTriangle size={12} /> UNVERIFIED DRAFT — REVIEW REQUIRED
          </span>
        )}
        <button
          onClick={onSeek}
          title="Jump to this frame"
          style={{
            background: "transparent", border: "1px solid var(--color-border)", borderRadius: 4,
            color: "#22d3ee", fontFamily: "monospace", fontSize: "0.68rem", padding: "2px 6px", cursor: "pointer",
            display: "inline-flex", alignItems: "center", gap: 4,
          }}
        >
          <Clock size={11} /> {f.timestamp_str}
        </button>
      </div>

      {/* body */}
      {editing ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <label style={{ fontSize: "0.68rem", color: "var(--color-text-muted)" }}>
            Label
            <input style={input} value={label} maxLength={120} onChange={(e) => setLabel(e.target.value)} />
          </label>
          <label style={{ fontSize: "0.68rem", color: "var(--color-text-muted)" }}>
            Readout text (exact visible characters or NONE)
            <input style={input} value={readout} maxLength={500} onChange={(e) => setReadout(e.target.value)} />
          </label>
          <label style={{ fontSize: "0.68rem", color: "var(--color-text-muted)" }}>
            Who / what is this?
            <input style={input} value={subject} maxLength={120} placeholder="e.g. J. Vance, silver USB drive, TX-882-V"
                   onChange={(e) => setSubject(e.target.value)} />
          </label>
          <label style={{ fontSize: "0.68rem", color: "var(--color-text-muted)" }}>
            Role
            <select style={input} value={role} onChange={(e) => setRole(e.target.value as FindingRole | "")}>
              <option value="">— not assigned —</option>
              {ROLE_OPTIONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
          </label>
          {verified && (
            <p style={{ fontSize: "0.68rem", color: "#f59e0b" }}>
              Saving a change will reset this finding to Unverified Draft.
            </p>
          )}
          <div style={{ display: "flex", gap: 6 }}>
            <button onClick={save} disabled={busy} style={smallBtn("var(--color-accent)", "#fff")}>Save</button>
            <button onClick={() => setEditing(false)} style={smallBtn("transparent", "var(--color-text-muted)")}>
              <X size={12} /> Cancel
            </button>
          </div>
        </div>
      ) : (
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
            <h4 style={{ fontSize: "0.9rem", fontWeight: 700, color: "var(--color-text-primary)" }}>{f.label}</h4>
            <span
              style={{
                fontSize: "0.62rem", fontWeight: 700, color: CATEGORY_COLOR[f.category] ?? "#94a3b8",
                border: `1px solid ${CATEGORY_COLOR[f.category] ?? "#94a3b8"}`, borderRadius: 4, padding: "0 5px",
              }}
            >
              {f.category}
            </span>
          </div>
          {f.readout_text && f.readout_text.toUpperCase() !== "NONE" && (
            <p style={{ fontFamily: "monospace", fontSize: "0.82rem", color: "#22d3ee", marginTop: 4 }}>
              “{f.readout_text}”
            </p>
          )}
          {f.details.length > 0 && (
            <ul style={{ margin: "6px 0 0 16px", fontSize: "0.78rem", color: "var(--color-text-body)", lineHeight: 1.5 }}>
              {f.details.map((d, i) => <li key={i}>{d}</li>)}
            </ul>
          )}
        </div>
      )}

      <ConfidenceBar value={f.confidence_score} />

      {!f.objective_lexicon_compliant && (
        <p style={{ display: "flex", gap: 6, fontSize: "0.68rem", color: "#a5b4fc", lineHeight: 1.4 }}>
          <Info size={12} style={{ flexShrink: 0, marginTop: 1 }} />
          Model wording was automatically rewritten to the objective lexicon. Original is stored encrypted in the audit trail.
        </p>
      )}

      {(f.role || f.subject_name) && (
        <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
          {f.role && (
            <span style={{ fontSize: "0.65rem", fontWeight: 700, color: "#22d3ee", border: "1px solid #22d3ee",
                           borderRadius: 4, padding: "0 6px" }}>
              {ROLE_OPTIONS.find((r) => r.value === f.role)?.label ?? f.role}
            </span>
          )}
          {f.subject_name && (
            <span style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--color-text-primary)" }}>{f.subject_name}</span>
          )}
        </div>
      )}

      {/* source reference */}
      <div style={{ fontSize: "0.65rem", color: "var(--color-text-subtle)", fontFamily: "monospace", wordBreak: "break-all" }}>
        <FileSearch size={11} style={{ display: "inline", marginRight: 4, verticalAlign: "-1px" }} />
        {f.source_reference}
        <br />
        crop sha256: {f.crop_sha256.slice(0, 16)}… · by {f.operator_id}
      </div>

      {/* actions */}
      {!editing && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {verified ? (
            <button onClick={onUnverify} disabled={busy} style={smallBtn("transparent", "var(--color-text-muted)", true)}>
              <Undo2 size={12} /> Revoke verification
            </button>
          ) : (
            <button onClick={() => onVerify(role || null, subject || null)} disabled={busy}
                    style={smallBtn("#059669", "#fff")} aria-label="Verify and approve for report">
              {busy ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle2 size={13} />}
              Verify &amp; Approve for Report
            </button>
          )}
          <button onClick={() => setEditing(true)} disabled={busy} style={smallBtn("transparent", "var(--color-text-muted)", true)}>
            <Pencil size={12} /> Edit
          </button>
        </div>
      )}
    </article>
  );
}

function smallBtn(bg: string, color: string, outline = false): React.CSSProperties {
  return {
    display: "inline-flex", alignItems: "center", gap: 6, height: 32, padding: "0 10px", borderRadius: 6,
    border: outline ? "1px solid var(--color-border-bright)" : `1px solid ${bg}`,
    background: bg, color, fontSize: "0.72rem", fontWeight: 700, cursor: "pointer",
  };
}

export function EvidenceDrawer({
  findings, latestPreviewB64, latestFindingId, busyId, error,
  onVerify, onUnverify, onEdit, onSeek, onDismissError,
}: EvidenceDrawerProps) {
  const drafts = findings.filter((f) => f.verification_status !== "Verified").length;
  const verified = findings.length - drafts;

  return (
    <aside
      aria-label="Evidence drawer"
      style={{
        display: "flex", flexDirection: "column", height: "100%", minHeight: 0,
        background: "var(--color-bg-card)", borderLeft: "1px solid var(--color-border)",
      }}
    >
      <header style={{ padding: "0.75rem 1rem", borderBottom: "1px solid var(--color-border)" }}>
        <h3 style={{ fontSize: "0.9rem", fontWeight: 700, color: "var(--color-text-primary)" }}>Operator Evidence</h3>
        <p style={{ fontSize: "0.7rem", color: "var(--color-text-muted)", marginTop: 2 }}>
          <span style={{ color: "#f59e0b", fontWeight: 700 }}>{drafts}</span> draft ·{" "}
          <span style={{ color: "#10b981", fontWeight: 700 }}>{verified}</span> verified
        </p>
      </header>

      {error && (
        <div
          role="alert"
          style={{
            margin: "0.75rem", padding: "0.6rem 0.75rem", borderRadius: 6, fontSize: "0.75rem",
            background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.35)", color: "#fca5a5",
            display: "flex", gap: 8, justifyContent: "space-between",
          }}
        >
          <span>{error}</span>
          {onDismissError && (
            <button onClick={onDismissError} aria-label="Dismiss error" style={{ background: "none", border: "none", color: "inherit", cursor: "pointer" }}>
              <X size={14} />
            </button>
          )}
        </div>
      )}

      <div style={{ flex: 1, overflowY: "auto", padding: "0.75rem", display: "flex", flexDirection: "column", gap: 10 }}>
        {latestPreviewB64 && (
          <figure style={{ margin: 0 }}>
            <img
              src={`data:image/png;base64,${latestPreviewB64}`}
              alt="Enhanced 448 by 448 patch sent to the local model"
              style={{ width: 112, height: 112, borderRadius: 6, border: "1px solid var(--color-border-bright)", imageRendering: "auto" }}
            />
            <figcaption style={{ fontSize: "0.62rem", color: "var(--color-text-subtle)", marginTop: 3 }}>
              Patch analysed by the local model (CLAHE + sharpen, 448×448)
            </figcaption>
          </figure>
        )}

        {findings.length === 0 ? (
          <div style={{ textAlign: "center", padding: "2.5rem 1rem", color: "var(--color-text-subtle)" }}>
            <FileSearch size={34} style={{ margin: "0 auto 10px", opacity: 0.6 }} />
            <p style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--color-text-muted)" }}>No observations yet</p>
            <p style={{ fontSize: "0.72rem", marginTop: 4 }}>
              Pause on a frame, drag a box around a region, then press “Regional Scan”.
            </p>
          </div>
        ) : (
          [...findings]
            .sort((a, b) => b.timestamp_ms - a.timestamp_ms || (b.created_at ?? "").localeCompare(a.created_at ?? ""))
            .map((f) => (
              <FindingCard
                key={f.id}
                f={f}
                isLatest={f.id === latestFindingId}
                busy={busyId === f.id}
                onVerify={(r, n) => onVerify(f.id, r, n)}
                onUnverify={() => onUnverify(f.id)}
                onEdit={(c) => onEdit(f.id, c)}
                onSeek={() => onSeek(f.timestamp_ms)}
              />
            ))
        )}
      </div>
    </aside>
  );
}
