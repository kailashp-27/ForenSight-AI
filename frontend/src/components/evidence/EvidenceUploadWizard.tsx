// frontend/src/components/evidence/EvidenceUploadWizard.tsx
// Multi-step upload wizard with Hold Point disclaimer enforcement — dark theme
import React, { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, X, FileVideo, FileImage, FileAudio, FileText, File, AlertTriangle, CheckCircle } from "lucide-react";
import { Button } from "../ui/Button";
import { evidenceApi } from "../../services/api";

interface Props {
  caseId: string;
  onSuccess: () => void;
  onClose: () => void;
}

const ALLOWED_TYPES: Record<string, string> = {
  "image/jpeg": "Image", "image/png": "Image", "image/webp": "Image",
  "video/mp4": "Video", "video/x-msvideo": "Video", "video/quicktime": "Video",
  "audio/mpeg": "Audio", "audio/wav": "Audio", "audio/ogg": "Audio",
  "application/pdf": "Document",
};

function FileIcon({ mime }: { mime: string }) {
  const s = { width: 16, height: 16 };
  if (mime.startsWith("video")) return <FileVideo  style={{ ...s, color: "#3b82f6" }} />;
  if (mime.startsWith("image")) return <FileImage  style={{ ...s, color: "#10b981" }} />;
  if (mime.startsWith("audio")) return <FileAudio  style={{ ...s, color: "#8b5cf6" }} />;
  if (mime.includes("pdf"))    return <FileText   style={{ ...s, color: "#f59e0b" }} />;
  return <File style={{ ...s, color: "var(--color-text-subtle)" }} />;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

type Step = 1 | 2 | 3;

export function EvidenceUploadWizard({ caseId, onSuccess, onClose }: Props) {
  const [step, setStep]             = useState<Step>(1);
  const [files, setFiles]           = useState<File[]>([]);
  const [disclaimer, setDisclaimer] = useState(false);
  const [uploading, setUploading]   = useState(false);
  const [error, setError]           = useState<string | null>(null);
  const [uploadedCount, setUploadedCount] = useState(0);

  const onDrop = useCallback((accepted: File[]) => {
    const valid = accepted.filter((f) => ALLOWED_TYPES[f.type]);
    setFiles(valid);
    if (valid.length > 0) setStep(2);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: true,
    accept: Object.fromEntries(Object.keys(ALLOWED_TYPES).map((k) => [k, []])),
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
      setError(e.message);
    } finally {
      setUploading(false);
    }
  };

  const STEP_LABELS = ["Select", "Confirm", "Done"];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>

      {/* Step Indicator */}
      <div
        style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "0.875rem 1.25rem",
          borderBottom: "1px solid var(--color-border)",
        }}
      >
        {[1, 2, 3].map((s) => (
          <React.Fragment key={s}>
            <div
              style={{
                width: 26, height: 26, borderRadius: "50%",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: "0.7rem", fontWeight: 700,
                background: step >= s ? "var(--color-accent)" : "var(--color-bg-elevated)",
                color: step >= s ? "#ffffff" : "var(--color-text-subtle)",
                border: step >= s ? "none" : "1px solid var(--color-border)",
                transition: "background 0.2s, color 0.2s",
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
                fontSize: "0.7rem", fontWeight: 500,
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

        {/* Step 1: File Selection */}
        {step === 1 && (
          <div>
            <h3 style={{ fontSize: "0.9rem", fontWeight: 700, color: "var(--color-text-primary)", marginBottom: 4 }}>
              Select Evidence Files
            </h3>
            <p style={{ fontSize: "0.77rem", color: "var(--color-text-muted)", marginBottom: 16, lineHeight: 1.5 }}>
              Upload images, videos, audio recordings, or PDF documents.
            </p>

            <div
              {...getRootProps()}
              className={`dropzone${isDragActive ? " active" : ""}`}
              style={{
                display: "flex", flexDirection: "column",
                alignItems: "center", justifyContent: "center",
                height: 180, cursor: "pointer",
              }}
            >
              <input {...getInputProps()} aria-label="File upload dropzone" />
              <Upload
                style={{
                  width: 32, height: 32, marginBottom: 10,
                  color: isDragActive ? "var(--color-accent)" : "var(--color-text-subtle)",
                  transition: "color 0.15s",
                }}
              />
              <p style={{ fontSize: "0.8rem", fontWeight: 600, color: isDragActive ? "var(--color-accent)" : "var(--color-text-body)" }}>
                {isDragActive ? "Drop files here" : "Drag & drop files here"}
              </p>
              <p style={{ fontSize: "0.72rem", color: "var(--color-text-subtle)", marginTop: 4 }}>
                or <span style={{ color: "var(--color-accent)", fontWeight: 500 }}>browse</span>
              </p>
              <p style={{ fontSize: "0.65rem", color: "var(--color-text-subtle)", marginTop: 8, fontFamily: "monospace" }}>
                MP4 · AVI · JPG · PNG · MP3 · WAV · PDF
              </p>
            </div>
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
                      {ALLOWED_TYPES[file.type]} · {formatSize(file.size)}
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
                  I accept responsibility for the accuracy and legal admissibility of these files.
                  I understand that AI analysis is assistive only and does not constitute legal evidence without human verification.
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
                Upload Complete
              </h3>
              <p style={{ fontSize: "0.78rem", color: "var(--color-text-muted)", lineHeight: 1.6 }}>
                {uploadedCount} file{uploadedCount !== 1 ? "s" : ""} submitted for AI processing.
                You will receive real-time progress updates as the pipeline runs.
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
