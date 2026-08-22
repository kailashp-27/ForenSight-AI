// frontend/src/components/layout/IntelligenceStrip.tsx
import React, { useState } from "react";
import {
  ChevronUp, ChevronDown, Zap, Brain, AlertCircle,
  Clock, TrendingUp, User, Monitor, Globe, CheckCircle,
} from "lucide-react";
import { ContextPanel, type ContextPanelItem } from "./ContextPanel";

/* ── Mock Data ────────────────────────────────────────────────────────────── */
const MOCK_LEADS: ContextPanelItem[] = [
  {
    id: "L001",
    title: "Unusual login pattern — User KP-2234",
    subtitle: "23 logins in 4 hours from 7 different IP addresses",
    type: "lead", risk: "high", confidence: 91,
    timestamp: "2026-08-19 03:41",
    aiReasoning:
      "The login velocity (23 in 4h) exceeds the user's 30-day baseline by 8.3×. " +
      "IP clustering analysis shows 5 of 7 IPs belong to known VPN exit nodes. " +
      "Temporal pattern aligns with known account-takeover sequences in the fraud dataset.",
    details: {
      "User ID":    "KP-2234",
      "IP Range":   "45.32.x.x / 192.168.x.x",
      "Time Range": "00:12 – 03:41 UTC",
      "Logins":     "23",
      "Unique IPs": "7",
    },
    relatedItems: [
      { label: "Case",     value: "CASE-2026-001" },
      { label: "Evidence", value: "access_log_aug19.csv" },
      { label: "Cluster",  value: "IP-CLUSTER-04" },
    ],
  },
  {
    id: "L002",
    title: "Transaction cluster — ₹4.7L split payments",
    subtitle: "14 transactions just below ₹50,000 threshold in 6h",
    type: "lead", risk: "high", confidence: 87,
    timestamp: "2026-08-19 08:15",
    aiReasoning:
      "Structuring pattern detected: 14 transfers averaging ₹33,571 in a 6-hour window. " +
      "All transfers originated from ACC-887 and were distributed to 6 distinct accounts " +
      "with no prior relationship. This aligns with smurfing behaviour in PMLA guidelines.",
    details: {
      "Source Account": "ACC-887",
      "Total Amount":   "₹4,70,000",
      "Transactions":   "14",
      "Time Window":    "6 hours",
      "Recipients":     "6 accounts",
    },
    relatedItems: [
      { label: "Case",    value: "CASE-2026-001" },
      { label: "Pattern", value: "SMURFING-v2" },
    ],
  },
  {
    id: "L003",
    title: "CCTV frame — Unidentified object detected",
    subtitle: "YOLOv8 detected firearm-like object at 02:14:33",
    type: "lead", risk: "high", confidence: 78,
    timestamp: "2026-08-19 02:14",
    aiReasoning:
      "YOLOv8 (confidence 78.3%) flagged a pistol-shaped silhouette in frame 3,260. " +
      "Grad-CAM heatmap shows activation concentrated on the right hand of subject. " +
      "REVIEW REQUIRED — human verification mandatory before any legal inference.",
    details: {
      "File":        "CCTV_lobby_aug19.mp4",
      "Frame":       "3260",
      "Timestamp":   "02:14:33",
      "Detection":   "Possible firearm",
      "Confidence":  "78.3%",
    },
    relatedItems: [
      { label: "Evidence",  value: "CCTV_lobby_aug19.mp4" },
      { label: "Grad-CAM",  value: "heatmap_frame3260.png" },
    ],
  },
  {
    id: "L004",
    title: "5 accounts — potential shared operator",
    subtitle: "Behavioral fingerprinting shows 94% similarity",
    type: "lead", risk: "medium", confidence: 76,
    timestamp: "2026-08-18 22:30",
    aiReasoning:
      "Device fingerprinting and typing-cadence analysis across 5 accounts show 94% " +
      "cosine similarity in behavioral vectors. Session overlap analysis confirms " +
      "at least 3 accounts were active simultaneously from the same device.",
    details: {
      "Accounts":    "5",
      "Similarity":  "94%",
      "Overlap":     "3 concurrent",
      "Device ID":   "DEVF-4420",
    },
    relatedItems: [
      { label: "Cluster", value: "BEHAV-CLUSTER-01" },
      { label: "Case",    value: "CASE-2026-001" },
    ],
  },
];

const MOCK_HYPOTHESES = [
  { id: "H001", text: "User KP-2234 is operating a mule account network", evidence: 8, confidence: 74, status: "exploring" },
  { id: "H002", text: "ACC-887 is the primary layering account in a 3-tier structure", evidence: 12, confidence: 81, status: "exploring" },
  { id: "H003", text: "The 5 flagged accounts share a single physical operator", evidence: 5, confidence: 63, status: "exploring" },
  { id: "H004", text: "CCTV lobby footage is unrelated to financial fraud", evidence: 3, confidence: 45, status: "rejected" },
];

const MOCK_GAPS = [
  { id: "G001", text: "No device metadata for IP 45.32.118.204 — VPN endpoint", severity: "high" },
  { id: "G002", text: "14-minute gap in CCTV recording between 02:00–02:14", severity: "high" },
  { id: "G003", text: "ACC-887 beneficiary details not yet verified with bank", severity: "medium" },
  { id: "G004", text: "Audio evidence from interview has not been transcribed", severity: "low" },
];

const MOCK_ACTIVITY = [
  { id: "A001", text: 'Analyst KP tagged Lead L001 as "Priority"', time: "2 min ago", icon: "tag" },
  { id: "A002", text: "AI clustered 14 transactions into Incident #45", time: "18 min ago", icon: "ai" },
  { id: "A003", text: "CCTV_lobby_aug19.mp4 — YOLOv8 analysis complete", time: "34 min ago", icon: "check" },
  { id: "A004", text: "Hypothesis H002 evidence count updated to 12", time: "1 hr ago", icon: "update" },
  { id: "A005", text: "Case CASE-2026-001 status changed to UNDER REVIEW", time: "2 hr ago", icon: "flag" },
];

/* ── Sub-components ──────────────────────────────────────────────────────── */
type Tab = "leads" | "hypotheses" | "gaps" | "activity";

const RISK_CONFIG = {
  high:   { color: "#ef4444", bg: "rgba(239,68,68,0.1)", label: "HIGH" },
  medium: { color: "#f59e0b", bg: "rgba(245,158,11,0.1)", label: "MED" },
  low:    { color: "#10b981", bg: "rgba(16,185,129,0.1)", label: "LOW" },
};

function LeadsTab({ onSelect }: { onSelect: (item: ContextPanelItem) => void }) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
        gap: "0.625rem",
        padding: "0.75rem 1rem",
        overflowY: "auto",
        flex: 1,
      }}
    >
      {MOCK_LEADS.map((lead) => (
        <div
          key={lead.id}
          className={`lead-card risk-${lead.risk}`}
          onClick={() => onSelect(lead)}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === "Enter" && onSelect(lead)}
          aria-label={`Open lead: ${lead.title}`}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
            <p
              style={{
                fontSize: "0.78rem", fontWeight: 600,
                color: "var(--color-text-primary)", lineHeight: 1.35, flex: 1,
              }}
            >
              {lead.title}
            </p>
            {lead.risk && (
              <span
                style={{
                  padding: "0.1rem 0.4rem", borderRadius: 4, flexShrink: 0,
                  fontSize: "0.6rem", fontWeight: 700, letterSpacing: "0.06em",
                  background: RISK_CONFIG[lead.risk].bg,
                  color: RISK_CONFIG[lead.risk].color,
                }}
              >
                {RISK_CONFIG[lead.risk].label}
              </span>
            )}
          </div>
          <p style={{ fontSize: "0.7rem", color: "var(--color-text-muted)", marginTop: 4, lineHeight: 1.4 }}>
            {lead.subtitle}
          </p>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 8 }}>
            <div className="confidence-bar" style={{ flex: 1, marginRight: 8 }}>
              <div
                className="confidence-fill"
                style={{
                  width: `${lead.confidence}%`,
                  background: (lead.confidence ?? 0) >= 80 ? "#ef4444" : (lead.confidence ?? 0) >= 60 ? "#f59e0b" : "#10b981",
                }}
              />
            </div>
            <span
              style={{
                fontSize: "0.6875rem", fontWeight: 700,
                fontFamily: "monospace",
                color: "var(--color-text-muted)",
              }}
            >
              {lead.confidence}%
            </span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6 }}>
            <span style={{ fontSize: "0.65rem", color: "var(--color-text-subtle)", fontFamily: "monospace" }}>
              {lead.timestamp}
            </span>
            <span style={{ fontSize: "0.65rem", color: "var(--color-accent)" }}>
              Open →
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

function HypothesesTab() {
  const STATUS_COLOR: Record<string, string> = { exploring: "#3b82f6", validated: "#10b981", rejected: "#6b7280" };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", padding: "0.75rem 1rem", overflowY: "auto", flex: 1 }}>
      {MOCK_HYPOTHESES.map((h) => (
        <div
          key={h.id}
          style={{
            background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)",
            borderRadius: 8, padding: "0.625rem 0.875rem",
            display: "grid", gridTemplateColumns: "1fr auto", alignItems: "center", gap: 12,
          }}
        >
          <div>
            <p style={{ fontSize: "0.78rem", color: "var(--color-text-primary)", lineHeight: 1.4 }}>
              {h.text}
            </p>
            <div style={{ display: "flex", gap: 8, marginTop: 4, alignItems: "center" }}>
              <span style={{ fontSize: "0.65rem", color: "var(--color-text-muted)" }}>
                {h.evidence} evidence
              </span>
              <span style={{ width: 3, height: 3, borderRadius: "50%", background: "var(--color-text-subtle)" }} />
              <span
                style={{
                  fontSize: "0.65rem", fontWeight: 600,
                  color: STATUS_COLOR[h.status] ?? "var(--color-text-muted)",
                  textTransform: "capitalize",
                }}
              >
                {h.status}
              </span>
            </div>
          </div>
          <div style={{ textAlign: "right" }}>
            <span
              style={{
                fontSize: "0.875rem", fontWeight: 700, fontFamily: "monospace",
                color: h.confidence >= 70 ? "#f59e0b" : "var(--color-text-muted)",
              }}
            >
              {h.confidence}%
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

function GapsTab() {
  const SEV: Record<string, { color: string; bg: string }> = {
    high:   { color: "#ef4444", bg: "rgba(239,68,68,0.1)" },
    medium: { color: "#f59e0b", bg: "rgba(245,158,11,0.1)" },
    low:    { color: "#10b981", bg: "rgba(16,185,129,0.1)" },
  };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", padding: "0.75rem 1rem", overflowY: "auto", flex: 1 }}>
      {MOCK_GAPS.map((g) => (
        <div
          key={g.id}
          style={{
            background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)",
            borderLeft: `3px solid ${SEV[g.severity].color}`,
            borderRadius: 8, padding: "0.625rem 0.875rem",
            display: "flex", gap: 10, alignItems: "flex-start",
          }}
        >
          <AlertCircle style={{ width: 13, height: 13, color: SEV[g.severity].color, flexShrink: 0, marginTop: 2 }} />
          <div style={{ flex: 1 }}>
            <p style={{ fontSize: "0.78rem", color: "var(--color-text-body)", lineHeight: 1.4 }}>
              {g.text}
            </p>
          </div>
          <span
            style={{
              padding: "0.1rem 0.4rem", borderRadius: 4, flexShrink: 0,
              fontSize: "0.6rem", fontWeight: 700, letterSpacing: "0.06em",
              background: SEV[g.severity].bg, color: SEV[g.severity].color,
            }}
          >
            {g.severity.toUpperCase()}
          </span>
        </div>
      ))}
    </div>
  );
}

function ActivityTab() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.375rem", padding: "0.75rem 1rem", overflowY: "auto", flex: 1 }}>
      {MOCK_ACTIVITY.map((a) => (
        <div
          key={a.id}
          style={{
            display: "flex", gap: 10, alignItems: "flex-start",
            padding: "0.5rem 0", borderBottom: "1px solid var(--color-border-subtle)",
          }}
        >
          <div
            style={{
              width: 24, height: 24, borderRadius: 6, flexShrink: 0,
              background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}
          >
            {a.icon === "ai"     && <Brain style={{ width: 11, height: 11, color: "var(--color-accent)" }} />}
            {a.icon === "check"  && <CheckCircle style={{ width: 11, height: 11, color: "#10b981" }} />}
            {a.icon === "update" && <TrendingUp style={{ width: 11, height: 11, color: "#f59e0b" }} />}
            {a.icon === "tag"    && <User style={{ width: 11, height: 11, color: "var(--color-text-muted)" }} />}
            {a.icon === "flag"   && <Globe style={{ width: 11, height: 11, color: "var(--color-text-muted)" }} />}
          </div>
          <div style={{ flex: 1 }}>
            <p style={{ fontSize: "0.76rem", color: "var(--color-text-body)", lineHeight: 1.4 }}>{a.text}</p>
            <span style={{ fontSize: "0.65rem", fontFamily: "monospace", color: "var(--color-text-subtle)", marginTop: 2, display: "block" }}>
              {a.time}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── Main Component ──────────────────────────────────────────────────────── */
interface IntelligenceStripProps {
  contextItem: ContextPanelItem | null;
  onContextSelect: (item: ContextPanelItem) => void;
  onContextClose: () => void;
}

export function IntelligenceStrip({ contextItem, onContextSelect, onContextClose }: IntelligenceStripProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>("leads");

  const TABS: { key: Tab; label: string; count?: number; icon: React.ReactNode }[] = [
    { key: "leads",       label: "Leads",           count: MOCK_LEADS.length,       icon: <Zap style={{ width: 11, height: 11 }} /> },
    { key: "hypotheses",  label: "Hypotheses",      count: MOCK_HYPOTHESES.length,  icon: <Brain style={{ width: 11, height: 11 }} /> },
    { key: "gaps",        label: "Gaps",            count: MOCK_GAPS.length,        icon: <AlertCircle style={{ width: 11, height: 11 }} /> },
    { key: "activity",    label: "Recent Activity", count: MOCK_ACTIVITY.length,    icon: <Clock style={{ width: 11, height: 11 }} /> },
  ];

  return (
    <div
      className={`hub-strip ${collapsed ? "collapsed" : ""}`}
      aria-label="Intelligence strip"
      role="region"
    >
      {/* Drag handle / collapse toggle */}
      <div
        className="strip-handle"
        onClick={() => setCollapsed((v) => !v)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && setCollapsed((v) => !v)}
        aria-label={collapsed ? "Expand intelligence strip" : "Collapse intelligence strip"}
        style={{ cursor: "pointer" }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "center" }}>
          <div className="strip-handle-bar" />
          {collapsed
            ? <ChevronUp style={{ width: 12, height: 12, color: "var(--color-text-subtle)" }} />
            : <ChevronDown style={{ width: 12, height: 12, color: "var(--color-text-subtle)" }} />
          }
          {!collapsed && (
            <span style={{ fontSize: "0.65rem", color: "var(--color-text-subtle)", letterSpacing: "0.1em", fontWeight: 600 }}>
              INTELLIGENCE STRIP
            </span>
          )}
          <div className="strip-handle-bar" />
        </div>
      </div>

      {!collapsed && (
        <div style={{ display: "flex", flexDirection: "column", height: "calc(100% - 20px)", overflow: "hidden" }}>
          {/* Tab Bar */}
          <div className="tab-bar">
            {TABS.map((t) => (
              <button
                key={t.key}
                className={`tab-btn ${activeTab === t.key ? "active" : ""}`}
                onClick={() => setActiveTab(t.key)}
                aria-selected={activeTab === t.key}
                role="tab"
                id={`strip-tab-${t.key}`}
              >
                <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
                  {t.icon}
                  {t.label}
                  {t.count !== undefined && (
                    <span
                      style={{
                        display: "inline-flex", alignItems: "center", justifyContent: "center",
                        width: 16, height: 16, borderRadius: "50%",
                        background: activeTab === t.key ? "var(--color-accent)" : "var(--color-border-bright)",
                        color: activeTab === t.key ? "white" : "var(--color-text-muted)",
                        fontSize: "0.6rem", fontWeight: 700,
                      }}
                    >
                      {t.count}
                    </span>
                  )}
                </span>
              </button>
            ))}
          </div>

          {/* Tab Content */}
          <div style={{ flex: 1, overflow: "hidden", display: "flex" }}>
            {activeTab === "leads"      && <LeadsTab onSelect={onContextSelect} />}
            {activeTab === "hypotheses" && <HypothesesTab />}
            {activeTab === "gaps"       && <GapsTab />}
            {activeTab === "activity"   && <ActivityTab />}
          </div>
        </div>
      )}
    </div>
  );
}
