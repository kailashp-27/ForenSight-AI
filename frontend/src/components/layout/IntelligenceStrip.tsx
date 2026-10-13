// frontend/src/components/layout/IntelligenceStrip.tsx
// Intelligence strip: REAL cross-case data only.
//   Leads    — strongest clues shared between evidence items (correlation engine)
//   Gaps     — concrete things missing/unfinished in the evidence
//   Activity — recent entries from the tamper-evident custody log
// Nothing here is hypothesised or hard-coded; it all comes from /api/v1/overview.

import React, { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  ChevronUp, ChevronDown, Zap, AlertCircle, Clock, Brain, CheckCircle, FileSearch, Loader2, RefreshCw,
} from "lucide-react";
import { type ContextPanelItem } from "./ContextPanel";
import { getSocket } from "../../services/socket";
import { caseViewsApi, type Overview, type OverviewLead } from "../../services/forensicApi";

type Tab = "leads" | "gaps" | "activity";

const RISK_CONFIG = {
  high: { color: "#ef4444", bg: "rgba(239,68,68,0.1)", label: "STRONG" },
  medium: { color: "#f59e0b", bg: "rgba(245,158,11,0.1)", label: "MEDIUM" },
  low: { color: "#10b981", bg: "rgba(16,185,129,0.1)", label: "LOW" },
};

const SEV: Record<string, { color: string; bg: string }> = {
  high: { color: "#ef4444", bg: "rgba(239,68,68,0.1)" },
  medium: { color: "#f59e0b", bg: "rgba(245,158,11,0.1)" },
  low: { color: "#10b981", bg: "rgba(16,185,129,0.1)" },
};

function relTime(iso: string): string {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return iso;
  const s = Math.max(0, Math.round((Date.now() - t) / 1000));
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} hr ago`;
  return `${Math.floor(s / 86400)} d ago`;
}

function leadToItem(l: OverviewLead): ContextPanelItem {
  return {
    id: l.id,
    type: "lead",
    title: `${l.kind}: ${l.value}`,
    subtitle: `Appears in ${l.files.length} evidence items — ${l.files.join(", ")}`,
    risk: l.strength === "STRONG" ? "high" : l.strength === "MEDIUM" ? "medium" : "low",
    confidence: Math.round(l.score * 100),
    timestamp: `${l.case_number}`,
    aiReasoning: l.explanation,
    details: {
      Case: `${l.case_number} — ${l.case_title}`,
      "Match type": l.match_type.replace("_", " "),
      Strength: l.strength,
      "Investigator-verified": l.verified ? "Yes" : "No — needs review",
    },
    relatedItems: l.sources.map((s) => ({
      label: `${s.file}${s.at ? ` @ ${s.at}` : ""}`,
      value: `${s.reading}${s.source ? ` (${s.source})` : ""}`,
    })),
  };
}

function Empty({ icon, title, hint }: { icon: React.ReactNode; title: string; hint: string }) {
  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                  padding: "1rem", textAlign: "center", color: "var(--color-text-subtle)" }}>
      <div style={{ opacity: 0.6, marginBottom: 6 }}>{icon}</div>
      <p style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--color-text-muted)" }}>{title}</p>
      <p style={{ fontSize: "0.7rem", marginTop: 3, maxWidth: 360 }}>{hint}</p>
    </div>
  );
}

function LeadsTab({ leads, onSelect }: { leads: OverviewLead[]; onSelect: (i: ContextPanelItem, l: ContextPanelItem[]) => void }) {
  const items = leads.map(leadToItem);
  if (!items.length) {
    return (
      <Empty
        icon={<Zap size={24} />}
        title="No shared clues yet"
        hint="A lead appears when the same plate, phone number, name or ID shows up in two or more evidence items. Run automatic analysis on a case."
      />
    );
  }
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", alignItems: "start",
                  alignContent: "start", gap: "0.625rem", padding: "0.75rem 1rem", overflowY: "auto", flex: 1 }}>
      {items.map((lead, idx) => {
        const cfg = RISK_CONFIG[(lead.risk as keyof typeof RISK_CONFIG) ?? "low"] ?? RISK_CONFIG.low;
        return (
          <div
            key={lead.id}
            className={`lead-card risk-${lead.risk}`}
            onClick={() => onSelect(lead, items)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === "Enter" && onSelect(lead, items)}
            aria-label={`Open lead: ${lead.title}`}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
              <p style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--color-text-primary)", lineHeight: 1.35, flex: 1,
                          wordBreak: "break-word" }}>
                {lead.title}
              </p>
              <span style={{ padding: "0.1rem 0.4rem", borderRadius: 4, flexShrink: 0, fontSize: "0.6rem", fontWeight: 700,
                             letterSpacing: "0.06em", background: cfg.bg, color: cfg.color }}>
                {cfg.label}
              </span>
            </div>
            <p style={{ fontSize: "0.7rem", color: "var(--color-text-muted)", marginTop: 4, lineHeight: 1.4 }}>{lead.subtitle}</p>
            <div style={{ display: "flex", alignItems: "center", marginTop: 8 }}>
              <div className="confidence-bar" style={{ flex: 1, marginRight: 8 }}>
                <div className="confidence-fill" style={{ width: `${lead.confidence}%`, background: cfg.color }} />
              </div>
              <span style={{ fontSize: "0.6875rem", fontWeight: 700, fontFamily: "monospace", color: "var(--color-text-muted)" }}>
                {lead.confidence}%
              </span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6 }}>
              <span style={{ fontSize: "0.65rem", color: "var(--color-text-subtle)", fontFamily: "monospace" }}>
                {lead.timestamp}{leads[idx]?.verified ? " · verified" : " · needs review"}
              </span>
              <span style={{ fontSize: "0.65rem", color: "var(--color-accent)" }}>Open →</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function GapsTab({ gaps }: { gaps: Overview["gaps"] }) {
  if (!gaps.length) {
    return <Empty icon={<CheckCircle size={24} />} title="No gaps detected"
                  hint="Every evidence item has been analysed and has the text and metadata it can have." />;
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", padding: "0.75rem 1rem", overflowY: "auto", flex: 1 }}>
      {gaps.map((g) => (
        <Link
          key={g.id}
          to={`/cases/${g.case_id}/investigation`}
          style={{ textDecoration: "none", background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)",
                   borderLeft: `3px solid ${SEV[g.severity].color}`, borderRadius: 8, padding: "0.625rem 0.875rem",
                   display: "flex", gap: 10, alignItems: "flex-start" }}
        >
          <AlertCircle style={{ width: 13, height: 13, color: SEV[g.severity].color, flexShrink: 0, marginTop: 2 }} />
          <div style={{ flex: 1 }}>
            <p style={{ fontSize: "0.78rem", color: "var(--color-text-body)", lineHeight: 1.4 }}>{g.text}</p>
            <span style={{ fontSize: "0.65rem", fontFamily: "monospace", color: "var(--color-text-subtle)" }}>{g.case_number}</span>
          </div>
          <span style={{ padding: "0.1rem 0.4rem", borderRadius: 4, flexShrink: 0, fontSize: "0.6rem", fontWeight: 700,
                         letterSpacing: "0.06em", background: SEV[g.severity].bg, color: SEV[g.severity].color }}>
            {g.severity.toUpperCase()}
          </span>
        </Link>
      ))}
    </div>
  );
}

function ActivityTab({ activity }: { activity: Overview["activity"] }) {
  if (!activity.length) {
    return <Empty icon={<Clock size={24} />} title="No activity yet" hint="Uploads, scans, reviews and reports are recorded here." />;
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.375rem", padding: "0.75rem 1rem", overflowY: "auto", flex: 1 }}>
      {activity.map((a) => (
        <div key={a.id} style={{ display: "flex", gap: 10, alignItems: "flex-start", padding: "0.5rem 0",
                                 borderBottom: "1px solid var(--color-border-subtle)" }}>
          <div style={{ width: 24, height: 24, borderRadius: 6, flexShrink: 0, background: "var(--color-bg-elevated)",
                        border: "1px solid var(--color-border)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            {a.action.includes("ANALYSIS") ? <Brain style={{ width: 11, height: 11, color: "var(--color-accent)" }} />
              : a.action.includes("VERIFIED") || a.action.includes("REVIEWED") ? <CheckCircle style={{ width: 11, height: 11, color: "#10b981" }} />
              : <FileSearch style={{ width: 11, height: 11, color: "var(--color-text-muted)" }} />}
          </div>
          <div style={{ flex: 1 }}>
            <p style={{ fontSize: "0.76rem", color: "var(--color-text-body)", lineHeight: 1.4 }}>
              {a.text}{a.case_number ? ` — ${a.case_number}` : ""}
            </p>
            <span style={{ fontSize: "0.65rem", fontFamily: "monospace", color: "var(--color-text-subtle)", marginTop: 2, display: "block" }}>
              {relTime(a.time)} · {a.operator}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

interface IntelligenceStripProps {
  contextItem: ContextPanelItem | null;
  onContextSelect: (item: ContextPanelItem, list: ContextPanelItem[]) => void;
  onContextClose: () => void;
}

export function IntelligenceStrip({ contextItem, onContextSelect }: IntelligenceStripProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>("leads");
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await caseViewsApi.overview());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load, refresh every 60 s, and whenever background processing finishes.
  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 60_000);
    const socket = getSocket();
    const onStatus = (p: { status?: string }) => {
      if (p?.status === "COMPLETED" || p?.status === "FAILED") void load();
    };
    socket.on("evidence:status_update", onStatus);
    return () => {
      window.clearInterval(timer);
      socket.off("evidence:status_update", onStatus);
    };
  }, [load]);

  const [height, setHeight] = useState(250);
  const [isDragging, setIsDragging] = useState(false);
  const dragStartY = useRef(0);
  const dragStartHeight = useRef(0);
  const isMoved = useRef(false);

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    isMoved.current = false;
    dragStartY.current = e.clientY;
    dragStartHeight.current = height;
    e.preventDefault();
  };

  useEffect(() => {
    if (!isDragging) return;
    const onMove = (e: MouseEvent) => {
      const deltaY = dragStartY.current - e.clientY;
      if (Math.abs(deltaY) > 5) isMoved.current = true;
      if (isMoved.current) {
        setCollapsed(false);
        setHeight(Math.max(200, Math.min(800, dragStartHeight.current + deltaY)));
      }
    };
    const onUp = () => {
      setIsDragging(false);
      if (!isMoved.current) setCollapsed((v) => !v);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [isDragging]);

  useEffect(() => {
    if (contextItem) setCollapsed(true);
  }, [contextItem]);

  const TABS: { key: Tab; label: string; count?: number; icon: React.ReactNode }[] = [
    { key: "leads", label: "Leads", count: data?.leads.length, icon: <Zap style={{ width: 11, height: 11 }} /> },
    { key: "gaps", label: "Gaps", count: data?.gaps.length, icon: <AlertCircle style={{ width: 11, height: 11 }} /> },
    { key: "activity", label: "Recent Activity", count: data?.activity.length, icon: <Clock style={{ width: 11, height: 11 }} /> },
  ];

  return (
    <div
      className={`hub-strip ${collapsed ? "collapsed" : ""}`}
      aria-label="Intelligence strip"
      role="region"
      style={{ height: collapsed ? undefined : height, transition: isDragging ? "none" : "height 0.3s ease" }}
    >
      <div
        className="strip-handle"
        onMouseDown={handleMouseDown}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && setCollapsed((v) => !v)}
        aria-label={collapsed ? "Expand intelligence strip" : "Collapse intelligence strip"}
        style={{ cursor: "ns-resize" }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "center" }}>
          <div className="strip-handle-bar" />
          {collapsed ? <ChevronUp style={{ width: 12, height: 12, color: "var(--color-text-subtle)" }} />
                     : <ChevronDown style={{ width: 12, height: 12, color: "var(--color-text-subtle)" }} />}
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
          <div className="tab-bar" style={{ display: "flex", alignItems: "center" }}>
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
                    <span style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", minWidth: 16,
                                   height: 16, padding: "0 3px", borderRadius: 8,
                                   background: activeTab === t.key ? "var(--color-accent)" : "var(--color-border-bright)",
                                   color: activeTab === t.key ? "white" : "var(--color-text-muted)",
                                   fontSize: "0.6rem", fontWeight: 700 }}>
                      {t.count}
                    </span>
                  )}
                </span>
              </button>
            ))}
            <button
              onClick={() => void load()}
              aria-label="Refresh intelligence strip"
              title={data ? `${data.stats.cases} case(s) · ${data.stats.evidence} evidence · ${data.stats.clues} clues` : "Refresh"}
              style={{ marginLeft: "auto", marginRight: 10, background: "none", border: "none", cursor: "pointer",
                       color: "var(--color-text-subtle)", display: "flex", alignItems: "center" }}
            >
              {loading ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
            </button>
          </div>

          <div style={{ flex: 1, overflow: "hidden", display: "flex" }}>
            {error && !data ? (
              <Empty icon={<AlertCircle size={24} />} title="Could not load intelligence" hint={error} />
            ) : !data ? (
              <Empty icon={<Loader2 size={24} className="animate-spin" />} title="Loading…" hint="" />
            ) : (
              <>
                {activeTab === "leads" && <LeadsTab leads={data.leads} onSelect={onContextSelect} />}
                {activeTab === "gaps" && <GapsTab gaps={data.gaps} />}
                {activeTab === "activity" && <ActivityTab activity={data.activity} />}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
