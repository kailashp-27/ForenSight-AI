// frontend/src/pages/EvidenceBrowser.tsx
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Search, FileVideo, FileImage, FileAudio, FileText, File, ChevronRight, Folder } from "lucide-react";
import { Badge, statusToVariant } from "../components/ui/Badge";
import { evidenceApi, type Evidence } from "../services/api";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function EvidenceIcon({ type }: { type: string }) {
  const s = { width: 16, height: 16 };
  if (type === "VIDEO")    return <FileVideo  style={{ ...s, color: "#3b82f6" }} />;
  if (type === "IMAGE")    return <FileImage  style={{ ...s, color: "#10b981" }} />;
  if (type === "AUDIO")    return <FileAudio  style={{ ...s, color: "#8b5cf6" }} />;
  if (type === "DOCUMENT") return <FileText   style={{ ...s, color: "#f59e0b" }} />;
  return <File style={{ ...s, color: "var(--color-text-subtle)" }} />;
}

export function EvidenceBrowser() {
  const [evidenceList, setEvidenceList] = useState<Evidence[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const data = await evidenceApi.listAll();
        setEvidenceList(data);
      } catch (err) {
        console.error("Failed to fetch evidence", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const filtered = evidenceList.filter((e) =>
    e.file_name.toLowerCase().includes(search.toLowerCase()) ||
    e.case_number?.toLowerCase().includes(search.toLowerCase()) ||
    e.case_title?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div
      style={{ padding: "1.5rem 2rem", display: "flex", flexDirection: "column", gap: "1.25rem", minHeight: "100%" }}
      className="animate-fade-in"
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <h1 style={{ fontSize: "1.375rem", fontWeight: 700, color: "var(--color-text-primary)" }}>
            Global Evidence Browser
          </h1>
          <p style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginTop: 4 }}>
            {loading ? "Loading…" : `${evidenceList.length} evidence file${evidenceList.length !== 1 ? "s" : ""} across all cases`}
          </p>
        </div>
      </div>

      {/* Search */}
      <div style={{ position: "relative", maxWidth: 400 }}>
        <Search
          style={{
            position: "absolute", left: "0.75rem", top: "50%", transform: "translateY(-50%)",
            width: 14, height: 14, color: "var(--color-text-subtle)", pointerEvents: "none",
          }}
        />
        <input
          type="search"
          placeholder="Search files by name or case number…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="input-dark"
          style={{ paddingLeft: "2.25rem", width: "100%" }}
        />
      </div>

      {/* Table */}
      <div className="card" style={{ overflow: "hidden", flex: 1 }}>
        {filtered.length === 0 && !loading ? (
          <div
            style={{
              display: "flex", flexDirection: "column", alignItems: "center",
              justifyContent: "center", padding: "4rem 1rem", textAlign: "center",
            }}
          >
            <Folder style={{ width: 40, height: 40, color: "var(--color-border-bright)", marginBottom: 12 }} />
            <p style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--color-text-muted)" }}>
              {search ? "No matches found" : "No evidence uploaded yet"}
            </p>
          </div>
        ) : (
          <table className="dark-table" style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th>File Name</th>
                <th>Case</th>
                <th>Type</th>
                <th>Size</th>
                <th>Status</th>
                <th>Uploaded</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {(loading ? Array(5).fill(null) : filtered).map((ev, i) => (
                <tr key={ev?.id ?? i}>
                  <td>
                    {ev ? (
                      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                        <div style={{ width: 32, height: 32, borderRadius: 6, background: "var(--color-bg-base)", display: "flex", alignItems: "center", justifyContent: "center", border: "1px solid var(--color-border-bright)" }}>
                          <EvidenceIcon type={ev.file_type} />
                        </div>
                        <span style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--color-text-primary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 200 }}>
                          {ev.file_name}
                        </span>
                      </div>
                    ) : <div className="skeleton" style={{ height: 32, width: "100%", borderRadius: 6 }} />}
                  </td>
                  <td>
                    {ev ? (
                      <div style={{ display: "flex", flexDirection: "column" }}>
                        <Link to={`/cases/${ev.case_id}`} style={{ fontSize: "0.8125rem", fontWeight: 500, color: "var(--color-text-primary)", textDecoration: "none" }}>
                          {ev.case_title}
                        </Link>
                        <span style={{ fontSize: "0.7rem", color: "var(--color-text-muted)", fontFamily: "monospace" }}>
                          {ev.case_number}
                        </span>
                      </div>
                    ) : <div className="skeleton" style={{ height: 24, width: 120 }} />}
                  </td>
                  <td>
                    {ev ? (
                      <span style={{ fontSize: "0.72rem", padding: "2px 6px", background: "var(--color-bg-elevated)", border: "1px solid var(--color-border)", borderRadius: 4, color: "var(--color-text-subtle)", letterSpacing: "0.05em" }}>
                        {ev.file_type}
                      </span>
                    ) : <div className="skeleton" style={{ height: 16, width: 60 }} />}
                  </td>
                  <td>
                    {ev ? (
                      <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", fontFamily: "monospace" }}>
                        {formatSize(ev.file_size)}
                      </span>
                    ) : <div className="skeleton" style={{ height: 14, width: 40 }} />}
                  </td>
                  <td>
                    {ev ? <Badge variant={statusToVariant(ev.status)} /> : <div className="skeleton" style={{ height: 20, width: 80, borderRadius: 999 }} />}
                  </td>
                  <td>
                    {ev ? (
                      <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", fontFamily: "monospace" }}>
                        {formatDate(ev.uploaded_at)}
                      </span>
                    ) : <div className="skeleton" style={{ height: 14, width: 80 }} />}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    {ev && (
                      <Link
                        to={`/cases/${ev.case_id}?evidence=${ev.id}`}
                        style={{
                          display: "inline-flex", alignItems: "center", gap: 2,
                          fontSize: "0.72rem", color: "var(--color-accent)",
                          textDecoration: "none", fontWeight: 500,
                        }}
                      >
                        Inspect <ChevronRight style={{ width: 12, height: 12 }} />
                      </Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
