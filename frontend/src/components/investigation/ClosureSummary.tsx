// frontend/src/components/investigation/ClosureSummary.tsx
// Summary of a closed case: who did it, what the evidence shows, how, and the
// investigator's guilty determination. Assembled from the evidence and the
// investigator's own designations; the system never decides guilt.

import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, BadgeCheck, Car, Fingerprint, Gavel, Loader2, Package, User } from "lucide-react";
import { closureApi, type ClosureSummaryData } from "../../services/forensicApi";

const h2: React.CSSProperties = {
  fontSize: "0.72rem", fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase",
  color: "var(--color-text-muted)", margin: "14px 0 6px",
};
const small: React.CSSProperties = { fontSize: "0.76rem", color: "var(--color-text-body)" };

function names(list: { name: string }[]): string {
  return list.length ? list.map((p) => p.name).join(", ") : "none recorded";
}

export function ClosureSummary({ caseId }: { caseId: string }) {
  const [data, setData] = useState<ClosureSummaryData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    closureApi.get(caseId).then((d) => live && setData(d)).catch((e: Error) => live && setError(e.message));
    return () => { live = false; };
  }, [caseId]);

  if (error) return <p role="alert" style={{ color: "#fca5a5", fontSize: "0.8rem" }}>{error}</p>;
  if (!data) return <div style={{ padding: "1rem" }}><Loader2 className="animate-spin" size={16} /></div>;

  const { guilty, others, how } = data;

  return (
    <section className="card" data-testid="closure-summary" style={{ padding: "1rem 1.25rem", marginBottom: 16 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <Gavel size={16} style={{ color: "var(--color-accent)" }} />
        <h2 style={{ fontSize: "1rem", fontWeight: 700, color: "var(--color-text-primary)" }}>Case closure summary</h2>
      </div>
      <p style={{ fontSize: "0.68rem", color: "var(--color-text-subtle)", marginTop: 2 }}>{data.notice}</p>

      {data.notes.map((n) => (
        <div key={n} role="alert" style={{ marginTop: 8, padding: "0.5rem 0.75rem", borderRadius: 6, fontSize: "0.76rem",
                                           background: "rgba(245,158,11,0.1)", border: "1px solid rgba(245,158,11,0.45)",
                                           display: "flex", gap: 6, alignItems: "center" }}>
          <AlertTriangle size={14} /> {n}
        </div>
      ))}

      {/* who did it */}
      {guilty.map((g) => (
        <div key={g.key} data-testid="closure-guilty" style={{ marginTop: 12, padding: "0.75rem", borderRadius: 8,
                                                              border: "1px solid rgba(239,68,68,0.45)", background: "rgba(239,68,68,0.05)" }}>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <img src={g.citizen?.photo_url ?? g.photos[0]?.url ?? ""} alt={g.name} loading="lazy"
                 onError={(e) => { (e.currentTarget as HTMLImageElement).style.visibility = "hidden"; }}
                 style={{ width: 84, height: 100, objectFit: "cover", borderRadius: 8, background: "#05070c" }} />
            <div style={{ flex: 1, minWidth: 240 }}>
              <div style={{ fontSize: "0.64rem", fontWeight: 700, color: "#ef4444", letterSpacing: "0.06em" }}>
                GUILTY — INVESTIGATOR'S DETERMINATION
              </div>
              <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--color-text-primary)" }}>{g.name}</div>
              {g.aliases.length > 0 && <div style={small}>Also seen as: {g.aliases.join(", ")}</div>}
              <div style={{ ...small, marginTop: 4 }}>
                Determined by <strong>{g.designated_by ?? "unknown"}</strong>{g.designated_at ? ` on ${g.designated_at}` : ""}
              </div>
              <div style={{ ...small, marginTop: 4 }}><strong>Basis:</strong> {g.basis || "No written basis recorded."}</div>
            </div>
          </div>

          {g.citizen && (
            <div style={{ marginTop: 10 }}>
              <div style={h2}>Citizen register file ({g.citizen.link_status === "CONFIRMED" ? "confirmed link" : "suggested, unconfirmed"})</div>
              <div style={small}>
                <Link to={`/citizens/${g.citizen.citizen_id}`} style={{ color: "var(--color-accent)", fontWeight: 700 }}>{g.citizen.full_name}</Link>
                {" · "}born {g.citizen.dob ?? "—"} · {g.citizen.phone ?? "no phone"} · {g.citizen.address ?? "no address"}
                {" · "}{g.citizen.occupation ?? "—"} · record: {g.citizen.criminal_record ?? "None"}
              </div>
            </div>
          )}

          <div style={h2}>What the evidence shows</div>
          {g.what_the_evidence_shows.length === 0 && g.support.length === 0 && (
            <p style={small}>No observations in other evidence mention this person.</p>
          )}
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {g.what_the_evidence_shows.map((e, i) => (
              <li key={i} style={small}>
                <strong>{e.file_name}</strong>{e.time ? ` · ${e.time}${e.assumed_date ? " (date assumed)" : ""}` : ""} — {e.text}
              </li>
            ))}
            {g.support.map((s) => (
              <li key={s.clue_id} style={small}>
                <strong>{s.file_name}</strong>{s.at ? ` @ ${s.at}` : ""} — {s.text}{s.verified ? " (verified)" : ""}
              </li>
            ))}
          </ul>

          {g.identifiers.length > 0 && (
            <>
              <div style={h2}>ID / badge found</div>
              {g.identifiers.map((i) => (
                <div key={i.norm} style={small}>
                  <Fingerprint size={12} style={{ display: "inline", marginRight: 4 }} />
                  {i.value} ({i.how}; {i.file_name}{i.at ? ` @ ${i.at}` : ""})
                </div>
              ))}
            </>
          )}
        </div>
      ))}

      {/* how: means and trail */}
      <div style={h2}>How: items, vehicles and identifiers in this case</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 10 }}>
        <div>
          <div style={{ ...small, fontWeight: 700 }}><Package size={12} style={{ display: "inline" }} /> Items / tools</div>
          {how.items.length ? how.items.map((i) => (
            <div key={i.name} style={small}>{i.name}{i.item_class ? ` (${i.item_class.toLowerCase()})` : ""}{i.verified ? " ✔" : ""}</div>
          )) : <div style={small}>none found</div>}
        </div>
        <div>
          <div style={{ ...small, fontWeight: 700 }}><Car size={12} style={{ display: "inline" }} /> Vehicles and plates</div>
          {how.vehicles.length ? how.vehicles.map((v) => (
            <div key={v.description} style={small}>
              {v.description}{v.plates.length ? ` — ${v.plates.map((p: unknown) => (typeof p === "string" ? p : (p as { value?: string }).value ?? "")).join(", ")}` : ""}{v.verified ? " ✔" : ""}
            </div>
          )) : <div style={small}>none found</div>}
        </div>
        <div>
          <div style={{ ...small, fontWeight: 700 }}><BadgeCheck size={12} style={{ display: "inline" }} /> Identifiers</div>
          {how.identifiers.length ? how.identifiers.map((i) => (
            <div key={i.value} style={small}>{i.value}{i.verified ? " ✔" : ""} ({i.files} file{i.files === 1 ? "" : "s"})</div>
          )) : <div style={small}>none found</div>}
        </div>
      </div>

      {data.sequence.length > 0 && (
        <>
          <div style={h2}>Sequence of events</div>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {data.sequence.map((e, i) => (
              <li key={i} style={small}><strong>{e.time}</strong>{e.assumed_date ? " (date assumed)" : ""} · {e.file_name} — {e.text}</li>
            ))}
          </ul>
        </>
      )}

      {/* everyone else */}
      <div style={h2}><User size={12} style={{ display: "inline" }} /> Others involved</div>
      <div style={small}>Victims: {names(others.victims)}</div>
      <div style={small}>Suspects / persons of interest: {names(others.suspects)}</div>
      <div style={small}>Witnesses: {names(others.witnesses)}</div>
      <div style={small}>Cleared: {names(others.cleared)}</div>
    </section>
  );
}
