// frontend/src/pages/Investigation.tsx
// Case investigation board: runs automatic analysis over every evidence item
// and shows what the portal connected — shared clues, map, graph, report.

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft, Clock, Download, Fingerprint, FileText, GraduationCap, Link2, ListChecks, Loader2, MapPin, MessageSquareText, Network, Play,
  Printer, Sparkles,
} from "lucide-react";
import { casesApi, type Case } from "../services/api";
import {
  investigationApi, caseViewsApi, caseBoardApi, type EventTimelineData, type KeyFindingsData, type AnalysisStatus, type CaseClue, type CaseGraph, type CaseMapData,
  type CaseTranscripts, type ClueMatch, type Correlations,
} from "../services/forensicApi";
import { ClueMatches } from "../components/investigation/ClueMatches";
import { ClueList } from "../components/investigation/ClueList";
import { KeyFindings } from "../components/investigation/KeyFindings";
import { EventTimeline } from "../components/investigation/EventTimeline";
import { TranscriptsPanel } from "../components/investigation/TranscriptsPanel";
import { ReviewQueue } from "../components/investigation/ReviewQueue";
import { CaseMap } from "../components/investigation/CaseMap";
import { EntityGraph } from "../components/cctv/EntityGraph";
import { AiDisclaimerBanner } from "../components/ai/AiDisclaimerBanner";

type Tab = "key" | "timeline" | "matches" | "clues" | "transcripts" | "review" | "map" | "graph" | "report";

const STATUS_COLOR: Record<string, string> = {
  COMPLETED: "#10b981", PARTIAL: "#f59e0b", RUNNING: "#3b82f6", FAILED: "#ef4444", NOT_RUN: "#64748b",
};

export function Investigation() {
  const { id: caseId } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [theCase, setTheCase] = useState<Case | null>(null);
  const [corr, setCorr] = useState<Correlations | null>(null);
  const [status, setStatus] = useState<AnalysisStatus | null>(null);
  const [map, setMap] = useState<CaseMapData | null>(null);
  const [graph, setGraph] = useState<CaseGraph | null>(null);
  const [clues, setClues] = useState<CaseClue[] | null>(null);
  const [keyFindings, setKeyFindings] = useState<KeyFindingsData | null>(null);
  const [events, setEvents] = useState<EventTimelineData | null>(null);
  const [transcripts, setTranscripts] = useState<CaseTranscripts | null>(null);
  const [tab, setTab] = useState<Tab>("key");
  const [highlight, setHighlight] = useState<ClueMatch | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const wasRunning = useRef(false);

  const loadViews = useCallback(async () => {
    if (!caseId) return;
    try {
      const [c, m, g, cl, tr, kf, ev] = await Promise.all([
        investigationApi.correlations(caseId),
        investigationApi.map(caseId),
        investigationApi.clueGraph(caseId),
        caseViewsApi.caseClues(caseId),
        caseViewsApi.transcripts(caseId),
        caseBoardApi.keyFindings(caseId),
        caseBoardApi.eventTimeline(caseId),
      ]);
      setKeyFindings(kf);
      setEvents(ev);
      setCorr(c);
      setMap(m);
      setGraph(g);
      setClues(cl);
      setTranscripts(tr);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [caseId]);

  const loadStatus = useCallback(async () => {
    if (!caseId) return null;
    try {
      const s = await investigationApi.status(caseId);
      setStatus(s);
      return s;
    } catch (e) {
      setError((e as Error).message);
      return null;
    }
  }, [caseId]);

  useEffect(() => {
    if (!caseId) return;
    casesApi.get(caseId).then(setTheCase).catch((e: Error) => setError(e.message));
    void loadStatus();
    void loadViews();
  }, [caseId, loadStatus, loadViews]);

  // Poll while analysis runs; refresh the views once it finishes.
  const running = status?.running ?? false;
  useEffect(() => {
    if (!running) {
      if (wasRunning.current) {
        wasRunning.current = false;
        void loadViews();
      }
      return;
    }
    wasRunning.current = true;
    const t = window.setInterval(() => void loadStatus(), 2500);
    return () => window.clearInterval(t);
  }, [running, loadStatus, loadViews]);

  const runAnalysis = async () => {
    if (!caseId) return;
    setStarting(true);
    setError(null);
    try {
      await investigationApi.analyzeCase(caseId);
      await loadStatus();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setStarting(false);
    }
  };

  const openMember = (evidenceId: string, fileType: string | null, ts: number | null) => {
    if (fileType === "VIDEO") navigate(`/workbench/${evidenceId}${ts != null ? `?t=${ts}` : ""}`);
    else navigate(`/cases/${caseId}?view=${evidenceId}`);
  };

  const typeOf = (evidenceId: string) => status?.items.find((i) => i.evidence_id === evidenceId)?.file_type ?? null;

  const extractText = async (evidenceId: string) => {
    try {
      await investigationApi.analyzeEvidence(evidenceId);
      await loadStatus();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const totals = corr?.totals;
  const highlightedEvidence = useMemo(() => highlight?.evidence_ids ?? [], [highlight]);

  const tabBtn = (t: Tab, label: string, icon: React.ReactNode, badge?: number) => (
    <button
      role="tab"
      aria-selected={tab === t}
      onClick={() => setTab(t)}
      style={{
        display: "inline-flex", alignItems: "center", gap: 6, padding: "7px 14px", borderRadius: 6, border: "none",
        cursor: "pointer", fontSize: "0.8rem", fontWeight: tab === t ? 700 : 500,
        background: tab === t ? "var(--color-accent-light)" : "transparent",
        color: tab === t ? "var(--color-text-primary)" : "var(--color-text-muted)",
      }}
    >
      {icon}
      {label}
      {badge != null && badge > 0 && (
        <span style={{ fontSize: "0.65rem", background: "rgba(168,85,247,0.2)", color: "#c084fc", borderRadius: 10, padding: "0 6px" }}>
          {badge}
        </span>
      )}
    </button>
  );

  const kpi = (label: string, value: number | string | undefined, color?: string, goTo?: Tab) => (
    <div
      className="card"
      role={goTo ? "button" : undefined}
      tabIndex={goTo ? 0 : undefined}
      aria-label={goTo ? `${label}: ${value ?? 0}. Open list` : undefined}
      onClick={goTo ? () => setTab(goTo) : undefined}
      onKeyDown={goTo ? (e) => e.key === "Enter" && setTab(goTo) : undefined}
      style={{ padding: "0.6rem 0.9rem", minWidth: 110, cursor: goTo ? "pointer" : "default",
               borderColor: goTo && tab === goTo ? "var(--color-accent)" : undefined }}
    >
      <div style={{ fontSize: "1.35rem", fontWeight: 800, color: color ?? "var(--color-text-primary)" }}>{value ?? "–"}</div>
      <div style={{ fontSize: "0.68rem", color: "var(--color-text-muted)" }}>
        {label}{goTo ? " ›" : ""}
      </div>
    </div>
  );

  return (
    <div className="animate-fade-in" style={{ display: "flex", flexDirection: "column", minHeight: "100%" }}>
      <AiDisclaimerBanner />

      <div style={{ padding: "1rem 1.25rem", borderBottom: "1px solid var(--color-border)", background: "var(--color-bg-header)" }}>
        <Link to={`/cases/${caseId}`} style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: "0.72rem", color: "var(--color-text-muted)", textDecoration: "none" }}>
          <ArrowLeft size={13} /> Back to case
        </Link>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginTop: 6 }}>
          <div style={{ flex: 1, minWidth: 220 }}>
            <h1 style={{ fontSize: "1.2rem", fontWeight: 700, color: "var(--color-text-primary)" }}>
              Investigation board{theCase ? ` — ${theCase.title}` : ""}
            </h1>
            <p style={{ fontSize: "0.74rem", color: "var(--color-text-muted)", marginTop: 2 }}>
              The portal reads every file, extracts clues and links the ones that appear in more than one item.
            </p>
          </div>
          <button
            onClick={runAnalysis}
            disabled={starting || running}
            style={{
              display: "inline-flex", alignItems: "center", gap: 8, height: 40, padding: "0 16px", borderRadius: 8,
              border: "1px solid var(--color-accent)", background: "var(--color-accent)", color: "#fff",
              fontWeight: 700, fontSize: "0.82rem", cursor: running ? "wait" : "pointer", opacity: starting || running ? 0.75 : 1,
            }}
          >
            {starting || running ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}
            {running ? "Analysing evidence…" : "Run automatic analysis"}
          </button>
        </div>

        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 12 }}>
          {kpi("Evidence", totals?.evidence)}
          {kpi("Clues extracted", totals?.clues, undefined, "clues")}
          {kpi("Strong matches", totals?.strong, "#10b981", "matches")}
          {kpi("Medium matches", totals?.medium, "#f59e0b", "matches")}
          {kpi("Shared keywords", totals?.keywords, "#06b6d4", "matches")}
          {kpi("Weak similarities", totals?.weak, "#94a3b8")}
        </div>
      </div>

      {error && (
        <div role="alert" style={{ margin: "0.75rem 1.25rem 0", padding: "0.5rem 0.75rem", borderRadius: 6, fontSize: "0.78rem",
                                   background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.35)", color: "#fca5a5" }}>
          {error}
        </div>
      )}

      {/* per-file analysis status */}
      {status && status.items.length > 0 && (
        <div style={{ padding: "0.75rem 1.25rem 0", display: "flex", gap: 8, flexWrap: "wrap" }}>
          {status.items.map((it) => (
            <div key={it.evidence_id} className="card" title={it.message ?? ""} style={{ padding: "0.4rem 0.65rem", minWidth: 190 }}>
              <div style={{ fontSize: "0.72rem", fontWeight: 600, color: "var(--color-text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 220 }}>
                {it.file_name}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 3 }}>
                <span style={{ fontSize: "0.62rem", fontWeight: 700, color: STATUS_COLOR[it.status] ?? "#64748b" }}>
                  {it.status.replace("_", " ")}
                </span>
                {it.status === "RUNNING" && (
                  <div style={{ flex: 1, height: 4, background: "var(--color-border)", borderRadius: 2 }}>
                    <div style={{ width: `${it.progress}%`, height: "100%", background: "#3b82f6", borderRadius: 2, transition: "width 0.4s" }} />
                  </div>
                )}
                {it.status === "NOT_RUN" && <Play size={10} style={{ color: "#64748b" }} />}
              </div>
            </div>
          ))}
        </div>
      )}

      <div style={{ padding: "0.75rem 1.25rem", display: "flex", gap: 4 }} role="tablist">
        {tabBtn("key", "Key findings", <Fingerprint size={14} />,
                (keyFindings?.people.length ?? 0) + (keyFindings?.items.length ?? 0) + (keyFindings?.vehicles.length ?? 0))}
        {tabBtn("timeline", "Event timeline", <Clock size={14} />, events?.groups.length)}
        {tabBtn("matches", "Matching clues", <Link2 size={14} />, (totals?.strong ?? 0) + (totals?.medium ?? 0))}
        {tabBtn("clues", "All clues", <ListChecks size={14} />, totals?.clues)}
        {tabBtn("transcripts", "Transcripts & text", <MessageSquareText size={14} />, transcripts?.totals.passages)}
        {tabBtn("review", "Review detections", <GraduationCap size={14} />)}
        {tabBtn("map", "Map", <MapPin size={14} />, map?.points.length)}
        {tabBtn("graph", "Graph", <Network size={14} />)}
        {tabBtn("report", "Report", <FileText size={14} />)}
      </div>

      <div style={{ flex: 1, padding: "0 1.25rem 1.25rem", minHeight: 0 }}>
        {tab === "matches" && (
          <ClueMatches
            matches={corr?.matches ?? []}
            highlightedId={highlight?.id}
            onHighlight={setHighlight}
            onOpenMember={openMember}
          />
        )}

        {tab === "key" && (
          <KeyFindings
            data={keyFindings}
            onOpen={(eid, ms) => openMember(eid, typeOf(eid), ms)}
          />
        )}

        {tab === "timeline" && (
          <EventTimeline
            data={events}
            onOpen={(eid, ftype, ms) => openMember(eid, ftype ?? typeOf(eid), ms)}
          />
        )}

        {tab === "clues" && (
          <ClueList
            clues={clues}
            onShowMatches={() => setTab("matches")}
            onOpen={(eid, ts) => openMember(eid, typeOf(eid), ts)}
          />
        )}

        {tab === "transcripts" && (
          <TranscriptsPanel
            data={transcripts}
            onAnalyze={extractText}
            onOpen={(eid, ftype, ts) => openMember(eid, ftype, ts)}
          />
        )}

        {tab === "review" && caseId && (
          <ReviewQueue caseId={caseId} operatorId={localStorage.getItem("forensight.operatorId") || "OPERATOR-1"} onChanged={() => void loadViews()} />
        )}

        {tab === "map" && (
          <div style={{ height: "62vh", minHeight: 420 }}>
            <CaseMap
              data={map}
              selectedEvidenceIds={highlightedEvidence}
              onSelectEvidence={(eid) => {
                const ev = status?.items.find((i) => i.evidence_id === eid);
                if (ev) openMember(eid, ev.file_type, null);
              }}
              onSetLocation={async (eid, lat, lon) => {
                await investigationApi.setLocation(eid, lat, lon, "Manual entry");
                await loadViews();
              }}
            />
          </div>
        )}

        {tab === "graph" && (
          <div className="card" style={{ height: "62vh", minHeight: 420, padding: 8 }}>
            <EntityGraph graph={graph} />
          </div>
        )}

        {tab === "report" && caseId && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <a
                href={investigationApi.reportUrl(caseId, true)}
                style={{ display: "inline-flex", alignItems: "center", gap: 6, height: 34, padding: "0 12px", borderRadius: 6,
                         background: "var(--color-accent)", color: "#fff", fontSize: "0.78rem", fontWeight: 700, textDecoration: "none" }}
              >
                <Download size={14} /> Download HTML
              </a>
              <button
                onClick={() => (document.getElementById("report-frame") as HTMLIFrameElement | null)?.contentWindow?.print()}
                style={{ display: "inline-flex", alignItems: "center", gap: 6, height: 34, padding: "0 12px", borderRadius: 6,
                         background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-bright)",
                         color: "var(--color-text-body)", fontSize: "0.78rem", fontWeight: 700, cursor: "pointer" }}
              >
                <Printer size={14} /> Print / save as PDF
              </button>
              <span style={{ alignSelf: "center", fontSize: "0.7rem", color: "var(--color-text-subtle)" }}>
                Generating a report is recorded in the chain of custody.
              </span>
            </div>
            <iframe
              id="report-frame"
              title="Case report"
              src={investigationApi.reportUrl(caseId)}
              style={{ width: "100%", height: "70vh", border: "1px solid var(--color-border)", borderRadius: 8, background: "#fff" }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
