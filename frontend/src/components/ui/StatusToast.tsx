// frontend/src/components/ui/StatusToast.tsx
// Real-time Socket.io processing toast notifications
import React from "react";
import { X, CheckCircle, AlertTriangle } from "lucide-react";
import { useSocketStore, type ProcessingToast } from "../../store/socketStore";

function ToastItem({ toast }: { toast: ProcessingToast }) {
  const dismiss = useSocketStore((s) => s.dismissToast);
  const isCompleted = toast.status === "COMPLETED" || toast.status === "CLEARED";
  const isFailed = toast.status === "FAILED";

  return (
    <div
      className="animate-slide-in-right bg-white border border-slate-200 rounded-xl shadow-elevated p-4 w-80"
      role="alert"
      aria-live="polite"
    >
      <div className="flex items-start gap-3">
        {/* Status Icon */}
        <div className="flex-shrink-0 mt-0.5">
          {isCompleted ? (
            <CheckCircle className="w-5 h-5 text-emerald-500" />
          ) : isFailed ? (
            <AlertTriangle className="w-5 h-5 text-red-500" />
          ) : (
            <div className="relative flex h-3 w-3 mt-1">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
              <span className="relative inline-flex h-3 w-3 rounded-full bg-blue-600" />
            </div>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-slate-800 truncate">{toast.file_name}</p>
          <p className="text-xs text-slate-500 mt-0.5">{toast.message}</p>

          {/* Progress Bar */}
          {!isCompleted && !isFailed && (
            <div className="mt-2">
              <div className="flex justify-between text-xs text-slate-400 mb-1">
                <span>{toast.status}</span>
                <span>{toast.progress}%</span>
              </div>
              <div className="h-1 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-600 rounded-full transition-all duration-300"
                  style={{ width: `${toast.progress}%` }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Dismiss */}
        <button
          onClick={() => dismiss(toast.evidence_id)}
          className="flex-shrink-0 text-slate-400 hover:text-slate-600 transition-colors"
          aria-label="Dismiss notification"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

export function StatusToastContainer() {
  const toasts = useSocketStore((s) => s.toasts);
  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <ToastItem key={toast.evidence_id} toast={toast} />
      ))}
    </div>
  );
}
