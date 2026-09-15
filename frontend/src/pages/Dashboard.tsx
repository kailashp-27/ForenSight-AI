// frontend/src/pages/Dashboard.tsx
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  FolderOpen, FileVideo, Clock, ShieldAlert,
  ChevronRight, Plus, TrendingUp,
  GitGraph, Map, CalendarDays,
} from "lucide-react";
import { Badge, statusToVariant } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { useCaseStore } from "../store/caseStore";
import { casesApi, evidenceApi, type TimelineEvent, type Case } from "../services/api";
import { TimelineView } from "../components/visualization/TimelineView";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "2-digit", month: "short", year: "numeric",
  });
}

/* ── Compute "added this week" ───────────────────────────────────────────── */
function countAddedThisWeek(items: { created_at: string }[]): number {
  const oneWeekAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
  return items.filter((i) => new Date(i.created_at).getTime() > oneWeekAgo).length;
}

/* ── Stat card ─────────────────────────────────────────────────────────── */
function StatCard({
  icon, value, label, loading, accent, trend,
}: {
  icon: React.ReactNode;
  value: string | number;
  label: string;
  loading: boolean;
  accent?: string;
  trend?: string;
}) {
  return (
    <div
      className="card"
      style={{ padding: "1.25rem", display: "flex", flexDirection: "column", gap: 12 }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div
          style={{
            width: 36, height: 36, borderRadius: 8,
            background: accent ? `${accent}18` : "var(--color-accent-light)",
            display: "flex", alignItems: "center", justifyContent: "center",
            color: accent ?? "var(--color-accent)",
          }}
        >
          {icon}
        </div>
        {trend && (
          <span
            style={{
              display: "flex", alignItems: "center", gap: 3,
              fontSize: "0.65rem", fontWeight: 600, color: "#10b981",
            }}
          >
            <TrendingUp style={{ width: 10, height: 10 }} />
            {trend}
          </span>
        )}
      </div>
      {loading ? (
        <div className="skeleton" style={{ height: 28, width: 56 }} />
      ) : (
        <p style={{ fontSize: "1.75rem", fontWeight: 700, color: "var(--color-text-primary)", lineHeight: 1 }}>
          {value}
        </p>
      )}
      <p style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>{label}</p>
    </div>
  );
}

/* ── Coming Soon Overlay ────────────────────────────────────────────────── */
function ComingSoonPane({ label }: { label: string }) {
  return (
    <div
      style={{
        display: "flex", flexDirection: "column", alignItems: "center",
        justifyContent: "center", padding: "4rem 1rem", textAlign: "center", gap: 12,
      }}
    >
      <div
        style={{
          width: 48, height: 48, borderRadius: 12,
          background: "var(--color-accent-light)", border: "1px solid var(--color-border-bright)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: "1.25rem",
        }}
      >
        🚧
      </div>
      <p style={{ fontSize: "0.9rem", fontWeight: 600, color: "var(--color-text-primary)" }}>
        {label} View
      </p>
      <p style={{ fontSize: "0.78rem", color: "var(--color-text-muted)", maxWidth: 280 }}>
        This view is coming in the next development phase. The Timeline is currently active.
      </p>
      <div
        style={{
          padding: "0.3rem 0.75rem", borderRadius: 6,
          background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)",
          fontSize: "0.7rem", fontFamily: "monospace", color: "var(--color-text-subtle)",
        }}
      >
        Coming in next phase
      </div>
    </div>
  );
}

/* ── Dashboard ─────────────────────────────────────────────────────────── */
export function Dashboard() {
  const { cases, loading, fetchCases } = useCaseStore();
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"Timeline" | "Graph" | "Map">("Timeline");
  const [timelineEvents, setTimelineEvents] = useState<TimelineEvent[]>([]);
  const [timelineLoading, setTimelineLoading] = useState(false);
  
  const [evidenceThisWeek, setEvidenceThisWeek] = useState<number | null>(null);

  useEffect(() => { fetchCases(); }, [fetchCases]);

  // Auto-select first case when cases load
  useEffect(() => {
    if (cases.length > 0 && !selectedCaseId) {
      setSelectedCaseId(cases[0].id);
    }
  }, [cases, selectedCaseId]);

  // Fetch timeline when selected case changes
  useEffect(() => {
    if (!selectedCaseId) return;
    setTimelineLoading(true);
    setTimelineEvents([]);
    casesApi.getTimeline(selectedCaseId)
      .then(setTimelineEvents)
      .catch(() => setTimelineEvents([]))
      .finally(() => setTimelineLoading(false));
  }, [selectedCaseId]);

  // Fetch all evidence to calculate this week's trend
  useEffect(() => {
    evidenceApi.listAll()
      .then(ev => {
        const now = new Date();
        const oneWeekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        const recent = ev.filter(e => new Date(e.uploaded_at) >= oneWeekAgo);
        setEvidenceThisWeek(recent.length);
      })
      .catch(console.error);
  }, []);

  const selectedCase: Case | undefined = cases.find((c) => c.id === selectedCaseId);

  const totalEvidence = cases.reduce((s, c) => s + (c.evidence_count ?? 0), 0);
  const openCases     = cases.filter((c) => c.status === "OPEN").length;
  const flaggedCases  = cases.filter((c) => c.status === "UNDER_REVIEW").length;

  // Dynamic trends from real data
  const casesThisWeek    = countAddedThisWeek(cases);
  // For evidence, we don't have individual timestamps available at this level,
  // so we show total count as a fact, not a trend
  const evidenceTrend = totalEvidence > 0 ? `${totalEvidence} total` : undefined;

  const handleTimelineEvent = (ev: TimelineEvent) => {
    console.log("[Dashboard] Timeline event clicked:", ev.id);
  };

  const VIEW_TABS: { label: "Timeline" | "Graph" | "Map"; icon: React.ReactNode }[] = [
    { label: "Timeline", icon: <CalendarDays style={{ width: 12, height: 12 }} /> },
    { label: "Graph",    icon: <GitGraph    style={{ width: 12, height: 12 }} /> },
    { label: "Map",      icon: <Map         style={{ width: 12, height: 12 }} /> },
  ];

  return (
    <div
      style={{ padding: "1.5rem 2rem", minHeight: "100%", display: "flex", flexDirection: "column", gap: "1.5rem" }}
      className="animate-fade-in"
    >
      {/* Page header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <div>
          <h1
            style={{
              fontSize: "1.375rem", fontWeight: 700,
              color: "var(--color-text-primary)", lineHeight: 1.2,
            }}
          >
            Investigation Dashboard
          </h1>
          <p style={{ fontSize: "0.8rem", color: "var(--color-text-muted)", marginTop: 4 }}>
            {loading ? "Loading…" : `${cases.length} case${cases.length !== 1 ? "s" : ""} · ${totalEvidence} evidence files`}
          </p>
        </div>
        <Link to="/cases/new">
          <Button icon={<Plus style={{ width: 14, height: 14 }} />} size="md">
            New Case
          </Button>
        </Link>
      </div>

      {/* KPI Row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.875rem" }}>
        <StatCard
          icon={<FolderOpen style={{ width: 16, height: 16 }} />}
          value={loading ? "—" : cases.length}
          label="Total Cases"
          loading={loading}
          trend={casesThisWeek > 0 ? `+${casesThisWeek} this week` : undefined}
        />
        <StatCard
          icon={<FileVideo style={{ width: 16, height: 16 }} />}
          value={loading ? "—" : totalEvidence}
          label="Evidence Files"
          loading={loading}
          accent="#10b981"
          trend={evidenceThisWeek !== null && evidenceThisWeek > 0 ? `+${evidenceThisWeek} this week` : undefined}
        />
        <StatCard
          icon={<Clock style={{ width: 16, height: 16 }} />}
          value={loading ? "—" : openCases}
          label="Open Cases"
          loading={loading}
          accent="#3b82f6"
        />
        <StatCard
          icon={<ShieldAlert style={{ width: 16, height: 16 }} />}
          value={loading ? "—" : flaggedCases}
          label="Under Review"
          loading={loading}
          accent={flaggedCases > 0 ? "#ef4444" : undefined}
        />
      </div>

      {/* Case Storyline Timeline */}
      <div className="card" style={{ overflow: "hidden" }}>
        {/* Header row */}
        <div
          style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "0.875rem 1.25rem",
            borderBottom: "1px solid var(--color-border)",
            gap: 16, flexWrap: "wrap",
          }}
        >
          {/* Left: Title + Case Selector */}
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div>
              <h2 style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--color-text-primary)" }}>
                Case Storyline
              </h2>
              {selectedCase && (
                <p style={{ fontSize: "0.7rem", color: "var(--color-text-muted)", marginTop: 2 }}>
                  {selectedCase.case_number} · Created {formatDate(selectedCase.created_at)} · Click events to inspect
                </p>
              )}
            </div>

            {/* Case dropdown selector */}
            {cases.length > 0 && (
              <select
                value={selectedCaseId ?? ""}
                onChange={(e) => setSelectedCaseId(e.target.value)}
                style={{
                  background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)",
                  borderRadius: 6, color: "var(--color-text-body)", fontSize: "0.75rem",
                  padding: "4px 8px", cursor: "pointer", outline: "none",
                  transition: "border-color 0.15s",
                }}
                aria-label="Select case for timeline"
              >
                {cases.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.case_number} — {c.title}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Right: View tabs */}
          <div style={{ display: "flex", gap: 4 }}>
            {VIEW_TABS.map(({ label, icon }) => (
              <button
                key={label}
                onClick={() => setViewMode(label)}
                style={{
                  display: "flex", alignItems: "center", gap: 5,
                  padding: "0.25rem 0.75rem", borderRadius: 6, fontSize: "0.72rem", fontWeight: 500,
                  cursor: "pointer", border: "1px solid",
                  background: viewMode === label ? "var(--color-accent)" : "transparent",
                  borderColor: viewMode === label ? "var(--color-accent)" : "var(--color-border)",
                  color: viewMode === label ? "white" : "var(--color-text-muted)",
                  transition: "all 0.15s",
                }}
                aria-pressed={viewMode === label}
              >
                {icon}
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Content area */}
        {viewMode === "Timeline" ? (
          <>
            {/* Timeline — handles its own horizontal scroll internally */}
            <div
              style={{
                opacity: timelineLoading ? 0.5 : 1,
                transition: "opacity 0.2s",
              }}
            >
              <TimelineView events={timelineEvents} onEventClick={handleTimelineEvent} />
            </div>

            {/* Legend */}
            <div
              style={{
                display: "flex", gap: 16, padding: "0.625rem 1.25rem",
                borderTop: "1px solid var(--color-border)",
              }}
            >
              {[
                { color: "#3b82f6", label: "Login" },
                { color: "#f59e0b", label: "Transaction" },
                { color: "#ef4444", label: "Detection" },
                { color: "#10b981", label: "Document" },
                { color: "#ec4899", label: "Alert" },
              ].map((l) => (
                <div key={l.label} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                  <span
                    style={{
                      width: 8, height: 8, borderRadius: "50%", flexShrink: 0,
                      background: l.color,
                      boxShadow: `0 0 4px ${l.color}80`,
                    }}
                  />
                  <span style={{ fontSize: "0.65rem", color: "var(--color-text-muted)" }}>{l.label}</span>
                </div>
              ))}
            </div>
          </>
        ) : (
          <ComingSoonPane label={viewMode} />
        )}
      </div>

      {/* Recent Cases */}
      <div className="card" style={{ overflow: "hidden" }}>
        <div
          style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "0.875rem 1.25rem",
            borderBottom: "1px solid var(--color-border)",
          }}
        >
          <h2 style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--color-text-primary)" }}>
            Recent Cases
          </h2>
          <Link
            to="/cases"
            style={{
              fontSize: "0.72rem", color: "var(--color-accent)", fontWeight: 500,
              textDecoration: "none",
              display: "flex", alignItems: "center", gap: 2,
            }}
          >
            View all <ChevronRight style={{ width: 12, height: 12 }} />
          </Link>
        </div>

        {cases.length === 0 && !loading ? (
          <div
            style={{
              display: "flex", flexDirection: "column", alignItems: "center",
              justifyContent: "center", padding: "3rem 1rem", textAlign: "center",
            }}
          >
            <FolderOpen style={{ width: 40, height: 40, color: "var(--color-border-bright)", marginBottom: 12 }} aria-hidden="true" />
            <p style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--color-text-muted)" }}>
              No cases yet
            </p>
            <p style={{ fontSize: "0.75rem", color: "var(--color-text-subtle)", marginTop: 4, marginBottom: 16 }}>
              Create your first investigation case to get started.
            </p>
            <Link to="/cases">
              <Button size="sm" icon={<Plus style={{ width: 12, height: 12 }} />}>
                Create Case
              </Button>
            </Link>
          </div>
        ) : (
          <table className="dark-table" style={{ width: "100%", borderCollapse: "collapse" }} aria-label="Recent cases">
            <thead>
              <tr>
                <th>Case #</th>
                <th>Title</th>
                <th>Status</th>
                <th>Evidence</th>
                <th>Created</th>
                <th className="sr-only">Actions</th>
              </tr>
            </thead>
            <tbody>
              {(loading ? Array(4).fill(null) : cases.slice(0, 6)).map((c, i) => (
                <tr key={c?.id ?? i}>
                  <td>
                    {c ? (
                      <span style={{ fontSize: "0.75rem", fontFamily: "monospace", color: "var(--color-text-subtle)" }}>
                        {c.case_number}
                      </span>
                    ) : <div className="skeleton" style={{ height: 14, width: 80 }} />}
                  </td>
                  <td>
                    {c ? (
                      <span style={{ fontWeight: 600, color: "var(--color-text-primary)" }}>{c.title}</span>
                    ) : <div className="skeleton" style={{ height: 14, width: 160 }} />}
                  </td>
                  <td>
                    {c ? <Badge variant={statusToVariant(c.status)} />
                       : <div className="skeleton" style={{ height: 20, width: 80, borderRadius: 999 }} />}
                  </td>
                  <td>
                    {c ? (
                      <span style={{ fontSize: "0.8rem", color: "var(--color-text-body)" }}>
                        {c.evidence_count ?? 0}
                      </span>
                    ) : <div className="skeleton" style={{ height: 14, width: 32 }} />}
                  </td>
                  <td>
                    {c ? (
                      <span style={{ fontSize: "0.72rem", fontFamily: "monospace", color: "var(--color-text-subtle)" }}>
                        {formatDate(c.created_at)}
                      </span>
                    ) : <div className="skeleton" style={{ height: 14, width: 80 }} />}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    {c && (
                      <Link
                        to={`/cases/${c.id}`}
                        style={{
                          display: "inline-flex", alignItems: "center", gap: 2,
                          fontSize: "0.72rem", color: "var(--color-accent)",
                          textDecoration: "none", fontWeight: 500,
                        }}
                        aria-label={`Open case ${c.case_number}`}
                      >
                        Open <ChevronRight style={{ width: 12, height: 12 }} />
                      </Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Bottom padding so FAB orb doesn't overlap content */}
      <div style={{ height: "4rem" }} />
    </div>
  );
}
