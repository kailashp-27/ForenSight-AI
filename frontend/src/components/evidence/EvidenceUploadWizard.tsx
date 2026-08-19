// frontend/src/components/evidence/EvidenceUploadWizard.tsx
// Multi-step upload wizard with Hold Point disclaimer enforcement
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
  if (mime.startsWith("video")) return <FileVideo className="w-5 h-5 text-blue-500" />;
  if (mime.startsWith("image")) return <FileImage className="w-5 h-5 text-emerald-500" />;
  if (mime.startsWith("audio")) return <FileAudio className="w-5 h-5 text-violet-500" />;
  if (mime.includes("pdf"))    return <FileText className="w-5 h-5 text-orange-500" />;
  return <File className="w-5 h-5 text-slate-400" />;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

type Step = 1 | 2 | 3;

export function EvidenceUploadWizard({ caseId, onSuccess, onClose }: Props) {
  const [step, setStep] = useState<Step>(1);
  const [files, setFiles] = useState<File[]>([]);
  const [disclaimer, setDisclaimer] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
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

  return (
    <div className="flex flex-col h-full">
      {/* Step Indicator */}
      <div className="flex items-center gap-2 px-6 py-4 border-b border-slate-100">
        {[1, 2, 3].map((s) => (
          <React.Fragment key={s}>
            <div
              className={`flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold
                ${step >= s ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-400"}`}
            >
              {s}
            </div>
            {s < 3 && (
              <div className={`flex-1 h-0.5 ${step > s ? "bg-blue-600" : "bg-slate-100"}`} />
            )}
          </React.Fragment>
        ))}
        <div className="flex gap-4 ml-2">
          <span className={`text-xs font-medium ${step === 1 ? "text-blue-600" : "text-slate-400"}`}>Select</span>
          <span className={`text-xs font-medium ${step === 2 ? "text-blue-600" : "text-slate-400"}`}>Confirm</span>
          <span className={`text-xs font-medium ${step === 3 ? "text-blue-600" : "text-slate-400"}`}>Done</span>
        </div>
      </div>

      <div className="flex-1 p-6 overflow-y-auto">
        {/* Step 1: File Selection */}
        {step === 1 && (
          <div>
            <h3 className="text-base font-semibold text-slate-800 mb-1">Select Evidence Files</h3>
            <p className="text-sm text-slate-500 mb-4">Upload images, videos, audio recordings, or PDF documents.</p>
            <div
              {...getRootProps()}
              className={`
                flex flex-col items-center justify-center h-48 border-2 border-dashed rounded-xl cursor-pointer
                transition-all duration-200
                ${isDragActive
                  ? "border-blue-500 bg-blue-50 scale-[1.01]"
                  : "border-slate-300 bg-slate-50 hover:border-blue-400 hover:bg-blue-50"
                }
              `}
            >
              <input {...getInputProps()} aria-label="File upload dropzone" />
              <Upload className={`w-10 h-10 mb-3 ${isDragActive ? "text-blue-500" : "text-slate-300"}`} />
              <p className="text-sm font-medium text-slate-600">
                {isDragActive ? "Drop files here" : "Drag & drop files here"}
              </p>
              <p className="text-xs text-slate-400 mt-1">or <span className="text-blue-600 font-medium">browse</span></p>
              <p className="text-xs text-slate-400 mt-2">MP4, AVI, JPG, PNG, MP3, WAV, PDF</p>
            </div>
          </div>
        )}

        {/* Step 2: Disclaimer Hold Point */}
        {step === 2 && (
          <div>
            <h3 className="text-base font-semibold text-slate-800 mb-1">
              Review & Confirm ({files.length} file{files.length !== 1 ? "s" : ""})
            </h3>

            {/* Selected files */}
            <div className="border border-slate-200 rounded-xl overflow-hidden mb-4">
              {files.map((file, i) => (
                <div key={i} className="flex items-center gap-3 px-4 py-3 border-b border-slate-100 last:border-0">
                  <FileIcon mime={file.type} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-700 truncate">{file.name}</p>
                    <p className="text-xs text-slate-400">{ALLOWED_TYPES[file.type]} · {formatSize(file.size)}</p>
                  </div>
                  <button onClick={() => setFiles((f) => f.filter((_, j) => j !== i))}
                    className="text-slate-300 hover:text-slate-500 transition-colors" aria-label="Remove file">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>

            {/* Disclaimer Hold Point */}
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <div className="flex gap-2 mb-3">
                <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
                <p className="text-xs font-semibold text-amber-700 uppercase tracking-wide">
                  Chain of Custody — Hold Point
                </p>
              </div>
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  id="disclaimer-checkbox"
                  checked={disclaimer}
                  onChange={(e) => setDisclaimer(e.target.checked)}
                  className="mt-0.5 w-4 h-4 text-blue-600 border-slate-300 rounded focus:ring-2 focus:ring-blue-500"
                  aria-required="true"
                />
                <span className="text-xs text-amber-800 leading-relaxed">
                  I confirm that uploading this evidence complies with chain-of-custody protocols.
                  I accept responsibility for the accuracy and legal admissibility of these files.
                  I understand that AI analysis is assistive only and does not constitute legal evidence without human verification.
                </span>
              </label>
            </div>

            {error && (
              <div className="mt-3 flex items-center gap-2 text-red-600 text-sm">
                <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                {error}
              </div>
            )}
          </div>
        )}

        {/* Step 3: Success */}
        {step === 3 && (
          <div className="flex flex-col items-center justify-center h-48 text-center">
            <CheckCircle className="w-14 h-14 text-emerald-500 mb-4" />
            <h3 className="text-base font-semibold text-slate-800">Upload Complete</h3>
            <p className="text-sm text-slate-500 mt-1">
              {uploadedCount} file{uploadedCount !== 1 ? "s" : ""} submitted for processing.
              You will receive real-time updates as the AI pipeline runs.
            </p>
          </div>
        )}
      </div>

      {/* Footer Actions */}
      <div className="flex items-center justify-between px-6 py-4 border-t border-slate-100 bg-slate-50/50">
        <Button variant="secondary" onClick={onClose}>
          {step === 3 ? "Close" : "Cancel"}
        </Button>
        <div className="flex gap-2">
          {step === 2 && (
            <Button variant="secondary" onClick={() => setStep(1)}>Back</Button>
          )}
          {step === 2 && (
            <Button
              variant="primary"
              loading={uploading}
              disabled={!disclaimer || files.length === 0}
              onClick={handleUpload}
              icon={<Upload />}
            >
              Upload {files.length} File{files.length !== 1 ? "s" : ""}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
