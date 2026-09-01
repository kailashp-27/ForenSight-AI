// frontend/src/pages/CaseDetail.tsx
import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ChevronRight, Upload, FileVideo, FileImage, FileAudio,
  FileText, File, MoreHorizontal, ArrowLeft, AlertTriangle,
} from "lucide-react";
import { Badge, statusToVariant } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { EvidenceUploadWizard } from "../components/evidence/EvidenceUploadWizard";
import { EvidenceViewer } from "../components/evidence/EvidenceViewer";
import { useCaseStore } from "../store/caseStore";
import type { Evidence } from "../services/api";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function EvidenceIcon({ type }: { type: string }) {
  const s = { width: 16, height: 16 };
  if (type === "VIDEO")    return <FileVideo  style={{ ...s, color: "#3b82f6" }} />;
  if (type === "IMAGE")    return <FileImage  style={{ ...s, color: "#10b981" }} />;
  if (type === "AUDIO")    return <FileAudio  style={{ ...s, color: "#8b5cf6" }} />;
  if (type === "DOCUMENT") return <FileText   style={{ ...s, color: "#f59e0b" }} />;
  return <File style={{ ...s, color: "var(--color-text-subtle)" }} />;
}

export function CaseDetail() {
  const { id } = useParams<{ id: string }>();
  const { selectedCase, loading, fetchCase } = useCaseStore();
  const [showUpload, setShowUpload] = useState(false);
  const [viewingEvidenceId, setViewingEvidenceId] = useState<string | null>(null);

  useEffect(() => { if (id) fetchCase(id); }, [id, fetchCase]);

  const handleUploadSuccess = () => {
    if (id) fetchCase(id);
    setTimeout(() => setShowUpload(false), 2000);
  };

  /* ── Loading skeleton ── */
  if (loading && !selectedCase) {
    return (
      <div style={{ padding: "1.5rem 2rem", display: "flex", flexDirection: "column", gap: "1rem" }}>
        <div className="skeleton" style={{ height: 16, width: 200 }} />
        <div className="card" style={{ padding: "1.25rem" }}>
          {[...Array(4)].map((_, i) => (
            <div key={i} className="skeleton" style={{ height: 14, marginBottom: 10, width: `${80 - i * 15}%` }} />
          ))}
        </div>
      </div>
    );
  }

  if (!selectedCase) {
    return (
      <div style={{ padding: "2rem", textAlign: "center" }}>
        <p style={{ color: "var(--color-text-muted)", fontSize: "0.875rem" }}>Case not found.</p>
        <Link
          to="/cases"
          style={{ color: "var(--color-accent)", fontSize: "0.8rem", marginTop: 8, display: "inline-block" }}
        >
          ← Back to Cases
        </Link>
      </div>
    );
  }

  const [filterType, setFilterType] = useState<string>("ALL");

  const evidence: Evidence[] = selectedCase.evidence ?? [];
  const audioCount = evidence.filter((e) => e.file_type === "AUDIO").length;
  const videoCount = evidence.filter((e) => e.file_type === "VIDEO").length;
  const docCount = evidence.filter((e) => e.file_type === "DOCUMENT").length;
  const imageCount = evidence.filter((e) => e.file_type === "IMAGE").length;

  const filteredEvidence = filterType === "ALL" 
    ? evidence 
    : evidence.filter((e) => e.file_type === filterType);

  const TABS = [
    { id: "ALL", label: "All Evidence", count: evidence.length, icon: File },
    { id: "AUDIO", label: "Audio Transcripts", count: audioCount, icon: FileAudio, color: "#a855f7" },
    { id: "VIDEO", label: "CCTV & Video", count: videoCount, icon: FileVideo, color: "#3b82f6" },
    { id: "DOCUMENT", label: "Documents", count: docCount, icon: FileText, color: "#f59e0b" },
    { id: "IMAGE", label: "Images", count: imageCount, icon: FileImage, color: "#10b981" },
  ];

  return (
    <div
      style={{ padding: "1.5rem 2rem", display: "flex", flexDirection: "column", gap: "1.25rem", minHeight: "100%" }}
      className="animate-fade-in"
    >
      {/* AI Disclaimer */}
      <div className="ai-disclaimer" style={{ borderRadius: 8 }}>
        <AlertTriangle style={{ width: 11, height: 11, flexShrink: 0 }} aria-hidden="true" />
        <span>
          AI analysis results are assistive only. All detections require human verification before any legal use.
        </span>
      </div>

      {/* Breadcrumb */}
      <nav
        style={{
          display: "flex", alignItems: "center", gap: 6,
          fontSize: "0.75rem", color: "var(--color-text-muted)",
        }}
        aria-label="Breadcrumb"
      >
        <Link
          to="/cases"
          style={{
            color: "var(--color-text-muted)", textDecoration: "none",
            display: "flex", alignItems: "center", gap: 4, transition: "color 0.15s",
          }}
          onMouseEnter={e => (e.currentTarget.style.color = "var(--color-text-body)")}
          onMouseLeave={e => (e.currentTarget.style.color = "var(--color-text-muted)")}
        >
          <ArrowLeft style={{ width: 12, height: 12 }} /> Cases
        </Link>
        <ChevronRight style={{ width: 12, height: 12 }} />
        <span style={{ color: "var(--color-text-body)", fontWeight: 500 }}>
          {selectedCase.case_number}
        </span>
      </nav>

      {/* Case Header card */}
      <div className="card" style={{ padding: "1.25rem" }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
              <span
                style={{
                  fontFamily: "monospace", fontSize: "0.7rem",
                  color: "var(--color-text-subtle)",
                  background: "var(--color-bg-elevated)",
                  border: "1px solid var(--color-border)",
                  borderRadius: 4, padding: "2px 6px",
                }}
              >
                {selectedCase.case_number}
              </span>
              <Badge variant={statusToVariant(selectedCase.status)} />
            </div>

            <h1
              style={{
                fontSize: "1.25rem", fontWeight: 700,
                color: "var(--color-text-primary)", lineHeight: 1.3, marginBottom: 4,
              }}
            >
              {selectedCase.title}
            </h1>

            {selectedCase.description && (
              <p style={{ fontSize: "0.8rem", color: "var(--color-text-muted)", lineHeight: 1.5, marginBottom: 10 }}>
                {selectedCase.description}
              </p>
            )}

            <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
              {[
                { label: "Investigator", value: selectedCase.created_by_name },
                { label: "Created",      value: formatDate(selectedCase.created_at) },
                { label: "Evidence",     value: `${evidence.length} file${evidence.length !== 1 ? "s" : ""}` },
              ].map((m) => (
                <div key={m.label}>
                  <span style={{ fontSize: "0.65rem", color: "var(--color-text-subtle)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                    {m.label}
                  </span>
                  <p style={{ fontSize: "0.8rem", color: "var(--color-text-body)", fontWeight: 500, marginTop: 1 }}>
                    {m.value}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <Button
            icon={<Upload style={{ width: 14, height: 14 }} />}
            onClick={() => setShowUpload(true)}
          >
            Upload Evidence
          </Button>
        </div>
      </div>

      {/* Evidence section */}
      <div className="card" style={{ overflow: "hidden", flex: 1 }}>
        <div
          style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "0.75rem 1.25rem", borderBottom: "1px solid var(--color-border)",
            flexWrap: "wrap", gap: 10,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <h2 style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--color-text-primary)" }}>
              Evidence Repository
            </h2>
            <span style={{ fontSize: "0.7rem", color: "var(--color-text-subtle)", background: "var(--color-bg-elevated)", padding: "1px 6px", borderRadius: 4 }}>
              {evidence.length} Total
            </span>
          </div>

          {/* Category Tabs */}
          <div style={{ display: "flex", gap: 4, background: "var(--color-bg-canvas)", padding: 3, borderRadius: 6, border: "1px solid var(--color-border)" }}>
            {TABS.map((tab) => {
              const Icon = tab.icon;
              const isActive = filterType === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setFilterType(tab.id)}
                  style={{
                    display: "flex", alignItems: "center", gap: 5,
                    padding: "4px 9px", borderRadius: 4, border: "none",
                    background: isActive ? "var(--color-bg-elevated)" : "transparent",
                    color: isActive ? "var(--color-text-primary)" : "var(--color-text-muted)",
                    fontSize: "0.7rem", fontWeight: isActive ? 600 : 500,
                    cursor: "pointer", transition: "all 0.15s",
                  }}
                >
                  <Icon style={{ width: 13, height: 13, color: tab.color || (isActive ? "var(--color-accent)" : "inherit") }} />
                  <span>{tab.label}</span>
                  <span
                    style={{
                      fontSize: "0.62rem",
                      padding: "0 4px",
                      borderRadius: 10,
                      background: isActive ? "rgba(255,255,255,0.1)" : "rgba(255,255,255,0.04)",
                      color: isActive ? "var(--color-text-primary)" : "var(--color-text-subtle)",
                    }}
                  >
                    {tab.count}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {filteredEvidence.length === 0 ? (
          <div
            style={{
              display: "flex", flexDirection: "column", alignItems: "center",
              justifyContent: "center", padding: "3rem 1rem", textAlign: "center",
            }}
          >
            <Upload style={{ width: 40, height: 40, color: "var(--color-border-bright)", marginBottom: 12 }} />
            <p style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--color-text-muted)" }}>
              {filterType === "ALL" ? "No evidence uploaded" : `No ${filterType.toLowerCase()} evidence files found`}
            </p>
            <p style={{ fontSize: "0.75rem", color: "var(--color-text-subtle)", marginTop: 4, marginBottom: 16 }}>
              {filterType === "ALL" 
                ? "Upload CCTV footage, images, audio recordings, or documents to begin AI analysis." 
                : `Upload a ${filterType.toLowerCase()} file to initiate forensic processing.`}
            </p>
            <Button size="sm" icon={<Upload style={{ width: 12, height: 12 }} />} onClick={() => setShowUpload(true)}>
              Upload Evidence
            </Button>
          </div>
        ) : (
          <table className="dark-table" style={{ width: "100%", borderCollapse: "collapse" }} aria-label="Evidence files">
            <thead>
              <tr>
                <th>File Name</th>
                <th>Type</th>
                <th>Status</th>
                <th>Size</th>
                <th>Uploaded</th>
                <th style={{ textAlign: "right" }}>Inspect</th>
              </tr>
            </thead>
            <tbody>
              {filteredEvidence.map((ev) => (
                <tr 
                  key={ev.id} 
                  onClick={() => setViewingEvidenceId(ev.id)}
                  style={{ cursor: "pointer" }}
                  onMouseEnter={e => e.currentTarget.style.background = "var(--color-bg-elevated)"}
                  onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                >
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <EvidenceIcon type={ev.file_type} />
                      <div>
                        <span
                          style={{
                            fontWeight: 500, color: "var(--color-text-primary)",
                            maxWidth: 240, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                            display: "block",
                          }}
                        >
                          {ev.file_name}
                        </span>
                        {ev.file_type === "AUDIO" && (
                          <span style={{ fontSize: "0.62rem", color: "#a855f7", fontWeight: 500 }}>
                            🎙️ Whisper Transcript Ready
                          </span>
                        )}
                        {ev.file_type === "VIDEO" && (
                          <span style={{ fontSize: "0.62rem", color: "#3b82f6", fontWeight: 500 }}>
                            🎥 Video Stream & YOLOv8
                          </span>
                        )}
                      </div>
                    </div>
                  </td>
                  <td>
                    <span
                      style={{
                        fontFamily: "monospace", fontSize: "0.65rem",
                        textTransform: "uppercase", letterSpacing: "0.06em",
                        color: "var(--color-text-subtle)",
                        padding: "2px 6px", borderRadius: 4,
                        background: "var(--color-bg-elevated)",
                        border: "1px solid var(--color-border)",
                      }}
                    >
                      {ev.file_type}
                    </span>
                  </td>
                  <td>
                    <Badge variant={statusToVariant(ev.status)} />
                  </td>
                  <td>
                    <span style={{ fontFamily: "monospace", fontSize: "0.72rem", color: "var(--color-text-subtle)" }}>
                      {formatSize(ev.file_size)}
                    </span>
                  </td>
                  <td>
                    <span style={{ fontFamily: "monospace", fontSize: "0.72rem", color: "var(--color-text-subtle)" }}>
                      {formatDate(ev.uploaded_at)}
                    </span>
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setViewingEvidenceId(ev.id);
                      }}
                      style={{
                        background: "rgba(168,85,247,0.1)",
                        border: "1px solid rgba(168,85,247,0.3)",
                        borderRadius: 4, padding: "3px 8px",
                        color: "#c084fc", fontSize: "0.68rem", fontWeight: 600,
                        cursor: "pointer", transition: "all 0.15s",
                      }}
                      onMouseEnter={e => {
                        e.currentTarget.style.background = "rgba(168,85,247,0.2)";
                        e.currentTarget.style.color = "#ffffff";
                      }}
                      onMouseLeave={e => {
                        e.currentTarget.style.background = "rgba(168,85,247,0.1)";
                        e.currentTarget.style.color = "#c084fc";
                      }}
                    >
                      {ev.file_type === "AUDIO" || ev.file_type === "VIDEO" ? "Play / Transcript →" : "Inspect →"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Bottom padding so FAB orb doesn't overlap */}
      <div style={{ height: "4rem" }} />

      {/* Upload Wizard Modal */}
      {showUpload && (
        <div
          className="modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-label="Upload evidence"
          onClick={(e) => e.target === e.currentTarget && setShowUpload(false)}
        >
          <div
            className="card animate-fade-in"
            style={{
              width: "100%", maxWidth: 480, margin: "0 1rem",
              maxHeight: "80vh", display: "flex", flexDirection: "column", overflow: "hidden",
            }}
          >
            <div
              style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "1rem 1.25rem", borderBottom: "1px solid var(--color-border)", flexShrink: 0,
              }}
            >
              <h2 style={{ fontSize: "0.9375rem", fontWeight: 700, color: "var(--color-text-primary)" }}>
                Upload Evidence
              </h2>
              <button
                onClick={() => setShowUpload(false)}
                style={{
                  background: "transparent", border: "1px solid var(--color-border)",
                  borderRadius: 6, width: 28, height: 28, display: "flex",
                  alignItems: "center", justifyContent: "center",
                  color: "var(--color-text-muted)", cursor: "pointer", fontSize: "0.875rem",
                }}
                aria-label="Close upload wizard"
              >
                ✕
              </button>
            </div>
            <div style={{ flex: 1, overflow: "hidden" }}>
              <EvidenceUploadWizard
                caseId={selectedCase.id}
                onSuccess={handleUploadSuccess}
                onClose={() => setShowUpload(false)}
              />
            </div>
          </div>
        </div>
      )}

      {/* Evidence Viewer Modal */}
      {viewingEvidenceId && (
        <EvidenceViewer 
          evidenceId={viewingEvidenceId} 
          onClose={() => setViewingEvidenceId(null)} 
        />
      )}
    </div>
  );
}
