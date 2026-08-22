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

  const evidence: Evidence[] = selectedCase.evidence ?? [];

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
            padding: "0.875rem 1.25rem", borderBottom: "1px solid var(--color-border)",
          }}
        >
          <h2 style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--color-text-primary)" }}>
            Evidence Files
          </h2>
          <span style={{ fontSize: "0.7rem", color: "var(--color-text-subtle)" }}>
            {evidence.length} file{evidence.length !== 1 ? "s" : ""}
          </span>
        </div>

        {evidence.length === 0 ? (
          <div
            style={{
              display: "flex", flexDirection: "column", alignItems: "center",
              justifyContent: "center", padding: "3rem 1rem", textAlign: "center",
            }}
          >
            <Upload style={{ width: 40, height: 40, color: "var(--color-border-bright)", marginBottom: 12 }} />
            <p style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--color-text-muted)" }}>
              No evidence uploaded
            </p>
            <p style={{ fontSize: "0.75rem", color: "var(--color-text-subtle)", marginTop: 4, marginBottom: 16 }}>
              Upload CCTV footage, images, audio, or documents to begin AI analysis.
            </p>
            <Button size="sm" icon={<Upload style={{ width: 12, height: 12 }} />} onClick={() => setShowUpload(true)}>
              Upload Evidence
            </Button>
          </div>
        ) : (
          <table className="dark-table" style={{ width: "100%", borderCollapse: "collapse" }} aria-label="Evidence files">
            <thead>
              <tr>
                <th>File</th>
                <th>Type</th>
                <th>Status</th>
                <th>Size</th>
                <th>Uploaded</th>
                <th className="sr-only">Actions</th>
              </tr>
            </thead>
            <tbody>
              {evidence.map((ev) => (
                <tr key={ev.id}>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <EvidenceIcon type={ev.file_type} />
                      <span
                        style={{
                          fontWeight: 500, color: "var(--color-text-primary)",
                          maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                        }}
                      >
                        {ev.file_name}
                      </span>
                    </div>
                  </td>
                  <td>
                    <span
                      style={{
                        fontFamily: "monospace", fontSize: "0.65rem",
                        textTransform: "uppercase", letterSpacing: "0.06em",
                        color: "var(--color-text-subtle)",
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
                      style={{
                        background: "transparent", border: "none",
                        color: "var(--color-text-subtle)", cursor: "pointer",
                        transition: "color 0.15s",
                      }}
                      aria-label={`Options for ${ev.file_name}`}
                      onMouseEnter={e => (e.currentTarget.style.color = "var(--color-text-body)")}
                      onMouseLeave={e => (e.currentTarget.style.color = "var(--color-text-subtle)")}
                    >
                      <MoreHorizontal style={{ width: 14, height: 14 }} />
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
    </div>
  );
}
