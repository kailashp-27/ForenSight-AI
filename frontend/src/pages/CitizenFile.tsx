// frontend/src/pages/CitizenFile.tsx
// One person's file from the citizen register: every detail, the photo (a
// placeholder until a real one is uploaded), and every case they are linked to.

import React, { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, BadgeCheck, Camera, Loader2 } from "lucide-react";
import { citizensApi, type CitizenFileData } from "../services/forensicApi";
import { StatusPill } from "./Citizens";

const ROLE_LABEL: Record<string, string> = {
  VICTIM: "Victim", SUSPECT: "Suspect", PERSON_OF_INTEREST: "Person of interest", WITNESS: "Witness",
  CLEARED: "Cleared", GUILTY: "Guilty (investigator's determination)",
};

export function CitizenFile() {
  const { id } = useParams<{ id: string }>();
  const [file, setFile] = useState<CitizenFileData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [photoKey, setPhotoKey] = useState(0);
  const input = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      setFile(await citizensApi.file(id));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const upload = async (f: File | undefined) => {
    if (!f || !file) return;
    setBusy(true);
    try {
      await citizensApi.uploadPhoto(file.id, f, localStorage.getItem("forensight.operatorId") || "OPERATOR-1");
      setPhotoKey((k) => k + 1);
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (error && !file) {
    return (
      <div style={{ padding: "2rem" }}>
        <p role="alert" style={{ color: "#fca5a5" }}>{error}</p>
        <Link to="/citizens" style={{ color: "var(--color-accent)" }}>← Back to the register</Link>
      </div>
    );
  }
  if (!file) return <div style={{ padding: "2rem" }}><Loader2 className="animate-spin" /></div>;

  const rows: [string, React.ReactNode][] = [
    ["Citizen ID", <span style={{ fontFamily: "monospace" }}>{file.id}</span>],
    ["Full name", file.full_name],
    ["Date of birth", file.dob ? `${file.dob}${file.age != null ? `  (age ${file.age})` : ""}` : "—"],
    ["Phone number", <span style={{ fontFamily: "monospace" }}>{file.phone ?? "—"}</span>],
    ["Address", file.address ?? "—"],
    ["Occupation", file.occupation ?? "—"],
    ["Criminal record", <span style={{ color: file.has_record ? "#fca5a5" : undefined }}>{file.criminal_record ?? "None"}</span>],
    ["Status", <StatusPill status={file.status} />],
  ];

  return (
    <div className="animate-fade-in" style={{ padding: "1.25rem", maxWidth: 1000, margin: "0 auto" }}>
      <Link to="/citizens" style={{ display: "inline-flex", gap: 4, alignItems: "center", fontSize: "0.75rem",
                                    color: "var(--color-text-muted)", textDecoration: "none", marginBottom: 10 }}>
        <ArrowLeft size={13} /> Citizen register
      </Link>

      {file.alert && (
        <div role="alert" data-testid="citizen-alert"
             style={{ display: "flex", gap: 10, alignItems: "flex-start", padding: "0.7rem 0.9rem", marginBottom: 12, borderRadius: 8,
                      background: file.alert.priority === "HIGH" ? "rgba(239,68,68,0.1)" : "rgba(245,158,11,0.1)",
                      border: `1px solid ${file.alert.priority === "HIGH" ? "rgba(239,68,68,0.5)" : "rgba(245,158,11,0.5)"}` }}>
          <AlertTriangle size={18} style={{ color: file.alert.priority === "HIGH" ? "#ef4444" : "#f59e0b", flexShrink: 0 }} />
          <div style={{ fontSize: "0.82rem", color: "var(--color-text-primary)" }}>
            <strong>Appears in {file.alert.case_count} cases.</strong> {file.alert.message}.
            <div style={{ fontSize: "0.72rem", color: "var(--color-text-muted)", marginTop: 2 }}>
              {file.alert.cases.map((c) => c.case_number).join(" · ")}
            </div>
          </div>
        </div>
      )}

      <div style={{ display: "flex", gap: 18, flexWrap: "wrap", alignItems: "flex-start" }}>
        <div style={{ width: 220, flexShrink: 0 }}>
          <img key={photoKey} src={`${file.photo_url}?v=${photoKey}`} alt={`${file.full_name}${file.has_photo ? "" : " (no photo available)"}`}
               data-testid="citizen-photo"
               style={{ width: 220, height: 264, objectFit: "cover", borderRadius: 10, background: "#05070c",
                        border: "1px solid var(--color-border-bright)" }} />
          <input ref={input} type="file" accept="image/jpeg,image/png" hidden onChange={(e) => void upload(e.target.files?.[0])} />
          <button onClick={() => input.current?.click()} disabled={busy}
                  style={{ marginTop: 8, width: "100%", height: 34, display: "inline-flex", gap: 6, alignItems: "center", justifyContent: "center",
                           borderRadius: 6, cursor: "pointer", background: "var(--color-bg-elevated)", color: "var(--color-text-body)",
                           border: "1px solid var(--color-border-bright)", fontSize: "0.75rem", fontWeight: 600 }}>
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Camera size={14} />}
            {file.has_photo ? "Replace photo" : "Upload a photo"}
          </button>
          <p style={{ fontSize: "0.64rem", color: "var(--color-text-subtle)", marginTop: 4, lineHeight: 1.4 }}>
            {file.has_photo ? "Photo on file." : "A placeholder is shown until a photo is uploaded. Photos will be used for matching suspects."}
          </p>
          {error && <p role="alert" style={{ color: "#fca5a5", fontSize: "0.72rem" }}>{error}</p>}
        </div>

        <div style={{ flex: 1, minWidth: 320 }}>
          <h1 style={{ fontSize: "1.4rem", fontWeight: 700, color: "var(--color-text-primary)", marginBottom: 8 }}>{file.full_name}</h1>
          <table className="card" style={{ width: "100%", borderCollapse: "collapse" }} data-testid="citizen-details">
            <tbody>
              {rows.map(([k, v]) => (
                <tr key={k} style={{ borderBottom: "1px solid var(--color-border-subtle)" }}>
                  <th style={{ textAlign: "left", width: 150, padding: "0.5rem 0.8rem", fontSize: "0.72rem", fontWeight: 600,
                               color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>{k}</th>
                  <td style={{ padding: "0.5rem 0.8rem", fontSize: "0.88rem", color: "var(--color-text-primary)" }}>{v}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h2 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--color-text-primary)", margin: "18px 0 8px" }}>
            Linked cases ({file.links.length})
          </h2>
          {file.links.length === 0 && (
            <p style={{ fontSize: "0.8rem", color: "var(--color-text-subtle)" }}>
              Not linked to any case. Links appear when a person in a case's People list matches this citizen.
            </p>
          )}
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {file.links.map((l) => (
              <div key={l.case_id + l.person_key} className="card" data-testid="citizen-link" style={{ padding: "0.6rem 0.8rem" }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <Link to={`/cases/${l.case_id}/investigation`} style={{ fontWeight: 700, color: "var(--color-accent)", textDecoration: "none" }}>
                    {l.case_number}
                  </Link>
                  <span style={{ fontSize: "0.8rem", color: "var(--color-text-body)" }}>{l.case_title}</span>
                  {l.status === "CONFIRMED" ? (
                    <span style={{ display: "inline-flex", gap: 3, alignItems: "center", fontSize: "0.66rem", fontWeight: 700, color: "#10b981" }}>
                      <BadgeCheck size={13} /> confirmed
                    </span>
                  ) : (
                    <span style={{ fontSize: "0.66rem", fontWeight: 700, color: "#f59e0b" }}>
                      suggested ({l.level?.toLowerCase()}) — unconfirmed
                    </span>
                  )}
                </div>
                <div style={{ fontSize: "0.76rem", color: "var(--color-text-body)", marginTop: 3 }}>
                  As <strong>{l.person_name}</strong>
                  {l.role ? <> — <strong>{ROLE_LABEL[l.role] ?? l.role}</strong></> : " — no role assigned yet"}
                </div>
                {l.reasons.length > 0 && (
                  <div style={{ fontSize: "0.7rem", color: "var(--color-text-subtle)", marginTop: 2 }}>Why: {l.reasons.join("; ")}</div>
                )}
              </div>
            ))}
          </div>
          <p style={{ fontSize: "0.68rem", color: "var(--color-text-subtle)", marginTop: 12 }}>{file.notice}</p>
        </div>
      </div>
    </div>
  );
}
