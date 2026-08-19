// frontend/src/pages/CaseDetail.tsx
import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ChevronRight, Upload, FileVideo, FileImage, FileAudio, FileText, File,
  MoreHorizontal, Trash2, ArrowLeft,
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
  const cls = "w-5 h-5";
  if (type === "VIDEO")    return <FileVideo className={`${cls} text-blue-500`} />;
  if (type === "IMAGE")    return <FileImage className={`${cls} text-emerald-500`} />;
  if (type === "AUDIO")    return <FileAudio className={`${cls} text-violet-500`} />;
  if (type === "DOCUMENT") return <FileText className={`${cls} text-orange-500`} />;
  return <File className={`${cls} text-slate-400`} />;
}

export function CaseDetail() {
  const { id } = useParams<{ id: string }>();
  const { selectedCase, loading, fetchCase } = useCaseStore();
  const [showUpload, setShowUpload] = useState(false);

  useEffect(() => {
    if (id) fetchCase(id);
  }, [id, fetchCase]);

  const handleUploadSuccess = () => {
    if (id) fetchCase(id);
    setTimeout(() => setShowUpload(false), 2000);
  };

  if (loading && !selectedCase) {
    return (
      <div className="p-8">
        <div className="h-8 w-48 bg-slate-100 rounded animate-pulse mb-6" />
        <div className="card p-6 space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-5 bg-slate-100 rounded animate-pulse" style={{ width: `${80 - i * 15}%` }} />
          ))}
        </div>
      </div>
    );
  }

  if (!selectedCase) {
    return (
      <div className="p-8 text-center">
        <p className="text-slate-500">Case not found.</p>
        <Link to="/cases" className="text-blue-600 text-sm mt-2 inline-block">← Back to Cases</Link>
      </div>
    );
  }

  const evidence: Evidence[] = selectedCase.evidence ?? [];

  return (
    <div className="p-6 lg:p-8 animate-fade-in">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 text-sm text-slate-400 mb-6" aria-label="Breadcrumb">
        <Link to="/cases" className="hover:text-slate-600 transition-colors flex items-center gap-1">
          <ArrowLeft className="w-3.5 h-3.5" /> Cases
        </Link>
        <ChevronRight className="w-3.5 h-3.5" />
        <span className="text-slate-700 font-medium">{selectedCase.case_number}</span>
      </nav>

      {/* Case Header */}
      <div className="card p-6 mb-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 mb-2 flex-wrap">
              <span className="font-mono text-xs text-slate-400 bg-slate-100 px-2 py-1 rounded">
                {selectedCase.case_number}
              </span>
              <Badge variant={statusToVariant(selectedCase.status)} />
            </div>
            <h1 className="text-xl font-bold text-slate-900 mb-1">{selectedCase.title}</h1>
            {selectedCase.description && (
              <p className="text-sm text-slate-500">{selectedCase.description}</p>
            )}
            <div className="flex items-center gap-4 mt-3 text-xs text-slate-400">
              <span>Investigator: <span className="text-slate-600 font-medium">{selectedCase.created_by_name}</span></span>
              <span>Created: <span className="font-mono">{formatDate(selectedCase.created_at)}</span></span>
              <span>Evidence: <span className="text-slate-600 font-medium">{evidence.length}</span></span>
            </div>
          </div>
          <Button icon={<Upload />} onClick={() => setShowUpload(true)}>
            Upload Evidence
          </Button>
        </div>
      </div>

      {/* Evidence Section */}
      <div className="card overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <h2 className="text-sm font-semibold text-slate-800">Evidence Files</h2>
          <span className="text-xs text-slate-400">{evidence.length} file{evidence.length !== 1 ? "s" : ""}</span>
        </div>

        {evidence.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <Upload className="w-12 h-12 text-slate-200 mb-3" />
            <h3 className="text-sm font-semibold text-slate-600">No evidence uploaded</h3>
            <p className="text-xs text-slate-400 mt-1 mb-4">
              Upload CCTV footage, images, audio, or documents to begin AI analysis.
            </p>
            <Button size="sm" icon={<Upload />} onClick={() => setShowUpload(true)}>
              Upload Evidence
            </Button>
          </div>
        ) : (
          <table className="w-full text-sm" aria-label="Evidence files">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-100">
                <th className="text-left px-6 py-3 text-xs font-bold text-slate-500 uppercase tracking-wider">File</th>
                <th className="text-left px-6 py-3 text-xs font-bold text-slate-500 uppercase tracking-wider">Type</th>
                <th className="text-left px-6 py-3 text-xs font-bold text-slate-500 uppercase tracking-wider">Status</th>
                <th className="text-left px-6 py-3 text-xs font-bold text-slate-500 uppercase tracking-wider">Size</th>
                <th className="text-left px-6 py-3 text-xs font-bold text-slate-500 uppercase tracking-wider">Uploaded</th>
                <th className="sr-only">Actions</th>
              </tr>
            </thead>
            <tbody>
              {evidence.map((ev) => (
                <tr key={ev.id} className="border-b border-slate-50 hover:bg-slate-50/70 transition-colors">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <EvidenceIcon type={ev.file_type} />
                      <span className="font-medium text-slate-700 truncate max-w-[200px]">{ev.file_name}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-slate-500 text-xs uppercase tracking-wide font-mono">{ev.file_type}</span>
                  </td>
                  <td className="px-6 py-4">
                    <Badge variant={statusToVariant(ev.status)} />
                  </td>
                  <td className="px-6 py-4">
                    <span className="font-mono text-xs text-slate-400">{formatSize(ev.file_size)}</span>
                  </td>
                  <td className="px-6 py-4">
                    <span className="font-mono text-xs text-slate-400">{formatDate(ev.uploaded_at)}</span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button
                      className="text-slate-300 hover:text-slate-500 transition-colors"
                      aria-label={`Options for ${ev.file_name}`}
                    >
                      <MoreHorizontal className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Upload Wizard Modal */}
      {showUpload && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-label="Upload evidence"
        >
          <div className="card w-full max-w-lg mx-4 h-[600px] flex flex-col animate-fade-in overflow-hidden">
            <div className="flex items-center justify-between px-6 py-5 border-b border-slate-100">
              <h2 className="text-base font-semibold text-slate-900">Upload Evidence</h2>
              <button
                onClick={() => setShowUpload(false)}
                className="text-slate-400 hover:text-slate-600 transition-colors"
                aria-label="Close upload wizard"
              >
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-hidden">
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
