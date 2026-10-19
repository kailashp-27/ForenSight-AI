// frontend/src/components/investigation/PeopleRoster.tsx
// Everyone involved in the case — found from names, chat authors, badges and ID
// cards in the evidence — and the controls for the INVESTIGATOR to decide who is
// the victim, a suspect, a person of interest, a witness, cleared, or (as their
// own recorded determination) guilty.

import React, { useMemo, useState } from "react";
import {
  AlertTriangle, BadgeCheck, ChevronDown, ChevronRight, CreditCard, ImageOff, Link2, Loader2, Plus, Search,
  ShieldAlert, UserPlus, X,
} from "lucide-react";
import { Link } from "react-router-dom";
import { citizensApi, peopleApi, type PeopleResponse, type PersonRole, type RosterPerson } from "../../services/forensicApi";

const ROLE_META: Record<string, { label: string; color: string }> = {
  VICTIM: { label: "Victim", color: "#3b82f6" },
  SUSPECT: { label: "Suspect", color: "#f59e0b" },
  PERSON_OF_INTEREST: { label: "Person of interest", color: "#a855f7" },
  WITNESS: { label: "Witness", color: "#10b981" },
  CLEARED: { label: "Cleared", color: "#64748b" },
  GUILTY: { label: "Guilty (investigator's determination)", color: "#ef4444" },
};
const ASSIGNABLE: PersonRole[] = ["VICTIM", "SUSPECT", "PERSON_OF_INTEREST", "WITNESS", "CLEARED"];

interface Props {
  people: RosterPerson[] | null;
  repeat?: PeopleResponse["repeat_people"];
  caseId: string;
  operatorId: string;
  onChanged: () => void;
  onOpen: (evidenceId: string, ms: number | null) => void;
}

function msFromAt(at: string | null): number | null {
  const m = at?.match(/(\d+):(\d+):(\d+)(?:[.:](\d+))?/);
  return m ? ((+m[1] * 60 + +m[2]) * 60 + +m[3]) * 1000 + (m[4] ? +m[4].padEnd(3, "0").slice(0, 3) : 0) : null;
}

export function PeopleRoster({ people, repeat = [], caseId, operatorId, onChanged, onOpen }: Props) {
  const [filter, setFilter] = useState<string>("ALL");
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [guilty, setGuilty] = useState<{ key: string; basis: string; ack: boolean } | null>(null);
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState("");
  const [newIds, setNewIds] = useState("");
  const [attach, setAttach] = useState<Record<string, string>>({});

  const list = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (people ?? []).filter((p) => {
      if (filter === "UNASSIGNED" && p.role) return false;
      if (filter === "BADGE" && p.identifiers.length === 0) return false;
      if (!["ALL", "UNASSIGNED", "BADGE"].includes(filter) && p.role !== filter) return false;
      if (!q) return true;
      return p.name.toLowerCase().includes(q) || p.aliases.some((a) => a.toLowerCase().includes(q)) ||
        p.identifiers.some((i) => i.value.toLowerCase().includes(q));
    });
  }, [people, filter, query]);

  const run = async (key: string, fn: () => Promise<unknown>) => {
    setBusy(key);
    setError(null);
    try {
      await fn();
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const setRole = (p: RosterPerson, role: PersonRole, basis?: string) =>
    run(p.key, () =>
      peopleApi.designate(caseId, p.key, {
        role, operator_id: operatorId, display_name: p.name,
        aliases: [...p.alias_norms, ...p.identifiers.map((i) => i.value)],
        basis: basis ?? p.designation?.basis ?? undefined,
      })
    );

  const merge = (source: RosterPerson, targetKey: string) => {
    const target = (people ?? []).find((x) => x.key === targetKey);
    if (!target) return;
    void run(source.key, async () => {
      await peopleApi.addAliases(caseId, target.key, {
        aliases: [...source.alias_norms, source.name, ...source.identifiers.map((i) => i.value)],
        display_name: target.name, operator_id: operatorId,
      });
      if (source.has_designation_row) await peopleApi.clear(caseId, source.key, operatorId);
    });
  };

  const counts = useMemo(() => {
    const c: Record<string, number> = { ALL: people?.length ?? 0, UNASSIGNED: 0, BADGE: 0 };
    for (const p of people ?? []) {
      if (!p.role) c.UNASSIGNED++;
      if (p.identifiers.length) c.BADGE++;
      if (p.role) c[p.role] = (c[p.role] ?? 0) + 1;
    }
    return c;
  }, [people]);

  const chip = (active: boolean, color = "var(--color-accent)"): React.CSSProperties => ({
    padding: "3px 10px", borderRadius: 999, fontSize: "0.7rem", fontWeight: 600, cursor: "pointer",
    border: `1px solid ${active ? color : "var(--color-border)"}`,
    background: active ? "var(--color-accent-light)" : "transparent",
    color: active ? "var(--color-text-primary)" : "var(--color-text-muted)",
  });

  if (!people) return <p style={{ color: "var(--color-text-muted)", fontSize: "0.85rem" }}>Loading people…</p>;

  return (
    <div data-testid="people-roster">
      <div className="card" style={{ padding: "0.7rem 0.9rem", marginBottom: 10, display: "flex", gap: 10, alignItems: "flex-start" }}>
        <ShieldAlert size={18} style={{ color: "#f59e0b", flexShrink: 0, marginTop: 2 }} />
        <p style={{ fontSize: "0.76rem", color: "var(--color-text-body)", lineHeight: 1.5 }}>
          These are <strong>everyone named, badged or carded in the evidence</strong>. Choose a role for each person. Your
          choices are recorded with your ID and the time. ForenSight only <em>suggests</em> victim / suspect / witness from a
          nearby word; it never suggests or decides guilt. “Guilty” is your own determination and needs a written basis.
        </p>
      </div>

      {repeat.length > 0 && (
        <div role="alert" data-testid="repeat-banner"
             style={{ padding: "0.6rem 0.85rem", marginBottom: 10, borderRadius: 8, background: "rgba(245,158,11,0.1)",
                      border: "1px solid rgba(245,158,11,0.5)", fontSize: "0.78rem", color: "var(--color-text-primary)" }}>
          <strong style={{ display: "inline-flex", gap: 6, alignItems: "center", color: "#fbbf24" }}>
            <AlertTriangle size={15} /> Repeat person{repeat.length > 1 ? "s" : ""} across cases
          </strong>
          {repeat.map((r) => (
            <div key={r.person_key + r.citizen_id} style={{ marginTop: 3 }}>
              <strong>{r.person_name}</strong> matches{" "}
              <Link to={`/citizens/${r.citizen_id}`} style={{ color: "var(--color-accent)" }}>{r.citizen_name}</Link>{" "}
              ({r.status === "CONFIRMED" ? "confirmed" : "suggested"}), who is also in{" "}
              {r.other_cases.map((o) => `${o.case_number}${o.role ? ` as ${o.role.toLowerCase().replace(/_/g, " ")}` : ""}`).join(", ")}.
            </div>
          ))}
        </div>
      )}

      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center", marginBottom: 10 }}>
        <div style={{ position: "relative" }}>
          <Search size={13} style={{ position: "absolute", left: 9, top: 9, color: "var(--color-text-subtle)" }} />
          <input aria-label="Search people" placeholder="Search name, badge or ID…" value={query}
                 onChange={(e) => setQuery(e.target.value)}
                 style={{ height: 31, width: 220, paddingLeft: 28, background: "var(--color-bg-input)",
                          color: "var(--color-text-primary)", border: "1px solid var(--color-border-bright)",
                          borderRadius: 6, fontSize: "0.78rem" }} />
        </div>
        {[["ALL", "All"], ["UNASSIGNED", "Unassigned"], ["BADGE", "With badge / ID"], ["VICTIM", "Victim"],
          ["SUSPECT", "Suspect"], ["PERSON_OF_INTEREST", "Person of interest"], ["WITNESS", "Witness"],
          ["CLEARED", "Cleared"], ["GUILTY", "Guilty"]].map(([k, label]) => (
          <button key={k} style={chip(filter === k)} onClick={() => setFilter(k)}>
            {label} <span style={{ opacity: 0.6 }}>{counts[k] ?? 0}</span>
          </button>
        ))}
        <button onClick={() => setAdding(!adding)}
                style={{ marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 5, height: 31, padding: "0 10px",
                         borderRadius: 6, border: "1px solid var(--color-accent)", background: "var(--color-accent)",
                         color: "#fff", fontSize: "0.75rem", fontWeight: 700, cursor: "pointer" }}>
          <UserPlus size={14} /> Add person
        </button>
      </div>

      {adding && (
        <div className="card" style={{ padding: "0.7rem 0.9rem", marginBottom: 10, display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input aria-label="New person name" placeholder="Full name" value={newName} onChange={(e) => setNewName(e.target.value)}
                 style={{ height: 32, flex: "1 1 200px", padding: "0 8px", background: "var(--color-bg-input)",
                          color: "var(--color-text-primary)", border: "1px solid var(--color-border-bright)", borderRadius: 6 }} />
          <input aria-label="Badge or ID values" placeholder="Badge / ID values, comma separated (optional)" value={newIds}
                 onChange={(e) => setNewIds(e.target.value)}
                 style={{ height: 32, flex: "2 1 260px", padding: "0 8px", background: "var(--color-bg-input)",
                          color: "var(--color-text-primary)", border: "1px solid var(--color-border-bright)", borderRadius: 6 }} />
          <button disabled={newName.trim().length < 2 || busy === "new"}
                  onClick={() => run("new", async () => {
                    await peopleApi.add(caseId, { name: newName.trim(), identifiers: newIds.split(",").map((s) => s.trim()).filter(Boolean),
                                                  operator_id: operatorId });
                    setNewName(""); setNewIds(""); setAdding(false);
                  })}
                  style={{ height: 32, padding: "0 12px", borderRadius: 6, border: "none", background: "#059669", color: "#fff",
                           fontWeight: 700, fontSize: "0.75rem", cursor: "pointer" }}>
            {busy === "new" ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />} Add
          </button>
        </div>
      )}

      {error && <p role="alert" style={{ color: "#fca5a5", fontSize: "0.78rem", marginBottom: 8 }}>{error}</p>}
      {list.length === 0 && <p style={{ fontSize: "0.8rem", color: "var(--color-text-muted)" }}>No people match.</p>}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(430px, 1fr))", gap: 10 }}>
        {list.map((p) => {
          const meta = p.role ? ROLE_META[p.role] : null;
          const expanded = open[p.key];
          const isBusy = busy === p.key;
          return (
            <article key={p.key} className="card" data-testid="roster-card"
                     style={{ padding: "0.75rem 0.9rem", borderLeft: `4px solid ${meta?.color ?? "var(--color-border-bright)"}` }}>
              <div style={{ display: "flex", gap: 10 }}>
                <div style={{ width: 72, height: 72, flexShrink: 0 }}>
                  {p.photos[0] ? (
                    <img src={p.photos[0].url} alt={`${p.name}: ${p.photos[0].caption}`} loading="lazy"
                         style={{ width: 72, height: 72, objectFit: "cover", borderRadius: 8, background: "#05070c",
                                  border: "1px solid var(--color-border-bright)" }} />
                  ) : (
                    <div style={{ width: 72, height: 72, borderRadius: 8, border: "1px dashed var(--color-border-bright)",
                                  display: "flex", alignItems: "center", justifyContent: "center", color: "var(--color-text-subtle)" }}>
                      <ImageOff size={16} />
                    </div>
                  )}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                    <strong style={{ fontSize: "0.95rem", color: "var(--color-text-primary)" }}>{p.name}</strong>
                    {p.verified && <BadgeCheck size={14} style={{ color: "#10b981" }} aria-label="investigator verified" />}
                    {meta && (
                      <span style={{ fontSize: "0.66rem", fontWeight: 700, color: meta.color, border: `1px solid ${meta.color}`,
                                     borderRadius: 4, padding: "0 6px" }}>{meta.label}</span>
                    )}
                    {p.manual && <span style={{ fontSize: "0.62rem", color: "var(--color-text-subtle)" }}>added by hand</span>}
                  </div>
                  {p.aliases.length > 0 && (
                    <div style={{ fontSize: "0.68rem", color: "var(--color-text-muted)" }}>also: {p.aliases.join(", ")}</div>
                  )}
                  <div style={{ fontSize: "0.66rem", color: "var(--color-text-subtle)", marginTop: 2 }}>
                    found via {p.found_via.join(", ") || "investigator"} · {p.evidence_count} evidence file(s)
                  </div>
                  {p.identifiers.length > 0 && (
                    <div style={{ display: "flex", gap: 5, flexWrap: "wrap", marginTop: 5 }}>
                      {p.identifiers.map((i) => (
                        <span key={i.norm} title={`${i.how} — ${i.file_name}${i.at ? " @" + i.at : ""}`}
                              style={{ display: "inline-flex", gap: 4, alignItems: "center", fontSize: "0.68rem", fontFamily: "monospace",
                                       color: "#22d3ee", border: "1px solid rgba(34,211,238,0.4)", borderRadius: 4, padding: "0 6px" }}>
                          <CreditCard size={10} /> {i.value}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* suggestion (never guilt) */}
              {!p.role && p.suggested_role && (
                <div style={{ marginTop: 8, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", fontSize: "0.7rem",
                              color: "#fbbf24", background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.3)",
                              borderRadius: 6, padding: "4px 8px" }}>
                  <AlertTriangle size={12} />
                  Suggested: <strong>{ROLE_META[p.suggested_role]?.label}</strong> — {p.suggested_reason}
                  <button disabled={isBusy} onClick={() => setRole(p, p.suggested_role as PersonRole)}
                          style={{ marginLeft: "auto", fontSize: "0.68rem", fontWeight: 700, background: "none",
                                   border: "1px solid #fbbf24", color: "#fbbf24", borderRadius: 4, padding: "1px 8px", cursor: "pointer" }}>
                    Accept
                  </button>
                </div>
              )}

              {/* role buttons */}
              <div role="group" aria-label={`Role for ${p.name}`}
                   style={{ display: "flex", gap: 5, flexWrap: "wrap", marginTop: 8, alignItems: "center" }}>
                {ASSIGNABLE.map((r) => {
                  const active = p.role === r;
                  return (
                    <button key={r} disabled={isBusy} onClick={() => (active ? undefined : setRole(p, r))}
                            aria-pressed={active}
                            style={{ fontSize: "0.7rem", fontWeight: 700, padding: "3px 9px", borderRadius: 6, cursor: "pointer",
                                     border: `1px solid ${ROLE_META[r].color}`,
                                     background: active ? ROLE_META[r].color : "transparent",
                                     color: active ? "#fff" : ROLE_META[r].color }}>
                      {ROLE_META[r].label}
                    </button>
                  );
                })}
                <button disabled={isBusy} onClick={() => setGuilty({ key: p.key, basis: p.designation?.basis ?? "", ack: false })}
                        aria-pressed={p.role === "GUILTY"}
                        style={{ fontSize: "0.7rem", fontWeight: 700, padding: "3px 9px", borderRadius: 6, cursor: "pointer",
                                 border: "1px solid #ef4444", background: p.role === "GUILTY" ? "#ef4444" : "transparent",
                                 color: p.role === "GUILTY" ? "#fff" : "#ef4444" }}>
                  Guilty…
                </button>
                {p.role && (
                  <button disabled={isBusy} title="Remove the role you assigned"
                          onClick={() => run(p.key, () => (p.has_designation_row
                            ? peopleApi.clear(caseId, p.key, operatorId) : Promise.resolve()))}
                          style={{ fontSize: "0.68rem", background: "none", border: "none", color: "var(--color-text-muted)",
                                   cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 2 }}>
                    <X size={11} /> clear
                  </button>
                )}
                {isBusy && <Loader2 size={14} className="animate-spin" />}
              </div>

              {p.designation && (
                <p style={{ fontSize: "0.66rem", color: "var(--color-text-subtle)", marginTop: 6, lineHeight: 1.4 }}>
                  Designated by <strong style={{ color: "var(--color-text-body)" }}>{p.designation.by}</strong>
                  {p.designation.at ? ` on ${p.designation.at.replace("T", " ").replace("Z", " UTC")}` : ""}
                  {p.designation.basis ? <> — basis: {p.designation.basis}</> : null}
                </p>
              )}

              {guilty?.key === p.key && (
                <div role="dialog" aria-label="Confirm guilty determination" data-testid="guilty-confirm"
                     style={{ marginTop: 8, padding: "0.6rem 0.7rem", borderRadius: 8, border: "1px solid #ef4444",
                              background: "rgba(239,68,68,0.08)" }}>
                  <p style={{ fontSize: "0.74rem", color: "var(--color-text-body)", lineHeight: 1.5 }}>
                    <strong style={{ color: "#fca5a5" }}>This records YOUR determination, attributed to {operatorId}.</strong>{" "}
                    ForenSight does not decide guilt, and this is not a legal verdict. It will appear in the report as the
                    investigator's determination, with the basis you write here.
                  </p>
                  <textarea aria-label="Basis for determination" rows={3} value={guilty.basis}
                            placeholder="Basis (required, at least 20 characters): which evidence supports this?"
                            onChange={(e) => setGuilty({ ...guilty, basis: e.target.value })}
                            style={{ width: "100%", marginTop: 6, padding: 6, fontSize: "0.76rem", background: "var(--color-bg-input)",
                                     color: "var(--color-text-primary)", border: "1px solid var(--color-border-bright)", borderRadius: 6 }} />
                  <label style={{ display: "flex", gap: 6, alignItems: "center", fontSize: "0.72rem", color: "var(--color-text-body)", marginTop: 4 }}>
                    <input type="checkbox" checked={guilty.ack} onChange={(e) => setGuilty({ ...guilty, ack: e.target.checked })} />
                    I understand this is my own determination and not a finding of the system.
                  </label>
                  <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
                    <button disabled={!guilty.ack || guilty.basis.trim().length < 20 || isBusy}
                            onClick={() => run(p.key, async () => {
                              await peopleApi.designate(caseId, p.key, {
                                role: "GUILTY", operator_id: operatorId, display_name: p.name, basis: guilty.basis.trim(),
                                aliases: [...p.alias_norms, ...p.identifiers.map((i) => i.value)], confirm_determination: true,
                              });
                              setGuilty(null);
                            })}
                            style={{ height: 30, padding: "0 12px", borderRadius: 6, border: "none", background: "#dc2626",
                                     color: "#fff", fontWeight: 700, fontSize: "0.74rem", cursor: "pointer",
                                     opacity: !guilty.ack || guilty.basis.trim().length < 20 ? 0.5 : 1 }}>
                      Record my determination
                    </button>
                    <button onClick={() => setGuilty(null)}
                            style={{ height: 30, padding: "0 10px", borderRadius: 6, border: "1px solid var(--color-border-bright)",
                                     background: "transparent", color: "var(--color-text-body)", fontSize: "0.74rem", cursor: "pointer" }}>
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {/* citizen register suggestions (never automatic identification) */}
              {(p.citizen_matches ?? []).length > 0 && (
                <div data-testid="citizen-matches" style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
                  <div style={{ fontSize: "0.66rem", fontWeight: 700, color: "var(--color-text-muted)", letterSpacing: "0.04em" }}>
                    CITIZEN REGISTER {(p.citizen_matches ?? []).some((m) => m.status === "CONFIRMED") ? "" : "— SUGGESTED, NOT CONFIRMED"}
                  </div>
                  {(p.citizen_matches ?? []).map((m) => (
                    <div key={m.citizen_id} style={{ display: "flex", gap: 8, padding: "6px 8px", borderRadius: 8,
                                                     border: `1px solid ${m.status === "CONFIRMED" ? "rgba(16,185,129,0.5)" : "var(--color-border)"}`,
                                                     background: "var(--color-bg-elevated)" }}>
                      <img src={m.photo_url} alt={`${m.full_name} (no photo available)`} loading="lazy"
                           style={{ width: 38, height: 46, objectFit: "cover", borderRadius: 5, background: "#05070c", flexShrink: 0 }} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                          <Link to={`/citizens/${m.citizen_id}`} style={{ fontWeight: 700, fontSize: "0.8rem", color: "var(--color-accent)", textDecoration: "none" }}>
                            {m.full_name}
                          </Link>
                          <span style={{ fontSize: "0.62rem", color: "var(--color-text-subtle)" }}>
                            ID {m.citizen_id}{m.citizen_status ? ` · ${m.citizen_status}` : ""}
                          </span>
                          <span style={{ fontSize: "0.62rem", fontWeight: 700, color: m.status === "CONFIRMED" ? "#10b981" : m.level === "LIKELY" || m.level === "STRONG" ? "#fbbf24" : "#94a3b8" }}>
                            {m.status === "CONFIRMED" ? "CONFIRMED" : `${m.level} · ${Math.round(m.score * 100)}%`}
                          </span>
                        </div>
                        <div style={{ fontSize: "0.66rem", color: "var(--color-text-muted)" }}>{m.reasons.join("; ")}</div>
                        {m.criminal_record && m.criminal_record !== "None" && (
                          <div style={{ fontSize: "0.64rem", color: "#fca5a5" }}>Record: {m.criminal_record}</div>
                        )}
                        {m.other_cases.length > 0 && (
                          <div data-testid="other-cases" style={{ marginTop: 3, fontSize: "0.68rem", fontWeight: 600, color: "#fbbf24", display: "flex", gap: 4, alignItems: "center", flexWrap: "wrap" }}>
                            <AlertTriangle size={11} /> also in {m.other_cases.map((o) => o.case_number).join(", ")}
                          </div>
                        )}
                        <div style={{ display: "flex", gap: 5, marginTop: 4 }}>
                          {m.status === "CONFIRMED" ? (
                            <button disabled={isBusy} onClick={() => run(p.key, () => citizensApi.decide(caseId, p.key, m.citizen_id, "reset", operatorId))}
                                    style={{ fontSize: "0.66rem", background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer" }}>
                              undo
                            </button>
                          ) : (
                            <>
                              <button disabled={isBusy} onClick={() => run(p.key, () => citizensApi.decide(caseId, p.key, m.citizen_id, "confirm", operatorId))}
                                      style={{ fontSize: "0.66rem", fontWeight: 700, padding: "2px 8px", borderRadius: 4, cursor: "pointer",
                                               border: "1px solid #10b981", background: "transparent", color: "#10b981" }}>
                                This is them
                              </button>
                              <button disabled={isBusy} onClick={() => run(p.key, () => citizensApi.decide(caseId, p.key, m.citizen_id, "reject", operatorId))}
                                      style={{ fontSize: "0.66rem", fontWeight: 700, padding: "2px 8px", borderRadius: 4, cursor: "pointer",
                                               border: "1px solid var(--color-border-bright)", background: "transparent", color: "var(--color-text-muted)" }}>
                                Not them
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* merge / attach / evidence */}
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginTop: 8 }}>
                <select aria-label={`Same person as (${p.name})`} value="" disabled={isBusy}
                        onChange={(e) => e.target.value && merge(p, e.target.value)}
                        style={{ height: 28, fontSize: "0.7rem", background: "var(--color-bg-input)", color: "var(--color-text-body)",
                                 border: "1px solid var(--color-border-bright)", borderRadius: 6, maxWidth: 190 }}>
                  <option value="">Same person as…</option>
                  {(people ?? []).filter((o) => o.key !== p.key).map((o) => <option key={o.key} value={o.key}>{o.name}</option>)}
                </select>
                <input aria-label={`Attach badge or ID to ${p.name}`} placeholder="Attach badge / ID…" value={attach[p.key] ?? ""}
                       onChange={(e) => setAttach({ ...attach, [p.key]: e.target.value })}
                       style={{ height: 28, width: 150, fontSize: "0.7rem", padding: "0 6px", background: "var(--color-bg-input)",
                                color: "var(--color-text-primary)", border: "1px solid var(--color-border-bright)", borderRadius: 6 }} />
                <button disabled={!(attach[p.key] ?? "").trim() || isBusy}
                        onClick={() => run(p.key, async () => {
                          await peopleApi.addAliases(caseId, p.key, { aliases: [attach[p.key].trim()], display_name: p.name,
                                                                      operator_id: operatorId });
                          setAttach({ ...attach, [p.key]: "" });
                        })}
                        style={{ height: 28, padding: "0 8px", fontSize: "0.7rem", borderRadius: 6, cursor: "pointer",
                                 border: "1px solid var(--color-border-bright)", background: "var(--color-bg-elevated)",
                                 color: "var(--color-text-body)" }}>
                  <Link2 size={11} /> Attach
                </button>
                <button onClick={() => setOpen({ ...open, [p.key]: !expanded })}
                        style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer",
                                 color: "var(--color-accent)", fontSize: "0.7rem", display: "inline-flex", alignItems: "center", gap: 3 }}>
                  {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />} {p.support.length} mention(s)
                </button>
              </div>
              {expanded && (
                <div style={{ display: "flex", flexDirection: "column", gap: 3, marginTop: 6 }}>
                  {p.support.map((s, i) => (
                    <button key={i} onClick={() => onOpen(s.evidence_id, msFromAt(s.at))}
                            style={{ textAlign: "left", cursor: "pointer", background: "var(--color-bg-card)",
                                     border: "1px solid var(--color-border)", borderRadius: 6, padding: "4px 8px",
                                     fontSize: "0.7rem", color: "var(--color-text-body)" }}>
                      <strong style={{ color: "var(--color-text-primary)" }}>{s.file_name}</strong>
                      {s.at && <span style={{ fontFamily: "monospace", color: "#22d3ee" }}> @{s.at}</span>}
                      <span style={{ color: "var(--color-text-subtle)" }}> · {s.source}</span>
                      <div style={{ color: "var(--color-text-muted)" }}>{s.text}</div>
                    </button>
                  ))}
                </div>
              )}
            </article>
          );
        })}
      </div>
    </div>
  );
}
