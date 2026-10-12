// frontend/src/pages/Workbench.tsx
// Master ForenSight workbench: video + reticle (the "Operator"), evidence
// drawer, chronological timeline and entity graph — all driven by one set
// of findings so that verifying a draft updates every view.

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { FileVideo, Fingerprint, Loader2, Network, ShieldCheck, ShieldAlert, GitCommitHorizontal } from "lucide-react";
import { evidenceApi, type Evidence } from "../services/api";
import {
  forensicApi, type CaseGraph, type CaseTimeline, type ChainReport, type Finding,
  type RelativeBox, type VideoMeta,
} from "../services/forensicApi";
import { VideoPlayer, type VideoPlayerHandle } from "../components/cctv/VideoPlayer";
import { ReticleCanvas } from "../components/cctv/ReticleCanvas";
import { EvidenceDrawer } from "../components/cctv/EvidenceDrawer";
import { EntityGraph } from "../components/cctv/EntityGraph";
import { TimelineView } from "../components/cctv/TimelineView";
import { AiDisclaimerBanner } from "../components/ai/AiDisclaimerBanner";

const OPERATOR_KEY = "forensight.operatorId";

function loadOperator(): string {
  try {
    return localStorage.getItem(OPERATOR_KEY) || "OPERATOR-1";
  } catch {
    return "OPERATOR-1";
  }
}

// ── evidence picker (no clip selected) ───────────────────────────────────────

function VideoPicker() {
  const [items, setItems] = useState<Evidence[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    evidenceApi
      .listAll()
      .then((all) => setItems(all.filter((e) => e.file_type === "VIDEO")))
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <div style={{ padding: "1.5rem", maxWidth: 900, margin: "0 auto" }} className="animate-fade-in">
      <h1 style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--color-text-primary)" }}>Forensic Workbench</h1>
      <p style={{ fontSize: "0.8rem", color: "var(--color-text-muted)", margin: "4px 0 16px" }}>
        Select a CCTV clip to inspect frame-by-frame, mark regions of interest and review local-model observations.
      </p>
      {error && <p role="alert" style={{ color: "#fca5a5", fontSize: "0.8rem" }}>{error}</p>}
      {!items && !error && <Loader2 className="animate-spin" />}
      {items && items.length === 0 && (
        <p style={{ color: "var(--color-text-muted)", fontSize: "0.85rem" }}>
          No video evidence uploaded yet. Upload a clip from a case first.
        </p>
      )}
      <div style={{ display: "grid", gap: 8 }}>
        {items?.map((e) => (
          <Link
            key={e.id}
            to={`/workbench/${e.id}`}
            className="card"
            style={{ display: "flex", alignItems: "center", gap: 12, padding: "0.75rem 1rem", textDecoration: "none" }}
          >
            <FileVideo size={20} style={{ color: "var(--color-accent)" }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ color: "var(--color-text-primary)", fontWeight: 600, fontSize: "0.9rem" }}>{e.file_name}</div>
              <div style={{ color: "var(--color-text-muted)", fontSize: "0.72rem" }}>
                {e.case_number ? `${e.case_number} · ` : ""}{e.case_title ?? e.case_id}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

// ── workbench ────────────────────────────────────────────────────────────────

export function Workbench() {
  const { evidenceId } = useParams<{ evidenceId?: string }>();
  if (!evidenceId) return <VideoPicker />;
  return <WorkbenchForClip key={evidenceId} evidenceId={evidenceId} />;
}

function WorkbenchForClip({ evidenceId }: { evidenceId: string }) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const playerRef = useRef<VideoPlayerHandle>(null);

  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [meta, setMeta] = useState<VideoMeta | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [findings, setFindings] = useState<Finding[]>([]);
  const [frameIndex, setFrameIndex] = useState(0);
  const [scanning, setScanning] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [latest, setLatest] = useState<{ id: string; preview: string } | null>(null);

  const [operatorId, setOperatorId] = useState(loadOperator);
  const [graph, setGraph] = useState<CaseGraph | null>(null);
  const [timeline, setTimeline] = useState<CaseTimeline | null>(null);
  const [viewsLoading, setViewsLoading] = useState(false);
  const [lowerTab, setLowerTab] = useState<"timeline" | "graph">("timeline");
  const [chain, setChain] = useState<ChainReport | null>(null);
  const [chainBusy, setChainBusy] = useState(false);

  const caseId = evidence?.case_id;

  // Initial load: evidence row, probe, existing findings.
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [ev, m, f] = await Promise.all([
          evidenceApi.get(evidenceId),
          forensicApi.videoMeta(evidenceId),
          forensicApi.findings(evidenceId),
        ]);
        if (!alive) return;
        setEvidence(ev);
        setMeta(m);
        setFindings(f);
      } catch (e) {
        if (alive) setLoadError((e as Error).message);
      }
    })();
    return () => {
      alive = false;
    };
  }, [evidenceId]);

  // Timeline + graph derive from verified findings; refetch whenever findings change.
  const verifiedSignature = useMemo(
    () => findings.map((f) => `${f.id}:${f.verification_status}:${f.label}:${f.readout_text}`).join("|"),
    [findings]
  );
  useEffect(() => {
    if (!caseId) return;
    let alive = true;
    setViewsLoading(true);
    Promise.all([forensicApi.graph(caseId), forensicApi.timeline(caseId, true)])
      .then(([g, t]) => {
        if (!alive) return;
        setGraph(g);
        setTimeline(t);
      })
      .catch((e: Error) => alive && setError(e.message))
      .finally(() => alive && setViewsLoading(false));
    return () => {
      alive = false;
    };
  }, [caseId, verifiedSignature]);

  const replaceFinding = useCallback((updated: Finding) => {
    setFindings((prev) => prev.map((f) => (f.id === updated.id ? updated : f)));
  }, []);

  const handleScan = async (box: RelativeBox) => {
    setScanning(true);
    setError(null);
    try {
      const frame = playerRef.current?.getFrameIndex() ?? frameIndex;
      const res = await forensicApi.scanRoi({ video_id: evidenceId, frame_offset: frame, operator_id: operatorId, ...box });
      setFindings((prev) => [...prev, res.finding]);
      setLatest({ id: res.finding.id, preview: res.crop_preview_b64 });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setScanning(false);
    }
  };

  const withBusy = async (id: string, fn: () => Promise<Finding>) => {
    setBusyId(id);
    setError(null);
    try {
      replaceFinding(await fn());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusyId(null);
    }
  };

  const runChainCheck = async () => {
    setChainBusy(true);
    try {
      setChain(await forensicApi.verifyChain());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setChainBusy(false);
    }
  };

  const onOperatorChange = (v: string) => {
    setOperatorId(v);
    try {
      localStorage.setItem(OPERATOR_KEY, v);
    } catch {
      /* storage may be unavailable; operator id just won't persist */
    }
  };

  const seekTo = (ms: number) => playerRef.current?.seekToMs(ms);

  // Deep link from a clue match: /workbench/<id>?t=<ms>
  const deepLinkMs = searchParams.get("t");
  useEffect(() => {
    if (!meta || deepLinkMs === null) return;
    const ms = Number(deepLinkMs);
    if (!Number.isFinite(ms)) return;
    const id = window.setTimeout(() => playerRef.current?.seekToMs(ms), 400);
    return () => window.clearTimeout(id);
  }, [meta, deepLinkMs]);

  if (loadError) {
    return (
      <div style={{ padding: "2rem" }}>
        <p role="alert" style={{ color: "#fca5a5" }}>{loadError}</p>
        <Link to="/workbench" style={{ color: "var(--color-accent)", fontSize: "0.85rem" }}>← Back to clip list</Link>
      </div>
    );
  }
  if (!evidence || !meta) {
    return (
      <div style={{ padding: "2rem", display: "flex", gap: 10, alignItems: "center", color: "var(--color-text-muted)" }}>
        <Loader2 className="animate-spin" size={18} /> Loading clip…
      </div>
    );
  }

  const tabStyle = (active: boolean): React.CSSProperties => ({
    display: "inline-flex", alignItems: "center", gap: 6, padding: "6px 12px", borderRadius: 6,
    border: "none", cursor: "pointer", fontSize: "0.78rem", fontWeight: active ? 700 : 500,
    background: active ? "var(--color-accent-light)" : "transparent",
    color: active ? "var(--color-text-primary)" : "var(--color-text-muted)",
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }} className="animate-fade-in">
      <AiDisclaimerBanner />

      {/* header */}
      <div
        style={{
          display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap",
          padding: "0.6rem 1rem", borderBottom: "1px solid var(--color-border)", background: "var(--color-bg-header)",
        }}
      >
        <FileVideo size={18} style={{ color: "var(--color-accent)" }} />
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: "0.9rem", color: "var(--color-text-primary)" }}>{evidence.file_name}</div>
          <div
            title={meta.file_sha256}
            style={{ fontFamily: "monospace", fontSize: "0.65rem", color: "var(--color-text-subtle)", display: "flex", gap: 4, alignItems: "center" }}
          >
            <Fingerprint size={11} /> SHA-256 {meta.file_sha256.slice(0, 20)}… · {meta.width}×{meta.height}
          </div>
        </div>

        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <label style={{ fontSize: "0.7rem", color: "var(--color-text-muted)", display: "flex", alignItems: "center", gap: 6 }}>
            Operator ID
            <input
              value={operatorId}
              maxLength={100}
              onChange={(e) => onOperatorChange(e.target.value)}
              style={{
                width: 130, height: 30, background: "var(--color-bg-input)", color: "var(--color-text-primary)",
                border: "1px solid var(--color-border-bright)", borderRadius: 6, padding: "0 8px", fontSize: "0.78rem",
                fontFamily: "monospace",
              }}
            />
          </label>
          <button
            onClick={runChainCheck}
            disabled={chainBusy}
            style={{
              display: "inline-flex", alignItems: "center", gap: 6, height: 30, padding: "0 10px", borderRadius: 6,
              border: "1px solid var(--color-border-bright)", background: "var(--color-bg-elevated)",
              color: "var(--color-text-body)", fontSize: "0.72rem", fontWeight: 600, cursor: "pointer",
            }}
          >
            {chainBusy ? <Loader2 size={13} className="animate-spin" /> : <GitCommitHorizontal size={13} />}
            Verify custody chain
          </button>
          {chain && (
            <span
              role="status"
              style={{
                display: "inline-flex", alignItems: "center", gap: 5, fontSize: "0.7rem", fontWeight: 700,
                color: chain.ok ? "#10b981" : "#ef4444",
              }}
            >
              {chain.ok ? <ShieldCheck size={14} /> : <ShieldAlert size={14} />}
              {chain.ok ? `Intact · ${chain.entries_checked} entries` : `BROKEN at #${chain.broken_at_seq}`}
            </span>
          )}
        </div>
      </div>

      {/* body */}
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <div style={{ flex: 1, minWidth: 0, overflowY: "auto", padding: "1rem", display: "flex", flexDirection: "column", gap: 14 }}>
          <VideoPlayer
            ref={playerRef}
            src={`/api/evidence/media/${evidenceId}`}
            fps={meta.fps}
            durationMs={meta.duration_ms}
            onFrameChange={(idx) => setFrameIndex(idx)}
            overlay={(videoRef) => (
              <ReticleCanvas videoRef={videoRef} frameKey={frameIndex} loading={scanning} onScan={handleScan} />
            )}
          />

          <section className="card" style={{ padding: "0.75rem", display: "flex", flexDirection: "column", minHeight: 300 }}>
            <div style={{ display: "flex", gap: 4, marginBottom: 8 }} role="tablist">
              <button role="tab" aria-selected={lowerTab === "timeline"} style={tabStyle(lowerTab === "timeline")} onClick={() => setLowerTab("timeline")}>
                Timeline
              </button>
              <button role="tab" aria-selected={lowerTab === "graph"} style={tabStyle(lowerTab === "graph")} onClick={() => setLowerTab("graph")}>
                <Network size={13} /> Entity graph
              </button>
              {viewsLoading && <Loader2 size={14} className="animate-spin" style={{ marginLeft: 8, alignSelf: "center" }} />}
            </div>
            <div style={{ flex: 1, minHeight: 240 }}>
              {lowerTab === "timeline" ? (
                <TimelineView
                  data={timeline}
                  activeEvidenceId={evidenceId}
                  onSelect={(evId, ms) => (evId === evidenceId ? seekTo(ms) : navigate(`/workbench/${evId}`))}
                />
              ) : (
                <EntityGraph graph={graph} loading={viewsLoading} />
              )}
            </div>
          </section>
        </div>

        <div style={{ width: 380, flexShrink: 0, minHeight: 0 }}>
          <EvidenceDrawer
            findings={findings}
            latestPreviewB64={latest?.preview}
            latestFindingId={latest?.id}
            busyId={busyId}
            error={error}
            onDismissError={() => setError(null)}
            onVerify={(id) => withBusy(id, () => forensicApi.verify(id, operatorId))}
            onUnverify={(id) => withBusy(id, () => forensicApi.unverify(id, operatorId))}
            onEdit={(id, changes) => withBusy(id, () => forensicApi.edit(id, operatorId, changes))}
            onSeek={seekTo}
          />
        </div>
      </div>
    </div>
  );
}
