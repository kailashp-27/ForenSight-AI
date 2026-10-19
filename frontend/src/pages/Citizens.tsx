// frontend/src/pages/Citizens.tsx
// The citizen register: every person on file, searchable by name, ID, phone,
// address, occupation or record. Click a person to open their file.
// People who appear in more than one case are flagged.

import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AlertTriangle, Loader2, Search, Users } from "lucide-react";
import { citizensApi, type CitizenSummary } from "../services/forensicApi";

const STATUS_COLOR: Record<string, string> = {
  Clear: "#10b981", Cleared: "#10b981", Closed: "#64748b",
  Active: "#f59e0b", Monitored: "#f59e0b", "Under Surveillance": "#f59e0b", Probation: "#f59e0b", Paroled: "#f59e0b",
  Flagged: "#f97316", "Under Review": "#f97316", Restricted: "#f97316",
  "High Risk": "#ef4444", Wanted: "#ef4444", Fugitive: "#ef4444", "Warrant Active": "#ef4444", Detained: "#ef4444",
};

export function StatusPill({ status }: { status: string | null }) {
  const c = STATUS_COLOR[status ?? ""] ?? "#94a3b8";
  return (
    <span style={{ fontSize: "0.66rem", fontWeight: 700, color: c, border: `1px solid ${c}`, borderRadius: 999, padding: "1px 8px", whiteSpace: "nowrap" }}>
      {status ?? "Unknown"}
    </span>
  );
}

export function Citizens() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [recordOnly, setRecordOnly] = useState(false);
  const [multiOnly, setMultiOnly] = useState(false);
  const [data, setData] = useState<{ total: number; items: CitizenSummary[]; statuses: string[]; multi_case_total: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Debounced server-side search.
  useEffect(() => {
    const t = window.setTimeout(async () => {
      setLoading(true);
      try {
        setData(await citizensApi.list({ q: query.trim(), status: status || undefined,
                                         has_record: recordOnly ? true : undefined, multi_case: multiOnly }));
        setError(null);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setLoading(false);
      }
    }, 220);
    return () => window.clearTimeout(t);
  }, [query, status, recordOnly, multiOnly]);

  const items = data?.items ?? [];
  const select: React.CSSProperties = {
    height: 34, background: "var(--color-bg-input)", color: "var(--color-text-body)",
    border: "1px solid var(--color-border-bright)", borderRadius: 6, fontSize: "0.78rem", padding: "0 8px",
  };

  return (
    <div className="animate-fade-in" style={{ padding: "1.25rem", maxWidth: 1200, margin: "0 auto" }}>
      <header style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
        <Users size={20} style={{ color: "var(--color-accent)" }} />
        <h1 style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--color-text-primary)" }}>Citizen register</h1>
        <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
          {data ? `${data.total} people` : ""}
        </span>
      </header>
      <p style={{ fontSize: "0.76rem", color: "var(--color-text-muted)", marginBottom: 12 }}>
        Reference database of people. Suspects found in a case are matched against this register; a match stays a suggestion
        until an investigator confirms it. This is fictional test data.
      </p>

      {data && data.multi_case_total > 0 && !multiOnly && (
        <button onClick={() => setMultiOnly(true)}
                style={{ display: "flex", gap: 8, alignItems: "center", width: "100%", textAlign: "left", cursor: "pointer",
                         marginBottom: 12, padding: "0.55rem 0.8rem", borderRadius: 8, color: "#fbbf24",
                         background: "rgba(245,158,11,0.1)", border: "1px solid rgba(245,158,11,0.45)", fontSize: "0.8rem" }}>
          <AlertTriangle size={16} />
          <strong>{data.multi_case_total}</strong> {data.multi_case_total === 1 ? "person appears" : "people appear"} in more than one case. Show them
        </button>
      )}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
        <div style={{ position: "relative", flex: "1 1 320px", maxWidth: 520 }}>
          <Search size={15} style={{ position: "absolute", left: 11, top: 10, color: "var(--color-text-subtle)" }} />
          <input aria-label="Search the citizen register" placeholder="Search name, ID, phone, address, occupation, record…"
                 value={query} onChange={(e) => setQuery(e.target.value)} autoFocus
                 style={{ ...select, width: "100%", paddingLeft: 32, fontSize: "0.85rem" }} />
        </div>
        <select aria-label="Filter by status" value={status} onChange={(e) => setStatus(e.target.value)} style={select}>
          <option value="">All statuses</option>
          {(data?.statuses ?? []).map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <label style={{ fontSize: "0.76rem", color: "var(--color-text-body)", display: "flex", gap: 5, alignItems: "center" }}>
          <input type="checkbox" checked={recordOnly} onChange={(e) => setRecordOnly(e.target.checked)} /> With criminal record
        </label>
        <label style={{ fontSize: "0.76rem", color: "var(--color-text-body)", display: "flex", gap: 5, alignItems: "center" }}>
          <input type="checkbox" checked={multiOnly} onChange={(e) => setMultiOnly(e.target.checked)} /> In multiple cases
        </label>
        {loading && <Loader2 size={15} className="animate-spin" />}
      </div>

      {error && <p role="alert" style={{ color: "#fca5a5", fontSize: "0.8rem" }}>{error}</p>}
      {data && items.length === 0 && (
        <p style={{ fontSize: "0.85rem", color: "var(--color-text-muted)", padding: "2rem", textAlign: "center" }}>
          No one matches “{query}”.
        </p>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 10 }}>
        {items.map((c) => (
          <Link key={c.id} to={`/citizens/${c.id}`} data-testid="citizen-card" className="card"
                style={{ display: "flex", gap: 10, padding: "0.65rem", textDecoration: "none",
                         borderLeft: c.multi_case ? "4px solid #f59e0b" : undefined }}
                onClick={(e) => { e.preventDefault(); navigate(`/citizens/${c.id}`); }}>
            <img src={c.photo_url} alt={`${c.full_name} (no photo available)`} loading="lazy"
                 style={{ width: 56, height: 68, objectFit: "cover", borderRadius: 6, flexShrink: 0, background: "#05070c" }} />
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ fontWeight: 700, fontSize: "0.9rem", color: "var(--color-text-primary)", overflow: "hidden",
                            textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.full_name}</div>
              <div style={{ fontSize: "0.68rem", color: "var(--color-text-muted)", fontFamily: "monospace" }}>
                ID {c.id}{c.age != null ? ` · age ${c.age}` : ""}
              </div>
              <div style={{ fontSize: "0.7rem", color: "var(--color-text-body)", overflow: "hidden", textOverflow: "ellipsis",
                            whiteSpace: "nowrap" }}>{c.occupation}</div>
              <div style={{ display: "flex", gap: 5, marginTop: 4, flexWrap: "wrap", alignItems: "center" }}>
                <StatusPill status={c.status} />
                {c.has_record && <span style={{ fontSize: "0.62rem", color: "#fca5a5" }}>record</span>}
                {c.multi_case && (
                  <span style={{ display: "inline-flex", gap: 3, alignItems: "center", fontSize: "0.64rem", fontWeight: 700, color: "#fbbf24" }}>
                    <AlertTriangle size={11} /> {c.case_count} cases
                  </span>
                )}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
