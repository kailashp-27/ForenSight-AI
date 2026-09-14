// frontend/src/components/evidence/EvidenceUploadWizard.tsx
// Multi-step upload wizard with upfront Evidence Type selection & Hold Point disclaimer
import React, { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import {
  Upload, X, FileVideo, FileImage, FileAudio, FileText,
  AlertTriangle, CheckCircle, Mic, Video, FileCheck, Layers
} from "lucide-react";
import { Button } from "../ui/Button";
import { evidenceApi } from "../../services/api";

interface Props {
  caseId: string;
  onSuccess: () => void;
  onClose: () => void;
}

type EvidenceCategory = "ALL" | "AUDIO" | "VIDEO" | "DOCUMENT" | "IMAGE";

interface CategoryMeta {
  id: EvidenceCategory;
  label: string;
  desc: string;
  icon: any;
  color: string;
  formats: string[];
  mimes: string[];
  badge: string;
}

const CATEGORIES: CategoryMeta[] = [
  {
    id: "AUDIO",
    label: "Audio Recording",
    desc: "Interrogations, phone calls, dispatch logs",
    icon: Mic,
    color: "#a855f7",
    formats: [".mp3", ".wav", ".ogg"],
    mimes: ["audio/mpeg", "audio/wav", "audio/ogg"],
    badge: "Whisper Speech-to-Text",
  },
  {
    id: "VIDEO",
    label: "CCTV / Video",
    desc: "Surveillance footage, dashcam recordings",
    icon: Video,
    color: "#3b82f6",
    formats: [".mp4", ".avi", ".mov"],
    mimes: ["video/mp4", "video/x-msvideo", "video/quicktime"],
    badge: "YOLOv8 + Grad-CAM",
  },
  {
    id: "DOCUMENT",
    label: "Official Document",
    desc: "Bank statements, CDR records, PDF warrants",
    icon: FileText,
    color: "#f59e0b",
    formats: [".pdf"],
    mimes: ["application/pdf"],
    badge: "OCR & Transaction Parser",
  },
  {
    id: "IMAGE",
    label: "Scene Image",
    desc: "Crime scene photos, evidence close-ups",
    icon: FileCheck,
    color: "#10b981",
    formats: [".jpg", ".png", ".webp"],
    mimes: ["image/jpeg", "image/png", "image/webp"],
    badge: "Visual Forensics",
  },
  {
    id: "ALL",
    label: "Auto-Detect",
    desc: "Accept any forensic evidence format",
    icon: Layers,
    color: "var(--color-accent)",
    formats: ["All media"],
    mimes: [
      "audio/mpeg", "audio/wav", "audio/ogg",
      "video/mp4", "video/x-msvideo", "video/quicktime",
      "application/pdf",
      "image/jpeg", "image/png", "image/webp"
    ],
    badge: "Automatic Routing",
  },
];

const ALL_ALLOWED: Record<string, string> = {
  "image/jpeg": "Image", "image/png": "Image", "image/webp": "Image",
  "video/mp4": "Video", "video/x-msvideo": "Video", "video/quicktime": "Video",
  "audio/mpeg": "Audio", "audio/wav": "Audio", "audio/ogg": "Audio",
  "application/pdf": "Document",
};

function FileIcon({ mime }: { mime: string }) {
  const s = { width: 16, height: 16 };
  if (mime.startsWith("video")) return <FileVideo  style={{ ...s, color: "#3b82f6" }} />;
  if (mime.startsWith("image")) return <FileImage  style={{ ...s, color: "#10b981" }} />;
  if (mime.startsWith("audio")) return <FileAudio  style={{ ...s, color: "#a855f7" }} />;
  if (mime.includes("pdf"))    return <FileText   style={{ ...s, color: "#f59e0b" }} />;
  return <Layers style={{ ...s, color: "var(--color-text-subtle)" }} />;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

type Step = 1 | 2 | 3;

export function EvidenceUploadWizard({ caseId, onSuccess, onClose }: Props) {
  const [selectedCategory, setSelectedCategory] = useState<EvidenceCategory>("AUDIO");
  const [step, setStep] = useState<Step>(1);
  const [files, setFiles] = useState<File[]>([]);
  const [disclaimer, setDisclaimer] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadedCount, setUploadedCount] = useState(0);

  const currentCat = CATEGORIES.find((c) => c.id === selectedCategory) || CATEGORIES[0];

  const onDrop = useCallback((accepted: File[]) => {
    const valid = accepted.filter((f) => {
      if (selectedCategory === "ALL") return ALL_ALLOWED[f.type];
      return currentCat.mimes.includes(f.type) || ALL_ALLOWED[f.type];
    });
    
    if (valid.length === 0 && accepted.length > 0) {
      setError(`Selected files do not match format requirements for ${currentCat.label}.`);
      return;
    }

    setFiles(valid);
    setError(null);
    if (valid.length > 0) setStep(2);
  }, [selectedCategory, currentCat]);

  const activeMimes = selectedCategory === "ALL" 
    ? Object.keys(ALL_ALLOWED) 
    : currentCat.mimes;

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: true,
    accept: Object.fromEntries(activeMimes.map((k) => [k, []])),
  });

  const handleUpload = async () => {
    setUploading(true);
    setError(null);
    try {
      for (const file of files) {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("case_id", caseId);
        formData.append("disclaimer_accepted", "true");
        await evidenceApi.upload(formData);
        setUploadedCount((c) => c + 1);
      }
      setStep(3);
      onSuccess();
    } catch (e: any) {
      setError(e.message || "Failed to upload evidence");
    } finally {
      setUploading(false);
    }
  };

  const STEP_LABELS = ["Type & File", "Chain of Custody", "Processing"];

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0, height: "100%" }}>

      {/* Step Indicator */}
      <div
        style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "0.75rem 1.25rem",
          borderBottom: "1px solid var(--color-border)",
          background: "var(--color-bg-canvas)",
        }}
      >
        {[1, 2, 3].map((s) => (
          <React.Fragment key={s}>
            <div
              style={{
                width: 24, height: 24, borderRadius: "50%",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: "0.7rem", fontWeight: 700,
                background: step >= s ? "var(--color-accent)" : "var(--color-bg-elevated)",
                color: step >= s ? "#ffffff" : "var(--color-text-subtle)",
                border: step >= s ? "none" : "1px solid var(--color-border)",
                transition: "all 0.2s",
              }}
            >
              {s}
            </div>
            {s < 3 && (
              <div
                style={{
                  flex: 1, height: 1,
                  background: step > s ? "var(--color-accent)" : "var(--color-border)",
                  transition: "background 0.3s",
                }}
              />
            )}
          </React.Fragment>
        ))}
        <div style={{ display: "flex", gap: 12, marginLeft: 8 }}>
          {STEP_LABELS.map((label, i) => (
            <span
              key={label}
              style={{
                fontSize: "0.68rem", fontWeight: 600,
                color: step === i + 1 ? "var(--color-accent)" : "var(--color-text-subtle)",
                transition: "color 0.15s",
              }}
            >
              {label}
            </span>
          ))}
        </div>
      </div>

      {/* Step Content */}
      <div style={{ flex: 1, padding: "1.25rem", overflowY: "auto" }}>

        {/* Step 1: Category & File Selection */}
        {step === 1 && (
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <div>
              <h3 style={{ fontSize: "0.9rem", fontWeight: 700, color: "var(--color-text-primary)", marginBottom: 2 }}>
                1. Select Evidence Category
              </h3>
              <p style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
                Choose the type of evidence beforehand to activate the correct AI extraction pipeline.
              </p>
            </div>

            {/* Category Cards Grid */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "0.625rem" }}>
              {CATEGORIES.filter(c => c.id !== "ALL").map((cat) => {
                const IconComponent = cat.icon;
                const isSelected = selectedCategory === cat.id;
                return (
                  <div
                    key={cat.id}
                    onClick={() => setSelectedCategory(cat.id)}
                    style={{
                      padding: "0.75rem",
                      borderRadius: 8,
                      border: isSelected ? `1.5px solid ${cat.color}` : "1px solid var(--color-border)",
                      background: isSelected ? "var(--color-bg-elevated)" : "rgba(255,255,255,0.02)",
                      cursor: "pointer",
                      display: "flex",
                      flexDirection: "column",
                      gap: 4,
                      position: "relative",
                      transition: "all 0.15s ease",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <IconComponent style={{ width: 15, height: 15, color: cat.color }} />
                        <span style={{ fontSize: "0.8rem", fontWeight: 600, color: isSelected ? "var(--color-text-primary)" : "var(--color-text-body)" }}>
                          {cat.label}
                        </span>
                      </div>
                      {isSelected && (
                        <div style={{ width: 6, height: 6, borderRadius: "50%", background: cat.color }} />
                      )}
                    </div>
                    <span style={{ fontSize: "0.68rem", color: "var(--color-text-muted)", lineHeight: 1.3 }}>
                      {cat.desc}
                    </span>
                    <div style={{ marginTop: 2, display: "flex", gap: 4 }}>
                      <span style={{ fontSize: "0.62rem", background: "rgba(255,255,255,0.06)", padding: "1px 5px", borderRadius: 4, color: cat.color, fontWeight: 500 }}>
                        {cat.badge}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Dropzone */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--color-text-primary)" }}>
                  2. Upload {currentCat.label}
                </span>
                <span style={{ fontSize: "0.68rem", color: "var(--color-text-subtle)", fontFamily: "monospace" }}>
                  Formats: {currentCat.formats.join(", ")}
                </span>
              </div>

              <div
                {...getRootProps()}
                className={`dropzone${isDragActive ? " active" : ""}`}
                style={{
                  display: "flex", flexDirection: "column",
                  alignItems: "center", justifyContent: "center",
                  height: 135, cursor: "pointer",
                  border: "1.5px dashed var(--color-border-bright)",
                  borderRadius: 8,
                  background: isDragActive ? "rgba(168,85,247,0.06)" : "var(--color-bg-canvas)",
                }}
              >
                <input {...getInputProps()} aria-label="File upload dropzone" />
                <Upload
                  style={{
                    width: 26, height: 26, marginBottom: 6,
                    color: isDragActive ? "var(--color-accent)" : currentCat.color,
                    transition: "color 0.15s",
                  }}
                />
                <p style={{ fontSize: "0.78rem", fontWeight: 600, color: isDragActive ? "var(--color-accent)" : "var(--color-text-body)" }}>
                  {isDragActive ? "Drop file here" : `Drag & drop ${currentCat.label.toLowerCase()} here`}
                </p>
                <p style={{ fontSize: "0.7rem", color: "var(--color-text-subtle)", marginTop: 2 }}>
                  or <span style={{ color: currentCat.color, fontWeight: 500 }}>browse from computer</span>
                </p>
              </div>
            </div>

            {error && (
              <div
                style={{
                  display: "flex", alignItems: "center", gap: 6,
                  fontSize: "0.75rem", color: "#ef4444",
                }}
              >
                <AlertTriangle style={{ width: 13, height: 13, flexShrink: 0 }} />
                {error}
              </div>
            )}
          </div>
        )}

        {/* Step 2: Disclaimer Hold Point */}
        {step === 2 && (
          <div>
            <h3 style={{ fontSize: "0.9rem", fontWeight: 700, color: "var(--color-text-primary)", marginBottom: 4 }}>
              Review & Confirm ({files.length} file{files.length !== 1 ? "s" : ""})
            </h3>

            {/* Selected files */}
            <div
              style={{
                border: "1px solid var(--color-border)",
                borderRadius: 8, overflow: "hidden", marginBottom: 16,
              }}
            >
              {files.map((file, i) => (
                <div
                  key={i}
                  style={{
                    display: "flex", alignItems: "center", gap: 10,
                    padding: "0.625rem 0.875rem",
                    borderBottom: i < files.length - 1 ? "1px solid var(--color-border-subtle)" : "none",
                  }}
                >
                  <FileIcon mime={file.type} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p
                      style={{
                        fontSize: "0.78rem", fontWeight: 500,
                        color: "var(--color-text-primary)",
                        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                      }}
                    >
                      {file.name}
                    </p>
                    <p style={{ fontSize: "0.65rem", color: "var(--color-text-muted)", marginTop: 1 }}>
                      {ALL_ALLOWED[file.type] || "Evidence"} · {formatSize(file.size)}
                    </p>
                  </div>
                  <button
                    onClick={() => setFiles((f) => f.filter((_, j) => j !== i))}
                    style={{
                      background: "transparent", border: "none",
                      color: "var(--color-text-subtle)", cursor: "pointer",
                      transition: "color 0.15s",
                    }}
                    aria-label="Remove file"
                    onMouseEnter={e => (e.currentTarget.style.color = "#ef4444")}
                    onMouseLeave={e => (e.currentTarget.style.color = "var(--color-text-subtle)")}
                  >
                    <X style={{ width: 13, height: 13 }} />
                  </button>
                </div>
              ))}
            </div>

            {/* Disclaimer Hold Point */}
            <div
              style={{
                background: "rgba(245,158,11,0.08)",
                border: "1px solid rgba(245,158,11,0.25)",
                borderRadius: 8, padding: "0.875rem 1rem",
              }}
            >
              <div style={{ display: "flex", gap: 8, marginBottom: 10, alignItems: "center" }}>
                <AlertTriangle style={{ width: 13, height: 13, color: "#f59e0b", flexShrink: 0 }} />
                <span
                  style={{
                    fontSize: "0.65rem", fontWeight: 700, letterSpacing: "0.08em",
                    textTransform: "uppercase", color: "#f59e0b",
                  }}
                >
                  Chain of Custody — Hold Point
                </span>
              </div>
              <label style={{ display: "flex", alignItems: "flex-start", gap: 10, cursor: "pointer" }}>
                <input
                  type="checkbox"
                  id="disclaimer-checkbox"
                  checked={disclaimer}
                  onChange={(e) => setDisclaimer(e.target.checked)}
                  style={{ marginTop: 2, width: 14, height: 14, accentColor: "var(--color-accent)" }}
                  aria-required="true"
                />
                <span style={{ fontSize: "0.75rem", color: "#fbbf24", lineHeight: 1.6 }}>
                  I confirm that uploading this evidence complies with chain-of-custody protocols.
                  I accept responsibility for the legal admissibility of these files.
                  I understand that AI analysis is assistive and requires human verification.
                </span>
              </label>
            </div>

            {error && (
              <div
                style={{
                  marginTop: 12, display: "flex", alignItems: "center", gap: 6,
                  fontSize: "0.78rem", color: "#ef4444",
                }}
              >
                <AlertTriangle style={{ width: 13, height: 13, flexShrink: 0 }} />
                {error}
              </div>
            )}
          </div>
        )}

        {/* Step 3: Success */}
        {step === 3 && (
          <div
            style={{
              display: "flex", flexDirection: "column", alignItems: "center",
              justifyContent: "center", minHeight: 200, textAlign: "center", gap: 12,
            }}
          >
            <div
              style={{
                width: 56, height: 56, borderRadius: "50%",
                background: "rgba(16,185,129,0.1)",
                border: "1px solid rgba(16,185,129,0.3)",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}
            >
              <CheckCircle style={{ width: 24, height: 24, color: "#10b981" }} />
            </div>
            <div>
              <h3 style={{ fontSize: "0.9375rem", fontWeight: 700, color: "var(--color-text-primary)", marginBottom: 6 }}>
                Evidence Ingested
              </h3>
              <p style={{ fontSize: "0.78rem", color: "var(--color-text-muted)", lineHeight: 1.6 }}>
                {uploadedCount} file{uploadedCount !== 1 ? "s" : ""} queued for AI pipeline processing.
                Whisper transcription and forensic analysis will update in real-time.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div
        style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "0.875rem 1.25rem",
          borderTop: "1px solid var(--color-border)",
          background: "var(--color-bg-canvas)",
          flexShrink: 0,
        }}
      >
        <Button variant="secondary" onClick={onClose}>
          {step === 3 ? "Close" : "Cancel"}
        </Button>
        <div style={{ display: "flex", gap: 8 }}>
          {step === 2 && (
            <Button variant="secondary" onClick={() => setStep(1)}>
              Back
            </Button>
          )}
          {step === 2 && (
            <Button
              variant="primary"
              loading={uploading}
              disabled={!disclaimer || files.length === 0}
              onClick={handleUpload}
              icon={<Upload style={{ width: 13, height: 13 }} />}
            >
              Upload {files.length} File{files.length !== 1 ? "s" : ""}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
