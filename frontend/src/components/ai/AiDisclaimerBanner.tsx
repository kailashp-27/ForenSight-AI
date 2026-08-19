// frontend/src/components/ai/AiDisclaimerBanner.tsx
// PERMANENT ethical guardrail banner — NEVER remove or hide this
import React from "react";
import { AlertTriangle } from "lucide-react";

export function AiDisclaimerBanner() {
  return (
    <div
      className="flex items-center gap-2 px-4 py-2.5 bg-amber-50 border-b border-amber-200 flex-shrink-0"
      role="alert"
      aria-label="AI ethical guardrail disclaimer"
    >
      <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" aria-hidden="true" />
      <p className="text-xs text-amber-700 leading-relaxed">
        <strong className="font-semibold">AI Assistance Only —</strong>{" "}
        AI-generated summaries are for assistive purposes only. Do not use for definitive legal conclusions.
        Every claim must be verified by a qualified investigator.
      </p>
    </div>
  );
}
