// frontend/src/components/investigation/ReviewQueue.tsx
// Human review of automatic detections: confirm, reject or relabel.
// Decisions clean the clue set immediately AND become fine-tuning labels
// (python -m backend.training.cli export ...).

import React, { useCallback, useEffect, useState } from "react";
import { Check, GraduationCap, Loader2, Pencil, X } from "lucide-react";
import { investigationApi, type ReviewItem } from "../../services/forensicApi";

const COMMON_CLASSES = [
  "person", "car", "truck", "bus", "motorcycle", "bicycle", "backpack", "handbag", "suitcase",
  "cell phone", "laptop", "bottle", "knife", "helmet", "license plate", "duffel bag", "crowbar", "hammer",
];

interface Props {
  caseId: string;
  operatorId: string;
  onChanged?: () => void;
}

export function ReviewQueue({ caseId, operatorId, onChanged }: Props) {
  const [items, setItems] = useState<ReviewItem[] | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [relabel, setRelabel] = useState<{ id: string; value: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await investigationApi.reviewQueue(caseId);
      setItems(r.items);
      setCounts(r.counts);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [caseId]);

  useEffect(() => {
    void load();
  }, [load]);

  const act = async (id: string, decision: "confirm" | "reject" | "relabel", className?: string) => {
    setBusy(id);
    setError(null);
    try {
      await investigationApi.reviewDetection(id, decision, operatorId, className);
      setItems((prev) => (prev ? prev.filter((i) => i.id !== id) : prev));
      setCounts((c) => ({
        ...c,
        Unverified_Draft: Math.max(0, (c.Unverified_Draft ?? 1) - 1),
        [decision === "reject" ? "Rejected" : "Verified"]: (c[decision === "reject" ? "Rejected" : "Verified"] ?? 0) + 1,
      }));
      setRelabel(null);
      onChanged?.();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const btn = (bg: string, fg: string): React.CSSProperties => ({
    display: "inline-flex", alignItems: "center", gap: 5, height: 30, padding: "0 10px", borderRadius: 6,
    border: `1px solid ${bg}`, background: bg, color: fg, fontSize: "0.72rem", fontWeight: 700, cursor: "pointer",
  });

  return (
    <div>
      <div className="card" style={{ padding: "0.7rem 0.9rem", marginBottom: 12, display: "flex", gap: 14, flexWrap: "wrap", alignItems: "center" }}>
        <GraduationCap size={18} style={{ color: "var(--color-accent)" }} />
        <div style={{ flex: 1, minWidth: 240, fontSize: "0.76rem", color: "var(--color-text-body)", lineHeight: 1.5 }}>
          Check what the detector found. <strong>Confirm</strong> correct detections, <strong>reject</strong> false ones,
          <strong> relabel</strong> wrong classes. Rejected items leave the clue set and report; every decision
          becomes training data for fine-tuning. Lowest-confidence items are shown first.
        </div>
        <div style={{ fontFamily: "monospace", fontSize: "0.74rem", color: "var(--color-text-muted)" }}>
          <span style={{ color: "#10b981" }}>{counts.Verified ?? 0}</span> confirmed ·{" "}
          <span style={{ color: "#ef4444" }}>{counts.Rejected ?? 0}</span> rejected ·{" "}
          <span style={{ color: "#f59e0b" }}>{counts.Unverified_Draft ?? 0}</span> pending
        </div>
      </div>

      {error && <p role="alert" style={{ color: "#fca5a5", fontSize: "0.78rem", marginBottom: 8 }}>{error}</p>}
      {items === null && <Loader2 className="animate-spin" size={18} />}
      {items && items.length === 0 && (
        <p style={{ fontSize: "0.85rem", color: "var(--color-text-muted)", padding: "2rem", textAlign: "center" }}>
          Nothing left to review. Run automatic analysis to generate detections.
        </p>
      )}

      <datalist id="review-classes">
        {COMMON_CLASSES.map((c) => <option key={c} value={c} />)}
      </datalist>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(290px, 1fr))", gap: 10 }}>
        {items?.map((it) => (
          <article key={it.id} data-testid="review-card" className="card" style={{ padding: 10, display: "flex", gap: 10 }}>
            <img
              src={investigationApi.cropUrl(it.id)}
              alt={`Crop of ${it.label}`}
              loading="lazy"
              style={{ width: 96, height: 96, objectFit: "cover", borderRadius: 6, background: "#05070c", flexShrink: 0 }}
            />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 700, fontSize: "0.85rem", color: "var(--color-text-primary)" }}>{it.label}</div>
              <div style={{ fontSize: "0.68rem", color: "var(--color-text-muted)", marginTop: 2 }}>
                {Math.round(it.confidence * 100)}% · {it.file_name} · <span style={{ fontFamily: "monospace" }}>{it.timestamp_str ?? ""}</span>
              </div>
              {it.readout_text && it.readout_text !== "NONE" && (
                <div style={{ fontFamily: "monospace", fontSize: "0.74rem", color: "#22d3ee", marginTop: 2 }}>plate: {it.readout_text}</div>
              )}
              {relabel?.id === it.id ? (
                <div style={{ display: "flex", gap: 4, marginTop: 6 }}>
                  <input
                    list="review-classes"
                    aria-label="Correct class"
                    value={relabel.value}
                    onChange={(e) => setRelabel({ id: it.id, value: e.target.value })}
                    placeholder="correct class"
                    style={{ flex: 1, minWidth: 0, height: 30, background: "var(--color-bg-input)", color: "var(--color-text-primary)",
                             border: "1px solid var(--color-border-bright)", borderRadius: 6, padding: "0 8px", fontSize: "0.75rem" }}
                  />
                  <button style={btn("var(--color-accent)", "#fff")} disabled={!relabel.value.trim() || busy === it.id}
                          onClick={() => act(it.id, "relabel", relabel.value)}>Save</button>
                </div>
              ) : (
                <div style={{ display: "flex", gap: 5, marginTop: 8, flexWrap: "wrap" }}>
                  <button style={btn("#059669", "#fff")} disabled={busy === it.id} onClick={() => act(it.id, "confirm")}>
                    {busy === it.id ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />} Confirm
                  </button>
                  <button style={btn("#dc2626", "#fff")} disabled={busy === it.id} onClick={() => act(it.id, "reject")}>
                    <X size={12} /> Reject
                  </button>
                  <button style={btn("var(--color-bg-elevated)", "var(--color-text-body)")} disabled={busy === it.id}
                          onClick={() => setRelabel({ id: it.id, value: it.class_name ?? "" })}>
                    <Pencil size={12} /> Relabel
                  </button>
                </div>
              )}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
