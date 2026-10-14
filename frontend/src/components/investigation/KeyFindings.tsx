// frontend/src/components/investigation/KeyFindings.tsx
// "What do we actually have": people (with photos), identifiers, items/tools/
// weapons, and the getaway vehicle with its plate — each with the supporting
// observations from other evidence and how strongly they are tied together.

import React, { useState } from "react";
import {
  AlertTriangle, BadgeCheck, Briefcase, Car, ChevronDown, ChevronRight, Fingerprint, ImageOff, User, Wrench,
} from "lucide-react";
import type { KeyFindingsData, KFSupport, KFPhoto, MatchStrength } from "../../services/forensicApi";

const STRENGTH_COLOR: Record<string, string> = { STRONG: "#10b981", MEDIUM: "#f59e0b", WEAK: "#94a3b8" };
const ROLE_COLOR: Record<string, string> = {
  SUSPECT: "#ef4444", VICTIM: "#3b82f6", WITNESS: "#10b981", STOLEN: "#f59e0b", WEAPON: "#ef4444",
  TOOL: "#f59e0b", ITEM: "#8b5cf6",
};
const CLASS_LABEL: Record<string, string> = {
  WEAPON: "Weapon", TOOL: "Tool", DEVICE: "Device", CARRIER: "Bag / carrier", OTHER: "Item",
};

function msFromAt(at: string | null): number | null {
  if (!at) return null;
  const m = at.match(/(\d+):(\d+):(\d+)(?:[.:](\d+))?/);
  if (!m) return null;
  return ((+m[1] * 60 + +m[2]) * 60 + +m[3]) * 1000 + (m[4] ? +m[4].padEnd(3, "0").slice(0, 3) : 0);
}

function StrengthBadge({ s, count }: { s: MatchStrength | null; count: number }) {
  if (!s && count < 2) {
    return <span style={{ fontSize: "0.62rem", color: "var(--color-text-subtle)" }}>single source</span>;
  }
  const c = STRENGTH_COLOR[s ?? "WEAK"];
  return (
    <span style={{ fontSize: "0.62rem", fontWeight: 700, color: c, border: `1px solid ${c}`, borderRadius: 999, padding: "0 7px" }}>
      {s ?? "LINKED"} · {count} files
    </span>
  );
}

function Photos({ photos }: { photos: KFPhoto[] }) {
  const [failed, setFailed] = useState<Record<string, boolean>>({});
  if (!photos.length) {
    return (
      <div style={{ width: 84, height: 84, borderRadius: 8, border: "1px dashed var(--color-border-bright)", display: "flex",
                    flexDirection: "column", alignItems: "center", justifyContent: "center", color: "var(--color-text-subtle)",
                    fontSize: "0.58rem", textAlign: "center", flexShrink: 0 }}>
        <ImageOff size={16} />
        no photo
      </div>
    );
  }
  return (
    <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
      {photos.slice(0, 3).map((p) => (
        <figure key={p.url} style={{ margin: 0 }}>
          {failed[p.url] ? (
            <div style={{ width: 84, height: 84, borderRadius: 8, background: "var(--color-bg-elevated)", display: "flex",
                          alignItems: "center", justifyContent: "center" }}><ImageOff size={16} /></div>
          ) : (
            <img src={p.url} alt={p.caption} loading="lazy" onError={() => setFailed({ ...failed, [p.url]: true })}
                 style={{ width: 84, height: 84, objectFit: "cover", borderRadius: 8, background: "#05070c",
                          border: `1px solid ${p.verified ? "#10b981" : "var(--color-border-bright)"}` }} />
          )}
          <figcaption style={{ fontSize: "0.55rem", color: "var(--color-text-subtle)", maxWidth: 84, marginTop: 2,
                               overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={p.caption}>
            {p.at ?? ""}
          </figcaption>
        </figure>
      ))}
    </div>
  );
}

function Support({ items, onOpen }: { items: KFSupport[]; onOpen: (evId: string, ms: number | null) => void }) {
  const [open, setOpen] = useState(false);
  if (!items.length) return null;
  return (
    <div style={{ marginTop: 6 }}>
      <button onClick={() => setOpen(!open)}
              style={{ background: "none", border: "none", cursor: "pointer", color: "var(--color-accent)", fontSize: "0.7rem",
                       display: "inline-flex", alignItems: "center", gap: 3, padding: 0 }}>
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />} {items.length} supporting observation(s)
      </button>
      {open && (
        <div style={{ display: "flex", flexDirection: "column", gap: 3, marginTop: 4 }}>
          {items.map((s, i) => (
            <button key={i} onClick={() => onOpen(s.evidence_id, msFromAt(s.at))}
                    style={{ textAlign: "left", cursor: "pointer", background: "var(--color-bg-card)",
                             border: "1px solid var(--color-border)", borderRadius: 6, padding: "4px 8px",
                             fontSize: "0.7rem", color: "var(--color-text-body)" }}>
              <strong style={{ color: "var(--color-text-primary)" }}>{s.file_name}</strong>
              {s.at && <span style={{ fontFamily: "monospace", color: "#22d3ee" }}> @{s.at}</span>}
              <span style={{ color: "var(--color-text-subtle)" }}> · {s.source}{s.verified ? " · verified" : ""}</span>
              <div style={{ color: "var(--color-text-muted)", marginTop: 1 }}>{s.text}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function Section({ title, icon, count, children, hint }: {
  title: string; icon: React.ReactNode; count: number; children: React.ReactNode; hint: string;
}) {
  return (
    <section style={{ marginBottom: 18 }}>
      <header style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 8 }}>
        <span style={{ color: "var(--color-accent)", alignSelf: "center" }}>{icon}</span>
        <h3 style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--color-text-primary)" }}>{title}</h3>
        <span style={{ fontSize: "0.7rem", color: "var(--color-text-muted)" }}>{count} · {hint}</span>
      </header>
      {count === 0 ? (
        <div className="card" style={{ padding: "0.8rem", fontSize: "0.78rem", color: "var(--color-text-subtle)" }}>
          Nothing identified yet. Verify a regional scan and assign it a role, or add more evidence.
        </div>
      ) : children}
    </section>
  );
}

const Badge = ({ text, color }: { text: string; color: string }) => (
  <span style={{ fontSize: "0.62rem", fontWeight: 700, color, border: `1px solid ${color}`, borderRadius: 4, padding: "0 6px" }}>
    {text}
  </span>
);

const Review = ({ show }: { show: boolean }) =>
  show ? (
    <span title="Inferred from a nearby word in the evidence — confirm it" style={{ display: "inline-flex", gap: 3, alignItems: "center",
          fontSize: "0.62rem", color: "#f59e0b", fontWeight: 700 }}>
      <AlertTriangle size={11} /> needs review
    </span>
  ) : null;

interface Props {
  data: KeyFindingsData | null;
  onOpen: (evidenceId: string, ms: number | null) => void;
}

export function KeyFindings({ data, onOpen }: Props) {
  if (!data) return <p style={{ color: "var(--color-text-muted)", fontSize: "0.85rem" }}>Loading key findings…</p>;
  const card: React.CSSProperties = { padding: "0.75rem 0.9rem", display: "flex", gap: 12 };

  return (
    <div data-testid="key-findings">
      <Section title="Victim & suspects" icon={<User size={17} />} count={data.people.length}
               hint="names, roles and photos — roles come from the investigator first">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(380px, 1fr))", gap: 10 }}>
          {data.people.map((p) => (
            <article key={p.id} className="card" style={card} data-testid="person-card">
              <Photos photos={p.photos} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                  <strong style={{ fontSize: "0.92rem", color: "var(--color-text-primary)" }}>{p.name}</strong>
                  {p.role && <Badge text={p.role} color={ROLE_COLOR[p.role] ?? "#94a3b8"} />}
                  {p.verified && <BadgeCheck size={14} style={{ color: "#10b981" }} aria-label="investigator verified" />}
                  <Review show={!!p.role && p.role_source !== "investigator"} />
                </div>
                {p.aliases.length > 0 && (
                  <div style={{ fontSize: "0.68rem", color: "var(--color-text-muted)" }}>also written: {p.aliases.join(", ")}</div>
                )}
                <div style={{ marginTop: 3 }}><StrengthBadge s={p.strength} count={p.evidence_count} /></div>
                <Support items={p.support} onOpen={onOpen} />
              </div>
            </article>
          ))}
        </div>
      </Section>

      <Section title="IDs & badges" icon={<Fingerprint size={17} />} count={data.ids.length}
               hint="badge, visitor, employee and serial identifiers">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 10 }}>
          {data.ids.map((i) => (
            <article key={i.id} className="card" style={{ padding: "0.6rem 0.8rem" }} data-testid="id-card">
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <strong style={{ fontFamily: "monospace", fontSize: "0.9rem", color: "var(--color-text-primary)" }}>{i.value}</strong>
                {i.verified && <BadgeCheck size={14} style={{ color: "#10b981" }} />}
              </div>
              <div style={{ marginTop: 3 }}><StrengthBadge s={i.strength} count={i.evidence_count} /></div>
              <Support items={i.support} onOpen={onOpen} />
            </article>
          ))}
        </div>
      </Section>

      <Section title="Tools, weapons & stolen items" icon={<Wrench size={17} />} count={data.items.length}
               hint="what was carried, used or taken">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(380px, 1fr))", gap: 10 }}>
          {data.items.map((it) => (
            <article key={it.id} className="card" style={card} data-testid="item-card">
              <Photos photos={it.photos} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                  <strong style={{ fontSize: "0.92rem", color: "var(--color-text-primary)", textTransform: "capitalize" }}>{it.name}</strong>
                  <Badge text={it.role ?? CLASS_LABEL[it.item_class] ?? "Item"} color={ROLE_COLOR[it.role ?? ""] ?? "#8b5cf6"} />
                  {it.verified && <BadgeCheck size={14} style={{ color: "#10b981" }} />}
                </div>
                <div style={{ fontSize: "0.68rem", color: "var(--color-text-muted)" }}>described as “{it.display}”</div>
                <div style={{ marginTop: 3 }}><StrengthBadge s={it.strength} count={it.evidence_count} /></div>
                <Support items={it.support} onOpen={onOpen} />
              </div>
            </article>
          ))}
        </div>
      </Section>

      <Section title="Vehicle & number plate" icon={<Car size={17} />}
               count={data.vehicles.length + data.unlinked_plates.length} hint="getaway vehicle and its registration">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(380px, 1fr))", gap: 10 }}>
          {data.vehicles.map((v) => (
            <article key={v.id} className="card" style={card} data-testid="vehicle-card">
              <Photos photos={v.photos} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <strong style={{ fontSize: "0.92rem", color: "var(--color-text-primary)", textTransform: "capitalize" }}>{v.display}</strong>
                {v.verified && <BadgeCheck size={14} style={{ color: "#10b981", marginLeft: 6 }} />}
                <div style={{ marginTop: 2 }}><StrengthBadge s={v.strength} count={v.evidence_count} /></div>
                {v.plates.map((p) => (
                  <div key={p.plate} style={{ marginTop: 6, padding: "4px 8px", borderRadius: 6, background: "var(--color-bg-elevated)",
                                              border: "1px solid var(--color-border)" }} data-testid="plate-row">
                    <span style={{ fontFamily: "monospace", fontWeight: 700, color: "#22d3ee", fontSize: "0.9rem" }}>{p.plate}</span>
                    <span style={{ marginLeft: 8 }}><StrengthBadge s={p.strength} count={p.evidence_count} /></span>
                    {p.match_type === "PARTIAL" || p.match_type === "FUZZY"
                      ? <span style={{ marginLeft: 6, fontSize: "0.62rem", color: "#f59e0b" }}>partly read — review</span> : null}
                    {v.plate_inferred && <div style={{ fontSize: "0.62rem", color: "var(--color-text-subtle)" }}>
                      attributed because it is the only vehicle in the case</div>}
                    <Support items={p.support} onOpen={onOpen} />
                  </div>
                ))}
                <Support items={v.support} onOpen={onOpen} />
              </div>
            </article>
          ))}
          {data.unlinked_plates.map((p) => (
            <article key={p.plate} className="card" style={{ padding: "0.6rem 0.8rem" }} data-testid="loose-plate">
              <span style={{ fontFamily: "monospace", fontWeight: 700, color: "#22d3ee" }}>{p.plate}</span>
              <span style={{ marginLeft: 8 }}><StrengthBadge s={p.strength} count={p.evidence_count} /></span>
              <div style={{ fontSize: "0.65rem", color: "var(--color-text-subtle)" }}>plate not tied to a described vehicle</div>
              <Support items={p.support} onOpen={onOpen} />
            </article>
          ))}
        </div>
      </Section>

      <p style={{ fontSize: "0.68rem", color: "var(--color-text-subtle)", display: "flex", gap: 5, alignItems: "center" }}>
        <Briefcase size={12} /> {data.notes.join(" ")}
      </p>
    </div>
  );
}
